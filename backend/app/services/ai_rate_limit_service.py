"""AI chat rate limiting for regular users (role=user, task=chat only)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.services import system_config_service as scs

WARNING_THRESHOLD = 0.8
CHAT_TASK = "chat"


class AIRateLimitExceeded(Exception):
    code = "CHAT_R001"

    def __init__(self, reason: Literal["daily", "weekly"], limit: int) -> None:
        self.reason = reason
        self.limit = limit
        if reason == "daily":
            message = f"CHAT_R001: 今日 AI 聊天次数已达上限（{limit} 次），请明日再试。"
        else:
            message = f"CHAT_R001: 本周 AI 聊天次数已达上限（{limit} 次），请下周再试。"
        super().__init__(message)


@dataclass(frozen=True)
class ChatUsageSnapshot:
    daily_count: int
    weekly_count: int


def _usage_table_exists(db: Session) -> bool:
    if db.bind is None:
        return False
    return "ai_usage_logs" in inspect(db.bind).get_table_names()


def count_chat_calls(db: Session, user_id: int, *, window: Literal["day", "week"]) -> int:
    if not _usage_table_exists(db):
        return 0

    today = date.today()
    if window == "day":
        start_date = today
    else:
        start_date = today - timedelta(days=6)

    row = db.execute(
        text(
            "SELECT COUNT(*) FROM ai_usage_logs "
            "WHERE user_id = :user_id AND task = :task "
            "AND DATE(created_at) >= :start_date"
        ),
        {"user_id": user_id, "task": CHAT_TASK, "start_date": start_date},
    ).scalar()
    return int(row or 0)


def get_chat_usage(db: Session, user_id: int) -> ChatUsageSnapshot:
    return ChatUsageSnapshot(
        daily_count=count_chat_calls(db, user_id, window="day"),
        weekly_count=count_chat_calls(db, user_id, window="week"),
    )


def compute_risk_flag(
    daily_count: int,
    weekly_count: int,
    *,
    daily_limit: int,
    weekly_limit: int,
) -> int:
    if daily_count >= daily_limit or weekly_count >= weekly_limit:
        return 2
    daily_warn = int(daily_limit * WARNING_THRESHOLD)
    weekly_warn = int(weekly_limit * WARNING_THRESHOLD)
    if daily_count >= daily_warn or weekly_count >= weekly_warn:
        return 1
    return 0


def sync_user_risk_flag(db: Session, user: User) -> int:
    limits = scs.get_rate_limit_config(db)
    usage = get_chat_usage(db, user.id)
    new_flag = compute_risk_flag(
        usage.daily_count,
        usage.weekly_count,
        daily_limit=limits["daily_limit"],
        weekly_limit=limits["weekly_limit"],
    )
    if user.risk_flag != new_flag:
        user.risk_flag = new_flag
        db.add(user)
        db.commit()
        db.refresh(user)
    return new_flag


def assert_chat_allowed(db: Session, user: User) -> None:
    """Raise AIRateLimitExceeded when a regular user exceeds chat quotas."""
    if user.role == UserRole.ADMIN:
        return

    limits = scs.get_rate_limit_config(db)
    usage = get_chat_usage(db, user.id)
    daily_limit = limits["daily_limit"]
    weekly_limit = limits["weekly_limit"]

    if usage.daily_count >= daily_limit:
        sync_user_risk_flag(db, user)
        raise AIRateLimitExceeded("daily", daily_limit)

    if usage.weekly_count >= weekly_limit:
        sync_user_risk_flag(db, user)
        raise AIRateLimitExceeded("weekly", weekly_limit)

    sync_user_risk_flag(db, user)
