"""
Verification code service for password reset.

Generates, stores, validates, and expires codes.
Default code length, TTL, and resend interval come from settings (configurable in Phase 5).
"""
from __future__ import annotations

import random
import string
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.verification_code import VerificationCode


_DEFAULT_CODE_LENGTH = 6
_DEFAULT_EXPIRE_MINUTES = 10
_DEFAULT_RESEND_INTERVAL_SECONDS = 60


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _code_length() -> int:
    return getattr(settings, "VERIFICATION_CODE_LENGTH", _DEFAULT_CODE_LENGTH)


def _expire_minutes() -> int:
    return getattr(settings, "VERIFICATION_CODE_EXPIRE_MINUTES", _DEFAULT_EXPIRE_MINUTES)


def _resend_interval_seconds() -> int:
    return getattr(settings, "VERIFICATION_CODE_RESEND_INTERVAL_SECONDS", _DEFAULT_RESEND_INTERVAL_SECONDS)


def _generate_code() -> str:
    digits = string.digits
    return "".join(random.choices(digits, k=_code_length()))


def can_send_code(db: Session, user_id: int, code_type: str) -> tuple[bool, int]:
    """Return (can_send, seconds_remaining_until_allowed)."""
    interval = _resend_interval_seconds()
    cutoff = _utcnow() - timedelta(seconds=interval)

    last = (
        db.query(VerificationCode)
        .filter(
            VerificationCode.user_id == user_id,
            VerificationCode.type == code_type,
            VerificationCode.created_at > cutoff,
        )
        .order_by(VerificationCode.created_at.desc())
        .first()
    )
    if not last:
        return True, 0

    elapsed = (_utcnow() - last.created_at).total_seconds()
    remaining = max(0, int(interval - elapsed))
    return remaining == 0, remaining


def create_code(db: Session, user_id: int, code_type: str) -> VerificationCode:
    """Generate a fresh code and persist it. Invalidates previous unused codes of the same type."""
    now = _utcnow()

    # Invalidate prior unexpired codes for this user+type by setting them as used
    db.query(VerificationCode).filter(
        VerificationCode.user_id == user_id,
        VerificationCode.type == code_type,
        VerificationCode.used_at.is_(None),
        VerificationCode.expires_at > now,
    ).update({"used_at": now})

    record = VerificationCode(
        user_id=user_id,
        type=code_type,
        code=_generate_code(),
        expires_at=now + timedelta(minutes=_expire_minutes()),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def verify_code(db: Session, user_id: int, code_type: str, code: str) -> bool:
    """
    Validate the code. Marks it as used on success.
    Returns True if valid, False otherwise.
    """
    now = _utcnow()
    record = (
        db.query(VerificationCode)
        .filter(
            VerificationCode.user_id == user_id,
            VerificationCode.type == code_type,
            VerificationCode.code == code,
            VerificationCode.used_at.is_(None),
            VerificationCode.expires_at > now,
        )
        .order_by(VerificationCode.created_at.desc())
        .first()
    )
    if not record:
        return False

    record.used_at = now
    db.commit()
    return True
