import logging
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.domain_events import DomainEventName
from app.core.event_bus import event_bus
from app.models.chat import ChatMessage, ChatSession, MessageRole
from app.schemas.chat import ChatMessageRead, ChatSendRequest, MessageDeliveryStatus
from app.services import ai_service, chat_context_service, profile_service

import asyncio
import threading


ASSISTANT_FAILURE_MESSAGE = "(The assistant failed to respond.)"
DEFAULT_SESSION_TITLE = "未命名会话"
_PLACEHOLDER_TITLES = frozenset({DEFAULT_SESSION_TITLE, "New chat"})
logger = logging.getLogger(__name__)


def _extract_response_text(response) -> str:
    # compatibility shim: keep this function for existing tests/imports.
    return ai_service.extract_response_text(response)


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

    return create_session(db, user_id=user_id, title=title or DEFAULT_SESSION_TITLE)


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


def is_placeholder_title(title: str | None) -> bool:
    if title is None:
        return True

    normalized = title.strip()
    if not normalized:
        return True

    return normalized in _PLACEHOLDER_TITLES


def _normalize_generated_title(raw: str) -> str:
    text = raw.strip().strip("\"'")
    return " ".join(text.split())


def generate_session_title(user_message: str, assistant_message: str) -> str:
    try:
        raw = ai_service.build_session_title_response(user_message, assistant_message)
        title = _normalize_generated_title(raw)
        if not title or len(title) > 24:
            return suggest_session_title(user_message)
        return title
    except (ai_service.AIServiceError, RuntimeError):
        return suggest_session_title(user_message)


def maybe_auto_update_session_title(
    db: Session,
    *,
    session_id: int,
    assistant_message: ChatMessage,
) -> str | None:
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session or not is_placeholder_title(session.title):
        return None

    user_messages = (
        db.query(ChatMessage)
        .filter(
            ChatMessage.session_id == session_id,
            ChatMessage.role == MessageRole.USER,
        )
        .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
        .all()
    )
    if len(user_messages) != 1:
        return None

    title = generate_session_title(user_messages[0].content, assistant_message.content or "")
    session.title = title
    db.add(session)
    db.commit()
    db.refresh(session)
    return title


def suggest_session_title(message: str) -> str:
    text = " ".join(message.strip().split())
    if not text:
        return "New chat"
    splitters = ("。", "！", "？", ".", "!", "?", "\n")
    first_sentence = text
    for splitter in splitters:
        if splitter in first_sentence:
            first_sentence = first_sentence.split(splitter, 1)[0].strip()
            break

    if not first_sentence:
        first_sentence = text

    if len(first_sentence) <= 24:
        return first_sentence

    return f"{first_sentence[:24].rstrip()}..."


def build_ai_response(
    message: str,
    *,
    instructions: str | None = None,
    db: Session | None = None,
    user_id: int | None = None,
) -> str:
    return ai_service.build_chat_response(
        message,
        instructions=instructions,
        db=db,
        user_id=user_id,
    )


def build_profile_extraction_response(message: str) -> str:
    return ai_service.build_profile_extraction_response(message)


def build_goal_breakdown_response(message: str) -> str:
    """
    Build AI response for goal breakdown.
    Input: structured prompt containing user goal and optional context.
    Output: raw AI response text containing JSON breakdown structure.
    """
    return ai_service.build_goal_breakdown_response(message)


def build_action_plan_response(message: str) -> str:
    """
    Build AI response for action plan generation.
    Input: structured prompt containing goal, breakdowns, and optional profile context.
    Output: raw AI response text containing strict JSON action plan structure.
    """
    return ai_service.build_action_plan_response(message)


def send_message(db: Session, payload: ChatSendRequest, *, user_id: int) -> tuple[ChatSession, ChatMessage, ChatMessage]:
    session = get_or_create_session(
        db,
        user_id=user_id,
        session_id=payload.session_id,
        title=payload.title or DEFAULT_SESSION_TITLE,
    )

    user_message = ChatMessage(
        session_id=session.id,
        role=MessageRole.USER,
        content=payload.message.strip(),
    )
    assistant_content = build_ai_response(payload.message, db=db, user_id=user_id)
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
        session_obj = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        owner_id = session_obj.user_id if session_obj else None

        # create a placeholder assistant message so clients can show typing/placeholder
        assistant_message = ChatMessage(
            session_id=session_id,
            role=MessageRole.ASSISTANT,
            content="",
        )
        db.add(assistant_message)
        db.commit()
        db.refresh(assistant_message)

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
        # Determine if session owner is admin → use admin chat path
        assistant_content = None
        try:
            is_admin_session = False
            if session_obj:
                from app.models.user import User, UserRole
                owner_user = db.query(User).filter(User.id == session_obj.user_id).first()
                is_admin_session = bool(owner_user and owner_user.role == UserRole.ADMIN)

            if is_admin_session:
                prompt = chat_context_service.build_legacy_chat_context(
                    db,
                    session_id=session_id,
                    current_user_message=message.strip(),
                )
                from app.services.ai_service import build_admin_chat_response
                assistant_content = build_admin_chat_response(prompt, db=db, user_id=owner_id)
            elif owner_id is not None:
                prompt = chat_context_service.build_chat_context(
                    db,
                    user_id=owner_id,
                    session_id=session_id,
                    current_user_message=message.strip(),
                )
                assistant_content = build_ai_response(prompt, db=db, user_id=owner_id)
            else:
                assistant_content = build_ai_response(message.strip(), db=db, user_id=owner_id)
        except Exception as exc:
            from app.services.ai_rate_limit_service import AIRateLimitExceeded

            if isinstance(exc, AIRateLimitExceeded):
                assistant_content = str(exc)
            else:
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

        updated_title = maybe_auto_update_session_title(
            db,
            session_id=session_id,
            assistant_message=assistant_message,
        )
        if updated_title and owner_id and manager and loop:
            try:
                title_payload = {
                    "type": "session_title_updated",
                    "session_id": session_id,
                    "title": updated_title,
                }
                loop.call_soon_threadsafe(asyncio.create_task, manager.send_personal_message(owner_id, title_payload))
            except Exception:
                pass

        if owner_id:
            chat_context_service.schedule_session_summary_update(session_id, owner_id)
            event_bus.publish(
                event_name=DomainEventName.ON_CHAT_MESSAGE.value,
                user_id=owner_id,
                payload={
                    "session_id": session_id,
                    "assistant_message_id": assistant_message.id,
                    "assistant_status": infer_message_status(
                        assistant_message.role,
                        assistant_message.content,
                    ).value,
                },
                fail_fast=False,
            )
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

    messages = profile_service.list_recent_messages_for_session(
        db,
        session_id=session_id,
        limit=settings.PROFILE_EXTRACTION_MESSAGE_WINDOW,
    )
    extraction_input = profile_service.build_extraction_input(messages)
    if not extraction_input:
        return

    raw_result = build_profile_extraction_response(extraction_input)
    extraction_result = profile_service.parse_extraction_result(raw_result)
    profile_service.apply_extraction_result_for_user(
        db,
        user_id=profile_user_id,
        result=extraction_result,
    )
