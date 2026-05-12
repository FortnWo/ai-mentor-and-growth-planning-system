from datetime import datetime, timezone
import json

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.chat import ChatMessage, ChatSession, MessageRole
from app.models.extended_profile import UserExtendedProfile
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

    db.commit()
    db.refresh(profile)
    return profile


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

    from app.services import ai_service

    prompt = build_extraction_input(messages)
    raw_output = ai_service.generate_profile_extraction(prompt)
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
