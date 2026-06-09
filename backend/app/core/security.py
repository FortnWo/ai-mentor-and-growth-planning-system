from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.user import AdminPermissionLevel, User, UserRole

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(subject: str, *, expires_delta: timedelta | None = None) -> tuple[str, int]:
    expire_delta = expires_delta or timedelta(minutes=settings.AUTH_ACCESS_TOKEN_EXPIRES_MINUTES)
    expires_in_minutes = int(expire_delta.total_seconds() // 60)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    payload = {
        "sub": subject,
        "exp": now + expire_delta,
        "iat": now,
    }
    token = jwt.encode(payload, settings.AUTH_SECRET_KEY, algorithm=settings.AUTH_ALGORITHM)
    return token, expires_in_minutes


def decode_access_token(token: str) -> str:
    try:
        payload = jwt.decode(token, settings.AUTH_SECRET_KEY, algorithms=[settings.AUTH_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="认证令牌无效") from exc

    subject = payload.get("sub")
    if not subject:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="认证令牌无效")

    return str(subject)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    from app.services import user_service

    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录")

    user_id = decode_access_token(credentials.credentials)
    if not user_id.isdigit():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="认证令牌无效")

    user = user_service.get_user(db, int(user_id))
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已被停用")

    return user


def is_admin_active(user: User) -> bool:
    if not user.is_active or user.role != UserRole.ADMIN:
        return False

    if user.admin_expires_at and user.admin_expires_at <= datetime.now(timezone.utc).replace(tzinfo=None):
        return False

    return True


def has_admin_access(user: User, permission: str | None = None) -> bool:
    from app.core.system_admin import is_system_admin

    if not is_admin_active(user):
        return False

    if is_system_admin(user):
        return True

    # Legacy admins may have role=admin with NULL level; treat as full (see user_service._apply_admin_defaults).
    if user.admin_permission_level is None or user.admin_permission_level == AdminPermissionLevel.FULL:
        return True

    if permission is None:
        return True

    return permission in user.admin_permissions


def has_full_admin_access(user: User) -> bool:
    from app.core.system_admin import is_system_admin

    if not is_admin_active(user):
        return False

    if is_system_admin(user):
        return True

    return user.admin_permission_level is None or user.admin_permission_level == AdminPermissionLevel.FULL


def require_admin(permission: str | None = None):
    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if not has_admin_access(current_user, permission):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
        return current_user

    return dependency


def require_full_admin():
    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if not has_full_admin_access(current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="需要完整管理员权限",
            )
        return current_user

    return dependency