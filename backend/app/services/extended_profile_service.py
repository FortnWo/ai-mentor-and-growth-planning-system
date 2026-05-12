from datetime import datetime, timezone
import json

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.chat import ChatMessage, ChatSession, MessageRole
from app.models.extended_profile import UserExtendedProfile
from app.models.user_trait import UserTrait
from app.schemas.extended_profile import (
    ExtendedProfileExtractionResult,
    UserExtendedProfileUpdate,
)

PROFILE_FIELDS = (
    "interests",
    "skills",
    "goals",
    "study_habits",
    "personality",
    "preferences",
)

TRAIT_TYPE_MAPPING = {
    "interests": "interest",
    "skills": "skill",
    "goals": "goal_signal",
    "study_habits": "study_habit",
    "personality": "personality",
    "preferences": "preference",
}


def get_profile_for_user(db: Session, user_id: int) -> UserExtendedProfile | None:
    return db.query(UserExtendedProfile).filter(UserExtendedProfile.user_id == user_id).first()


def get_or_create_profile_for_user(db: Session, user_id: int) -> UserExtendedProfile:
    profile = get_profile_for_user(db, user_id)
    if profile:
        return profile

    profile = UserExtendedProfile(user_id=user_id)
    for field in PROFILE_FIELDS:
        setattr(profile, field, [])

    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def update_profile_for_user(db: Session, user_id: int, profile_in: UserExtendedProfileUpdate) -> UserExtendedProfile:
    profile = get_or_create_profile_for_user(db, user_id)
    update_data = profile_in.model_dump(exclude_unset=True)

    for field in PROFILE_FIELDS:
        if field in update_data:
            setattr(profile, field, update_data[field] or [])

    _sync_traits_for_profile(db, user_id, profile, source="profile_update")
    db.commit()
    db.refresh(profile)
    return profile


def merge_unique(existing: list[str], incoming: list[str]) -> list[str]:
    merged: list[str] = []
    for item in existing + incoming:
        value = str(item).strip()
        if value and value not in merged:
            merged.append(value)
    return merged


def apply_extraction_result_for_user(
    db: Session,
    user_id: int,
    result: ExtendedProfileExtractionResult,
) -> UserExtendedProfile:
    profile = get_or_create_profile_for_user(db, user_id)

    for field in PROFILE_FIELDS:
        merged = merge_unique(getattr(profile, field), getattr(result, field))
        setattr(profile, field, merged)

    profile.last_extracted_at = datetime.now(timezone.utc).replace(tzinfo=None)
    _sync_traits_for_profile(db, user_id, profile, source="chat_extraction")

    db.commit()
    db.refresh(profile)
    return profile


def _sync_traits_for_profile(db: Session, user_id: int, profile: UserExtendedProfile, *, source: str) -> None:
    trait_types = list(TRAIT_TYPE_MAPPING.values())
    existing_traits = (
        db.query(UserTrait)
        .filter(UserTrait.user_id == user_id, UserTrait.trait_type.in_(trait_types))
        .all()
    )
    existing_index = {(trait.trait_type, trait.trait_key.lower()): trait for trait in existing_traits}

    observed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    for field_name, trait_type in TRAIT_TYPE_MAPPING.items():
        field_values = getattr(profile, field_name, []) or []
        for raw_value in field_values:
            trait_key = str(raw_value).strip()
            if not trait_key:
                continue

            lookup_key = (trait_type, trait_key.lower())
            trait = existing_index.get(lookup_key)
            if trait is None:
                trait = UserTrait(
                    user_id=user_id,
                    trait_type=trait_type,
                    trait_key=trait_key,
                    trait_score=1.0,
                    source=source,
                    confidence=0.8,
                    last_observed_at=observed_at,
                    trait_value=json.dumps({"label": trait_key}, ensure_ascii=False),
                )
                existing_index[lookup_key] = trait
            else:
                current_score = float(trait.trait_score or 1.0)
                trait.trait_score = min(current_score + 0.1, 10.0)
                trait.source = source
                trait.last_observed_at = observed_at
                trait.trait_value = json.dumps({"label": trait_key}, ensure_ascii=False)

            db.add(trait)


def parse_extraction_result(raw_text: str) -> ExtendedProfileExtractionResult:
    payload = _load_json_payload(raw_text)
    if isinstance(payload.get("profile"), dict):
        payload = payload["profile"]

    normalized_payload: dict[str, list[str]] = {}
    for field in PROFILE_FIELDS:
        raw_value = payload.get(field, []) if isinstance(payload, dict) else []
        normalized_payload[field] = _normalize_value_to_list(raw_value)

    return ExtendedProfileExtractionResult(**normalized_payload)


def refresh_profile_from_chat_history(
    db: Session,
    user_id: int,
) -> tuple[UserExtendedProfile, ExtendedProfileExtractionResult]:
    if not settings.PROFILE_EXTRACTION_ENABLED:
        raise ValueError("Profile extraction is disabled")

    messages = list_recent_messages_for_user(
        db,
        user_id=user_id,
        limit=settings.PROFILE_EXTRACTION_MESSAGE_WINDOW,
    )
    if not messages:
        raise ValueError("No chat history available for extraction")

    from app.services import chat_service

    prompt = build_extraction_input(messages)
    raw_output = chat_service.build_profile_extraction_response(prompt)
    extraction = parse_extraction_result(raw_output)
    profile = apply_extraction_result_for_user(db, user_id=user_id, result=extraction)
    return profile, extraction


def list_recent_messages_for_session(db: Session, session_id: int, limit: int) -> list[ChatMessage]:
    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
        .limit(max(limit, 1))
        .all()
    )
    messages.reverse()
    return messages


def list_recent_messages_for_user(db: Session, user_id: int, limit: int) -> list[ChatMessage]:
    messages = (
        db.query(ChatMessage)
        .join(ChatSession, ChatSession.id == ChatMessage.session_id)
        .filter(ChatSession.user_id == user_id)
        .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
        .limit(max(limit, 1))
        .all()
    )
    messages.reverse()
    return messages


def build_extraction_input(messages: list[ChatMessage]) -> str:
    lines: list[str] = []
    for message in messages:
        role = message.role.value if isinstance(message.role, MessageRole) else str(message.role)
        text = (message.content or "").strip()
        if not text:
            continue
        speaker = "User" if role == MessageRole.USER.value else "Assistant"
        lines.append(f"{speaker}: {text}")

    return "\n".join(lines).strip()


def _normalize_value_to_list(value: object) -> list[str]:
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


def _load_json_payload(raw_text: str) -> dict[str, object]:
    text = (raw_text or "").strip()
    if not text:
        raise ValueError("AI extraction output is empty")

    try:
        loaded = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end <= start:
            raise ValueError("AI extraction output is not valid JSON")

        snippet = text[start : end + 1]
        try:
            loaded = json.loads(snippet)
        except json.JSONDecodeError as exc:
            raise ValueError("AI extraction output is not valid JSON") from exc

    if not isinstance(loaded, dict):
        raise ValueError("AI extraction output must be a JSON object")

    return loaded
