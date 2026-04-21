from datetime import datetime
import re

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.models.user import AdminPermissionLevel, UserRole


class UserBase(BaseModel):
    username: str = Field(min_length=3, max_length=100)
    email: EmailStr
    full_name: str | None = Field(default=None, max_length=255)
    major: str | None = Field(default=None, max_length=255)
    year_of_study: int | None = Field(default=None, ge=1, le=12)
    bio: str | None = None


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)
    role: UserRole = Field(default=UserRole.USER)
    is_active: bool = True
    admin_permission_level: AdminPermissionLevel | None = None
    admin_permissions: list[str] = Field(default_factory=list)
    admin_expires_at: datetime | None = None

    @model_validator(mode="after")
    def validate_role_specific_rules(self) -> "UserCreate":
        username = self.username.strip()
        if self.role == UserRole.USER and not re.fullmatch(r"\d{10}", username):
            raise ValueError("Student username must be a 10-digit student ID")

        if self.role == UserRole.USER and (
            self.admin_permission_level
            or self.admin_permissions
            or self.admin_expires_at
        ):
            raise ValueError("Student accounts cannot receive admin permissions")

        if self.role == UserRole.ADMIN:
            if self.admin_permission_level is None:
                self.admin_permission_level = (
                    AdminPermissionLevel.LIMITED if self.admin_permissions else AdminPermissionLevel.FULL
                )
            if self.admin_permission_level == AdminPermissionLevel.LIMITED and not self.admin_permissions:
                raise ValueError("Limited admin accounts require at least one permission")
            if self.admin_permission_level == AdminPermissionLevel.FULL:
                self.admin_permissions = []

        return self


class UserUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=3, max_length=100)
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)
    role: UserRole | None = None
    is_active: bool | None = None
    admin_permission_level: AdminPermissionLevel | None = None
    admin_permissions: list[str] | None = None
    admin_expires_at: datetime | None = None
    full_name: str | None = Field(default=None, max_length=255)
    major: str | None = Field(default=None, max_length=255)
    year_of_study: int | None = Field(default=None, ge=1, le=12)
    bio: str | None = None


class ProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=255)
    major: str | None = Field(default=None, max_length=255)
    year_of_study: int | None = Field(default=None, ge=1, le=12)
    bio: str | None = None


class PasswordUpdate(BaseModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class AdminPrivilegeUpdate(BaseModel):
    permission_level: AdminPermissionLevel = Field(default=AdminPermissionLevel.LIMITED)
    permissions: list[str] = Field(default_factory=list)
    expires_at: datetime | None = None


class UserRead(UserBase):
    id: int
    role: UserRole
    is_active: bool
    admin_permission_level: AdminPermissionLevel | None = None
    admin_permissions: list[str] = Field(default_factory=list)
    admin_expires_at: datetime | None = None
    last_login_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
