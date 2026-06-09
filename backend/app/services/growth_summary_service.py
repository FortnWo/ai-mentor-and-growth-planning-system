from datetime import date

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.growth_summary import GrowthSummary
from app.services import ai_service, chat_service, ukl_feedback_prompt_service


def create_weekly_summary(db: Session, user_id: int, start_date: date, end_date: date) -> GrowthSummary:
    if settings.UKL_ENABLED:
        prompt = ukl_feedback_prompt_service.build_weekly_summary_prompt(
            db, user_id, start_date, end_date
        )
        try:
            summary_text = ai_service.build_weekly_summary_response(prompt)
        except Exception:
            summary_text = "本周有进步，继续保持小步前进的节奏。"
    else:
        from app.models.growth_record import GrowthRecord

        records = (
            db.query(GrowthRecord)
            .filter(
                GrowthRecord.user_id == user_id,
                GrowthRecord.deleted_at.is_(None),
                GrowthRecord.record_date >= start_date,
                GrowthRecord.record_date <= end_date,
            )
            .order_by(GrowthRecord.occurred_at.asc())
            .all()
        )
        prompt = ukl_feedback_prompt_service.build_legacy_weekly_summary_prompt(records)
        try:
            summary_text = chat_service.build_ai_response(prompt)
        except Exception:
            summary_text = "Good week — keep going! Try to record small steps regularly."

    summary = GrowthSummary(user_id=user_id, start_date=start_date, end_date=end_date, summary=summary_text)
    db.add(summary)
    db.commit()
    db.refresh(summary)
    return summary


def get_latest_weekly_summary(db: Session, user_id: int, start_date: date, end_date: date) -> GrowthSummary | None:
    return (
        db.query(GrowthSummary)
        .filter(
            GrowthSummary.user_id == user_id,
            GrowthSummary.start_date == start_date,
            GrowthSummary.end_date == end_date,
        )
        .order_by(GrowthSummary.created_at.desc(), GrowthSummary.id.desc())
        .first()
    )
