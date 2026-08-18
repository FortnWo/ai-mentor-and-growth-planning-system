from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class GrowthRecordCreate(BaseModel):
    title: str = Field(..., min_length=1)
    summary: str | None = None
    content: str | None = None
    record_type: str | None = Field(default="manual")
    source_type: str | None = Field(default="manual")
    source_ref_id: int | None = None
    occurred_at: datetime | None = None
    record_date: str | None = None
    emotion: str | None = None
    score: int | None = None
    idempotency_key: str | None = None



class GrowthRecordRead(BaseModel):
    id: int
    user_id: int
    title: str
    summary: str | None = None
    content: str | None = None
    record_type: str
    source_type: str
    source_ref_id: int | None = None
    occurred_at: datetime | None = None
    record_date: str | None = None
    emotion: str | None = None
    score: int | None = None
    ai_summary: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GrowthRecordListItem(BaseModel):
    id: int
    title: str
    summary: str | None = None
    record_date: str | None = None
    occurred_at: datetime | None = None
    record_type: str
    source_type: str

    model_config = ConfigDict(from_attributes=True)


class GrowthRecordStats(BaseModel):
    completed_count: int = 0
    reflection_count: int = 0
    milestone_count: int = 0
    consecutive_days: int = 0
    growth_score: int = 0
    last_activity_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class GrowthDailyTrendPoint(BaseModel):
    """One calendar day of rolled-up growth metrics for charts."""

    record_date: str
    completed_count: int = 0
    reflection_count: int = 0
    milestone_count: int = 0
    growth_score: int = 0

    model_config = ConfigDict(from_attributes=True)
