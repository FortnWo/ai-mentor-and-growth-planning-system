from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ChatMessageRequest(BaseModel):
    session_id: Optional[int] = None
    message: str


class ChatMessageResponse(BaseModel):
    session_id: int
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}
