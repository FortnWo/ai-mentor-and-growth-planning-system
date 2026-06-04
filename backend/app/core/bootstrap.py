from app.core.config import settings
from app.core.database import SessionLocal
from app.core.system_admin import enforce_system_admin_full_access, get_system_admin_username, is_system_admin
from app.models.user import AdminPermissionLevel, User, UserRole
from app.schemas.user import UserCreate
from app.services import user_service


def _migrate_legacy_admin_permissions(db) -> None:
    """Set full admin level for role=admin rows missing admin_permission_level."""
    legacy_admins = (
        db.query(User)
        .filter(User.role == UserRole.ADMIN, User.admin_permission_level.is_(None))
        .all()
    )
    if not legacy_admins:
        return

    for admin_user in legacy_admins:
        if is_system_admin(admin_user):
            enforce_system_admin_full_access(admin_user)
        else:
            admin_user.admin_permission_level = AdminPermissionLevel.FULL
            admin_user.admin_permissions = []
            admin_user.admin_expires_at = None
        db.add(admin_user)

    db.commit()


def _ensure_system_admin_integrity(db) -> None:
    username = get_system_admin_username()
    if not username:
        return

    admin_user = user_service.get_user_by_username(db, username)
    if not admin_user or admin_user.role != UserRole.ADMIN:
        return

    enforce_system_admin_full_access(admin_user)
    db.add(admin_user)
    db.commit()


def migrate_legacy_admin_permissions() -> None:
    db = SessionLocal()
    try:
        _migrate_legacy_admin_permissions(db)
        _ensure_system_admin_integrity(db)
    finally:
        db.close()


def ensure_bootstrap_admin() -> None:
    migrate_legacy_admin_permissions()

    bootstrap_email = (settings.BOOTSTRAP_ADMIN_EMAIL or "").strip()
    if not settings.BOOTSTRAP_ADMIN_USERNAME or not bootstrap_email or not settings.BOOTSTRAP_ADMIN_PASSWORD:
        return

    db = SessionLocal()
    try:
        existing = user_service.get_user_by_username(db, settings.BOOTSTRAP_ADMIN_USERNAME)
        if existing:
            if existing.role == UserRole.ADMIN:
                enforce_system_admin_full_access(existing)
                db.add(existing)
                db.commit()
            return

        if user_service.get_user_by_email(db, bootstrap_email):
            return

        user_service.create_user(
            db,
            UserCreate(
                username=settings.BOOTSTRAP_ADMIN_USERNAME,
                email=bootstrap_email,
                password=settings.BOOTSTRAP_ADMIN_PASSWORD,
                full_name=settings.BOOTSTRAP_ADMIN_FULL_NAME,
                role=UserRole.ADMIN,
                admin_permission_level=AdminPermissionLevel.FULL,
                admin_permissions=[],
            ),
        )
    finally:
        db.close()