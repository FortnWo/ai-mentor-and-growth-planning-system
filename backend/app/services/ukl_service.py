from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.ukl_constants import (
    PROFILE_FIELD_NAMES,
    REF_TYPE_GOAL,
    REF_TYPE_USER,
    SCENE_ACTION_PLAN,
    SCENE_BREAKDOWN,
    SCENE_CHAT,
    SLICE_TYPE_BREAKDOWN_ANCHORS,
    SLICE_TYPE_BREAKDOWN_SUMMARY,
    SLICE_TYPE_GOAL_INTENT,
    SLICE_TYPE_PROFILE,
    SOURCE_MODULE_PROFILE,
)
from app.models.ukl_slice import UklSlice
from app.schemas.profile import UserTraitRead
from app.schemas.ukl import (
    BreakdownAnchorsPayload,
    BreakdownSummaryPayload,
    ContextBundle,
    ExecutionFeedbackPayload,
    ProfileSlicePayload,
    TraitSnapshot,
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


def _assemble_chat_context(db: Session, user_id: int) -> ContextBundle:
    payload = _load_profile_slice_payload(db, user_id, fallback_live=False)
    if payload is None:
        return ContextBundle(scene=SCENE_CHAT)

    narrative_blocks: list[str] = []
    snapshot = (payload.snapshot or "").strip()
    if snapshot:
        narrative_blocks.append(snapshot)

    return ContextBundle(
        scene=SCENE_CHAT,
        narrative_blocks=narrative_blocks,
        anchors=_profile_to_anchors(payload),
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

    workload = ukl_projection_service.compute_workload_snapshot(db, user_id)
    anchors["workload"] = workload.model_dump()

    if is_refresh:
        execution = ukl_projection_service.compute_execution_feedback_for_goal(db, user_id, goal_id)
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

    workload = ukl_projection_service.compute_workload_snapshot(db, user_id)
    anchors["workload"] = workload.model_dump()
    if workload.active_goal_count > 1:
        narrative_blocks.append(
            f"跨目标负载：并行活跃目标 {workload.active_goal_count} 个，"
            f"待办行动项 {workload.pending_item_count} 项。"
        )

    execution = ukl_projection_service.compute_execution_feedback(db, user_id, goal_id)
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


def assemble_context(
    db: Session,
    user_id: int,
    scene: str,
    *,
    goal_id: int | None = None,
    main_breakdown_id: int | None = None,
    is_refresh: bool = False,
    **kwargs: Any,
) -> ContextBundle:
    if scene == SCENE_CHAT:
        return _assemble_chat_context(db, user_id)
    if scene == SCENE_BREAKDOWN:
        return _assemble_breakdown_context(db, user_id, goal_id=goal_id, is_refresh=is_refresh)
    if scene == SCENE_ACTION_PLAN:
        return _assemble_action_plan_context(
            db,
            user_id,
            goal_id=goal_id,
            main_breakdown_id=main_breakdown_id,
        )
    raise ValueError(f"Unsupported UKL assemble scene: {scene}")
