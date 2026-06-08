from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.ukl_constants import (
    PROFILE_FIELD_NAMES,
    REF_TYPE_USER,
    SCENE_CHAT,
    SLICE_TYPE_PROFILE,
    SOURCE_MODULE_PROFILE,
)
from app.models.ukl_slice import UklSlice
from app.schemas.profile import UserTraitRead
from app.schemas.ukl import ContextBundle, ProfileSlicePayload, TraitSnapshot
from app.services import profile_service, trait_service


def _serialize_payload(payload: dict[str, Any] | ProfileSlicePayload) -> str:
    if isinstance(payload, ProfileSlicePayload):
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
    payload: dict[str, Any] | ProfileSlicePayload,
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


def _assemble_chat_context(db: Session, user_id: int) -> ContextBundle:
    row = get_latest_slice(
        db,
        user_id,
        SLICE_TYPE_PROFILE,
        ref_type=REF_TYPE_USER,
        ref_id=user_id,
    )
    if row is None:
        return ContextBundle(scene=SCENE_CHAT)

    raw = _deserialize_payload(row.payload)
    try:
        payload = ProfileSlicePayload.model_validate(raw)
    except Exception:
        return ContextBundle(scene=SCENE_CHAT)

    narrative_blocks: list[str] = []
    snapshot = (payload.snapshot or "").strip()
    if snapshot:
        narrative_blocks.append(snapshot)

    anchors: dict[str, Any] = {
        "profile_fields": payload.fields,
        "traits": [t.model_dump() for t in payload.traits],
    }

    return ContextBundle(
        scene=SCENE_CHAT,
        narrative_blocks=narrative_blocks,
        anchors=anchors,
    )


def assemble_context(
    db: Session,
    user_id: int,
    scene: str,
    **kwargs: Any,
) -> ContextBundle:
    if scene == SCENE_CHAT:
        return _assemble_chat_context(db, user_id)
    raise ValueError(f"Unsupported UKL assemble scene: {scene}")
