from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.ukl_constants import SCENE_INSTANT_FEEDBACK
from app.services import ai_service, ukl_service

logger = logging.getLogger(__name__)

_FALLBACK_TEMPLATE = "恭喜达成「{title}」！这一步很不容易，继续保持节奏。"


def build_instant_feedback_summary(
    db: Session,
    user_id: int,
    *,
    goal_id: int,
    breakdown_id: int,
    title: str,
) -> str:
    if not settings.INSTANT_FEEDBACK_ENABLED:
        return _FALLBACK_TEMPLATE.format(title=title)

    try:
        bundle = ukl_service.assemble_context(
            db,
            user_id,
            SCENE_INSTANT_FEEDBACK,
            goal_id=goal_id,
            main_breakdown_id=breakdown_id,
        )
        context_text = "\n".join(block.strip() for block in bundle.narrative_blocks if block and block.strip())
        prompt = (
            f"里程碑节点：{title}\n"
            f"goal_id={goal_id} breakdown_id={breakdown_id}\n"
            f"上下文：\n{context_text or '（无额外上下文）'}"
        )
        generated = ai_service.build_instant_feedback_response(prompt).strip()
        if generated:
            return generated
    except Exception:
        logger.exception(
            "Instant feedback generation failed user_id=%s breakdown_id=%s",
            user_id,
            breakdown_id,
        )
    return _FALLBACK_TEMPLATE.format(title=title)
