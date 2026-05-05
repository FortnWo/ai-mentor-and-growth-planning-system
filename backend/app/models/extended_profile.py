import json

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.mysql import INTEGER as MYSQL_INTEGER
from sqlalchemy.orm import relationship

from app.core.database import Base


UnsignedInt = Integer().with_variant(MYSQL_INTEGER(unsigned=True), "mysql")


class UserExtendedProfile(Base):
    __tablename__ = "user_extended_profiles"

    id = Column(UnsignedInt, primary_key=True, index=True)
    user_id = Column(
        UnsignedInt,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    _interests_json = Column("interests", Text, nullable=True)
    _skills_json = Column("skills", Text, nullable=True)
    _goals_json = Column("goals", Text, nullable=True)
    _study_habits_json = Column("study_habits", Text, nullable=True)
    _personality_json = Column("personality", Text, nullable=True)
    _preferences_json = Column("preferences", Text, nullable=True)

    last_extracted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User", back_populates="extended_profile")

    @staticmethod
    def _load_json_list(raw_value: str | None) -> list[str]:
        if not raw_value:
            return []

        try:
            loaded = json.loads(raw_value)
        except json.JSONDecodeError:
            return []

        if not isinstance(loaded, list):
            return []

        normalized: list[str] = []
        for item in loaded:
            value = str(item).strip()
            if value and value not in normalized:
                normalized.append(value)

        return normalized

    @staticmethod
    def _dump_json_list(items: list[str] | None) -> str:
        normalized: list[str] = []
        for item in items or []:
            value = str(item).strip()
            if value and value not in normalized:
                normalized.append(value)

        return json.dumps(normalized, ensure_ascii=False)

    @property
    def interests(self) -> list[str]:
        return self._load_json_list(self._interests_json)

    @interests.setter
    def interests(self, values: list[str] | None) -> None:
        self._interests_json = self._dump_json_list(values)

    @property
    def skills(self) -> list[str]:
        return self._load_json_list(self._skills_json)

    @skills.setter
    def skills(self, values: list[str] | None) -> None:
        self._skills_json = self._dump_json_list(values)

    @property
    def goals(self) -> list[str]:
        return self._load_json_list(self._goals_json)

    @goals.setter
    def goals(self, values: list[str] | None) -> None:
        self._goals_json = self._dump_json_list(values)

    @property
    def study_habits(self) -> list[str]:
        return self._load_json_list(self._study_habits_json)

    @study_habits.setter
    def study_habits(self, values: list[str] | None) -> None:
        self._study_habits_json = self._dump_json_list(values)

    @property
    def personality(self) -> list[str]:
        return self._load_json_list(self._personality_json)

    @personality.setter
    def personality(self, values: list[str] | None) -> None:
        self._personality_json = self._dump_json_list(values)

    @property
    def preferences(self) -> list[str]:
        return self._load_json_list(self._preferences_json)

    @preferences.setter
    def preferences(self, values: list[str] | None) -> None:
        self._preferences_json = self._dump_json_list(values)