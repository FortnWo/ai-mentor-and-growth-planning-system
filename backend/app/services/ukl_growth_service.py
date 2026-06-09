from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.ukl_constants import REF_TYPE_RECORD, SLICE_TYPE_GROWTH_JOURNAL, SOURCE_MODULE_GROWTH
from app.models.growth_record import GrowthRecord
from app.schemas.ukl import GrowthJournalPayload
from app.services import ukl_service

logger = logging.getLogger(__name__)


def _fallback_narrative(record: GrowthRecord) -> str:
    if record.summary and str(record.summary).strip():
        return str(record.summary).strip()[:300]
    if record.content and str(record.content).strip():
        return str(record.content).strip()[:300]
    return f"记录了：{record.title}"


def ingest_growth_journal_for_record(db: Session, user_id: int, record_id: int) -> None:
    if not settings.UKL_ENABLED or not settings.GROWTH_JOURNAL_ENABLED:
        return

    try:
        record = (
            db.query(GrowthRecord)
            .filter(GrowthRecord.id == record_id, GrowthRecord.user_id == user_id)
            .first()
        )
        if not record or record.deleted_at is not None:
            return

        from app.services import ai_service

        input_text = (
            f"标题：{record.title}\n"
            f"类型：{record.record_type or 'manual'}\n"
            f"摘要：{record.summary or '（无）'}\n"
            f"内容：{record.content or '（无）'}\n"
            f"情绪：{record.emotion or '（无）'}"
        )
        try:
            narrative = ai_service.build_growth_journal_response(input_text).strip()
        except Exception:
            narrative = ""
        if not narrative:
            narrative = _fallback_narrative(record)

        occurred_at = record.occurred_at
        if isinstance(occurred_at, datetime) and occurred_at.tzinfo is not None:
            occurred_at = occurred_at.replace(tzinfo=None)

        ukl_service.ingest(
            db,
            user_id,
            slice_type=SLICE_TYPE_GROWTH_JOURNAL,
            source_module=SOURCE_MODULE_GROWTH,
            ref_type=REF_TYPE_RECORD,
            ref_id=record_id,
            payload=GrowthJournalPayload(
                record_id=record_id,
                title=record.title,
                narrative=narrative,
                record_type=record.record_type,
                occurred_at=occurred_at,
            ),
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("UKL growth_journal ingest failed user_id=%s record_id=%s", user_id, record_id)
