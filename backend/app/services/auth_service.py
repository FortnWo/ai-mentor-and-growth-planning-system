from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.security import create_access_token, verify_password
from app.schemas.auth import LoginRequest, TokenResponse
from app.services import user_service


def login(db: Session, payload: LoginRequest) -> TokenResponse | None:
    user = user_service.get_user_by_username(db, payload.username)
    if not user or not user.is_active:
        return None

    if not verify_password(payload.password, user.password_hash):
        return None

    user.last_login_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.add(user)
    db.commit()
    db.refresh(user)

    access_token, expires_in_minutes = create_access_token(str(user.id))
    return TokenResponse(
        access_token=access_token,
        expires_in_minutes=expires_in_minutes,
        user=user,
    )
