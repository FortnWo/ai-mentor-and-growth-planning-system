from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.user_trait import UserTrait
from app.schemas.profile import UserTraitRead

TRAIT_TYPE_MAPPING: dict[str, str] = {
    "interests": "interest",
    "skills": "skill",
    "goals": "goal_signal",
    "study_habits": "study_habit",
    "personality": "personality",
    "preferences": "preference",
}

TRAIT_TYPE_LABELS: dict[str, str] = {
    "interest": "兴趣",
    "skill": "技能",
    "goal_signal": "目标",
    "study_habit": "学习习惯",
    "personality": "性格",
    "preference": "偏好",
}

TRAIT_TYPE_ORDER: list[str] = list(TRAIT_TYPE_MAPPING.values())


def trait_type_sort_key(trait_type: str) -> int:
    try:
        return TRAIT_TYPE_ORDER.index(trait_type)
    except ValueError:
        return len(TRAIT_TYPE_ORDER)


def list_traits_for_user(db: Session, user_id: int) -> list[UserTraitRead]:
    trait_types = list(TRAIT_TYPE_MAPPING.values())
    traits = (
        db.query(UserTrait)
        .filter(UserTrait.user_id == user_id, UserTrait.trait_type.in_(trait_types))
        .all()
    )

    traits.sort(
        key=lambda trait: (
            trait_type_sort_key(trait.trait_type),
            -(float(trait.trait_score or 0)),
            trait.trait_key.lower(),
        )
    )

    return [
        UserTraitRead(
            trait_type=trait.trait_type,
            trait_key=trait.trait_key,
            source=trait.source,
            confidence=trait.confidence,
            trait_score=float(trait.trait_score or 1.0),
            last_observed_at=trait.last_observed_at,
        )
        for trait in traits
    ]
