from app.core.config import settings
from app.core.database import SessionLocal
from app.models.user import AdminPermissionLevel, UserRole
from app.schemas.user import UserCreate
from app.services import user_service


def ensure_bootstrap_admin() -> None:
    if not settings.BOOTSTRAP_ADMIN_USERNAME or not settings.BOOTSTRAP_ADMIN_EMAIL or not settings.BOOTSTRAP_ADMIN_PASSWORD:
        return

    db = SessionLocal()
    try:
        existing = user_service.get_user_by_username(db, settings.BOOTSTRAP_ADMIN_USERNAME)
        if existing:
            if existing.role == UserRole.ADMIN:
                if existing.admin_permission_level != AdminPermissionLevel.FULL or existing.admin_permissions:
                    existing.admin_permission_level = AdminPermissionLevel.FULL
                    existing.admin_permissions = []
                    existing.admin_expires_at = None
                    db.add(existing)
                    db.commit()
            return

        if user_service.get_user_by_email(db, settings.BOOTSTRAP_ADMIN_EMAIL):
            return

        user_service.create_user(
            db,
            UserCreate(
                username=settings.BOOTSTRAP_ADMIN_USERNAME,
                email=settings.BOOTSTRAP_ADMIN_EMAIL,
                password=settings.BOOTSTRAP_ADMIN_PASSWORD,
                full_name=settings.BOOTSTRAP_ADMIN_FULL_NAME,
                role=UserRole.ADMIN,
                admin_permission_level=AdminPermissionLevel.FULL,
                admin_permissions=[],
            ),
        )
    finally:
        db.close()