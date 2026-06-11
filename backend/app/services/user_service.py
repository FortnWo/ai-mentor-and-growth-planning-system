import re

from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.core.system_admin import (
    assert_system_admin_permissions_immutable,
    enforce_system_admin_full_access,
    get_system_admin_username,
    is_system_admin,
)
from app.models.user import AdminPermissionLevel, User, UserRole
from app.schemas.user import AdminPrivilegeUpdate, InfoUpdate, PasswordUpdate, UserCreate, UserUpdate

STUDENT_USERNAME_RE = re.compile(r"^\d{10}$")
PHONE_RE = re.compile(r"^\d{11}$")


def get_user(db: Session, user_id: int) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email.strip().lower()).first()


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.query(User).filter(User.username == username.strip()).first()


def list_users(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    username_like: str | None = None,
    major: str | None = None,
    year: int | None = None,
    is_active: bool | None = None,
) -> list[User]:
    query = db.query(User)
    if username_like:
        query = query.filter(User.username.like(f"%{username_like.strip()}%"))
    if major:
        query = query.filter(User.major == major.strip())
    if year is not None:
        query = query.filter(User.enrollment_year == year)
    if is_active is not None:
        query = query.filter(User.is_active == is_active)
    return query.order_by(User.created_at.desc(), User.id.desc()).offset(skip).limit(limit).all()


def _normalize_permissions(permissions: list[str] | None) -> list[str]:
    normalized_permissions: list[str] = []
    for permission in permissions or []:
        value = str(permission).strip()
        if value and value not in normalized_permissions:
            normalized_permissions.append(value)
    return normalized_permissions


def _validate_student_username(username: str) -> None:
    if not STUDENT_USERNAME_RE.fullmatch(username.strip()):
        raise ValueError("学生用户名必须为 10 位学号")


def _validate_phone(phone: str | None) -> None:
    if phone and not PHONE_RE.fullmatch(phone.strip()):
        raise ValueError("USER_4002: 手机号必须为 11 位数字")


def _validate_unique_identity(db: Session, *, username: str, email: str, current_user_id: int | None = None) -> None:
    existing_username = get_user_by_username(db, username)
    if existing_username and existing_username.id != current_user_id:
        raise ValueError("用户名已被注册")

    existing_email = get_user_by_email(db, email)
    if existing_email and existing_email.id != current_user_id:
        raise ValueError("邮箱已被注册")


def _apply_admin_defaults(user: User) -> None:
    if is_system_admin(user):
        enforce_system_admin_full_access(user)
        return

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
    system_username = get_system_admin_username()

    if system_username and username == system_username:
        if user_in.role != UserRole.ADMIN:
            raise ValueError("系统管理员账号必须保持管理员身份")
        user_in = user_in.model_copy(
            update={
                "role": UserRole.ADMIN,
                "admin_permission_level": AdminPermissionLevel.FULL,
                "admin_permissions": [],
                "admin_expires_at": None,
                "is_active": True,
            }
        )

    if user_in.role == UserRole.USER:
        _validate_student_username(username)

    _validate_unique_identity(db, username=username, email=email)

    _validate_phone(user_in.phone)

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
        phone=user_in.phone,
        address=user_in.address,
        enrollment_year=user_in.enrollment_year,
        admin_permission_level=user_in.admin_permission_level if user_in.role == UserRole.ADMIN else None,
        admin_expires_at=user_in.admin_expires_at if user_in.role == UserRole.ADMIN else None,
    )

    if user_in.role == UserRole.ADMIN:
        if user_in.admin_permission_level == AdminPermissionLevel.LIMITED and not user_in.admin_permissions:
            raise ValueError("受限管理员账号至少需要一项权限")
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

    if "is_active" in update_data and db_user.role == UserRole.ADMIN:
        raise ValueError("管理员账号不能修改启用状态")

    if is_system_admin(db_user):
        system_username = get_system_admin_username()
        if "username" in update_data and new_username != system_username:
            raise ValueError("系统管理员用户名不可修改")
        if new_role == UserRole.USER:
            raise ValueError("系统管理员账号不能降级为学生")
        for field in ("admin_permission_level", "admin_permissions", "admin_expires_at"):
            if field in update_data:
                raise ValueError("系统管理员账号权限不可修改")

    if new_role == UserRole.USER:
        _validate_student_username(new_username)

    _validate_unique_identity(db, username=new_username, email=new_email, current_user_id=db_user.id)

    db_user.username = new_username
    db_user.email = new_email

    if "password" in update_data and update_data["password"]:
        db_user.password_hash = hash_password(update_data["password"])

    if "phone" in update_data:
        _validate_phone(update_data["phone"])

    for field in ("full_name", "major", "year_of_study", "bio", "is_active", "phone", "address", "enrollment_year"):
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
            raise ValueError("受限管理员账号至少需要一项权限")
        if db_user.admin_permission_level == AdminPermissionLevel.FULL:
            db_user.admin_permissions = []

    enforce_system_admin_full_access(db_user)

    db.commit()
    db.refresh(db_user)
    return db_user


def update_info(db: Session, user_id: int, info_in: InfoUpdate) -> User | None:
    db_user = get_user(db, user_id)
    if not db_user:
        return None

    update_data = info_in.model_dump(exclude_unset=True)

    if "phone" in update_data:
        _validate_phone(update_data["phone"])

    if "email" in update_data and update_data["email"]:
        new_email = str(update_data["email"]).strip().lower()
        existing = get_user_by_email(db, new_email)
        if existing and existing.id != user_id:
            raise ValueError("邮箱已被注册")
        update_data["email"] = new_email

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
        raise ValueError("当前密码不正确")

    db_user.password_hash = hash_password(password_in.new_password)
    db.commit()
    db.refresh(db_user)
    return db_user


def grant_admin_access(db: Session, user_id: int, privilege_in: AdminPrivilegeUpdate) -> User | None:
    db_user = get_user(db, user_id)
    if not db_user:
        return None

    assert_system_admin_permissions_immutable(db_user)

    db_user.role = UserRole.ADMIN
    db_user.admin_permission_level = privilege_in.permission_level
    db_user.admin_expires_at = privilege_in.expires_at
    db_user.admin_permissions = _normalize_permissions(privilege_in.permissions)

    if db_user.admin_permission_level == AdminPermissionLevel.LIMITED and not db_user.admin_permissions:
        raise ValueError("受限管理员账号至少需要一项权限")

    if db_user.admin_permission_level == AdminPermissionLevel.FULL:
        db_user.admin_permissions = []

    db.commit()
    db.refresh(db_user)
    return db_user


def revoke_admin_access(db: Session, user_id: int) -> User | None:
    db_user = get_user(db, user_id)
    if not db_user:
        return None

    assert_system_admin_permissions_immutable(db_user)

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

    assert_system_admin_permissions_immutable(db_user)

    db.delete(db_user)
    db.commit()
    return True


def bulk_reset_password(db: Session, user_ids: list[int], new_password: str) -> dict:
    """Reset password for multiple users. Returns success_count and failed_ids."""
    new_hash = hash_password(new_password)
    success_count = 0
    failed_ids: list[int] = []

    for uid in user_ids:
        user = get_user(db, uid)
        if not user:
            failed_ids.append(uid)
            continue
        user.password_hash = new_hash
        success_count += 1

    db.commit()
    return {"success_count": success_count, "failed_ids": failed_ids}


def import_users_from_excel(db: Session, file_bytes: bytes) -> dict:
    """
    Parse an Excel file and bulk-create student accounts.

    Expected columns (case-insensitive, order flexible):
      username (学号, required), full_name (姓名), major (专业),
      enrollment_year (入学年份), phone (手机, required), email (邮箱),
      password (默认密码, optional — falls back to 'usth123456')

    Returns { success_count, failed: [{row, reason}] }
    """
    try:
        import io
        import openpyxl
    except ImportError as exc:
        raise ValueError("USER_4091: 服务器未安装 openpyxl") from exc

    try:
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
    except Exception as exc:
        raise ValueError(f"USER_4091: 无法解析 Excel 文件: {exc}") from exc

    if not rows:
        raise ValueError("USER_4091: Excel 文件为空")

    # Build column index map (first row = header)
    header = [str(cell).strip().lower() if cell is not None else "" for cell in rows[0]]

    COL_ALIASES: dict[str, list[str]] = {
        "username": ["username", "学号", "用户名"],
        "full_name": ["full_name", "姓名", "name"],
        "major": ["major", "专业"],
        "enrollment_year": ["enrollment_year", "入学年份", "入学年", "year"],
        "phone": ["phone", "手机", "手机号", "手机号码", "mobile"],
        "email": ["email", "邮箱", "邮件"],
        "password": ["password", "密码", "初始密码"],
    }

    col_idx: dict[str, int | None] = {}
    for field, aliases in COL_ALIASES.items():
        col_idx[field] = next((i for i, h in enumerate(header) if h in aliases), None)

    DEFAULT_PASSWORD = "usth123456"
    success_count = 0
    failed: list[dict] = []

    for row_num, row in enumerate(rows[1:], start=2):
        def _cell(field: str) -> str:
            idx = col_idx.get(field)
            if idx is None or idx >= len(row):
                return ""
            return str(row[idx]).strip() if row[idx] is not None else ""

        username = _cell("username")
        phone = _cell("phone")

        if not username:
            failed.append({"row": row_num, "reason": "学号为必填项"})
            continue

        password = _cell("password") or DEFAULT_PASSWORD
        enrollment_year_raw = _cell("enrollment_year")
        enrollment_year = int(enrollment_year_raw) if enrollment_year_raw.isdigit() else None

        email_val = _cell("email") or f"{username}@student.placeholder"

        try:
            user_in = UserCreate(
                username=username,
                email=email_val,
                password=password,
                full_name=_cell("full_name") or None,
                major=_cell("major") or None,
                enrollment_year=enrollment_year,
                phone=phone or None,
                role=UserRole.USER,
            )
            create_user(db, user_in)
            success_count += 1
        except Exception as exc:
            failed.append({"row": row_num, "reason": str(exc)})

    return {"success_count": success_count, "failed": failed}
