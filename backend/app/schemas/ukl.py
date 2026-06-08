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


class ContextBundle(BaseModel):
    scene: str
    narrative_blocks: list[str] = Field(default_factory=list)
    anchors: dict[str, Any] = Field(default_factory=dict)
    token_budget_hint: int | None = None

    model_config = ConfigDict(from_attributes=True)
