from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.chat import ChatMessageRequest, ChatMessageResponse
from app.services import chat_service

router = APIRouter(prefix="/chat", tags=["chat"])

# Stub user_id until authentication is implemented
_STUB_USER_ID = 1


@router.post("", response_model=ChatMessageResponse)
def send_message(payload: ChatMessageRequest, db: Session = Depends(get_db)):
    """Accept a user message and return a stub AI reply."""
    session = chat_service.get_or_create_session(db, _STUB_USER_ID, payload.session_id)

    chat_service.save_message(db, session.id, "user", payload.message)

    reply_text = chat_service.echo_reply(payload.message)
    reply_msg = chat_service.save_message(db, session.id, "assistant", reply_text)

    return ChatMessageResponse(
        session_id=session.id,
        role=reply_msg.role,
        content=reply_msg.content,
        created_at=reply_msg.created_at,
    )
