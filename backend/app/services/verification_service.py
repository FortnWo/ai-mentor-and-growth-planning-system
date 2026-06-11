"""
Verification code service for password reset.

Generates, stores, validates, and expires codes.
TTL, resend interval, and code length come from system_config (admin panel).
"""
from __future__ import annotations

import random
import string
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.verification_code import VerificationCode
from app.services import system_config_service as scs


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _verification_settings(db: Session) -> dict:
    return scs.get_verification_config(db)


def _generate_code(db: Session) -> str:
    digits = string.digits
    length = _verification_settings(db)["code_length"]
    return "".join(random.choices(digits, k=length))


def can_send_code(db: Session, user_id: int, code_type: str) -> tuple[bool, int]:
    """Return (can_send, seconds_remaining_until_allowed)."""
    cfg = _verification_settings(db)
    interval = cfg["resend_interval_seconds"]
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
    expire_minutes = _verification_settings(db)["expire_minutes"]

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
        code=_generate_code(db),
        expires_at=now + timedelta(minutes=expire_minutes),
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
