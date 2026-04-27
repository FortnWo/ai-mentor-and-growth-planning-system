from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

PROFILE_FIELDS = (
    "interests",
    "skills",
    "goals",
    "study_habits",
    "personality",
    "preferences",
)


def _normalize_string_list(value: object) -> list[str]:
    if value is None:
        return []

    if isinstance(value, str):
        candidates = [value]
    elif isinstance(value, list):
        candidates = value
    else:
        return []

    normalized: list[str] = []
    for item in candidates:
        text = str(item).strip()
        if text and text not in normalized:
            normalized.append(text)

    return normalized


class ExtendedProfileBase(BaseModel):
    interests: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    goals: list[str] = Field(default_factory=list)
    study_habits: list[str] = Field(default_factory=list)
    personality: list[str] = Field(default_factory=list)
    preferences: list[str] = Field(default_factory=list)

    @field_validator(*PROFILE_FIELDS, mode="before")
    @classmethod
    def normalize_fields(cls, value: object) -> list[str]:
        return _normalize_string_list(value)


class UserExtendedProfileRead(ExtendedProfileBase):
    id: int
    user_id: int
    last_extracted_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserExtendedProfileUpdate(BaseModel):
    interests: list[str] | None = None
    skills: list[str] | None = None
    goals: list[str] | None = None
    study_habits: list[str] | None = None
    personality: list[str] | None = None
    preferences: list[str] | None = None

    @field_validator(*PROFILE_FIELDS, mode="before")
    @classmethod
    def normalize_optional_fields(cls, value: object) -> list[str] | None:
        if value is None:
            return None
        return _normalize_string_list(value)


class ExtendedProfileExtractionResult(ExtendedProfileBase):
    pass


class ExtendedProfileRefreshResponse(BaseModel):
    profile: UserExtendedProfileRead
    extracted: ExtendedProfileExtractionResult