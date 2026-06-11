from datetime import datetime, timezone
import json
import logging

from sqlalchemy.orm import Session

from app.core.config import settings

logger = logging.getLogger(__name__)
from app.models.chat import ChatMessage, ChatSession, MessageRole
from app.models.profile import UserProfile
from app.models.user_trait import UserTrait
from app.schemas.profile import ProfileExtractionResult, ProfileInsightsRead, UserProfileUpdate, UserTraitRead
from app.services import trait_service

PROFILE_FIELDS = (
    "interests",
    "skills",
    "goals",
    "study_habits",
    "personality",
    "preferences",
)

TRAIT_TYPE_MAPPING = trait_service.TRAIT_TYPE_MAPPING


def get_profile_for_user(db: Session, user_id: int) -> UserProfile | None:
    return db.query(UserProfile).filter(UserProfile.user_id == user_id).first()


def get_or_create_profile_for_user(db: Session, user_id: int) -> UserProfile:
    profile = get_profile_for_user(db, user_id)
    if profile:
        return profile

    profile = UserProfile(user_id=user_id)
    for field in PROFILE_FIELDS:
        setattr(profile, field, [])

    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def update_profile_for_user(db: Session, user_id: int, profile_in: UserProfileUpdate) -> UserProfile:
    profile = get_or_create_profile_for_user(db, user_id)
    update_data = profile_in.model_dump(exclude_unset=True)

    for field in PROFILE_FIELDS:
        if field in update_data:
            setattr(profile, field, update_data[field] or [])

    _sync_traits_for_profile(db, user_id, profile, source="profile_update")
    db.commit()
    db.refresh(profile)
    refresh_portrait_summary_for_user(db, user_id)
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
    result: ProfileExtractionResult,
) -> UserProfile:
    profile = get_or_create_profile_for_user(db, user_id)

    for field in PROFILE_FIELDS:
        merged = merge_unique(getattr(profile, field), getattr(result, field))
        setattr(profile, field, merged)

    profile.last_extracted_at = datetime.now(timezone.utc).replace(tzinfo=None)
    _sync_traits_for_profile(db, user_id, profile, source="chat_extraction")

    db.commit()
    db.refresh(profile)
    refresh_portrait_summary_for_user(db, user_id)
    db.refresh(profile)
    return profile


def get_profile_insights_for_user(db: Session, user_id: int) -> ProfileInsightsRead:
    profile = get_or_create_profile_for_user(db, user_id)
    traits = trait_service.list_traits_for_user(db, user_id)

    if traits and not (profile.portrait_summary or "").strip():
        refresh_portrait_summary_for_user(db, user_id)
        db.refresh(profile)

    return ProfileInsightsRead(
        last_extracted_at=profile.last_extracted_at,
        portrait_summary=profile.portrait_summary,
        portrait_summary_at=profile.portrait_summary_at,
        traits=traits,
    )


def refresh_portrait_summary_for_user(db: Session, user_id: int) -> UserProfile:
    profile = get_or_create_profile_for_user(db, user_id)
    traits = trait_service.list_traits_for_user(db, user_id)

    if not traits:
        profile.portrait_summary = _build_template_portrait_summary(traits)
        profile.portrait_summary_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
        db.refresh(profile)
        return profile

    summary = _generate_portrait_summary(traits)
    profile.portrait_summary = summary
    profile.portrait_summary_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    db.refresh(profile)
    _maybe_sync_profile_to_ukl(db, user_id)
    return profile


def _maybe_sync_profile_to_ukl(db: Session, user_id: int) -> None:
    if not settings.UKL_ENABLED:
        return
    try:
        from app.services import ukl_service

        ukl_service.ingest_profile_from_user(db, user_id)
        db.commit()
    except Exception:
        logger.exception("UKL profile ingest failed user_id=%s", user_id)


def apply_growth_pattern_for_user(db: Session, user_id: int) -> None:
    if not settings.UKL_ENABLED or not settings.GROWTH_PATTERN_ENABLED:
        return

    try:
        from app.core.ukl_constants import REF_TYPE_USER, SLICE_TYPE_GROWTH_PATTERN
        from app.schemas.ukl import GrowthPatternPayload
        from app.services import ukl_service

        row = ukl_service.get_latest_slice(
            db,
            user_id,
            SLICE_TYPE_GROWTH_PATTERN,
            ref_type=REF_TYPE_USER,
            ref_id=user_id,
        )
        if row is None or not row.payload:
            return

        import json

        raw = json.loads(row.payload)
        pattern = GrowthPatternPayload.model_validate(raw)

        profile = get_or_create_profile_for_user(db, user_id)
        observed_at = datetime.now(timezone.utc).replace(tzinfo=None)

        if pattern.checkin_count >= settings.GROWTH_PATTERN_CHECKIN_THRESHOLD:
            _upsert_pattern_trait(
                db,
                user_id,
                trait_type="study_habit",
                trait_key="坚持打卡",
                source="growth_pattern",
                observed_at=observed_at,
            )
            habits = list(profile.study_habits or [])
            if "坚持打卡" not in habits:
                profile.study_habits = habits + ["坚持打卡"]

        if pattern.emotion_trend == "积极":
            _upsert_pattern_trait(
                db,
                user_id,
                trait_type="personality",
                trait_key="积极乐观",
                source="growth_pattern",
                observed_at=observed_at,
            )
            personality = list(profile.personality or [])
            if "积极乐观" not in personality:
                profile.personality = personality + ["积极乐观"]

        for theme in (pattern.themes or [])[:3]:
            theme_key = str(theme).strip()
            if not theme_key:
                continue
            _upsert_pattern_trait(
                db,
                user_id,
                trait_type="interest",
                trait_key=theme_key,
                source="growth_pattern",
                observed_at=observed_at,
            )

        db.add(profile)
        db.flush()
        refresh_portrait_summary_for_user(db, user_id)
    except Exception:
        logger.exception("Growth pattern profile reinforcement failed user_id=%s", user_id)


def _upsert_pattern_trait(
    db: Session,
    user_id: int,
    *,
    trait_type: str,
    trait_key: str,
    source: str,
    observed_at: datetime,
) -> None:
    trait = (
        db.query(UserTrait)
        .filter(
            UserTrait.user_id == user_id,
            UserTrait.trait_type == trait_type,
            UserTrait.trait_key == trait_key,
        )
        .first()
    )
    if trait is None:
        trait = UserTrait(
            user_id=user_id,
            trait_type=trait_type,
            trait_key=trait_key,
            trait_score=1.0,
            source=source,
            confidence=0.6,
            last_observed_at=observed_at,
            trait_value=json.dumps({"label": trait_key}, ensure_ascii=False),
        )
    else:
        current_score = float(trait.trait_score or 1.0)
        trait.trait_score = min(current_score + 0.05, 10.0)
        trait.source = source
        trait.confidence = min(float(trait.confidence or 0.6) + 0.05, 0.9)
        trait.last_observed_at = observed_at

    db.add(trait)


def _llm_summary_enabled() -> bool:
    from app.services import system_config_service as scs

    return scs.is_llm_configured()


def _generate_portrait_summary(traits: list[UserTraitRead]) -> str:
    if _llm_summary_enabled():
        payload = _build_traits_summary_input(traits)
        try:
            from app.services import ai_service

            generated = ai_service.build_portrait_summary_response(payload).strip()
            if generated:
                return generated
        except Exception:
            pass

    return _build_template_portrait_summary(traits)


def _build_traits_summary_input(traits: list[UserTraitRead]) -> str:
    grouped: dict[str, list[str]] = {}
    for trait in traits:
        label = trait_service.TRAIT_TYPE_LABELS.get(trait.trait_type, trait.trait_type)
        grouped.setdefault(label, []).append(trait.trait_key)

    lines: list[str] = []
    for trait_type in trait_service.TRAIT_TYPE_ORDER:
        label = trait_service.TRAIT_TYPE_LABELS.get(trait_type, trait_type)
        values = grouped.get(label, [])
        if values:
            lines.append(f"{label}: {', '.join(values[:8])}")

    return "\n".join(lines).strip()


def _build_template_portrait_summary(traits: list[UserTraitRead]) -> str:
    if not traits:
        return "尚未形成可描述的画像特质，建议多与 AI 导师交流或补充画像字段。"

    grouped: dict[str, list[str]] = {}
    for trait in traits:
        label = trait_service.TRAIT_TYPE_LABELS.get(trait.trait_type, trait.trait_type)
        grouped.setdefault(label, []).append(trait.trait_key)

    segments: list[str] = []
    for trait_type in trait_service.TRAIT_TYPE_ORDER:
        label = trait_service.TRAIT_TYPE_LABELS.get(trait_type, trait_type)
        values = grouped.get(label, [])
        if values:
            segments.append(f"在{label}方面关注 {', '.join(values[:5])}")

    if not segments:
        return "尚未形成可描述的画像特质，建议多与 AI 导师交流或补充画像字段。"

    return f"你{'，'.join(segments)}。"


def _sync_traits_for_profile(db: Session, user_id: int, profile: UserProfile, *, source: str) -> None:
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


def parse_extraction_result(raw_text: str) -> ProfileExtractionResult:
    payload = _load_json_payload(raw_text)
    if isinstance(payload.get("profile"), dict):
        payload = payload["profile"]

    normalized_payload: dict[str, list[str]] = {}
    for field in PROFILE_FIELDS:
        raw_value = payload.get(field, []) if isinstance(payload, dict) else []
        normalized_payload[field] = _normalize_value_to_list(raw_value)

    return ProfileExtractionResult(**normalized_payload)


def refresh_profile_from_chat_history(
    db: Session,
    user_id: int,
) -> tuple[UserProfile, ProfileExtractionResult]:
    if not settings.PROFILE_EXTRACTION_ENABLED:
        raise ValueError("画像抽取功能未启用")

    messages = list_recent_messages_for_user(
        db,
        user_id=user_id,
        limit=settings.PROFILE_EXTRACTION_MESSAGE_WINDOW,
    )
    if not messages:
        raise ValueError("没有可用于抽取的聊天记录")

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
        speaker = "用户" if role == MessageRole.USER.value else "助手"
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
        raise ValueError("AI 抽取输出为空")

    try:
        loaded = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end <= start:
            raise ValueError("AI 抽取输出不是有效的 JSON")

        snippet = text[start : end + 1]
        try:
            loaded = json.loads(snippet)
        except json.JSONDecodeError as exc:
            raise ValueError("AI 抽取输出不是有效的 JSON") from exc

    if not isinstance(loaded, dict):
        raise ValueError("AI 抽取输出必须是 JSON 对象")

    return loaded
