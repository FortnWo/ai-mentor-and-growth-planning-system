from datetime import datetime, date, timedelta

from sqlalchemy.orm import Session
from sqlalchemy import case, func

from app.models.growth_record import GrowthRecord, GrowthRecordSource, GrowthRecordType
from app.services import chat_service
from sqlalchemy.exc import SQLAlchemyError


def _as_date(value: date | str | None) -> date:
    if isinstance(value, date):
        return value
    if value is None:
        raise ValueError("record_date 为必填项")
    return date.fromisoformat(str(value))


def _effective_record_date_expr():
    """Calendar day used for analytics when record_date is missing."""
    return func.coalesce(
        GrowthRecord.record_date,
        func.date(GrowthRecord.occurred_at),
        func.date(GrowthRecord.created_at),
    )


def _apply_effective_date_range(q, start_date: str | None, end_date: str | None):
    effective = _effective_record_date_expr()
    if start_date:
        q = q.filter(effective >= _as_date(start_date))
    if end_date:
        q = q.filter(effective <= _as_date(end_date))
    return q


def _apply_aggregate_delta(db: Session, user_id: int, record: GrowthRecord, *, sign: int) -> None:
    from app.models.growth_aggregate import GrowthDailyAggregate

    try:
        agg_date = _as_date(record.record_date) if record.record_date else date.today()
    except Exception:
        agg_date = date.today()

    existing = (
        db.query(GrowthDailyAggregate)
        .filter(GrowthDailyAggregate.user_id == user_id, GrowthDailyAggregate.record_date == agg_date)
        .with_for_update(nowait=False)
        .first()
    )

    delta_completed = sign * (1 if record.record_type == GrowthRecordType.ACTION_PLAN.value else 0)
    delta_milestone = sign * (1 if record.record_type == GrowthRecordType.MILESTONE.value else 0)
    delta_reflection = sign * (1 if record.record_type == GrowthRecordType.MANUAL.value else 0)
    delta_score = sign * int(record.score or 0)

    if existing:
        existing.completed_count = max(0, (existing.completed_count or 0) + delta_completed)
        existing.milestone_count = max(0, (existing.milestone_count or 0) + delta_milestone)
        existing.reflection_count = max(0, (existing.reflection_count or 0) + delta_reflection)
        existing.growth_score = max(0, (existing.growth_score or 0) + delta_score)
        db.add(existing)
    elif sign > 0:
        db.add(
            GrowthDailyAggregate(
                user_id=user_id,
                record_date=agg_date,
                completed_count=max(0, delta_completed),
                milestone_count=max(0, delta_milestone),
                reflection_count=max(0, delta_reflection),
                growth_score=max(0, delta_score),
            )
        )


def create_growth_record(
    db: Session,
    user_id: int,
    *,
    title: str,
    summary: str | None = None,
    content: str | None = None,
    record_type: str | None = None,
    source_type: str | None = None,
    source_ref_id: int | None = None,
    occurred_at: datetime | None = None,
    record_date: str | None = None,
    emotion: str | None = None,
    score: int | None = None,
    idempotency_key: str | None = None,
    commit: bool = True,
    refresh: bool = True,
) -> GrowthRecord:
    resolved_occurred_at = occurred_at
    if resolved_occurred_at is None and idempotency_key:
        resolved_occurred_at = datetime.utcnow()

    if record_date is not None:
        resolved_record_date = _as_date(record_date)
    else:
        # 与聚合表、前端图表使用同一本地日历日，避免 UTC occurred_at 与 date.today() 跨日不一致
        resolved_record_date = date.today()

    # idempotency: refresh timestamps on active rows; restore soft-deleted rows
    if idempotency_key:
        existing = (
            db.query(GrowthRecord)
            .filter(GrowthRecord.user_id == user_id, GrowthRecord.idempotency_key == idempotency_key)
            .first()
        )
        if existing:
            was_deleted = existing.deleted_at is not None
            if was_deleted:
                existing.deleted_at = None
            existing.title = title
            if summary is not None:
                existing.summary = summary
            if content is not None:
                existing.content = content
            existing.record_type = record_type or existing.record_type
            existing.source_type = source_type or existing.source_type
            if source_ref_id is not None:
                existing.source_ref_id = source_ref_id
            if emotion is not None:
                existing.emotion = emotion
            if score is not None:
                existing.score = score
            if resolved_occurred_at is not None:
                existing.occurred_at = resolved_occurred_at
                existing.record_date = resolved_record_date
            db.add(existing)
            db.flush()
            if was_deleted:
                _apply_aggregate_delta(db, user_id, existing, sign=1)
            if commit:
                db.commit()
            if refresh:
                db.refresh(existing)
            return existing

    record = GrowthRecord(
        user_id=user_id,
        title=title,
        summary=summary,
        content=content,
        record_type=(record_type or GrowthRecordType.MANUAL.value),
        source_type=(source_type or GrowthRecordSource.MANUAL.value),
        source_ref_id=source_ref_id,
        occurred_at=resolved_occurred_at,
        record_date=resolved_record_date,
        emotion=emotion,
        score=score,
        idempotency_key=idempotency_key,
    )

    db.add(record)
    db.flush()

    try:
        _apply_aggregate_delta(db, user_id, record, sign=1)
    except Exception:
        pass

    if commit:
        db.commit()
    if refresh:
        db.refresh(record)
    return record


def void_growth_record_by_idempotency_key(
    db: Session,
    user_id: int,
    idempotency_key: str,
    *,
    commit: bool = True,
) -> bool:
    """Soft-delete a growth record by idempotency key and reverse its daily aggregate deltas."""
    from datetime import datetime, timezone

    rec = (
        db.query(GrowthRecord)
        .filter(
            GrowthRecord.user_id == user_id,
            GrowthRecord.idempotency_key == idempotency_key,
            GrowthRecord.deleted_at.is_(None),
        )
        .first()
    )
    if not rec:
        return False

    rec.deleted_at = datetime.now(timezone.utc)
    db.add(rec)

    try:
        _apply_aggregate_delta(db, user_id, rec, sign=-1)
    except Exception:
        pass

    if commit:
        db.commit()
    return True


def list_growth_records(
    db: Session,
    user_id: int,
    *,
    limit: int = 20,
    offset: int = 0,
    start_date: str | None = None,
    end_date: str | None = None,
    record_type: str | None = None,
    source_type: str | None = None,
):
    q = db.query(GrowthRecord).filter(GrowthRecord.user_id == user_id, GrowthRecord.deleted_at.is_(None))
    if start_date:
        q = q.filter(GrowthRecord.record_date >= _as_date(start_date))
    if end_date:
        q = q.filter(GrowthRecord.record_date <= _as_date(end_date))
    if record_type:
        q = q.filter(GrowthRecord.record_type == record_type)
    if source_type:
        q = q.filter(GrowthRecord.source_type == source_type)

    total = q.count()
    effective_time = func.coalesce(
        GrowthRecord.occurred_at,
        GrowthRecord.updated_at,
        GrowthRecord.created_at,
    )
    items = (
        q.order_by(effective_time.desc(), GrowthRecord.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return total, items


def get_growth_record(db: Session, user_id: int, record_id: int) -> GrowthRecord | None:
    return db.query(GrowthRecord).filter(GrowthRecord.user_id == user_id, GrowthRecord.id == record_id, GrowthRecord.deleted_at.is_(None)).first()


def process_record_summary_background(record_id: int) -> None:
    # Background worker to generate ai_summary and sentiment using LLM (best-effort)
    from app.core.db_session import session_scope

    prompt: str | None = None
    record_summary: str | None = None

    with session_scope() as db:
        record = db.query(GrowthRecord).filter(GrowthRecord.id == record_id).first()
        if not record:
            return
        record_summary = record.summary
        prompt = (
            f"Summarize the following user growth record in one concise sentence and return JSON with keys 'summary' and 'sentiment' (one of positive, neutral, negative).\\n"
            f"Content:\nTitle: {record.title}\nSummary: {record.summary or ''}\nContent: {record.content or ''}"
        )

    ai_summary_text = None
    sentiment = None
    try:
        response = chat_service.build_ai_response(prompt)
        import json

        text = response.strip()
        try:
            payload = json.loads(text)
            ai_summary_text = payload.get("summary") if isinstance(payload, dict) else None
            sentiment = payload.get("sentiment") if isinstance(payload, dict) else None
        except Exception:
            ai_summary_text = text
    except Exception:
        ai_summary_text = None

    if not sentiment:
        stext = (ai_summary_text or record_summary or "").lower()
        if any(w in stext for w in ["good", "great", "progress", "completed", "done", "happy", "proud", "yay"]):
            sentiment = "positive"
        elif any(w in stext for w in ["not", "failed", "bad", "sad", "missed"]):
            sentiment = "negative"
        else:
            sentiment = "neutral"

    try:
        with session_scope() as db:
            record = db.query(GrowthRecord).filter(GrowthRecord.id == record_id).first()
            if not record:
                return
            record.ai_summary = ai_summary_text
            record.emotion = sentiment
            db.add(record)
    except SQLAlchemyError:
        pass


def _stats_from_raw_records(
    db: Session,
    user_id: int,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    base = db.query(GrowthRecord).filter(GrowthRecord.user_id == user_id, GrowthRecord.deleted_at.is_(None))
    q = _apply_effective_date_range(base, start_date, end_date)

    completed_count = q.filter(GrowthRecord.record_type == GrowthRecordType.ACTION_PLAN.value).count()
    milestone_count = q.filter(GrowthRecord.record_type == GrowthRecordType.MILESTONE.value).count()
    reflection_count = q.filter(GrowthRecord.record_type == GrowthRecordType.MANUAL.value).count()

    activity_q = db.query(GrowthRecord).filter(GrowthRecord.user_id == user_id, GrowthRecord.deleted_at.is_(None))
    activity_q = _apply_effective_date_range(activity_q, start_date, end_date)
    last_activity = activity_q.with_entities(func.max(GrowthRecord.created_at)).scalar()
    growth_score = (
        activity_q.with_entities(func.coalesce(func.sum(GrowthRecord.score), 0)).scalar() or 0
    )

    consecutive_days = 0
    try:
        effective = _effective_record_date_expr()
        dates = [
            r[0]
            for r in db.query(effective)
            .filter(GrowthRecord.user_id == user_id, GrowthRecord.deleted_at.is_(None))
            .distinct()
            .order_by(effective.desc())
            .limit(30)
            .all()
        ]
        from datetime import datetime

        if dates:
            today = datetime.utcnow().date()
            streak = 0
            for d in dates:
                if not d:
                    continue
                try:
                    od = _as_date(d)
                except Exception:
                    continue
                if od == today - timedelta(days=streak):
                    streak += 1
                else:
                    break
            consecutive_days = streak
    except Exception:
        consecutive_days = 0

    return {
        "completed_count": int(completed_count or 0),
        "reflection_count": int(reflection_count or 0),
        "milestone_count": int(milestone_count or 0),
        "consecutive_days": int(consecutive_days),
        "growth_score": int(growth_score),
        "last_activity_at": last_activity,
    }


def _has_raw_records_in_range(
    db: Session,
    user_id: int,
    start_date: str | None,
    end_date: str | None,
) -> bool:
    q = db.query(GrowthRecord.id).filter(GrowthRecord.user_id == user_id, GrowthRecord.deleted_at.is_(None))
    q = _apply_effective_date_range(q, start_date, end_date)
    return q.limit(1).first() is not None


def stats_for_user(db: Session, user_id: int, start_date: str | None = None, end_date: str | None = None) -> dict:
    # Prefer aggregated daily table when available for performance
    try:
        from app.models.growth_aggregate import GrowthDailyAggregate

        agg_q = db.query(GrowthDailyAggregate).filter(GrowthDailyAggregate.user_id == user_id)
        if start_date:
            agg_q = agg_q.filter(GrowthDailyAggregate.record_date >= _as_date(start_date))
        if end_date:
            agg_q = agg_q.filter(GrowthDailyAggregate.record_date <= _as_date(end_date))

        rows = agg_q.all()
        completed_count = sum((r.completed_count or 0) for r in rows)
        reflection_count = sum((r.reflection_count or 0) for r in rows)
        milestone_count = sum((r.milestone_count or 0) for r in rows)
        growth_score = sum((r.growth_score or 0) for r in rows)

        agg_total = completed_count + reflection_count + milestone_count + growth_score
        if agg_total == 0 and _has_raw_records_in_range(db, user_id, start_date, end_date):
            return _stats_from_raw_records(db, user_id, start_date, end_date)

        last_activity = db.query(func.max(GrowthRecord.created_at)).filter(GrowthRecord.user_id == user_id, GrowthRecord.deleted_at.is_(None)).scalar()

        # consecutive_days: count consecutive recent dates present in aggregate
        consecutive_days = 0
        try:
            dates = [r.record_date for r in db.query(GrowthDailyAggregate.record_date).filter(GrowthDailyAggregate.user_id == user_id).distinct().order_by(GrowthDailyAggregate.record_date.desc()).limit(30).all()]
            from datetime import datetime

            if dates:
                today = datetime.utcnow().date()
                streak = 0
                for d in dates:
                    if isinstance(d, str):
                        od = datetime.fromisoformat(d).date()
                    else:
                        od = d
                    if od == today - timedelta(days=streak):
                        streak += 1
                    else:
                        break
                consecutive_days = streak
        except Exception:
            consecutive_days = 0

        return {
            "completed_count": int(completed_count or 0),
            "reflection_count": int(reflection_count or 0),
            "milestone_count": int(milestone_count or 0),
            "consecutive_days": int(consecutive_days),
            "growth_score": int(growth_score),
            "last_activity_at": last_activity,
        }
    except Exception:
        return _stats_from_raw_records(db, user_id, start_date, end_date)


def daily_trend_for_user(db: Session, user_id: int, start_date: str, end_date: str) -> list[dict]:
    """Return one row per calendar day in [start_date, end_date] for charting."""
    sd = _as_date(start_date)
    ed = _as_date(end_date)
    if sd > ed:
        return []

    from app.models.growth_aggregate import GrowthDailyAggregate

    by_date: dict[str, dict] = {}

    agg_rows = (
        db.query(GrowthDailyAggregate)
        .filter(
            GrowthDailyAggregate.user_id == user_id,
            GrowthDailyAggregate.record_date >= sd,
            GrowthDailyAggregate.record_date <= ed,
        )
        .order_by(GrowthDailyAggregate.record_date.asc())
        .all()
    )
    for r in agg_rows:
        k = r.record_date.isoformat() if hasattr(r.record_date, "isoformat") else str(r.record_date)
        by_date[k] = {
            "record_date": k,
            "completed_count": int(r.completed_count or 0),
            "reflection_count": int(r.reflection_count or 0),
            "milestone_count": int(r.milestone_count or 0),
            "growth_score": int(r.growth_score or 0),
        }

    ap = GrowthRecordType.ACTION_PLAN.value
    mn = GrowthRecordType.MANUAL.value
    ms = GrowthRecordType.MILESTONE.value
    effective = _effective_record_date_expr()

    grouped = (
        db.query(
            effective.label("effective_date"),
            func.sum(case((GrowthRecord.record_type == ap, 1), else_=0)).label("completed_sum"),
            func.sum(case((GrowthRecord.record_type == mn, 1), else_=0)).label("reflection_sum"),
            func.sum(case((GrowthRecord.record_type == ms, 1), else_=0)).label("milestone_sum"),
            func.coalesce(func.sum(GrowthRecord.score), 0).label("score_sum"),
        )
        .filter(
            GrowthRecord.user_id == user_id,
            GrowthRecord.deleted_at.is_(None),
            effective >= sd,
            effective <= ed,
        )
        .group_by(effective)
        .all()
    )
    _trend_fields = ("completed_count", "reflection_count", "milestone_count", "growth_score")
    for row in grouped:
        raw_key = row[0]
        if not raw_key:
            continue
        k = raw_key if isinstance(raw_key, str) else raw_key.isoformat()
        raw = {
            "record_date": k,
            "completed_count": int(row.completed_sum or 0),
            "reflection_count": int(row.reflection_sum or 0),
            "milestone_count": int(row.milestone_sum or 0),
            "growth_score": int(row.score_sum or 0),
        }
        if k not in by_date:
            by_date[k] = raw
        else:
            for field in _trend_fields:
                by_date[k][field] = max(by_date[k][field], raw[field])

    out: list[dict] = []
    cur = sd
    while cur <= ed:
        k = cur.isoformat()
        out.append(
            by_date.get(
                k,
                {
                    "record_date": k,
                    "completed_count": 0,
                    "reflection_count": 0,
                    "milestone_count": 0,
                    "growth_score": 0,
                },
            )
        )
        cur += timedelta(days=1)
    return out
