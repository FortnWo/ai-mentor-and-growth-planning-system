from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.chat import (
    ChatMessageRead,
    ChatSendRequest,
    ChatSendResponse,
    ChatSessionRead,
    ChatSessionRenameRequest,
)
from app.services import chat_service

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatSendResponse)
def send_message(payload: ChatSendRequest, db: Session = Depends(get_db)):
    try:
        session, user_message, assistant_message = chat_service.send_message(db, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return ChatSendResponse(
        session=session,
        user_message=user_message,
        assistant_message=assistant_message,
    )


@router.get("/sessions", response_model=list[ChatSessionRead])
def list_sessions(user_id: int, db: Session = Depends(get_db)):
    return chat_service.list_sessions_for_user(db, user_id=user_id)


@router.get("/{session_id}/messages", response_model=list[ChatMessageRead])
def list_messages(session_id: int, user_id: int | None = None, db: Session = Depends(get_db)):
    try:
        return chat_service.list_messages_for_session(db, session_id=session_id, user_id=user_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/{session_id}", response_model=ChatSessionRead)
def rename_session(session_id: int, payload: ChatSessionRenameRequest, user_id: int, db: Session = Depends(get_db)):
    session = chat_service.rename_session_for_user(
        db,
        user_id=user_id,
        session_id=session_id,
        title=payload.title,
    )
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found")

    return session


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(session_id: int, user_id: int, db: Session = Depends(get_db)):
    deleted = chat_service.delete_session_for_user(db, user_id=user_id, session_id=session_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found")

    return None
