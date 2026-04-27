from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


class MessageDeliveryStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class ChatSessionBase(BaseModel):
    title: str | None = Field(default=None, max_length=255)


class ChatSessionCreate(ChatSessionBase):
    user_id: int = Field(gt=0)


class ChatSessionRenameRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Session title cannot be empty")

        return normalized


class ChatSessionRead(ChatSessionBase):
    id: int
    user_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatMessageBase(BaseModel):
    role: MessageRole
    content: str = Field(min_length=1)


class ChatMessageCreate(ChatMessageBase):
    session_id: int = Field(gt=0)


class ChatMessageUpdate(BaseModel):
    content: str | None = Field(default=None, min_length=1)


class ChatMessageRead(ChatMessageBase):
    # Assistant placeholder messages can be temporarily empty while background generation is in progress.
    content: str = Field(default="")
    status: MessageDeliveryStatus = Field(default=MessageDeliveryStatus.COMPLETED)
    id: int
    session_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatSendRequest(BaseModel):
    message: str = Field(min_length=1)
    session_id: int | None = Field(default=None, gt=0)
    title: str | None = Field(default=None, max_length=255)


class ChatSendResponse(BaseModel):
    session: ChatSessionRead
    user_message: ChatMessageRead
    assistant_message: ChatMessageRead | None = None


class ChatDeleteResponse(BaseModel):
    success: bool = True
