from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.domain_events import DomainEventName
from app.core.event_bus import event_bus
from app.core.ukl_constants import (
    REF_TYPE_USER,
    SLICE_TYPE_GROWTH_PATTERN,
    SLICE_TYPE_WEEKLY_NARRATIVE,
    SOURCE_MODULE_PATTERN,
)
from app.models.growth_record import GrowthRecord, GrowthRecordType
from app.schemas.ukl import GrowthPatternPayload, WeeklyNarrativePayload
from app.services import ukl_service

logger = logging.getLogger(__name__)


def _week_bounds(reference: date | None = None) -> tuple[date, date]:
    ref = reference or date.today()
    start = ref - timedelta(days=ref.weekday())
    end = start + timedelta(days=6)
    return start, end


def _count_week_checkins(db: Session, user_id: int, week_start: date, week_end: date) -> int:
    return (
        db.query(GrowthRecord)
        .filter(
            GrowthRecord.user_id == user_id,
            GrowthRecord.deleted_at.is_(None),
            GrowthRecord.record_date >= week_start,
            GrowthRecord.record_date <= week_end,
        )
        .count()
    )


def _list_period_records(
    db: Session,
    user_id: int,
    period_start: date,
    period_end: date,
) -> list[GrowthRecord]:
    return (
        db.query(GrowthRecord)
        .filter(
            GrowthRecord.user_id == user_id,
            GrowthRecord.deleted_at.is_(None),
            GrowthRecord.record_date >= period_start,
            GrowthRecord.record_date <= period_end,
        )
        .order_by(GrowthRecord.occurred_at.asc(), GrowthRecord.id.asc())
        .all()
    )


def should_refresh_growth_pattern(db: Session, user_id: int) -> bool:
    if not settings.UKL_ENABLED or not settings.GROWTH_PATTERN_ENABLED:
        return False

    week_start, week_end = _week_bounds()
    checkin_count = _count_week_checkins(db, user_id, week_start, week_end)
    if checkin_count >= settings.GROWTH_PATTERN_CHECKIN_THRESHOLD:
        return True

    existing = ukl_service.get_latest_slice(
        db,
        user_id,
        SLICE_TYPE_GROWTH_PATTERN,
        ref_type=REF_TYPE_USER,
        ref_id=user_id,
    )
    if existing is None:
        return checkin_count > 0

    updated_at = existing.updated_at or existing.created_at
    if updated_at is None:
        return True
    min_days = max(int(settings.GROWTH_PATTERN_MIN_DAYS), 1)
    return (datetime.utcnow() - updated_at).days >= min_days


def _build_pattern_input(records: list[GrowthRecord]) -> str:
    lines: list[str] = []
    for record in records:
        lines.append(
            f"- [{record.record_type}] {record.title}: {record.summary or record.content or ''}"
        )
    return "\n".join(lines) if lines else "（暂无成长记录）"


def _fallback_pattern_payload(
    records: list[GrowthRecord],
    period_start: date,
    period_end: date,
) -> GrowthPatternPayload:
    checkin_count = len(records)
    reflection_count = sum(
        1 for r in records if r.record_type in (GrowthRecordType.MANUAL.value, GrowthRecordType.MILESTONE.value)
    )
    return GrowthPatternPayload(
        themes=["坚持执行"] if checkin_count else [],
        emotion_trend="平稳",
        checkin_count=checkin_count,
        reflection_count=reflection_count,
        period_start=period_start.isoformat(),
        period_end=period_end.isoformat(),
        narrative=f"本期共 {checkin_count} 条成长记录，保持持续记录的习惯。",
    )


def refresh_growth_pattern_for_user(
    db: Session,
    user_id: int,
    *,
    period_start: date | None = None,
    period_end: date | None = None,
    force: bool = False,
) -> GrowthPatternPayload | None:
    if not settings.UKL_ENABLED or not settings.GROWTH_PATTERN_ENABLED:
        return None
    if not force and not should_refresh_growth_pattern(db, user_id):
        return None

    if period_start is None or period_end is None:
        period_start, period_end = _week_bounds()

    records = _list_period_records(db, user_id, period_start, period_end)
    payload = _fallback_pattern_payload(records, period_start, period_end)

    try:
        from app.services import ai_service

        input_text = _build_pattern_input(records)
        generated = ai_service.build_growth_pattern_response(
            f"统计区间：{period_start} 至 {period_end}\n记录条数：{len(records)}\n\n{input_text}"
        ).strip()
        if generated:
            payload.narrative = generated
            if "积极" in generated:
                payload.emotion_trend = "积极"
            elif "波动" in generated or "低落" in generated:
                payload.emotion_trend = "波动"
    except Exception:
        logger.exception("Growth pattern LLM failed user_id=%s", user_id)

    row = ukl_service.ingest(
        db,
        user_id,
        slice_type=SLICE_TYPE_GROWTH_PATTERN,
        source_module=SOURCE_MODULE_PATTERN,
        ref_type=REF_TYPE_USER,
        ref_id=user_id,
        payload=payload,
    )
    db.commit()

    event_bus.publish(
        event_name=DomainEventName.ON_GROWTH_PATTERN_UPDATED.value,
        user_id=user_id,
        payload={"pattern_version": row.version},
        fail_fast=False,
    )
    return payload


def ingest_weekly_narrative(
    db: Session,
    user_id: int,
    start: date,
    end: date,
    narrative: str,
) -> None:
    if not settings.UKL_ENABLED:
        return

    ukl_service.ingest(
        db,
        user_id,
        slice_type=SLICE_TYPE_WEEKLY_NARRATIVE,
        source_module=SOURCE_MODULE_PATTERN,
        ref_type=REF_TYPE_USER,
        ref_id=user_id,
        payload=WeeklyNarrativePayload(
            week_start=start.isoformat(),
            week_end=end.isoformat(),
            narrative=narrative.strip(),
        ),
    )
    db.commit()
