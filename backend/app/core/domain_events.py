from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


class DomainEventName(str, Enum):
    ON_CHAT_MESSAGE = "on_chat_message"
    ON_PROFILE_UPDATED = "on_profile_updated"
    ON_GOAL_DETECTED = "on_goal_detected"
    ON_GOAL_BREAKDOWN = "on_goal_breakdown"
    ON_ACTION_GENERATED = "on_action_generated"
    ON_ACTION_COMPLETED = "on_action_completed"
    ON_GROWTH_UPDATED = "on_growth_updated"


@dataclass(slots=True, frozen=True)
class DomainEvent:
    event_id: str
    trace_id: str
    name: str
    user_id: int
    payload: dict[str, Any]
    occurred_at: datetime


def build_domain_event(
    *,
    event_name: str,
    user_id: int,
    payload: dict[str, Any] | None = None,
    trace_id: str | None = None,
) -> DomainEvent:
    normalized_trace_id = trace_id.strip() if isinstance(trace_id, str) and trace_id.strip() else str(uuid4())
    return DomainEvent(
        event_id=str(uuid4()),
        trace_id=normalized_trace_id,
        name=event_name,
        user_id=user_id,
        payload=payload or {},
        occurred_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )

