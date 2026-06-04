"""
Admin tool service — provides DB query tools for the admin chat assistant.

All tools are read-only SELECT queries.
Tool schema follows the OpenAI function-calling format.
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime

from sqlalchemy import func, text
from sqlalchemy.orm import Session

logger = logging.getLogger("ai_mentor.admin_tools")

# ── Tool definitions (OpenAI function-calling schema) ─────────────────────────

ADMIN_TOOLS: list[dict] = [
    {
        "type": "function",
        "name": "get_system_stats",
        "description": (
            "Get aggregate system statistics: total users, active users, admin count, "
            "today's chat session count, total growth records."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "type": "function",
        "name": "query_users",
        "description": (
            "Query users with optional filters. Returns id, username, full_name, role, "
            "is_active, major, enrollment_year, created_at."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "role": {
                    "type": "string",
                    "enum": ["user", "admin"],
                    "description": "Filter by role",
                },
                "is_active": {
                    "type": "boolean",
                    "description": "Filter by active status",
                },
                "major": {
                    "type": "string",
                    "description": "Filter by major (exact match)",
                },
                "username_like": {
                    "type": "string",
                    "description": "Student ID / username substring search",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max rows to return (default 20, max 100)",
                },
            },
            "required": [],
        },
    },
    {
        "type": "function",
        "name": "get_error_logs",
        "description": "Read recent error log entries from the error.log file.",
        "parameters": {
            "type": "object",
            "properties": {
                "lines": {
                    "type": "integer",
                    "description": "Number of recent lines to return (default 30, max 200)",
                },
            },
            "required": [],
        },
    },
    {
        "type": "function",
        "name": "get_ai_usage_stats",
        "description": "Get LLM call usage statistics (total calls, token usage) by period.",
        "parameters": {
            "type": "object",
            "properties": {
                "period": {
                    "type": "string",
                    "enum": ["today", "week", "month"],
                    "description": "Period to summarize (default: today)",
                },
                "username": {
                    "type": "string",
                    "description": "Optional: filter by a specific user's username",
                },
            },
            "required": [],
        },
    },
]


# ── Tool execution ─────────────────────────────────────────────────────────────

def execute_tool(db: Session, tool_name: str, args: dict) -> str:
    """
    Execute a tool by name and return JSON-serialisable string result.
    Raises ValueError for unknown tools.
    """
    if tool_name == "get_system_stats":
        return _get_system_stats(db)
    if tool_name == "query_users":
        return _query_users(db, **args)
    if tool_name == "get_error_logs":
        return _get_error_logs(lines=int(args.get("lines", 30)))
    if tool_name == "get_ai_usage_stats":
        return _get_ai_usage_stats(db, period=args.get("period", "today"), username=args.get("username"))
    raise ValueError(f"CHAT_A002: Unknown tool: {tool_name}")


def _json(obj) -> str:
    def default(o):
        if isinstance(o, (date, datetime)):
            return o.isoformat()
        return str(o)
    return json.dumps(obj, ensure_ascii=False, default=default)


def _get_system_stats(db: Session) -> str:
    from app.models.user import User
    from app.models.chat import ChatSession
    from app.models.growth_record import GrowthRecord

    total_users = db.query(func.count(User.id)).scalar() or 0
    active_users = db.query(func.count(User.id)).filter(User.is_active == True).scalar() or 0
    admin_count = db.query(func.count(User.id)).filter(User.role == "admin").scalar() or 0

    today = date.today()
    today_sessions = (
        db.query(func.count(ChatSession.id))
        .filter(func.date(ChatSession.created_at) == today)
        .scalar() or 0
    )
    total_growth = db.query(func.count(GrowthRecord.id)).scalar() or 0

    return _json({
        "total_users": total_users,
        "active_users": active_users,
        "admin_count": admin_count,
        "student_count": total_users - admin_count,
        "today_chat_sessions": today_sessions,
        "total_growth_records": total_growth,
        "as_of": datetime.now().isoformat(),
    })


def _query_users(
    db: Session,
    role: str | None = None,
    is_active: bool | None = None,
    major: str | None = None,
    username_like: str | None = None,
    limit: int = 20,
) -> str:
    from app.models.user import User

    limit = min(max(1, int(limit)), 100)
    query = db.query(
        User.id,
        User.username,
        User.full_name,
        User.role,
        User.is_active,
        User.major,
        User.enrollment_year,
        User.phone,
        User.created_at,
    )
    if role:
        query = query.filter(User.role == role)
    if is_active is not None:
        query = query.filter(User.is_active == is_active)
    if major:
        query = query.filter(User.major == major)
    if username_like:
        query = query.filter(User.username.like(f"%{username_like}%"))

    rows = query.order_by(User.created_at.desc()).limit(limit).all()
    result = []
    for r in rows:
        result.append({
            "id": r.id,
            "username": r.username,
            "full_name": r.full_name,
            "role": r.role,
            "is_active": r.is_active,
            "major": r.major,
            "enrollment_year": r.enrollment_year,
            "phone": r.phone,
            "created_at": r.created_at,
        })
    return _json({"users": result, "count": len(result)})


def _get_error_logs(lines: int = 30) -> str:
    from pathlib import Path

    lines = min(max(1, lines), 200)
    log_path = Path(__file__).resolve().parents[2] / "logs" / "error.log"
    if not log_path.exists():
        return _json({"lines": [], "note": "No error log found"})

    with log_path.open(encoding="utf-8", errors="replace") as f:
        all_lines = f.readlines()

    tail = [l.rstrip() for l in all_lines[-lines:]]
    return _json({"lines": tail, "total_lines": len(all_lines), "returned": len(tail)})


def _get_ai_usage_stats(db: Session, period: str = "today", username: str | None = None) -> str:
    """Query ai_usage_logs if it exists, otherwise return a not-yet-available note."""
    from sqlalchemy import inspect as sa_inspect

    insp = sa_inspect(db.bind)
    if "ai_usage_logs" not in insp.get_table_names():
        return _json({"note": "AI usage logs not yet available (Phase 5 feature)", "period": period})

    today = date.today()
    if period == "today":
        start = datetime(today.year, today.month, today.day)
    elif period == "week":
        from datetime import timedelta
        start = datetime(today.year, today.month, today.day) - timedelta(days=6)
    else:
        start = datetime(today.year, today.month, 1)

    base = "SELECT COUNT(*) as calls, SUM(prompt_tokens) as prompt_tokens, SUM(completion_tokens) as completion_tokens FROM ai_usage_logs WHERE created_at >= :start"
    params: dict = {"start": start}
    if username:
        base += " AND user_id = (SELECT id FROM users WHERE username = :uname LIMIT 1)"
        params["uname"] = username

    row = db.execute(text(base), params).fetchone()
    return _json({
        "period": period,
        "calls": row[0] or 0,
        "prompt_tokens": row[1] or 0,
        "completion_tokens": row[2] or 0,
        "username_filter": username,
    })
