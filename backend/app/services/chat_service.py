from sqlalchemy.orm import Session

from app.models.chat import ChatMessage, ChatSession, MessageRole
from app.schemas.chat import ChatSendRequest


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
    return (
        "Here is a starter plan: 1) clarify your goal, "
        "2) break it into weekly milestones, "
        "3) track wins and blockers. "
        f"You said: {message.strip()}"
    )


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
    assistant_message = ChatMessage(
        session_id=session.id,
        role=MessageRole.ASSISTANT,
        content=build_ai_response(payload.message),
    )

    db.add_all([user_message, assistant_message])
    db.commit()
    db.refresh(user_message)
    db.refresh(assistant_message)

    return session, user_message, assistant_message
