"""画像抽取调度：异步执行、降频门控与按需触发。"""

from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.ai_worker import submit_ai_task
from app.core.config import settings
from app.core.db_session import session_scope
from app.core.domain_events import DomainEventName
from app.core.event_bus import event_bus
from app.models.chat import ChatMessage, MessageRole
from app.models.profile import UserProfile
from app.schemas.profile import ProfileExtractionResult
from app.services import chat_service, profile_service

logger = logging.getLogger(__name__)

_PROFILE_SIGNAL_KEYWORDS = (
    "目标",
    "打算",
    "计划",
    "想学",
    "兴趣",
    "擅长",
    "技能",
    "专业",
    "习惯",
    "性格",
    "偏好",
    "喜欢",
    "讨厌",
    "考研",
    "就业",
    "实习",
    "证书",
    "我是",
    "我的",
    "goal",
    "skill",
    "major",
)

_SMALL_TALK_KEYWORDS = ("你好", "您好", "谢谢", "在吗", "早上好", "晚上好", "嗨", "hello", "hi")

_in_flight_lock = threading.Lock()
_in_flight_user_ids: set[int] = set()


@dataclass(frozen=True, slots=True)
class ProfileExtractionScheduleDecision:
    should_schedule: bool
    reason: str | None = None


def should_trigger_profile_extraction(user_message: str) -> bool:
    """根据用户消息判断是否可能含画像信号（避免纯寒暄误触发）。"""
    text = (user_message or "").strip()
    if not text:
        return False
    if _is_small_talk_only(text):
        return False
    if any(keyword in text for keyword in _PROFILE_SIGNAL_KEYWORDS):
        return True

    lower = text.lower()
    if any(keyword in lower for keyword in ("goal", "skill", "major")):
        return True

    min_chars = max(int(settings.PROFILE_EXTRACTION_MIN_USER_MESSAGE_CHARS), 1)
    return len(text) >= min_chars


def _is_small_talk_only(text: str) -> bool:
    normalized = re.sub(r"[\s\W_]+", "", text.strip().lower())
    if not normalized:
        return True

    remainder = normalized
    for keyword in _SMALL_TALK_KEYWORDS:
        remainder = remainder.replace(keyword.lower(), "")
    return len(remainder) < 2


def _minutes_since_last_extracted(last_extracted_at: datetime | None) -> float | None:
    if last_extracted_at is None:
        return None
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    reference = last_extracted_at
    if reference.tzinfo is not None:
        reference = reference.replace(tzinfo=None)
    return (now - reference).total_seconds() / 60.0


def passes_throttle(
    db: Session,
    user_id: int,
    *,
    last_extracted_at: datetime | None,
    force: bool,
) -> bool:
    if force:
        return True
    if last_extracted_at is None:
        return True

    user_turns = profile_service.count_user_messages_since(db, user_id, last_extracted_at)
    burst_threshold = max(int(settings.PROFILE_EXTRACTION_BURST_USER_TURNS), 1)
    if user_turns >= burst_threshold:
        return True

    min_interval = max(int(settings.PROFILE_EXTRACTION_MIN_INTERVAL_MINUTES), 0)
    minutes_since = _minutes_since_last_extracted(last_extracted_at)
    if minutes_since is not None and user_turns >= 1 and minutes_since >= min_interval:
        return True

    return False


def passes_on_demand(
    *,
    last_extracted_at: datetime | None,
    user_message: str | None,
    force: bool,
) -> bool:
    if force:
        return True
    if last_extracted_at is None:
        return True
    if not settings.PROFILE_EXTRACTION_ON_DEMAND_ENABLED:
        return True
    return should_trigger_profile_extraction(user_message or "")


def should_schedule_profile_extraction(
    db: Session,
    user_id: int,
    *,
    user_message: str | None,
    force: bool = False,
) -> ProfileExtractionScheduleDecision:
    if not settings.PROFILE_EXTRACTION_ENABLED:
        return ProfileExtractionScheduleDecision(False, "disabled")

    profile = profile_service.get_profile_for_user(db, user_id)
    last_extracted_at = profile.last_extracted_at if profile else None

    if not passes_throttle(db, user_id, last_extracted_at=last_extracted_at, force=force):
        return ProfileExtractionScheduleDecision(False, "throttled")

    if not passes_on_demand(
        last_extracted_at=last_extracted_at,
        user_message=user_message,
        force=force,
    ):
        return ProfileExtractionScheduleDecision(False, "on_demand")

    return ProfileExtractionScheduleDecision(True, None)


def _resolve_user_message_for_assistant(
    db: Session,
    *,
    session_id: int,
    assistant_message_id: int | None,
) -> str:
    if assistant_message_id is None:
        messages = profile_service.list_recent_messages_for_session(
            db,
            session_id=session_id,
            limit=settings.PROFILE_EXTRACTION_MESSAGE_WINDOW,
        )
        for message in reversed(messages):
            role = message.role.value if isinstance(message.role, MessageRole) else str(message.role)
            if role == MessageRole.USER.value:
                return (message.content or "").strip()
        return ""

    assistant = (
        db.query(ChatMessage)
        .filter(ChatMessage.id == assistant_message_id, ChatMessage.session_id == session_id)
        .first()
    )
    if assistant is None:
        return ""

    for message in (
        db.query(ChatMessage)
        .filter(
            ChatMessage.session_id == session_id,
            ChatMessage.id < assistant_message_id,
        )
        .order_by(ChatMessage.id.desc())
        .all()
    ):
        role = message.role.value if isinstance(message.role, MessageRole) else str(message.role)
        if role == MessageRole.USER.value:
            return (message.content or "").strip()

    return ""


def _release_in_flight(user_id: int) -> None:
    with _in_flight_lock:
        _in_flight_user_ids.discard(user_id)


def _try_acquire_in_flight(user_id: int) -> bool:
    with _in_flight_lock:
        if user_id in _in_flight_user_ids:
            return False
        _in_flight_user_ids.add(user_id)
        return True


def schedule_profile_extraction_from_chat(
    *,
    user_id: int,
    session_id: int,
    trace_id: str,
    assistant_message_id: int | None = None,
) -> ProfileExtractionScheduleDecision:
    with session_scope() as db:
        user_message = _resolve_user_message_for_assistant(
            db,
            session_id=session_id,
            assistant_message_id=assistant_message_id,
        )
        decision = should_schedule_profile_extraction(
            db,
            user_id,
            user_message=user_message,
            force=False,
        )

    if not decision.should_schedule:
        logger.info(
            "Skip profile extraction schedule user_id=%s session_id=%s reason=%s",
            user_id,
            session_id,
            decision.reason,
        )
        return decision

    if not _try_acquire_in_flight(user_id):
        logger.debug(
            "Skip profile extraction schedule user_id=%s session_id=%s reason=in_flight",
            user_id,
            session_id,
        )
        return ProfileExtractionScheduleDecision(False, "in_flight")

    submit_ai_task(
        run_profile_extraction_from_chat,
        user_id=user_id,
        session_id=session_id,
        trace_id=trace_id,
    )
    return ProfileExtractionScheduleDecision(True, None)


def run_profile_extraction_from_chat(
    *,
    user_id: int,
    session_id: int,
    trace_id: str,
) -> None:
    try:
        with session_scope() as db:
            messages = profile_service.list_recent_messages_for_session(
                db,
                session_id=session_id,
                limit=settings.PROFILE_EXTRACTION_MESSAGE_WINDOW,
            )
            extraction_input = profile_service.build_extraction_input(messages)

        if not extraction_input:
            return

        raw_result = chat_service.build_profile_extraction_response(extraction_input)
        extraction_result = profile_service.parse_extraction_result(raw_result)

        with session_scope() as db:
            profile = profile_service.apply_extraction_result_for_user(
                db,
                user_id=user_id,
                result=extraction_result,
            )
            profile_id = profile.id

        event_bus.publish(
            event_name=DomainEventName.ON_PROFILE_UPDATED.value,
            user_id=user_id,
            payload={
                "session_id": session_id,
                "profile_id": profile_id,
                "extracted": extraction_result.model_dump(),
            },
            trace_id=trace_id,
            fail_fast=False,
        )
    except Exception:
        logger.exception(
            "Profile extraction from chat failed user_id=%s session_id=%s trace_id=%s",
            user_id,
            session_id,
            trace_id,
        )
    finally:
        _release_in_flight(user_id)


def run_profile_extraction_for_user(
    db: Session,
    user_id: int,
    *,
    force: bool = False,
) -> tuple[UserProfile, ProfileExtractionResult]:
    if not settings.PROFILE_EXTRACTION_ENABLED:
        raise ValueError("画像抽取功能未启用")

    messages = profile_service.list_recent_messages_for_user(
        db,
        user_id=user_id,
        limit=settings.PROFILE_EXTRACTION_MESSAGE_WINDOW,
    )
    if not messages:
        raise ValueError("没有可用于抽取的聊天记录")

    user_message = ""
    for message in reversed(messages):
        role = message.role.value if isinstance(message.role, MessageRole) else str(message.role)
        if role == MessageRole.USER.value:
            user_message = (message.content or "").strip()
            break

    decision = should_schedule_profile_extraction(
        db,
        user_id,
        user_message=user_message,
        force=force,
    )
    if not force and not decision.should_schedule:
        raise ValueError(f"当前不满足画像抽取条件：{decision.reason or 'unknown'}")

    extraction_input = profile_service.build_extraction_input(messages)
    if not extraction_input:
        raise ValueError("没有可用于抽取的聊天记录")

    raw_output = chat_service.build_profile_extraction_response(extraction_input)
    extraction = profile_service.parse_extraction_result(raw_output)
    profile = profile_service.apply_extraction_result_for_user(db, user_id=user_id, result=extraction)

    session_id = messages[-1].session_id
    event_bus.publish(
        event_name=DomainEventName.ON_PROFILE_UPDATED.value,
        user_id=user_id,
        payload={
            "session_id": session_id,
            "profile_id": profile.id,
            "extracted": extraction.model_dump(),
            "source": "manual_refresh",
        },
        fail_fast=False,
    )
    return profile, extraction
