import re

from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.user import AdminPermissionLevel, User, UserRole
from app.schemas.user import AdminPrivilegeUpdate, PasswordUpdate, ProfileUpdate, UserCreate, UserUpdate

STUDENT_USERNAME_RE = re.compile(r"^\d{10}$")


def get_user(db: Session, user_id: int) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email.strip().lower()).first()


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.query(User).filter(User.username == username.strip()).first()


def list_users(db: Session, skip: int = 0, limit: int = 100) -> list[User]:
    return db.query(User).order_by(User.created_at.desc(), User.id.desc()).offset(skip).limit(limit).all()


def _normalize_permissions(permissions: list[str] | None) -> list[str]:
    normalized_permissions: list[str] = []
    for permission in permissions or []:
        value = str(permission).strip()
        if value and value not in normalized_permissions:
            normalized_permissions.append(value)
    return normalized_permissions


def _validate_student_username(username: str) -> None:
    if not STUDENT_USERNAME_RE.fullmatch(username.strip()):
        raise ValueError("Student username must be a 10-digit student ID")


def _validate_unique_identity(db: Session, *, username: str, email: str, current_user_id: int | None = None) -> None:
    existing_username = get_user_by_username(db, username)
    if existing_username and existing_username.id != current_user_id:
        raise ValueError("Username already registered")

    existing_email = get_user_by_email(db, email)
    if existing_email and existing_email.id != current_user_id:
        raise ValueError("Email already registered")


def _apply_admin_defaults(user: User) -> None:
    if user.role != UserRole.ADMIN:
        user.admin_permission_level = None
        user.admin_permissions = []
        user.admin_expires_at = None
        return

    if user.admin_permission_level is None:
        user.admin_permission_level = AdminPermissionLevel.FULL

    if user.admin_permission_level == AdminPermissionLevel.FULL:
        user.admin_permissions = []


def create_user(db: Session, user_in: UserCreate) -> User:
    username = user_in.username.strip()
    email = user_in.email.strip().lower()

    if user_in.role == UserRole.USER:
        _validate_student_username(username)

    _validate_unique_identity(db, username=username, email=email)

    db_user = User(
        username=username,
        email=email,
        password_hash=hash_password(user_in.password),
        role=user_in.role,
        is_active=user_in.is_active,
        full_name=user_in.full_name,
        major=user_in.major,
        year_of_study=user_in.year_of_study,
        bio=user_in.bio,
        admin_permission_level=user_in.admin_permission_level if user_in.role == UserRole.ADMIN else None,
        admin_expires_at=user_in.admin_expires_at if user_in.role == UserRole.ADMIN else None,
    )

    if user_in.role == UserRole.ADMIN:
        if user_in.admin_permission_level == AdminPermissionLevel.LIMITED and not user_in.admin_permissions:
            raise ValueError("Limited admin accounts require at least one permission")
        db_user.admin_permissions = user_in.admin_permissions

    _apply_admin_defaults(db_user)

    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def update_user(db: Session, user_id: int, user_in: UserUpdate) -> User | None:
    db_user = get_user(db, user_id)
    if not db_user:
        return None

    update_data = user_in.model_dump(exclude_unset=True)
    new_username = (update_data.get("username") or db_user.username).strip()
    new_email = (update_data.get("email") or db_user.email).strip().lower()
    new_role = update_data.get("role") or db_user.role

    if new_role == UserRole.USER:
        _validate_student_username(new_username)

    _validate_unique_identity(db, username=new_username, email=new_email, current_user_id=db_user.id)

    db_user.username = new_username
    db_user.email = new_email

    if "password" in update_data and update_data["password"]:
        db_user.password_hash = hash_password(update_data["password"])

    for field in ("full_name", "major", "year_of_study", "bio", "is_active"):
        if field in update_data:
            setattr(db_user, field, update_data[field])

    if "role" in update_data:
        db_user.role = update_data["role"]

    if db_user.role == UserRole.USER:
        db_user.admin_permission_level = None
        db_user.admin_permissions = []
        db_user.admin_expires_at = None
    else:
        if "admin_permission_level" in update_data:
            db_user.admin_permission_level = update_data["admin_permission_level"]
        if "admin_permissions" in update_data:
            db_user.admin_permissions = update_data["admin_permissions"]
        if "admin_expires_at" in update_data:
            db_user.admin_expires_at = update_data["admin_expires_at"]
        if db_user.admin_permission_level is None:
            db_user.admin_permission_level = AdminPermissionLevel.FULL
        if db_user.admin_permission_level == AdminPermissionLevel.LIMITED and not db_user.admin_permissions:
            raise ValueError("Limited admin accounts require at least one permission")
        if db_user.admin_permission_level == AdminPermissionLevel.FULL:
            db_user.admin_permissions = []

    db.commit()
    db.refresh(db_user)
    return db_user


def update_profile(db: Session, user_id: int, profile_in: ProfileUpdate) -> User | None:
    db_user = get_user(db, user_id)
    if not db_user:
        return None

    update_data = profile_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_user, field, value)

    db.commit()
    db.refresh(db_user)
    return db_user


def change_password(db: Session, user_id: int, password_in: PasswordUpdate) -> User | None:
    db_user = get_user(db, user_id)
    if not db_user:
        return None

    if not verify_password(password_in.current_password, db_user.password_hash):
        raise ValueError("Current password is incorrect")

    db_user.password_hash = hash_password(password_in.new_password)
    db.commit()
    db.refresh(db_user)
    return db_user


def grant_admin_access(db: Session, user_id: int, privilege_in: AdminPrivilegeUpdate) -> User | None:
    db_user = get_user(db, user_id)
    if not db_user:
        return None

    db_user.role = UserRole.ADMIN
    db_user.admin_permission_level = privilege_in.permission_level
    db_user.admin_expires_at = privilege_in.expires_at
    db_user.admin_permissions = _normalize_permissions(privilege_in.permissions)

    if db_user.admin_permission_level == AdminPermissionLevel.LIMITED and not db_user.admin_permissions:
        raise ValueError("Limited admin accounts require at least one permission")

    if db_user.admin_permission_level == AdminPermissionLevel.FULL:
        db_user.admin_permissions = []

    db.commit()
    db.refresh(db_user)
    return db_user


def revoke_admin_access(db: Session, user_id: int) -> User | None:
    db_user = get_user(db, user_id)
    if not db_user:
        return None

    db_user.role = UserRole.USER
    db_user.admin_permission_level = None
    db_user.admin_permissions = []
    db_user.admin_expires_at = None

    db.commit()
    db.refresh(db_user)
    return db_user


def delete_user(db: Session, user_id: int) -> bool:
    db_user = get_user(db, user_id)
    if not db_user:
        return False

    db.delete(db_user)
    db.commit()
    return True
