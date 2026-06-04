from app.core.config import settings
from app.models.user import AdminPermissionLevel, User, UserRole


def get_system_admin_username() -> str | None:
    username = (settings.BOOTSTRAP_ADMIN_USERNAME or "").strip()
    return username or None


def is_system_admin(user: User) -> bool:
    system_username = get_system_admin_username()
    if not system_username:
        return False
    return user.username == system_username


def enforce_system_admin_full_access(user: User) -> None:
    if not is_system_admin(user):
        return

    user.role = UserRole.ADMIN
    user.admin_permission_level = AdminPermissionLevel.FULL
    user.admin_permissions = []
    user.admin_expires_at = None
    user.is_active = True


def assert_system_admin_permissions_immutable(user: User) -> None:
    if is_system_admin(user):
        raise ValueError("System admin account permissions cannot be modified")
