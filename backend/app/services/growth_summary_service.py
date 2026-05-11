from datetime import date
from sqlalchemy.orm import Session
from app.models.growth_summary import GrowthSummary
from app.models.growth_record import GrowthRecord
from app.services import chat_service


def create_weekly_summary(db: Session, user_id: int, start_date: date, end_date: date) -> GrowthSummary:
    # build a short narrative from recent records and request an AI to create a warm weekly summary
    records = (
        db.query(GrowthRecord)
        .filter(GrowthRecord.user_id == user_id, GrowthRecord.deleted_at.is_(None), GrowthRecord.record_date >= start_date.isoformat(), GrowthRecord.record_date <= end_date.isoformat())
        .order_by(GrowthRecord.occurred_at.asc())
        .all()
    )

    parts = []
    for r in records:
        parts.append(f"- {r.title}: {r.summary or ''}")

    prompt_body = "\n".join(parts) or "No notable entries this week."
    prompt = (
        f"You are a compassionate mentor. Given the user's weekly growth timeline below, write a short encouraging weekly summary (2-4 sentences) focusing on progress and next small steps.\\n{prompt_body}"
    )

    summary_text = None
    try:
        summary_text = chat_service.build_ai_response(prompt)
    except Exception:
        summary_text = "Good week — keep going! Try to record small steps regularly."

    summary = GrowthSummary(user_id=user_id, start_date=start_date, end_date=end_date, summary=summary_text)
    db.add(summary)
    db.commit()
    db.refresh(summary)
    return summary
