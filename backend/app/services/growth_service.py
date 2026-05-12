from sqlalchemy.orm import Session

from app.models.growth_record import GrowthRecord
from app.models.growth_summary import GrowthSummary
import app.services.growth_record_service as growth_record_service
import app.services.growth_summary_service as growth_summary_service


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
    occurred_at=None,
    record_date: str | None = None,
    emotion: str | None = None,
    score: int | None = None,
    idempotency_key: str | None = None,
) -> GrowthRecord:
    return growth_record_service.create_growth_record(
        db,
        user_id,
        title=title,
        summary=summary,
        content=content,
        record_type=record_type,
        source_type=source_type,
        source_ref_id=source_ref_id,
        occurred_at=occurred_at,
        record_date=record_date,
        emotion=emotion,
        score=score,
        idempotency_key=idempotency_key,
    )


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
    return growth_record_service.list_growth_records(
        db,
        user_id,
        limit=limit,
        offset=offset,
        record_type=record_type,
        start_date=start_date,
        end_date=end_date,
        source_type=source_type,
    )


def get_growth_record(db: Session, user_id: int, record_id: int) -> GrowthRecord | None:
    return growth_record_service.get_growth_record(db, user_id, record_id)


def get_growth_stats(
    db: Session,
    user_id: int,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
):
    return growth_record_service.stats_for_user(db, user_id, start_date=start_date, end_date=end_date)


def create_weekly_summary(db: Session, user_id: int, start_date, end_date) -> GrowthSummary:
    return growth_summary_service.create_weekly_summary(db, user_id, start_date, end_date)


def process_record_summary_background(record_id: int) -> None:
    growth_record_service.process_record_summary_background(record_id)

