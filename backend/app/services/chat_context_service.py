"""聊天注意力链：Tier1 会话摘要 + UKL 画像/叙事 + Tier2 事实记忆。

为每条用户消息拼装送入 LLM 的上下文块；消息落库后异步触发摘要更新与事实抽取。
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.ai_worker import submit_ai_task
from app.core.config import settings
from app.core.db_session import session_scope
from app.core.ukl_constants import PROFILE_FIELD_NAMES, SCENE_CHAT
from app.models.chat import ChatMessage, MessageRole
from app.models.chat_session_summary import ChatSessionSummary
from app.services import ai_service, profile_service, ukl_memory_fact_service, ukl_service

logger = logging.getLogger(__name__)

_PROFILE_SECTION_HEADER = "[用户画像]"
_EPISODIC_SECTION_HEADER = "[跨会话记忆]"
_MEMORY_FACT_SECTION_HEADER = "[相关事实记忆]"
_SESSION_SUMMARY_HEADER = "[本会话Earlier摘要]"


def should_trigger_tier2_retrieval(query: str) -> bool:
    return ukl_memory_fact_service.should_trigger_tier2_retrieval(query)


def should_include_episodic_extra(query: str) -> bool:
    return should_trigger_tier2_retrieval(query)


def _role_to_value(role: MessageRole | str) -> str:
    return role.value if hasattr(role, "value") else str(role)


def _is_pending_assistant(message: ChatMessage) -> bool:
    role = _role_to_value(message.role)
    if role != MessageRole.ASSISTANT.value:
        return False
    return not (message.content or "").strip()


def list_session_messages(db: Session, session_id: int) -> list[ChatMessage]:
    return (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
        .all()
    )


def filter_completed_messages(messages: list[ChatMessage]) -> list[ChatMessage]:
    return [m for m in messages if not _is_pending_assistant(m)]


def format_dialogue_lines(messages: list[ChatMessage]) -> list[str]:
    lines: list[str] = []
    for message in messages:
        role = _role_to_value(message.role)
        content = (message.content or "").strip()
        if not content:
            continue
        if role == MessageRole.USER.value:
            lines.append(f"用户: {content}")
        elif role == MessageRole.ASSISTANT.value:
            lines.append(f"助手: {content}")
    return lines


def build_legacy_chat_context(
    db: Session,
    *,
    session_id: int,
    current_user_message: str,
) -> str:
    """Full session history + current message (UKL disabled path)."""
    messages = filter_completed_messages(list_session_messages(db, session_id))
    lines = format_dialogue_lines(messages)
    current = current_user_message.strip()
    if not lines or (lines and not lines[-1].startswith(f"用户: {current}")):
        if current:
            lines.append(f"用户: {current}")
    return "\n".join(lines) if lines else current


def _schedule_lazy_profile_ingest(user_id: int) -> None:
    def _run() -> None:
        try:
            with session_scope() as db:
                ukl_service.ingest_profile_from_user(db, user_id)
        except Exception:
            logger.exception("UKL lazy profile ingest failed user_id=%s", user_id)

    submit_ai_task(_run)


def _build_profile_section(
    db: Session,
    user_id: int,
    *,
    current_user_message: str = "",
) -> str | None:
    bundle = ukl_service.assemble_context(
        db,
        user_id,
        SCENE_CHAT,
        query=current_user_message,
    )
    narrative = "\n".join(block.strip() for block in bundle.narrative_blocks if block and block.strip()).strip()

    sections: list[str] = []
    if narrative:
        sections.append(f"{_PROFILE_SECTION_HEADER}\n{narrative}")

    episodic = bundle.anchors.get("episodic_narrative")
    episodic_text = ""
    if isinstance(episodic, dict):
        episodic_text = str(episodic.get("summary") or "").strip()
    if episodic_text and should_include_episodic_extra(current_user_message):
        sections.append(f"{_EPISODIC_SECTION_HEADER}\n{episodic_text}")

    memory_facts = bundle.anchors.get("memory_facts")
    if isinstance(memory_facts, list) and memory_facts:
        fact_lines = [
            f"- {str(item.get('fact') or '').strip()}"
            for item in memory_facts
            if isinstance(item, dict) and str(item.get("fact") or "").strip()
        ]
        if fact_lines:
            sections.append(f"{_MEMORY_FACT_SECTION_HEADER}\n" + "\n".join(fact_lines))

    if sections:
        return "\n\n".join(sections)

    profile = profile_service.get_or_create_profile_for_user(db, user_id)
    fallback_parts: list[str] = []
    snapshot = (profile.portrait_summary or "").strip()
    if snapshot:
        fallback_parts.append(snapshot)

    field_bits: list[str] = []
    for name in PROFILE_FIELD_NAMES:
        values = getattr(profile, name, []) or []
        if values:
            field_bits.append(f"{name}: {', '.join(values[:6])}")
    if field_bits:
        fallback_parts.append("; ".join(field_bits))

    if not fallback_parts:
        _schedule_lazy_profile_ingest(user_id)
        return None

    _schedule_lazy_profile_ingest(user_id)
    return f"{_PROFILE_SECTION_HEADER}\n" + "\n".join(fallback_parts)


def _get_session_summary_row(db: Session, session_id: int) -> ChatSessionSummary | None:
    return db.query(ChatSessionSummary).filter(ChatSessionSummary.session_id == session_id).first()


def build_chat_context(
    db: Session,
    *,
    user_id: int,
    session_id: int,
    current_user_message: str,
) -> str:
    if not settings.UKL_ENABLED:
        return build_legacy_chat_context(
            db,
            session_id=session_id,
            current_user_message=current_user_message,
        )

    sections: list[str] = []

    profile_section = _build_profile_section(
        db, user_id, current_user_message=current_user_message
    )
    if profile_section:
        sections.append(profile_section)

    completed = filter_completed_messages(list_session_messages(db, session_id))
    total_count = len(completed)
    work_memory_limit = max(int(settings.CHAT_WORK_MEMORY_MAX_MESSAGES), 1)
    threshold = max(int(settings.CHAT_SUMMARY_USE_THRESHOLD), work_memory_limit + 1)
    summary_row = _get_session_summary_row(db, session_id)
    summary_text = (summary_row.summary or "").strip() if summary_row else ""

    use_summary = total_count > threshold and bool(summary_text)
    if use_summary:
        sections.append(f"{_SESSION_SUMMARY_HEADER}\n{summary_text}")

    if total_count <= threshold:
        dialogue_messages = completed
    else:
        dialogue_messages = completed[-work_memory_limit:]

    dialogue_lines = format_dialogue_lines(dialogue_messages)
    current = current_user_message.strip()
    if current and (not dialogue_lines or not dialogue_lines[-1].startswith(f"用户: {current}")):
        dialogue_lines.append(f"用户: {current}")

    if dialogue_lines:
        sections.append("\n".join(dialogue_lines))

    if sections:
        return "\n\n".join(sections)
    return current


def update_session_summary(db: Session, *, session_id: int, user_id: int) -> ChatSessionSummary | None:
    if not settings.UKL_ENABLED or not settings.CHAT_SESSION_SUMMARY_ENABLED:
        return None

    completed = filter_completed_messages(list_session_messages(db, session_id))
    work_memory_limit = max(int(settings.CHAT_WORK_MEMORY_MAX_MESSAGES), 1)
    threshold = max(int(settings.CHAT_SUMMARY_USE_THRESHOLD), work_memory_limit + 1)

    if len(completed) <= threshold:
        return None

    archive_cutoff = len(completed) - work_memory_limit
    archive_candidates = completed[:archive_cutoff]
    if not archive_candidates:
        return None

    existing = _get_session_summary_row(db, session_id)
    last_summarized_id = existing.summarized_through_message_id if existing else None
    new_messages = [m for m in archive_candidates if last_summarized_id is None or m.id > last_summarized_id]
    if not new_messages:
        return existing

    new_dialogue = "\n".join(format_dialogue_lines(new_messages)).strip()
    if not new_dialogue:
        return existing

    prior = (existing.summary or "").strip() if existing else None
    last_id = new_messages[-1].id
    total_archived = len(archive_candidates)

    merged_summary = ai_service.build_session_summary_response(
        prior,
        new_dialogue,
        user_id=user_id,
    ).strip()
    if not merged_summary:
        return existing

    if existing:
        existing.summary = merged_summary
        existing.summarized_through_message_id = last_id
        existing.message_count = total_archived
        db.add(existing)
        db.flush()
        _schedule_episodic_narrative_ingest(user_id)
        return existing

    row = ChatSessionSummary(
        session_id=session_id,
        user_id=user_id,
        summary=merged_summary,
        summarized_through_message_id=last_id,
        message_count=total_archived,
    )
    db.add(row)
    db.flush()
    _schedule_episodic_narrative_ingest(user_id)
    return row


def _schedule_episodic_narrative_ingest(user_id: int) -> None:
    if not settings.UKL_ENABLED or not settings.EPISODIC_NARRATIVE_ENABLED:
        return

    def _run() -> None:
        from app.services import ukl_narrative_service

        try:
            with session_scope() as db:
                ukl_narrative_service.ingest_episodic_narrative_for_user(db, user_id)
        except Exception:
            logger.exception("Episodic narrative ingest failed user_id=%s", user_id)

    submit_ai_task(_run)


def _run_memory_fact_extraction(
    *,
    user_id: int,
    session_id: int,
    assistant_message_id: int,
) -> None:
    if not settings.UKL_ENABLED or not settings.MEMORY_FACT_ENABLED:
        return
    if not settings.MEMORY_FACT_EXTRACTION_ENABLED:
        return

    try:
        with session_scope() as db:
            messages = filter_completed_messages(list_session_messages(db, session_id))
            assistant = next((m for m in messages if m.id == assistant_message_id), None)
            if assistant is None:
                return

            assistant_text = (assistant.content or "").strip()
            user_text = ""
            for message in reversed(messages):
                if message.id >= assistant_message_id:
                    continue
                role = _role_to_value(message.role)
                if role == MessageRole.USER.value:
                    user_text = (message.content or "").strip()
                    break

            summary_row = _get_session_summary_row(db, session_id)
            session_summary = (summary_row.summary or "").strip() if summary_row else None

            count = ukl_memory_fact_service.extract_and_ingest_facts_for_turn(
                db,
                user_id=user_id,
                session_id=session_id,
                message_id=assistant_message_id,
                user_message=user_text,
                assistant_message=assistant_text,
                session_summary=session_summary,
            )
            if count:
                logger.info(
                    "Memory facts ingested user_id=%s session_id=%s message_id=%s count=%s",
                    user_id,
                    session_id,
                    assistant_message_id,
                    count,
                )
    except Exception:
        logger.exception(
            "Memory fact extraction failed user_id=%s session_id=%s message_id=%s",
            user_id,
            session_id,
            assistant_message_id,
        )


def schedule_memory_fact_extraction(
    *,
    user_id: int,
    session_id: int,
    assistant_message_id: int,
) -> None:
    if not settings.UKL_ENABLED or not settings.MEMORY_FACT_ENABLED:
        return
    if not settings.MEMORY_FACT_EXTRACTION_ENABLED:
        return

    submit_ai_task(
        _run_memory_fact_extraction,
        user_id=user_id,
        session_id=session_id,
        assistant_message_id=assistant_message_id,
    )


def schedule_session_summary_update(session_id: int, user_id: int) -> None:
    if not settings.UKL_ENABLED or not settings.CHAT_SESSION_SUMMARY_ENABLED:
        return

    def _run() -> None:
        try:
            with session_scope() as db:
                update_session_summary(db, session_id=session_id, user_id=user_id)
        except Exception:
            logger.exception("Session summary update failed session_id=%s", session_id)

    submit_ai_task(_run)
