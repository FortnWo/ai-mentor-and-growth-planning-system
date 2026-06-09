from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.ukl_constants import (
    FEEDBACK_MAX_ACTIVE_GOALS,
    PROFILE_FIELD_NAMES,
    REF_TYPE_BREAKDOWN,
    REF_TYPE_GOAL,
    REF_TYPE_RECORD,
    REF_TYPE_USER,
    SCENE_ACTION_PLAN,
    SCENE_BREAKDOWN,
    SCENE_CHAT,
    SCENE_FEEDBACK,
    SCENE_INSTANT_FEEDBACK,
    SLICE_TYPE_BREAKDOWN_ANCHORS,
    SLICE_TYPE_BREAKDOWN_SUMMARY,
    SLICE_TYPE_EPISODIC_NARRATIVE,
    SLICE_TYPE_EXECUTION_FEEDBACK,
    SLICE_TYPE_GOAL_INTENT,
    SLICE_TYPE_GROWTH_JOURNAL,
    SLICE_TYPE_GROWTH_PATTERN,
    SLICE_TYPE_MILESTONE_ACHIEVEMENT,
    SLICE_TYPE_PROFILE,
    SLICE_TYPE_WEEKLY_NARRATIVE,
    SLICE_TYPE_WORKLOAD_SNAPSHOT,
    SOURCE_MODULE_PROFILE,
)
from app.models.goal import Goal, GoalStatus
from app.models.growth_record import GrowthRecord
from app.models.ukl_slice import UklSlice
from app.schemas.profile import UserTraitRead
from app.schemas.ukl import (
    BreakdownAnchorsPayload,
    BreakdownSummaryPayload,
    ContextBundle,
    EpisodicNarrativePayload,
    ExecutionFeedbackPayload,
    FeedbackAnchorsPayload,
    GrowthJournalPayload,
    GrowthPatternPayload,
    MilestoneAchievementPayload,
    ProfileSlicePayload,
    TraitSnapshot,
    WeeklyNarrativePayload,
    WorkloadSnapshotPayload,
)
from app.services import profile_service, trait_service, ukl_projection_service


def _serialize_payload(payload: dict[str, Any] | BaseModel) -> str:
    if isinstance(payload, BaseModel):
        data = payload.model_dump(mode="json")
    else:
        data = payload
    return json.dumps(data, ensure_ascii=False)


def _deserialize_payload(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def ingest(
    db: Session,
    user_id: int,
    *,
    slice_type: str,
    source_module: str,
    ref_type: str | None,
    ref_id: int | None,
    payload: dict[str, Any] | BaseModel,
) -> UklSlice:
    serialized = _serialize_payload(payload)
    existing = (
        db.query(UklSlice)
        .filter(
            UklSlice.user_id == user_id,
            UklSlice.slice_type == slice_type,
            UklSlice.ref_type == ref_type,
            UklSlice.ref_id == ref_id,
        )
        .first()
    )

    if existing:
        existing.source_module = source_module
        existing.payload = serialized
        existing.version = int(existing.version or 1) + 1
        db.add(existing)
        db.flush()
        return existing

    row = UklSlice(
        user_id=user_id,
        slice_type=slice_type,
        source_module=source_module,
        ref_type=ref_type,
        ref_id=ref_id,
        payload=serialized,
        version=1,
    )
    db.add(row)
    db.flush()
    return row


def get_latest_slice(
    db: Session,
    user_id: int,
    slice_type: str,
    *,
    ref_type: str | None = None,
    ref_id: int | None = None,
) -> UklSlice | None:
    return (
        db.query(UklSlice)
        .filter(
            UklSlice.user_id == user_id,
            UklSlice.slice_type == slice_type,
            UklSlice.ref_type == ref_type,
            UklSlice.ref_id == ref_id,
        )
        .order_by(UklSlice.updated_at.desc(), UklSlice.id.desc())
        .first()
    )


def _trait_to_snapshot(trait: UserTraitRead) -> TraitSnapshot:
    return TraitSnapshot(
        trait_type=trait.trait_type,
        trait_key=trait.trait_key,
        trait_score=float(trait.trait_score or 1.0),
        source=trait.source,
        confidence=trait.confidence,
    )


def build_profile_slice_payload(db: Session, user_id: int) -> ProfileSlicePayload:
    profile = profile_service.get_or_create_profile_for_user(db, user_id)
    traits = trait_service.list_traits_for_user(db, user_id)

    fields = {name: list(getattr(profile, name, []) or []) for name in PROFILE_FIELD_NAMES}
    snapshot_at = profile.portrait_summary_at
    if isinstance(snapshot_at, datetime) and snapshot_at.tzinfo is not None:
        snapshot_at = snapshot_at.replace(tzinfo=None)

    return ProfileSlicePayload(
        fields=fields,
        traits=[_trait_to_snapshot(t) for t in traits],
        snapshot=(profile.portrait_summary or None),
        snapshot_at=snapshot_at,
    )


def ingest_profile_from_user(db: Session, user_id: int) -> UklSlice:
    payload = build_profile_slice_payload(db, user_id)
    return ingest(
        db,
        user_id,
        slice_type=SLICE_TYPE_PROFILE,
        source_module=SOURCE_MODULE_PROFILE,
        ref_type=REF_TYPE_USER,
        ref_id=user_id,
        payload=payload,
    )


def _load_profile_slice_payload(db: Session, user_id: int, *, fallback_live: bool) -> ProfileSlicePayload | None:
    row = get_latest_slice(
        db,
        user_id,
        SLICE_TYPE_PROFILE,
        ref_type=REF_TYPE_USER,
        ref_id=user_id,
    )
    if row is None:
        if fallback_live:
            return build_profile_slice_payload(db, user_id)
        return None

    raw = _deserialize_payload(row.payload)
    try:
        return ProfileSlicePayload.model_validate(raw)
    except Exception:
        if fallback_live:
            return build_profile_slice_payload(db, user_id)
        return None


def _profile_to_anchors(payload: ProfileSlicePayload) -> dict[str, Any]:
    return {
        "profile_fields": payload.fields,
        "traits": [t.model_dump() for t in payload.traits],
    }


def _optional_slice_payload(
    db: Session,
    user_id: int,
    slice_type: str,
    *,
    ref_type: str | None,
    ref_id: int | None,
) -> dict[str, Any] | None:
    row = get_latest_slice(db, user_id, slice_type, ref_type=ref_type, ref_id=ref_id)
    if row is None:
        return None
    return _deserialize_payload(row.payload)


def _load_workload_snapshot(db: Session, user_id: int) -> WorkloadSnapshotPayload:
    raw = _optional_slice_payload(
        db,
        user_id,
        SLICE_TYPE_WORKLOAD_SNAPSHOT,
        ref_type=REF_TYPE_USER,
        ref_id=user_id,
    )
    if raw:
        try:
            return WorkloadSnapshotPayload.model_validate(raw)
        except Exception:
            pass
    return ukl_projection_service.compute_workload_snapshot(db, user_id)


def _load_execution_feedback(db: Session, user_id: int, goal_id: int) -> ExecutionFeedbackPayload:
    raw = _optional_slice_payload(
        db,
        user_id,
        SLICE_TYPE_EXECUTION_FEEDBACK,
        ref_type=REF_TYPE_GOAL,
        ref_id=goal_id,
    )
    if raw:
        try:
            return ExecutionFeedbackPayload.model_validate(raw)
        except Exception:
            pass
    return ukl_projection_service.compute_execution_feedback(db, user_id, goal_id)


def _list_active_goals(db: Session, user_id: int, *, limit: int = FEEDBACK_MAX_ACTIVE_GOALS) -> list[Goal]:
    return (
        db.query(Goal)
        .filter(Goal.user_id == user_id, Goal.status == GoalStatus.ACTIVE.value)
        .order_by(Goal.updated_at.desc(), Goal.id.desc())
        .limit(limit)
        .all()
    )


def _list_week_records(
    db: Session,
    user_id: int,
    start_date: date,
    end_date: date,
) -> list[GrowthRecord]:
    return (
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


def _load_growth_pattern_light(db: Session, user_id: int) -> GrowthPatternPayload | None:
    raw = _optional_slice_payload(
        db,
        user_id,
        SLICE_TYPE_GROWTH_PATTERN,
        ref_type=REF_TYPE_USER,
        ref_id=user_id,
    )
    if not raw:
        return None
    try:
        return GrowthPatternPayload.model_validate(raw)
    except Exception:
        return None


def _assemble_chat_context(db: Session, user_id: int, *, query: str | None = None) -> ContextBundle:
    payload = _load_profile_slice_payload(db, user_id, fallback_live=False)
    narrative_blocks: list[str] = []
    anchors: dict[str, Any] = {}

    if payload is not None:
        snapshot = (payload.snapshot or "").strip()
        if snapshot:
            narrative_blocks.append(snapshot)
        anchors = _profile_to_anchors(payload)

    episodic_raw = _optional_slice_payload(
        db,
        user_id,
        SLICE_TYPE_EPISODIC_NARRATIVE,
        ref_type=REF_TYPE_USER,
        ref_id=user_id,
    )
    if episodic_raw:
        try:
            episodic = EpisodicNarrativePayload.model_validate(episodic_raw)
            anchors["episodic_narrative"] = episodic.model_dump()
            if episodic.summary.strip():
                narrative_blocks.append(episodic.summary.strip())
        except Exception:
            anchors["episodic_narrative"] = episodic_raw

    pattern = _load_growth_pattern_light(db, user_id)
    if pattern:
        anchors["growth_pattern"] = pattern.model_dump()
        if pattern.narrative and pattern.narrative.strip():
            narrative_blocks.append(pattern.narrative.strip()[:200])

    if query and query.strip():
        from app.services import ukl_memory_fact_service

        if ukl_memory_fact_service.should_trigger_tier2_retrieval(query):
            memory_facts = ukl_memory_fact_service.search_memory_facts(db, user_id, query)
            if memory_facts:
                anchors["memory_facts"] = memory_facts

    return ContextBundle(
        scene=SCENE_CHAT,
        narrative_blocks=narrative_blocks,
        anchors=anchors,
    )


def _assemble_breakdown_context(
    db: Session,
    user_id: int,
    *,
    goal_id: int | None,
    is_refresh: bool,
) -> ContextBundle:
    if goal_id is None:
        raise ValueError("goal_id is required for breakdown scene")

    profile_payload = _load_profile_slice_payload(db, user_id, fallback_live=True)
    assert profile_payload is not None
    narrative_blocks: list[str] = []
    snapshot = (profile_payload.snapshot or "").strip()
    if snapshot:
        narrative_blocks.append(snapshot)

    anchors: dict[str, Any] = _profile_to_anchors(profile_payload)

    goal_intent = _optional_slice_payload(
        db,
        user_id,
        SLICE_TYPE_GOAL_INTENT,
        ref_type=REF_TYPE_GOAL,
        ref_id=goal_id,
    )
    if goal_intent:
        anchors["goal_intent"] = goal_intent
        intent_text = str(goal_intent.get("summary") or goal_intent.get("intent") or "").strip()
        if intent_text:
            narrative_blocks.append(intent_text)

    workload = _load_workload_snapshot(db, user_id)
    anchors["workload"] = workload.model_dump()

    if is_refresh:
        execution = _load_execution_feedback(db, user_id, goal_id)
        anchors["execution_feedback"] = execution.model_dump()
        if execution.total_items:
            narrative_blocks.append(
                f"执行反馈：已完成 {execution.completed_items}/{execution.total_items} 项行动计划"
                f"（完成率 {int(execution.completion_rate * 100)}%）。"
            )

    anchors["entity_hints"] = {"goal_id": goal_id}

    return ContextBundle(
        scene=SCENE_BREAKDOWN,
        narrative_blocks=narrative_blocks,
        anchors=anchors,
    )


def _assemble_action_plan_context(
    db: Session,
    user_id: int,
    *,
    goal_id: int | None,
    main_breakdown_id: int | None,
) -> ContextBundle:
    if goal_id is None or main_breakdown_id is None:
        raise ValueError("goal_id and main_breakdown_id are required for action_plan scene")

    profile_payload = _load_profile_slice_payload(db, user_id, fallback_live=True)
    assert profile_payload is not None
    narrative_blocks: list[str] = []
    snapshot = (profile_payload.snapshot or "").strip()
    if snapshot:
        narrative_blocks.append(snapshot)

    anchors: dict[str, Any] = _profile_to_anchors(profile_payload)

    breakdown_summary_raw = _optional_slice_payload(
        db,
        user_id,
        SLICE_TYPE_BREAKDOWN_SUMMARY,
        ref_type=REF_TYPE_GOAL,
        ref_id=goal_id,
    )
    if breakdown_summary_raw:
        try:
            summary_payload = BreakdownSummaryPayload.model_validate(breakdown_summary_raw)
            anchors["breakdown_summary"] = summary_payload.model_dump()
            if summary_payload.summary.strip():
                narrative_blocks.append(summary_payload.summary.strip())
        except Exception:
            anchors["breakdown_summary"] = breakdown_summary_raw

    breakdown_anchors_raw = _optional_slice_payload(
        db,
        user_id,
        SLICE_TYPE_BREAKDOWN_ANCHORS,
        ref_type=REF_TYPE_GOAL,
        ref_id=goal_id,
    )
    if breakdown_anchors_raw:
        try:
            anchors_payload = BreakdownAnchorsPayload.model_validate(breakdown_anchors_raw)
            anchors["breakdown_anchors"] = anchors_payload.model_dump()
            constraints = anchors_payload.critical_constraints
            if constraints:
                narrative_blocks.append("关键约束：" + "；".join(constraints))
        except Exception:
            anchors["breakdown_anchors"] = breakdown_anchors_raw

    workload = _load_workload_snapshot(db, user_id)
    anchors["workload"] = workload.model_dump()
    if workload.active_goal_count > 1:
        narrative_blocks.append(
            f"跨目标负载：并行活跃目标 {workload.active_goal_count} 个，"
            f"待办行动项 {workload.pending_item_count} 项。"
        )

    execution = _load_execution_feedback(db, user_id, goal_id)
    anchors["execution_feedback"] = execution.model_dump()
    if execution.total_items:
        narrative_blocks.append(
            f"本目标执行：已完成 {execution.completed_items}/{execution.total_items} 项。"
        )

    anchors["entity_hints"] = {"goal_id": goal_id, "main_breakdown_id": main_breakdown_id}

    return ContextBundle(
        scene=SCENE_ACTION_PLAN,
        narrative_blocks=narrative_blocks,
        anchors=anchors,
    )


def _assemble_feedback_context(
    db: Session,
    user_id: int,
    *,
    start_date: date | None,
    end_date: date | None,
    goal_id: int | None,
) -> ContextBundle:
    profile_payload = _load_profile_slice_payload(db, user_id, fallback_live=True)
    assert profile_payload is not None

    narrative_blocks: list[str] = []
    snapshot = (profile_payload.snapshot or "").strip()
    if snapshot:
        narrative_blocks.append(snapshot)

    anchors: dict[str, Any] = _profile_to_anchors(profile_payload)

    week_start = start_date or date.today()
    week_end = end_date or week_start
    records = _list_week_records(db, user_id, week_start, week_end)

    record_hints: list[dict[str, Any]] = []
    growth_journals: list[dict[str, Any]] = []
    for record in records:
        record_hints.append(
            {
                "id": record.id,
                "title": record.title,
                "record_type": record.record_type,
                "record_date": str(record.record_date) if record.record_date else None,
            }
        )
        journal_raw = _optional_slice_payload(
            db,
            user_id,
            SLICE_TYPE_GROWTH_JOURNAL,
            ref_type=REF_TYPE_RECORD,
            ref_id=record.id,
        )
        if journal_raw:
            try:
                journal = GrowthJournalPayload.model_validate(journal_raw)
                growth_journals.append(journal.model_dump())
                if journal.narrative.strip():
                    narrative_blocks.append(journal.narrative.strip())
            except Exception:
                growth_journals.append(journal_raw)

    anchors["growth_journals"] = growth_journals

    execution_list: list[dict[str, Any]] = []
    breakdown_summaries: list[dict[str, Any]] = []
    goal_refs: list[int] = []

    for goal in _list_active_goals(db, user_id):
        if goal_id is not None and goal.id != goal_id:
            continue
        goal_refs.append(goal.id)
        execution = _load_execution_feedback(db, user_id, goal.id)
        execution_list.append(execution.model_dump())
        if execution.total_items:
            narrative_blocks.append(
                f"目标「{goal.title}」执行：已完成 {execution.completed_items}/{execution.total_items} 项。"
            )

        breakdown_raw = _optional_slice_payload(
            db,
            user_id,
            SLICE_TYPE_BREAKDOWN_SUMMARY,
            ref_type=REF_TYPE_GOAL,
            ref_id=goal.id,
        )
        if breakdown_raw:
            try:
                summary_payload = BreakdownSummaryPayload.model_validate(breakdown_raw)
                breakdown_summaries.append(
                    {"goal_id": goal.id, "summary": summary_payload.summary}
                )
            except Exception:
                breakdown_summaries.append({"goal_id": goal.id, "summary": breakdown_raw.get("summary", "")})

        intent_raw = _optional_slice_payload(
            db,
            user_id,
            SLICE_TYPE_GOAL_INTENT,
            ref_type=REF_TYPE_GOAL,
            ref_id=goal.id,
        )
        if intent_raw:
            intent_text = str(intent_raw.get("summary") or intent_raw.get("intent") or "").strip()
            if intent_text:
                narrative_blocks.append(f"目标「{goal.title}」意图：{intent_text}")

    anchors["execution_feedback_list"] = execution_list
    anchors["breakdown_summaries"] = breakdown_summaries
    anchors["feedback_anchors"] = FeedbackAnchorsPayload(
        goal_refs=goal_refs,
        record_ids=[r.id for r in records],
        week_start=week_start.isoformat(),
        week_end=week_end.isoformat(),
    ).model_dump()

    workload = _load_workload_snapshot(db, user_id)
    anchors["workload"] = workload.model_dump()

    pattern = _load_growth_pattern_light(db, user_id)
    if pattern:
        anchors["growth_pattern"] = pattern.model_dump()
        if pattern.narrative and pattern.narrative.strip():
            narrative_blocks.append(pattern.narrative.strip())

    weekly_raw = _optional_slice_payload(
        db,
        user_id,
        SLICE_TYPE_WEEKLY_NARRATIVE,
        ref_type=REF_TYPE_USER,
        ref_id=user_id,
    )
    if weekly_raw:
        try:
            weekly = WeeklyNarrativePayload.model_validate(weekly_raw)
            anchors["weekly_narrative"] = weekly.model_dump()
            if weekly.narrative.strip():
                narrative_blocks.append(weekly.narrative.strip())
        except Exception:
            anchors["weekly_narrative"] = weekly_raw

    milestone_achievements: list[dict[str, Any]] = []
    for record in records:
        if record.record_type != "milestone" or not record.source_ref_id:
            continue
        mile_raw = _optional_slice_payload(
            db,
            user_id,
            SLICE_TYPE_MILESTONE_ACHIEVEMENT,
            ref_type=REF_TYPE_BREAKDOWN,
            ref_id=record.source_ref_id,
        )
        if mile_raw:
            try:
                mile = MilestoneAchievementPayload.model_validate(mile_raw)
                milestone_achievements.append(mile.model_dump())
                if mile.narrative.strip():
                    narrative_blocks.append(mile.narrative.strip())
            except Exception:
                milestone_achievements.append(mile_raw)
    if milestone_achievements:
        anchors["milestone_achievements"] = milestone_achievements

    anchors["entity_hints"] = {"records": record_hints}

    return ContextBundle(
        scene=SCENE_FEEDBACK,
        narrative_blocks=narrative_blocks,
        anchors=anchors,
    )


def _assemble_instant_feedback_context(
    db: Session,
    user_id: int,
    *,
    goal_id: int | None,
    main_breakdown_id: int | None,
) -> ContextBundle:
    profile_payload = _load_profile_slice_payload(db, user_id, fallback_live=True)
    narrative_blocks: list[str] = []
    anchors: dict[str, Any] = {}

    if profile_payload is not None:
        snapshot = (profile_payload.snapshot or "").strip()
        if snapshot:
            narrative_blocks.append(snapshot)
        anchors = _profile_to_anchors(profile_payload)

    if goal_id is not None:
        execution = _load_execution_feedback(db, user_id, goal_id)
        anchors["execution_feedback"] = execution.model_dump()
        if execution.total_items:
            narrative_blocks.append(
                f"本目标执行：已完成 {execution.completed_items}/{execution.total_items} 项。"
            )

    anchors["entity_hints"] = {
        "goal_id": goal_id,
        "breakdown_id": main_breakdown_id,
    }

    return ContextBundle(
        scene=SCENE_INSTANT_FEEDBACK,
        narrative_blocks=narrative_blocks,
        anchors=anchors,
    )


def assemble_context(
    db: Session,
    user_id: int,
    scene: str,
    *,
    goal_id: int | None = None,
    main_breakdown_id: int | None = None,
    is_refresh: bool = False,
    start_date: date | None = None,
    end_date: date | None = None,
    query: str | None = None,
    **kwargs: Any,
) -> ContextBundle:
    if scene == SCENE_CHAT:
        return _assemble_chat_context(db, user_id, query=query)
    if scene == SCENE_BREAKDOWN:
        return _assemble_breakdown_context(db, user_id, goal_id=goal_id, is_refresh=is_refresh)
    if scene == SCENE_ACTION_PLAN:
        return _assemble_action_plan_context(
            db,
            user_id,
            goal_id=goal_id,
            main_breakdown_id=main_breakdown_id,
        )
    if scene == SCENE_FEEDBACK:
        return _assemble_feedback_context(
            db,
            user_id,
            start_date=start_date,
            end_date=end_date,
            goal_id=goal_id,
        )
    if scene == SCENE_INSTANT_FEEDBACK:
        return _assemble_instant_feedback_context(
            db,
            user_id,
            goal_id=goal_id,
            main_breakdown_id=main_breakdown_id,
        )
    raise ValueError(f"Unsupported UKL assemble scene: {scene}")
