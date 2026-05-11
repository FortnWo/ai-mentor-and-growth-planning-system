from datetime import date, datetime
from pydantic import BaseModel, ConfigDict


class GrowthSummaryCreate(BaseModel):
    start_date: date
    end_date: date


class GrowthSummaryRead(BaseModel):
    id: int
    user_id: int
    start_date: date
    end_date: date
    summary: str | None = None
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
