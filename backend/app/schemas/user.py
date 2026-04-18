from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    username: str = Field(min_length=3, max_length=100)
    email: EmailStr
    full_name: str | None = Field(default=None, max_length=255)
    major: str | None = Field(default=None, max_length=255)
    year_of_study: int | None = Field(default=None, ge=1, le=12)
    bio: str | None = None


class UserCreate(UserBase):
    pass


class UserUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=3, max_length=100)
    email: EmailStr | None = None
    full_name: str | None = Field(default=None, max_length=255)
    major: str | None = Field(default=None, max_length=255)
    year_of_study: int | None = Field(default=None, ge=1, le=12)
    bio: str | None = None


class UserRead(UserBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
