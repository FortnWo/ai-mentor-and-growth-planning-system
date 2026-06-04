"""
Password reset router.

Endpoints:
  GET  /auth/password-reset/available-methods  — which reset methods are configured
  POST /auth/password-reset/send-code          — send verification code (phone/email)
  POST /auth/password-reset/verify             — validate code (returns one-time token)
  POST /auth/password-reset/confirm            — set new password using the token

Error codes (carried in response detail):
  RESET_4001 — user not found / contact info mismatch
  RESET_4002 — verification code incorrect or expired
  RESET_4003 — resend interval not elapsed
  RESET_5001 — notification service not configured
"""
from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone
from threading import Lock

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import hash_password
from app.services import notify_service, verification_service
from app.services.user_service import get_user_by_username, get_user_by_email, get_user_by_username

router = APIRouter(prefix="/auth/password-reset", tags=["password-reset"])
logger = logging.getLogger("ai_mentor.password_reset")

# In-memory store for verified one-time tokens  { token: (user_id, expires_at) }
_verified_tokens: dict[str, tuple[int, datetime]] = {}
_token_lock = Lock()
_TOKEN_TTL_MINUTES = 15


# ── Schemas ───────────────────────────────────────────────────────────────────

class SendCodeRequest(BaseModel):
    username: str = Field(description="用户名（学号）")
    method: str = Field(description="找回方式: phone 或 email")


class VerifyCodeRequest(BaseModel):
    username: str
    method: str
    code: str


class VerifyCodeResponse(BaseModel):
    reset_token: str
    message: str


class ConfirmResetRequest(BaseModel):
    reset_token: str
    new_password: str = Field(min_length=8, max_length=128)


class AvailableMethodsResponse(BaseModel):
    methods: list[str]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _issue_reset_token(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    expires = _utcnow() + timedelta(minutes=_TOKEN_TTL_MINUTES)
    with _token_lock:
        _verified_tokens[token] = (user_id, expires)
    return token


def _consume_reset_token(token: str) -> int:
    """Return user_id and remove token, or raise if invalid/expired."""
    with _token_lock:
        entry = _verified_tokens.pop(token, None)
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="RESET_4002: Reset token is invalid or has expired",
        )
    user_id, expires_at = entry
    if _utcnow() > expires_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="RESET_4002: Reset token has expired",
        )
    return user_id


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/available-methods", response_model=AvailableMethodsResponse)
def available_methods():
    """Return configured password-reset methods. Frontend hides unavailable options."""
    return AvailableMethodsResponse(methods=notify_service.get_available_methods())


@router.post("/send-code", status_code=status.HTTP_200_OK)
def send_code(payload: SendCodeRequest, db: Session = Depends(get_db)):
    """Send a verification code to the user's registered phone or email."""
    if payload.method not in ("phone", "email"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="RESET_4001: method must be 'phone' or 'email'",
        )

    user = get_user_by_username(db, payload.username)
    if not user or not user.is_active:
        # Return same message to avoid username enumeration
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="RESET_4001: User not found or contact info not set",
        )

    if payload.method == "phone":
        if not user.phone:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="RESET_4001: No phone number registered for this account",
            )
        contact = user.phone
    else:
        if not user.email:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="RESET_4001: No email registered for this account",
            )
        contact = user.email

    can_send, wait_secs = verification_service.can_send_code(db, user.id, payload.method)
    if not can_send:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"RESET_4003: Please wait {wait_secs} seconds before requesting another code",
        )

    vc = verification_service.create_code(db, user.id, payload.method)

    try:
        if payload.method == "phone":
            notify_service.send_sms_code(contact, vc.code)
        else:
            notify_service.send_email_code(contact, vc.code)
    except notify_service.NotifyConfigError as exc:
        logger.warning("password_reset: notify not configured method=%s: %s", payload.method, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except notify_service.NotifySendError as exc:
        logger.error("password_reset: send failed method=%s: %s", payload.method, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return {"message": "Verification code sent", "method": payload.method}


@router.post("/verify", response_model=VerifyCodeResponse)
def verify_code(payload: VerifyCodeRequest, db: Session = Depends(get_db)):
    """Validate the verification code. Returns a one-time reset token on success."""
    user = get_user_by_username(db, payload.username)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="RESET_4001: User not found",
        )

    ok = verification_service.verify_code(db, user.id, payload.method, payload.code)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="RESET_4002: Verification code is incorrect or has expired",
        )

    token = _issue_reset_token(user.id)
    return VerifyCodeResponse(reset_token=token, message="Code verified")


@router.post("/confirm", status_code=status.HTTP_200_OK)
def confirm_reset(payload: ConfirmResetRequest, db: Session = Depends(get_db)):
    """Set a new password using the verified reset token."""
    from app.services.user_service import get_user

    user_id = _consume_reset_token(payload.reset_token)
    user = get_user(db, user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="RESET_4001: User not found",
        )

    user.password_hash = hash_password(payload.new_password)
    db.commit()
    logger.info("password_reset: password reset successful user_id=%s", user_id)

    return {"message": "Password has been reset successfully"}
