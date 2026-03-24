from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.chat import ChatMessage, ChatSession
from app.schemas.chat import ChatMessageResponse


def get_or_create_session(db: Session, user_id: int, session_id: int | None) -> ChatSession:
    if session_id is not None:
        session = db.query(ChatSession).filter(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id,
        ).first()
        if session:
            return session

    session = ChatSession(user_id=user_id)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def save_message(db: Session, session_id: int, role: str, content: str) -> ChatMessage:
    message = ChatMessage(session_id=session_id, role=role, content=content)
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def echo_reply(user_message: str) -> str:
    """Placeholder: returns a stub response until a real AI service is wired in."""
    return f"[AI Mentor] Received: {user_message!r} — AI response coming soon."
