from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class ActionPlanCreate(BaseModel):
    goal_id: int = Field(..., ge=1)


class ActionPlanRead(BaseModel):
    id: int
    goal_id: int
    title: str
    summary: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ActionPlanItemRead(BaseModel):
    id: int
    plan_id: int
    breakdown_id: int | None = None
    title: str
    description: str | None = None
    frequency: str
    schedule: str | None = None
    status: str
    start_date: date | None = None
    due_date: date | None = None
    sequence: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ActionPlanDetailRead(ActionPlanRead):
    items: list[ActionPlanItemRead] = Field(default_factory=list)