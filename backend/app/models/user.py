import json
from datetime import date
from enum import Enum

from sqlalchemy import Boolean, Column, DateTime, Enum as SQLEnum, Integer, SmallInteger, String, Text, func, text
from sqlalchemy.dialects.mysql import INTEGER as MYSQL_INTEGER, SMALLINT as MYSQL_SMALLINT
from sqlalchemy.orm import relationship

from app.core.database import Base


class UserRole(str, Enum):
    USER = "user"
    ADMIN = "admin"


class AdminPermissionLevel(str, Enum):
    FULL = "full"
    LIMITED = "limited"


UnsignedInt = Integer().with_variant(MYSQL_INTEGER(unsigned=True), "mysql")
UnsignedSmallInt = SmallInteger().with_variant(MYSQL_SMALLINT(unsigned=True), "mysql")


class User(Base):
    __tablename__ = "users"

    id = Column(UnsignedInt, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(
        SQLEnum(
            UserRole,
            values_callable=lambda values: [value.value for value in values],
            native_enum=False,
        ),
        nullable=False,
        server_default=text("'user'"),
    )
    is_active = Column(Boolean, nullable=False, server_default=text("1"))
    admin_permission_level = Column(
        SQLEnum(
            AdminPermissionLevel,
            values_callable=lambda values: [value.value for value in values],
            native_enum=False,
        ),
        nullable=True,
    )
    _admin_permissions_json = Column("admin_permissions", Text, nullable=True)
    admin_expires_at = Column(DateTime, nullable=True)
    last_login_at = Column(DateTime, nullable=True)
    full_name = Column(String(255), nullable=True)
    major = Column(String(255), nullable=True)
    year_of_study = Column(Integer, nullable=True)
    bio = Column(Text, nullable=True)
    phone = Column(String(20), nullable=True)
    address = Column(String(500), nullable=True)
    enrollment_year = Column(UnsignedSmallInt, nullable=True)
    risk_flag = Column(Integer, nullable=False, server_default=text("0"))
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    sessions = relationship(
        "ChatSession",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    profile = relationship(
        "UserProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    goals = relationship(
        "Goal",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    traits = relationship(
        "UserTrait",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    @property
    def is_system_admin(self) -> bool:
        from app.core.system_admin import is_system_admin as check_system_admin

        return check_system_admin(self)

    @property
    def admin_permissions(self) -> list[str]:
        raw = self._admin_permissions_json
        if raw is None or raw == "":
            return []

        if isinstance(raw, list):
            raw_permissions = raw
        elif isinstance(raw, dict):
            return []
        else:
            try:
                raw_permissions = json.loads(str(raw))
            except (json.JSONDecodeError, TypeError):
                return []

        if not isinstance(raw_permissions, list):
            return []

        return [str(permission) for permission in raw_permissions if str(permission).strip()]

    @admin_permissions.setter
    def admin_permissions(self, permissions: list[str] | None) -> None:
        normalized_permissions = []
        for permission in permissions or []:
            normalized = str(permission).strip()
            if normalized and normalized not in normalized_permissions:
                normalized_permissions.append(normalized)

        self._admin_permissions_json = json.dumps(normalized_permissions, ensure_ascii=False)

    @property
    def computed_year_of_study(self) -> int | None:
        """计算当前年级：入学年份到当前学年已过的年数（从当年 9 月起算）。"""
        if not self.enrollment_year:
            return None
        today = date.today()
        academic_year_start = today.year if today.month >= 9 else today.year - 1
        year = academic_year_start - self.enrollment_year + 1
        return max(1, year) if year >= 1 else None
