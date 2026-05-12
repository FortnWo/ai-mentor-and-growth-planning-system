import logging
from openai import OpenAI
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.chat import ChatMessage, ChatSession, MessageRole
from app.schemas.chat import ChatMessageRead, ChatSendRequest, MessageDeliveryStatus
from app.services import extended_profile_service

import asyncio
import threading


ASSISTANT_FAILURE_MESSAGE = "(The assistant failed to respond.)"
logger = logging.getLogger(__name__)


def _get_ai_client() -> OpenAI:
    if not settings.LLM_API_KEY:
        raise RuntimeError("LLM_API_KEY is not configured")
    if not settings.LLM_API_BASE_URL:
        raise RuntimeError("LLM_API_BASE_URL is not configured")

    return OpenAI(
        base_url=settings.LLM_API_BASE_URL,
        api_key=settings.LLM_API_KEY,
    )


def _extract_response_text(response) -> str:
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    output = getattr(response, "output", None) or []
    chunks: list[str] = []

    for item in output:
        if getattr(item, "type", None) != "message":
            continue

        content_items = getattr(item, "content", None) or []
        for content_item in content_items:
            if getattr(content_item, "type", None) != "output_text":
                continue

            text = getattr(content_item, "text", None)
            if isinstance(text, str) and text.strip():
                chunks.append(text.strip())

    if chunks:
        return "\n".join(chunks).strip()

    raise RuntimeError("AI response did not contain any text content")


def _role_to_value(role: MessageRole | str) -> str:
    return role.value if hasattr(role, "value") else str(role)


def infer_message_status(role: MessageRole | str, content: str) -> MessageDeliveryStatus:
    role_value = _role_to_value(role)
    text = (content or "").strip()

    if role_value != MessageRole.ASSISTANT.value:
        return MessageDeliveryStatus.COMPLETED

    if not text:
        return MessageDeliveryStatus.PENDING

    if text == ASSISTANT_FAILURE_MESSAGE:
        return MessageDeliveryStatus.FAILED

    return MessageDeliveryStatus.COMPLETED


def serialize_chat_message(message: ChatMessage) -> ChatMessageRead:
    role_value = _role_to_value(message.role)
    content = message.content or ""
    return ChatMessageRead(
        id=message.id,
        session_id=message.session_id,
        role=role_value,
        content=content,
        status=infer_message_status(role_value, content),
        created_at=message.created_at,
    )


def serialize_chat_messages(messages: list[ChatMessage]) -> list[ChatMessageRead]:
    return [serialize_chat_message(message) for message in messages]


def create_session(db: Session, user_id: int, title: str | None = None) -> ChatSession:
    session = ChatSession(user_id=user_id, title=title)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_session_for_user(db: Session, user_id: int, session_id: int) -> ChatSession | None:
    return db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == user_id,
    ).first()


def get_or_create_session(
    db: Session,
    user_id: int,
    session_id: int | None,
    title: str | None = None,
) -> ChatSession:
    if session_id:
        session = get_session_for_user(db, user_id, session_id)
        if not session:
            raise LookupError("Chat session not found for the user")
        return session

    return create_session(db, user_id=user_id, title=title or suggest_session_title("New chat"))


def list_sessions_for_user(db: Session, user_id: int) -> list[ChatSession]:
    return db.query(ChatSession).filter(ChatSession.user_id == user_id).order_by(ChatSession.created_at.desc(), ChatSession.id.desc()).all()


def list_messages_for_session(
    db: Session,
    session_id: int,
    user_id: int | None = None,
) -> list[ChatMessage]:
    session_query = db.query(ChatSession).filter(ChatSession.id == session_id)
    if user_id is not None:
        session_query = session_query.filter(ChatSession.user_id == user_id)

    session = session_query.first()
    if not session:
        raise LookupError("Chat session not found")

    return (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
        .all()
    )


def delete_session_for_user(db: Session, user_id: int, session_id: int) -> bool:
    session = get_session_for_user(db, user_id=user_id, session_id=session_id)
    if not session:
        return False

    db.delete(session)
    db.commit()
    return True


def rename_session_for_user(db: Session, user_id: int, session_id: int, title: str) -> ChatSession | None:
    session = get_session_for_user(db, user_id=user_id, session_id=session_id)
    if not session:
        return None

    session.title = title
    db.commit()
    db.refresh(session)
    return session


def suggest_session_title(message: str) -> str:
    text = " ".join(message.strip().split())
    if not text:
        return "New chat"

    words = text.split(" ")
    if len(words) <= 6:
        return text

    return f"{' '.join(words[:6])}..."


def build_ai_response(message: str, *, instructions: str | None = None) -> str:
    try:
        client = _get_ai_client()
        if not settings.LLM_MODEL:
            raise RuntimeError("LLM_MODEL is not configured")
        instr = instructions if instructions is not None else (settings.LLM_SYSTEM_PROMPT or None)
        response = client.responses.create(
            model=settings.LLM_MODEL,
            instructions=instr,
            input=message.strip(),
        )
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"AI provider request failed: {exc}") from exc

    return _extract_response_text(response)


def build_profile_extraction_response(message: str) -> str:
    try:
        client = _get_ai_client()
        if not settings.LLM_MODEL:
            raise RuntimeError("LLM_MODEL is not configured")

        response = client.responses.create(
            model=settings.LLM_MODEL,
            instructions=settings.PROFILE_EXTRACTION_SYSTEM_PROMPT,
            input=message.strip(),
        )
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"AI profile extraction request failed: {exc}") from exc

    return _extract_response_text(response)


def build_goal_breakdown_response(message: str) -> str:
    """
    Build AI response for goal breakdown.
    Input: structured prompt containing user goal and optional context.
    Output: raw AI response text containing JSON breakdown structure.
    """
    try:
        client = _get_ai_client()
        if not settings.LLM_MODEL:
            raise RuntimeError("LLM_MODEL is not configured")

        response = client.responses.create(
            model=settings.LLM_MODEL,
            instructions=settings.GOAL_BREAKDOWN_SYSTEM_PROMPT,
            input=message.strip(),
        )
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"AI goal breakdown request failed: {exc}") from exc

    return _extract_response_text(response)


def build_action_plan_response(message: str) -> str:
    """
    Build AI response for action plan generation.
    Input: structured prompt containing goal, breakdowns, and optional profile context.
    Output: raw AI response text containing strict JSON action plan structure.
    """
    try:
        client = _get_ai_client()
        if not settings.LLM_MODEL:
            raise RuntimeError("LLM_MODEL is not configured")

        response = client.responses.create(
            model=settings.LLM_MODEL,
            instructions=settings.ACTION_PLAN_SYSTEM_PROMPT,
            input=message.strip(),
        )
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"AI action plan request failed: {exc}") from exc

    return _extract_response_text(response)


def send_message(db: Session, payload: ChatSendRequest, *, user_id: int) -> tuple[ChatSession, ChatMessage, ChatMessage]:
    session = get_or_create_session(
        db,
        user_id=user_id,
        session_id=payload.session_id,
        title=payload.title or suggest_session_title(payload.message),
    )

    user_message = ChatMessage(
        session_id=session.id,
        role=MessageRole.USER,
        content=payload.message.strip(),
    )
    assistant_content = build_ai_response(payload.message)
    assistant_message = ChatMessage(
        session_id=session.id,
        role=MessageRole.ASSISTANT,
        content=assistant_content,
    )

    db.add_all([user_message, assistant_message])
    db.commit()
    db.refresh(user_message)
    db.refresh(assistant_message)

    return session, user_message, assistant_message


def create_user_message(db: Session, session: ChatSession, message: str) -> ChatMessage:
    """Create and persist a user message for a given session."""
    user_message = ChatMessage(
        session_id=session.id,
        role=MessageRole.USER,
        content=message.strip(),
    )
    db.add(user_message)
    db.commit()
    db.refresh(user_message)
    return user_message


def process_message_in_background(session_id: int, message: str) -> None:
    """Background worker: call LLM and store assistant message for a session."""
    # import database module at runtime so tests can override SessionLocal
    import app.core.database as database_module
    import app.core.ws_manager as ws_module

    db = database_module.SessionLocal()
    try:
        # Build prompt using recent session history (if possible)
        try:
            history_msgs = (
                db.query(ChatMessage)
                .filter(ChatMessage.session_id == session_id)
                .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
                .all()
            )
            parts: list[str] = []
            for m in history_msgs:
                role = _role_to_value(m.role)
                if role == MessageRole.USER.value:
                    parts.append(f"User: {m.content}")
                else:
                    # Skip unresolved placeholder assistant rows from context.
                    status = infer_message_status(role, m.content or "")
                    if status == MessageDeliveryStatus.PENDING:
                        continue
                    parts.append(f"Assistant: {m.content}")
            parts.append(f"User: {message.strip()}")
            prompt = "\n".join(parts)
        except Exception:
            prompt = message.strip()

        # create a placeholder assistant message so clients can show typing/placeholder
        assistant_message = ChatMessage(
            session_id=session_id,
            role=MessageRole.ASSISTANT,
            content="",
        )
        db.add(assistant_message)
        db.commit()
        db.refresh(assistant_message)

        # fetch session owner to know which user to notify
        session_obj = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        owner_id = session_obj.user_id if session_obj else None

        manager = ws_module.manager
        loop = getattr(manager, "loop", None)

        # start typing heartbeat (best-effort) while LLM generates
        stop_event = threading.Event()
        if owner_id and manager and loop:
            async def _heartbeat(user_id: int, msg_id: int):
                try:
                    while not stop_event.is_set():
                        payload = {
                            "type": "typing",
                            "session_id": session_id,
                            "message_id": msg_id,
                            "status": MessageDeliveryStatus.PENDING.value,
                        }
                        try:
                            await manager.send_personal_message(user_id, payload)
                        except Exception:
                            pass
                        await asyncio.sleep(0.8)
                except Exception:
                    pass

            try:
                loop.call_soon_threadsafe(asyncio.create_task, _heartbeat(owner_id, assistant_message.id))
            except Exception:
                # ignore; continue without heartbeat
                pass

        # build response from LLM (may be slow)
        assistant_content = None
        try:
            assistant_content = build_ai_response(prompt)
        except Exception:
            assistant_content = ASSISTANT_FAILURE_MESSAGE

        # stop heartbeat
        try:
            stop_event.set()
        except Exception:
            pass

        # persist final assistant content
        assistant_message.content = assistant_content
        db.add(assistant_message)
        db.commit()
        db.refresh(assistant_message)

        # notify connected WebSocket clients (if any) with final message
        try:
            if owner_id and manager and loop:
                payload = {
                    "type": "new_message",
                    "message": {
                        "id": assistant_message.id,
                        "session_id": assistant_message.session_id,
                        "role": _role_to_value(assistant_message.role),
                        "content": assistant_message.content,
                        "status": infer_message_status(assistant_message.role, assistant_message.content).value,
                        "created_at": assistant_message.created_at.isoformat() if assistant_message.created_at else None,
                    },
                }
                loop.call_soon_threadsafe(asyncio.create_task, manager.send_personal_message(owner_id, payload))
        except Exception:
            pass

        try:
            import app.services.automation_service as automation_service

            automation_service.run_chat_automation_pipeline(db, session_id=session_id, user_id=owner_id)
        except Exception as exc:
            logger.warning("Automation pipeline failed for session_id=%s user_id=%s error=%s", session_id, owner_id, exc)
    finally:
        db.close()


def _refresh_profile_from_session_history(db: Session, *, session_id: int, user_id: int | None) -> None:
    if not settings.PROFILE_EXTRACTION_ENABLED:
        return

    profile_user_id = user_id
    if profile_user_id is None:
        session_obj = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if not session_obj:
            return
        profile_user_id = session_obj.user_id

    messages = extended_profile_service.list_recent_messages_for_session(
        db,
        session_id=session_id,
        limit=settings.PROFILE_EXTRACTION_MESSAGE_WINDOW,
    )
    extraction_input = extended_profile_service.build_extraction_input(messages)
    if not extraction_input:
        return

    raw_result = build_profile_extraction_response(extraction_input)
    extraction_result = extended_profile_service.parse_extraction_result(raw_result)
    extended_profile_service.apply_extraction_result_for_user(
        db,
        user_id=profile_user_id,
        result=extraction_result,
    )
