from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.ukl_constants import SCENE_FEEDBACK
from app.models.growth_record import GrowthRecord
from app.schemas.ukl import ContextBundle
from app.services import ukl_service


def build_legacy_weekly_summary_prompt(records: list[GrowthRecord]) -> str:
    parts: list[str] = []
    for record in records:
        parts.append(f"- {record.title}: {record.summary or ''}")
    prompt_body = "\n".join(parts) or "No notable entries this week."
    return (
        "You are a compassionate mentor. Given the user's weekly growth timeline below, "
        f"write a short encouraging weekly summary (2-4 sentences) focusing on progress and next small steps.\n{prompt_body}"
    )


def format_feedback_context_section(bundle: ContextBundle) -> str:
    lines: list[str] = ["[UKL 反馈上下文]"]
    for block in bundle.narrative_blocks:
        text = (block or "").strip()
        if text:
            lines.append(text)

    anchors = bundle.anchors or {}
    profile_fields = anchors.get("profile_fields") or {}
    if profile_fields:
        bits: list[str] = []
        for key in ("goals", "skills", "interests", "study_habits"):
            values = profile_fields.get(key) or []
            if values:
                bits.append(f"{key}={', '.join(str(v) for v in values)}")
        if bits:
            lines.append("用户画像：" + "；".join(bits))

    journals = anchors.get("growth_journals") or []
    if journals:
        lines.append("本周成长叙事：")
        for entry in journals[:12]:
            if isinstance(entry, dict) and entry.get("narrative"):
                lines.append(f"- {entry['narrative']}")

    execution_list = anchors.get("execution_feedback_list") or []
    for item in execution_list[:5]:
        if not isinstance(item, dict):
            continue
        gid = item.get("goal_id")
        total = item.get("total_items", 0)
        done = item.get("completed_items", 0)
        if total:
            lines.append(f"目标 {gid} 执行：完成 {done}/{total} 项。")

    breakdown_list = anchors.get("breakdown_summaries") or []
    for item in breakdown_list[:5]:
        if isinstance(item, dict) and item.get("summary"):
            lines.append(f"拆解摘要（goal {item.get('goal_id')}）：{item['summary']}")

    return "\n".join(lines)


def _format_record_anchors(records: list[GrowthRecord]) -> str:
    lines: list[str] = ["[当周成长记录（实体锚点）]"]
    if not records:
        lines.append("（本周暂无成长记录）")
        return "\n".join(lines)

    for record in records:
        record_date = record.record_date or (
            record.occurred_at.date().isoformat() if record.occurred_at else ""
        )
        lines.append(
            f"- id={record.id} type={record.record_type or 'manual'} "
            f"date={record_date} title={record.title}"
        )
    return "\n".join(lines)


def build_weekly_summary_prompt(
    db: Session,
    user_id: int,
    start_date: date,
    end_date: date,
) -> str:
    records = (
        db.query(GrowthRecord)
        .filter(
            GrowthRecord.user_id == user_id,
            GrowthRecord.deleted_at.is_(None),
            GrowthRecord.record_date >= start_date,
            GrowthRecord.record_date <= end_date,
        )
        .order_by(GrowthRecord.occurred_at.asc(), GrowthRecord.id.asc())
        .all()
    )

    if not settings.UKL_ENABLED:
        return build_legacy_weekly_summary_prompt(records)

    bundle = ukl_service.assemble_context(
        db,
        user_id,
        SCENE_FEEDBACK,
        start_date=start_date,
        end_date=end_date,
    )
    return "\n\n".join([format_feedback_context_section(bundle), _format_record_anchors(records)])
