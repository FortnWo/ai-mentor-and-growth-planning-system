from datetime import datetime, date

from sqlalchemy.orm import Session
from sqlalchemy import case, func

from app.models.growth_record import GrowthRecord, GrowthRecordSource, GrowthRecordType
from app.services import chat_service
from sqlalchemy.exc import SQLAlchemyError


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
    # idempotency: if idempotency_key provided, return existing record when present
    if idempotency_key:
        existing = (
            db.query(GrowthRecord)
            .filter(GrowthRecord.user_id == user_id, GrowthRecord.idempotency_key == idempotency_key)
            .first()
        )
        if existing:
            return existing

    record = GrowthRecord(
        user_id=user_id,
        title=title,
        summary=summary,
        content=content,
        record_type=(record_type or GrowthRecordType.MANUAL.value),
        source_type=(source_type or GrowthRecordSource.MANUAL.value),
        source_ref_id=source_ref_id,
        occurred_at=occurred_at,
        record_date=(record_date or (date.today().isoformat() if occurred_at is None else occurred_at.date().isoformat())),
        emotion=emotion,
        score=score,
        idempotency_key=idempotency_key,
    )

    db.add(record)
    db.flush()

    # Incremental update to daily aggregate in same transaction
    try:
        from app.models.growth_aggregate import GrowthDailyAggregate

        agg_date = None
        try:
            # record.record_date is YYYY-MM-DD string
            from datetime import datetime

            agg_date = datetime.fromisoformat(record.record_date).date()
        except Exception:
            from datetime import date as _date

            agg_date = _date.today()

        # try to fetch existing aggregate row
        existing = (
            db.query(GrowthDailyAggregate)
            .filter(GrowthDailyAggregate.user_id == user_id, GrowthDailyAggregate.record_date == agg_date)
            .with_for_update(nowait=False)
            .first()
        )

        delta_completed = 1 if (record.record_type == GrowthRecordType.ACTION_PLAN.value) else 0
        delta_milestone = 1 if (record.record_type == GrowthRecordType.MILESTONE.value) else 0
        delta_reflection = 1 if (record.record_type == GrowthRecordType.MANUAL.value) else 0
        delta_score = int(record.score or 0)

        if existing:
            existing.completed_count = (existing.completed_count or 0) + delta_completed
            existing.milestone_count = (existing.milestone_count or 0) + delta_milestone
            existing.reflection_count = (existing.reflection_count or 0) + delta_reflection
            existing.growth_score = (existing.growth_score or 0) + delta_score
            db.add(existing)
        else:
            db.add(
                GrowthDailyAggregate(
                    user_id=user_id,
                    record_date=agg_date,
                    completed_count=delta_completed,
                    milestone_count=delta_milestone,
                    reflection_count=delta_reflection,
                    growth_score=delta_score,
                )
            )
    except Exception:
        # non-fatal: avoid breaking creation on aggregation issues
        pass

    if commit:
        db.commit()
    if refresh:
        db.refresh(record)
    return record


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
        q = q.filter(GrowthRecord.record_date >= start_date)
    if end_date:
        q = q.filter(GrowthRecord.record_date <= end_date)
    if record_type:
        q = q.filter(GrowthRecord.record_type == record_type)
    if source_type:
        q = q.filter(GrowthRecord.source_type == source_type)

    total = q.count()
    # MySQL does not support NULLS LAST; emulate by ordering NULLs last explicitly.
    items = (
        q.order_by(
            GrowthRecord.occurred_at.is_(None).asc(),
            GrowthRecord.occurred_at.desc(),
            GrowthRecord.id.desc(),
        )
        .offset(offset)
        .limit(limit)
        .all()
    )
    return total, items


def get_growth_record(db: Session, user_id: int, record_id: int) -> GrowthRecord | None:
    return db.query(GrowthRecord).filter(GrowthRecord.user_id == user_id, GrowthRecord.id == record_id, GrowthRecord.deleted_at.is_(None)).first()


def process_record_summary_background(record_id: int) -> None:
    # Background worker to generate ai_summary and sentiment using LLM (best-effort)
    import app.core.database as database_module

    db = database_module.SessionLocal()
    try:
        record = db.query(GrowthRecord).filter(GrowthRecord.id == record_id).first()
        if not record:
            return

        # Build prompt asking the model to return a short summary and sentiment as JSON
        prompt = (
            f"Summarize the following user growth record in one concise sentence and return JSON with keys 'summary' and 'sentiment' (one of positive, neutral, negative).\\n"
            f"Content:\nTitle: {record.title}\nSummary: {record.summary or ''}\nContent: {record.content or ''}"
        )

        ai_summary_text = None
        sentiment = None
        try:
            response = chat_service.build_ai_response(prompt)
            # Try to parse JSON from response
            import json

            text = response.strip()
            try:
                payload = json.loads(text)
                ai_summary_text = payload.get("summary") if isinstance(payload, dict) else None
                sentiment = payload.get("sentiment") if isinstance(payload, dict) else None
            except Exception:
                # fallback: use whole response as summary and simple sentiment rules
                ai_summary_text = text
        except Exception:
            # LLM failed; leave ai_summary_text None
            ai_summary_text = None

        if not sentiment:
            # simple sentiment heuristic
            stext = (ai_summary_text or record.summary or "").lower()
            if any(w in stext for w in ["good", "great", "progress", "completed", "done", "happy", "proud", "yay"]):
                sentiment = "positive"
            elif any(w in stext for w in ["not", "failed", "bad", "sad", "missed"]):
                sentiment = "negative"
            else:
                sentiment = "neutral"

        # write back into record
        try:
            record.ai_summary = ai_summary_text
            record.emotion = sentiment
            db.add(record)
            db.commit()
        except SQLAlchemyError:
            db.rollback()
    finally:
        db.close()


def stats_for_user(db: Session, user_id: int, start_date: str | None = None, end_date: str | None = None) -> dict:
    # Prefer aggregated daily table when available for performance
    try:
        from app.models.growth_aggregate import GrowthDailyAggregate

        agg_q = db.query(GrowthDailyAggregate).filter(GrowthDailyAggregate.user_id == user_id)
        if start_date:
            agg_q = agg_q.filter(GrowthDailyAggregate.record_date >= start_date)
        if end_date:
            agg_q = agg_q.filter(GrowthDailyAggregate.record_date <= end_date)

        rows = agg_q.all()
        completed_count = sum((r.completed_count or 0) for r in rows)
        reflection_count = sum((r.reflection_count or 0) for r in rows)
        milestone_count = sum((r.milestone_count or 0) for r in rows)
        growth_score = sum((r.growth_score or 0) for r in rows)

        last_activity = db.query(func.max(GrowthRecord.created_at)).filter(GrowthRecord.user_id == user_id, GrowthRecord.deleted_at.is_(None)).scalar()

        # consecutive_days: count consecutive recent dates present in aggregate
        consecutive_days = 0
        try:
            dates = [r.record_date for r in db.query(GrowthDailyAggregate.record_date).filter(GrowthDailyAggregate.user_id == user_id).distinct().order_by(GrowthDailyAggregate.record_date.desc()).limit(30).all()]
            from datetime import datetime, timedelta

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
        # fallback to scanning raw records
        q = db.query(GrowthRecord).filter(GrowthRecord.user_id == user_id, GrowthRecord.deleted_at.is_(None))
        if start_date:
            q = q.filter(GrowthRecord.record_date >= start_date)
        if end_date:
            q = q.filter(GrowthRecord.record_date <= end_date)

        completed_count = q.filter(GrowthRecord.record_type == GrowthRecordType.ACTION_PLAN.value).count()
        milestone_count = q.filter(GrowthRecord.record_type == GrowthRecordType.MILESTONE.value).count()
        reflection_count = q.filter(GrowthRecord.record_type == GrowthRecordType.MANUAL.value).count()
        last_activity = db.query(func.max(GrowthRecord.created_at)).filter(GrowthRecord.user_id == user_id, GrowthRecord.deleted_at.is_(None)).scalar()
        growth_score = db.query(func.coalesce(func.sum(GrowthRecord.score), 0)).filter(GrowthRecord.user_id == user_id, GrowthRecord.deleted_at.is_(None)).scalar() or 0

        # consecutive_days fallback
        consecutive_days = 0
        try:
            dates = [r[0] for r in db.query(GrowthRecord.record_date).filter(GrowthRecord.user_id == user_id, GrowthRecord.deleted_at.is_(None)).distinct().order_by(GrowthRecord.record_date.desc()).limit(30).all()]
            from datetime import datetime, timedelta

            if dates:
                today = datetime.utcnow().date()
                streak = 0
                for d in dates:
                    try:
                        od = datetime.fromisoformat(d).date()
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


def daily_trend_for_user(db: Session, user_id: int, start_date: str, end_date: str) -> list[dict]:
    """Return one row per calendar day in [start_date, end_date] for charting.

    Prefers ``growth_daily_aggregates`` when present; fills gaps from grouped
    ``growth_records``. Missing days are zero-filled.
    """
    from datetime import datetime, timedelta

    sd = datetime.fromisoformat(start_date).date()
    ed = datetime.fromisoformat(end_date).date()
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

    grouped = (
        db.query(
            GrowthRecord.record_date,
            func.sum(case((GrowthRecord.record_type == ap, 1), else_=0)).label("completed_sum"),
            func.sum(case((GrowthRecord.record_type == mn, 1), else_=0)).label("reflection_sum"),
            func.sum(case((GrowthRecord.record_type == ms, 1), else_=0)).label("milestone_sum"),
            func.coalesce(func.sum(GrowthRecord.score), 0).label("score_sum"),
        )
        .filter(
            GrowthRecord.user_id == user_id,
            GrowthRecord.deleted_at.is_(None),
            GrowthRecord.record_date.isnot(None),
            GrowthRecord.record_date >= start_date,
            GrowthRecord.record_date <= end_date,
        )
        .group_by(GrowthRecord.record_date)
        .all()
    )
    for row in grouped:
        raw_key = row[0]
        if not raw_key:
            continue
        k = raw_key if isinstance(raw_key, str) else raw_key.isoformat()
        if k not in by_date:
            by_date[k] = {
                "record_date": k,
                "completed_count": int(row.completed_sum or 0),
                "reflection_count": int(row.reflection_sum or 0),
                "milestone_count": int(row.milestone_sum or 0),
                "growth_score": int(row.score_sum or 0),
            }

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
