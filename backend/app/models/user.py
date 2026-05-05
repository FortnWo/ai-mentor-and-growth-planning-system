import json
from enum import Enum

from sqlalchemy import Boolean, Column, DateTime, Enum as SQLEnum, Integer, String, Text, func, text
from sqlalchemy.dialects.mysql import INTEGER as MYSQL_INTEGER
from sqlalchemy.orm import relationship

from app.core.database import Base


class UserRole(str, Enum):
    USER = "user"
    ADMIN = "admin"


class AdminPermissionLevel(str, Enum):
    FULL = "full"
    LIMITED = "limited"


UnsignedInt = Integer().with_variant(MYSQL_INTEGER(unsigned=True), "mysql")


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
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    sessions = relationship(
        "ChatSession",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    extended_profile = relationship(
        "UserExtendedProfile",
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

    @property
    def admin_permissions(self) -> list[str]:
        if not self._admin_permissions_json:
            return []

        try:
            raw_permissions = json.loads(self._admin_permissions_json)
        except json.JSONDecodeError:
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
