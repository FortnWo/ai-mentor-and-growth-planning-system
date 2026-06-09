import logging
import traceback

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from app.core.ai_worker import submit_ai_task
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.chat import (
    ChatMessageRead,
    ChatSendRequest,
    ChatSendResponse,
    ChatSessionRead,
    ChatSessionRenameRequest,
)
from app.services import chat_service
from app.services.ai_rate_limit_service import AIRateLimitExceeded, assert_chat_allowed

router = APIRouter(prefix="/chat", tags=["chat"])
error_logger = logging.getLogger("ai_mentor.errors")


@router.post("", response_model=ChatSendResponse)
def send_message(
    payload: ChatSendRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        session = chat_service.get_or_create_session(
            db,
            user_id=current_user.id,
            session_id=payload.session_id,
            title=payload.title or chat_service.DEFAULT_SESSION_TITLE,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    try:
        assert_chat_allowed(db, current_user)
    except AIRateLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
        ) from exc

    user_message = chat_service.create_user_message(db, session=session, message=payload.message)
    assistant_placeholder = chat_service.create_assistant_placeholder(db, session)
    chat_service.chat_generation_registry.register(assistant_placeholder.id)

    def _enqueue_chat_worker() -> None:
        submit_ai_task(
            chat_service.process_message_in_background,
            session.id,
            payload.message,
            assistant_placeholder.id,
        )

    background_tasks.add_task(_enqueue_chat_worker)

    return ChatSendResponse(
        session=session,
        user_message=chat_service.serialize_chat_message(user_message),
        assistant_message=chat_service.serialize_chat_message(assistant_placeholder),
    )


@router.post("/{session_id}/messages/{message_id}/stop", status_code=status.HTTP_204_NO_CONTENT)
def stop_message_generation(
    session_id: int,
    message_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        stopped = chat_service.stop_message_generation(
            db,
            user_id=current_user.id,
            session_id=session_id,
            message_id=message_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if not stopped:
        raise HTTPException(status_code=409, detail="Message is not pending generation")

    return None


@router.get("/sessions", response_model=list[ChatSessionRead])
def list_sessions(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return chat_service.list_sessions_for_user(db, user_id=current_user.id)


@router.get("/{session_id}/messages", response_model=list[ChatMessageRead])
def list_messages(session_id: int, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        messages = chat_service.list_messages_for_session(db, session_id=session_id, user_id=current_user.id)
        return chat_service.serialize_chat_messages(messages)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - runtime debugging
        origin = request.headers.get("origin") if request is not None else None
        error_logger.error(
            "list_messages failed session_id=%s user_id=%s origin=%s error=%s\n%s",
            session_id,
            current_user.id,
            origin,
            exc,
            traceback.format_exc(),
        )

        raise HTTPException(status_code=500, detail="Internal Server Error") from exc


@router.patch("/{session_id}", response_model=ChatSessionRead)
def rename_session(session_id: int, payload: ChatSessionRenameRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = chat_service.rename_session_for_user(
        db,
        user_id=current_user.id,
        session_id=session_id,
        title=payload.title,
    )
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found")

    return session


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(session_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    deleted = chat_service.delete_session_for_user(db, user_id=current_user.id, session_id=session_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found")

    return None
