from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.ukl_constants import (
    REF_TYPE_GOAL,
    REF_TYPE_USER,
    SLICE_TYPE_EPISODIC_NARRATIVE,
    SLICE_TYPE_GOAL_INTENT,
    SOURCE_MODULE_NARRATIVE,
)
from app.models.chat_session_summary import ChatSessionSummary
from app.models.goal import Goal
from app.schemas.ukl import EpisodicNarrativePayload, GoalIntentPayload
from app.services import ukl_service

logger = logging.getLogger(__name__)

_EPISODIC_SESSION_LIMIT = 8


def ingest_episodic_narrative_for_user(db: Session, user_id: int) -> None:
    if not settings.UKL_ENABLED or not settings.EPISODIC_NARRATIVE_ENABLED:
        return

    try:
        summaries = (
            db.query(ChatSessionSummary)
            .filter(ChatSessionSummary.user_id == user_id)
            .order_by(ChatSessionSummary.updated_at.desc(), ChatSessionSummary.id.desc())
            .limit(_EPISODIC_SESSION_LIMIT)
            .all()
        )
        session_texts = [s.summary.strip() for s in summaries if s.summary and s.summary.strip()]
        if not session_texts:
            return

        prior_raw = ukl_service.get_latest_slice(
            db,
            user_id,
            SLICE_TYPE_EPISODIC_NARRATIVE,
            ref_type=REF_TYPE_USER,
            ref_id=user_id,
        )
        prior_text = ""
        if prior_raw and prior_raw.payload:
            import json

            try:
                loaded = json.loads(prior_raw.payload)
                prior_text = str(loaded.get("summary") or "").strip()
            except json.JSONDecodeError:
                prior_text = ""

        merged_input = "\n\n".join(
            [
                f"已有跨会话叙事：\n{prior_text}" if prior_text else "",
                "近期会话摘要：\n" + "\n---\n".join(reversed(session_texts)),
            ]
        ).strip()

        summary = "\n".join(session_texts[:3])
        try:
            from app.services import ai_service

            generated = ai_service.build_episodic_narrative_response(merged_input).strip()
            if generated:
                summary = generated
        except Exception:
            logger.exception("Episodic narrative LLM failed user_id=%s", user_id)

        ukl_service.ingest(
            db,
            user_id,
            slice_type=SLICE_TYPE_EPISODIC_NARRATIVE,
            source_module=SOURCE_MODULE_NARRATIVE,
            ref_type=REF_TYPE_USER,
            ref_id=user_id,
            payload=EpisodicNarrativePayload(
                summary=summary,
                updated_at=datetime.utcnow(),
            ),
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Episodic narrative ingest failed user_id=%s", user_id)


def ingest_goal_intent_for_goal(db: Session, user_id: int, goal_id: int) -> None:
    if not settings.UKL_ENABLED or not settings.GOAL_INTENT_ENABLED:
        return

    try:
        goal = db.query(Goal).filter(Goal.id == goal_id, Goal.user_id == user_id).first()
        if not goal:
            return

        summary = f"用户希望达成：{goal.title}"
        if goal.description and str(goal.description).strip():
            summary = f"{summary}。{str(goal.description).strip()[:200]}"

        try:
            from app.services import ai_service

            prompt = f"目标标题：{goal.title}\n目标描述：{goal.description or '（无）'}"
            generated = ai_service.build_goal_intent_response(prompt).strip()
            if generated:
                summary = generated
        except Exception:
            logger.exception("Goal intent LLM failed goal_id=%s", goal_id)

        ukl_service.ingest(
            db,
            user_id,
            slice_type=SLICE_TYPE_GOAL_INTENT,
            source_module=SOURCE_MODULE_NARRATIVE,
            ref_type=REF_TYPE_GOAL,
            ref_id=goal_id,
            payload=GoalIntentPayload(goal_id=goal_id, summary=summary, intent=summary),
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Goal intent ingest failed user_id=%s goal_id=%s", user_id, goal_id)
