from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TraitSnapshot(BaseModel):
    trait_type: str
    trait_key: str
    trait_score: float = 1.0
    source: str | None = None
    confidence: float | None = None


class ProfileSlicePayload(BaseModel):
    fields: dict[str, list[str]] = Field(default_factory=dict)
    traits: list[TraitSnapshot] = Field(default_factory=list)
    snapshot: str | None = None
    snapshot_at: datetime | None = None


class BreakdownAnchorsPayload(BaseModel):
    goal_id: int
    critical_constraints: list[str] = Field(default_factory=list)
    dependency_notes: list[str] = Field(default_factory=list)
    capacity_hint: str | None = None


class BreakdownSummaryPayload(BaseModel):
    goal_id: int
    summary: str
    entity_updated_at: datetime | None = None


class WorkloadSnapshotPayload(BaseModel):
    active_goal_count: int = 0
    total_goal_count: int = 0
    active_plan_count: int = 0
    pending_item_count: int = 0
    in_progress_item_count: int = 0


class ExecutionFeedbackPayload(BaseModel):
    goal_id: int
    total_items: int = 0
    completed_items: int = 0
    completion_rate: float = 0.0
    by_breakdown_id: dict[str, dict[str, int]] = Field(default_factory=dict)


class GrowthJournalPayload(BaseModel):
    record_id: int
    title: str
    narrative: str
    record_type: str | None = None
    occurred_at: datetime | None = None


class FeedbackAnchorsPayload(BaseModel):
    goal_refs: list[int] = Field(default_factory=list)
    record_ids: list[int] = Field(default_factory=list)
    week_start: str | None = None
    week_end: str | None = None


class ContextBundle(BaseModel):
    scene: str
    narrative_blocks: list[str] = Field(default_factory=list)
    anchors: dict[str, Any] = Field(default_factory=dict)
    token_budget_hint: int | None = None

    model_config = ConfigDict(from_attributes=True)
