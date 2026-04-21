from openai import OpenAI
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.chat import ChatMessage, ChatSession, MessageRole
from app.schemas.chat import ChatSendRequest


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


def suggest_session_title(message: str) -> str:
    text = " ".join(message.strip().split())
    if not text:
        return "New chat"

    words = text.split(" ")
    if len(words) <= 6:
        return text

    return f"{' '.join(words[:6])}..."


def build_ai_response(message: str) -> str:
    try:
        client = _get_ai_client()
        if not settings.LLM_MODEL:
            raise RuntimeError("LLM_MODEL is not configured")
        response = client.responses.create(
            model=settings.LLM_MODEL,
            instructions=settings.LLM_SYSTEM_PROMPT or None,
            input=message.strip(),
        )
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"AI provider request failed: {exc}") from exc

    return _extract_response_text(response)


def send_message(db: Session, payload: ChatSendRequest) -> tuple[ChatSession, ChatMessage, ChatMessage]:
    session = get_or_create_session(
        db,
        user_id=payload.user_id,
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
