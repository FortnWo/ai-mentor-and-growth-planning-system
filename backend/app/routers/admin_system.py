"""
Admin system maintenance router.

Endpoints:
  GET  /admin/system/ai-config
  PUT  /admin/system/ai-config
  GET  /admin/system/llm-presets
  POST /admin/system/llm-presets
  DELETE /admin/system/llm-presets/{preset_id}
  POST /admin/system/llm-presets/{preset_id}/activate
  GET  /admin/system/notify-config
  PUT  /admin/system/notify-config
  GET  /admin/system/rate-limit-config
  PUT  /admin/system/rate-limit-config
  GET  /admin/system/verification-config
  PUT  /admin/system/verification-config
  GET  /admin/system/logs/error
  GET  /admin/system/logs/usage

Error codes: SYS_5xxx
"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_full_admin
from app.services import system_config_service as scs

router = APIRouter(prefix="/admin/system", tags=["admin-system"])
logger = logging.getLogger("ai_mentor.admin_system")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _llm_preset_http_error(exc: scs.LlmPresetError) -> HTTPException:
    message = str(exc)
    if "已存在" in message:
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=message)
    if "未找到" in message:
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message)
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)


# ── AI Config ─────────────────────────────────────────────────────────────────

class LlmConfigSource(BaseModel):
    llm_api_key: Literal["env", "db", "unset"]
    llm_api_base_url: Literal["env", "db", "unset"]
    llm_model: Literal["env", "db", "unset"]


class AIConfigRead(BaseModel):
    llm_api_key_set: bool
    llm_api_key_masked: str | None
    llm_api_base_url: str | None
    llm_model: str | None
    llm_system_prompt: str | None
    admin_llm_system_prompt: str | None
    active_preset_id: str | None
    effective_llm_api_key_set: bool
    effective_llm_api_key_masked: str | None
    effective_llm_api_base_url: str | None
    effective_llm_model: str | None
    llm_config_source: LlmConfigSource


class AIConfigUpdate(BaseModel):
    llm_api_key: str | None = None
    llm_api_base_url: str | None = None
    llm_model: str | None = None
    llm_system_prompt: str | None = None
    admin_llm_system_prompt: str | None = None


@router.get("/ai-config", response_model=AIConfigRead)
def get_ai_config(
    _current_user=Depends(require_full_admin()),
    db: Session = Depends(get_db),
):
    cfg = scs.get_ai_config(db)
    effective = scs.get_effective_ai_config(db)
    sources = scs.get_llm_config_source(db)
    api_key = cfg.get("llm_api_key")
    effective_key = effective.get("llm_api_key")
    return AIConfigRead(
        llm_api_key_set=bool(api_key),
        llm_api_key_masked=scs.mask_secret(api_key) if api_key else None,
        llm_api_base_url=cfg.get("llm_api_base_url"),
        llm_model=cfg.get("llm_model"),
        llm_system_prompt=cfg.get("llm_system_prompt"),
        admin_llm_system_prompt=cfg.get("admin_llm_system_prompt"),
        active_preset_id=cfg.get("llm_active_preset_id"),
        effective_llm_api_key_set=bool(effective_key),
        effective_llm_api_key_masked=scs.mask_secret(effective_key) if effective_key else None,
        effective_llm_api_base_url=effective.get("llm_api_base_url"),
        effective_llm_model=effective.get("llm_model"),
        llm_config_source=LlmConfigSource(**sources),
    )


@router.put("/ai-config", status_code=status.HTTP_200_OK)
def update_ai_config(
    payload: AIConfigUpdate,
    _current_user=Depends(require_full_admin()),
    db: Session = Depends(get_db),
):
    fields = payload.model_dump(exclude_unset=True)
    for key, value in fields.items():
        if value is not None:
            scs.set(db, key, value)
    return {"message": "AI config updated", "updated_keys": list(fields.keys())}


# ── LLM Presets ───────────────────────────────────────────────────────────────

class LlmPresetRead(BaseModel):
    id: str
    name: str
    llm_api_base_url: str | None
    llm_model: str | None
    llm_api_key_set: bool
    llm_api_key_masked: str | None


class LlmPresetCreate(BaseModel):
    name: str
    llm_api_key: str | None = None
    llm_api_base_url: str | None = None
    llm_model: str | None = None


class LlmPresetListResponse(BaseModel):
    presets: list[LlmPresetRead]


@router.get("/llm-presets", response_model=LlmPresetListResponse)
def list_llm_presets(
    _current_user=Depends(require_full_admin()),
    db: Session = Depends(get_db),
):
    presets = scs.list_llm_presets(db)
    return LlmPresetListResponse(presets=[LlmPresetRead(**p) for p in presets])


@router.post("/llm-presets", response_model=LlmPresetRead, status_code=status.HTTP_201_CREATED)
def create_llm_preset(
    payload: LlmPresetCreate,
    _current_user=Depends(require_full_admin()),
    db: Session = Depends(get_db),
):
    try:
        preset = scs.create_llm_preset(
            db,
            name=payload.name,
            llm_api_key=payload.llm_api_key,
            llm_api_base_url=payload.llm_api_base_url,
            llm_model=payload.llm_model,
        )
    except scs.LlmPresetError as exc:
        raise _llm_preset_http_error(exc) from exc
    return LlmPresetRead(**preset)


@router.delete("/llm-presets/{preset_id}", status_code=status.HTTP_200_OK)
def delete_llm_preset(
    preset_id: str,
    _current_user=Depends(require_full_admin()),
    db: Session = Depends(get_db),
):
    try:
        scs.delete_llm_preset(db, preset_id)
    except scs.LlmPresetError as exc:
        raise _llm_preset_http_error(exc) from exc
    return {"message": "Preset deleted"}


@router.post("/llm-presets/{preset_id}/activate", status_code=status.HTTP_200_OK)
def activate_llm_preset(
    preset_id: str,
    _current_user=Depends(require_full_admin()),
    db: Session = Depends(get_db),
):
    try:
        scs.activate_llm_preset(db, preset_id)
    except scs.LlmPresetError as exc:
        raise _llm_preset_http_error(exc) from exc
    return {"message": "Preset activated", "active_preset_id": preset_id}


# ── Notify Config ─────────────────────────────────────────────────────────────

class SMSConfigUpdate(BaseModel):
    vendor: str | None = None
    access_key_id: str | None = None
    access_key_secret: str | None = None
    endpoint: str | None = None
    sign_name: str | None = None
    template_code: str | None = None
    sdk_app_id: str | None = None
    region: str | None = None


class SMTPConfigUpdate(BaseModel):
    smtp_host: str | None = None
    smtp_port: int | None = None
    from_email: str | None = None
    email_password: str | None = None
    sender_name: str | None = None


class NotifyConfigRead(BaseModel):
    sms_configured: bool
    sms_vendor: str | None
    sms_access_key_id_set: bool
    sms_endpoint: str | None
    sms_sign_name: str | None
    smtp_configured: bool
    smtp_host: str | None
    smtp_port: str | None
    smtp_from_email: str | None
    smtp_sender_name: str | None


@router.get("/notify-config", response_model=NotifyConfigRead)
def get_notify_config(
    _current_user=Depends(require_full_admin()),
    db: Session = Depends(get_db),
):
    sms = scs.get_sms_config(db)
    smtp = scs.get_smtp_config(db)
    return NotifyConfigRead(
        sms_configured=bool(sms),
        sms_vendor=sms.get("vendor") if sms else None,
        sms_access_key_id_set=bool(sms and sms.get("access_key_id")),
        sms_endpoint=sms.get("endpoint") if sms else None,
        sms_sign_name=sms.get("sign_name") if sms else None,
        smtp_configured=bool(smtp),
        smtp_host=smtp.get("smtp_host") if smtp else None,
        smtp_port=str(smtp.get("smtp_port", "")) if smtp else None,
        smtp_from_email=smtp.get("from_email") if smtp else None,
        smtp_sender_name=smtp.get("sender_name") if smtp else None,
    )


@router.put("/notify-config/sms", status_code=status.HTTP_200_OK)
def update_sms_config(
    payload: SMSConfigUpdate,
    _current_user=Depends(require_full_admin()),
    db: Session = Depends(get_db),
):
    mapping = {
        "vendor": "sms_vendor",
        "access_key_id": "sms_access_key_id",
        "access_key_secret": "sms_access_key_secret",
        "endpoint": "sms_endpoint",
        "sign_name": "sms_sign_name",
        "template_code": "sms_template_code",
        "sdk_app_id": "sms_sdk_app_id",
        "region": "sms_region",
    }
    fields = payload.model_dump(exclude_unset=True)
    for field, cfg_key in mapping.items():
        if field in fields and fields[field] is not None:
            scs.set(db, cfg_key, str(fields[field]))
    return {"message": "SMS config updated"}


@router.put("/notify-config/smtp", status_code=status.HTTP_200_OK)
def update_smtp_config(
    payload: SMTPConfigUpdate,
    _current_user=Depends(require_full_admin()),
    db: Session = Depends(get_db),
):
    mapping = {
        "smtp_host": "smtp_host",
        "smtp_port": "smtp_port",
        "from_email": "smtp_from_email",
        "email_password": "email_password",
        "sender_name": "smtp_sender_name",
    }
    fields = payload.model_dump(exclude_unset=True)
    for field, cfg_key in mapping.items():
        if field in fields and fields[field] is not None:
            scs.set(db, cfg_key, str(fields[field]))
    return {"message": "SMTP config updated"}


# ── Rate limit config ─────────────────────────────────────────────────────────

class RateLimitConfig(BaseModel):
    daily_limit: int
    weekly_limit: int


@router.get("/rate-limit-config", response_model=RateLimitConfig)
def get_rate_limit_config(
    _current_user=Depends(require_full_admin()),
    db: Session = Depends(get_db),
):
    return RateLimitConfig(**scs.get_rate_limit_config(db))


@router.put("/rate-limit-config", status_code=status.HTTP_200_OK)
def update_rate_limit_config(
    payload: RateLimitConfig,
    _current_user=Depends(require_full_admin()),
    db: Session = Depends(get_db),
):
    scs.set(db, "rate_limit_daily", str(payload.daily_limit))
    scs.set(db, "rate_limit_weekly", str(payload.weekly_limit))
    return {"message": "Rate limit config updated"}


# ── Verification code config ──────────────────────────────────────────────────

class VerificationConfig(BaseModel):
    expire_minutes: int
    resend_interval_seconds: int
    code_length: int


@router.get("/verification-config", response_model=VerificationConfig)
def get_verification_config(
    _current_user=Depends(require_full_admin()),
    db: Session = Depends(get_db),
):
    return VerificationConfig(**scs.get_verification_config(db))


@router.put("/verification-config", status_code=status.HTTP_200_OK)
def update_verification_config(
    payload: VerificationConfig,
    _current_user=Depends(require_full_admin()),
    db: Session = Depends(get_db),
):
    scs.set(db, "vc_expire_minutes", str(payload.expire_minutes))
    scs.set(db, "vc_resend_interval_seconds", str(payload.resend_interval_seconds))
    scs.set(db, "vc_code_length", str(payload.code_length))
    return {"message": "Verification config updated"}


# ── Error logs ────────────────────────────────────────────────────────────────

_LOG_HEADER_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})")


def _group_log_lines(lines: list[str]) -> list[list[str]]:
    groups: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if _LOG_HEADER_RE.match(line):
            if current:
                groups.append(current)
            current = [line]
        elif current:
            current.append(line)
        elif line.strip():
            groups.append([line])
    if current:
        groups.append(current)
    return groups


def _filter_log_lines_by_date(lines: list[str], target: date) -> list[str]:
    date_str = target.isoformat()
    matched: list[list[str]] = []
    for group in _group_log_lines(lines):
        header = _LOG_HEADER_RE.match(group[0])
        if header and header.group(1) == date_str:
            matched.append(group)
    flattened: list[str] = []
    for group in matched:
        flattened.extend(group)
    return flattened


class ErrorLogResponse(BaseModel):
    lines: list[str]
    total_lines: int
    page: int
    page_size: int
    date: str | None = None


@router.get("/logs/error", response_model=ErrorLogResponse)
def get_error_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    log_date: date | None = Query(default=None, alias="date"),
    _current_user=Depends(require_full_admin()),
):
    log_path = Path(__file__).resolve().parents[2] / "logs" / "error.log"
    if not log_path.exists():
        return ErrorLogResponse(
            lines=[],
            total_lines=0,
            page=page,
            page_size=page_size,
            date=log_date.isoformat() if log_date else None,
        )

    with log_path.open(encoding="utf-8", errors="replace") as f:
        all_lines = [l.rstrip() for l in f.readlines()]

    if log_date is not None:
        all_lines = _filter_log_lines_by_date(all_lines, log_date)

    total = len(all_lines)
    # Most recent first: reverse then paginate
    reversed_lines = list(reversed(all_lines))
    start = (page - 1) * page_size
    end = start + page_size
    return ErrorLogResponse(
        lines=reversed_lines[start:end],
        total_lines=total,
        page=page,
        page_size=page_size,
        date=log_date.isoformat() if log_date else None,
    )


# ── AI usage logs ─────────────────────────────────────────────────────────────

class UsageStatEntry(BaseModel):
    period: str
    date_label: str
    calls: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class UsageLogsResponse(BaseModel):
    stats: list[UsageStatEntry]
    user_detail: list[dict] | None = None


class UsageLogsDebugResponse(BaseModel):
    table_exists: bool
    total_rows: int
    null_user_id_rows: int
    last_rows: list[dict]


@router.get("/logs/usage/debug", response_model=UsageLogsDebugResponse)
def get_usage_logs_debug(
    _current_user=Depends(require_full_admin()),
    db: Session = Depends(get_db),
):
    from sqlalchemy import inspect as sa_inspect

    insp = sa_inspect(db.bind)
    table_exists = "ai_usage_logs" in insp.get_table_names()
    if not table_exists:
        return UsageLogsDebugResponse(
            table_exists=False,
            total_rows=0,
            null_user_id_rows=0,
            last_rows=[],
        )

    total_rows = db.execute(text("SELECT COUNT(*) FROM ai_usage_logs")).scalar() or 0
    null_user_id_rows = db.execute(
        text("SELECT COUNT(*) FROM ai_usage_logs WHERE user_id IS NULL")
    ).scalar() or 0
    rows = db.execute(
        text(
            "SELECT id, user_id, model, task, prompt_tokens, completion_tokens, created_at "
            "FROM ai_usage_logs ORDER BY id DESC LIMIT 5"
        )
    ).fetchall()
    last_rows = [
        {
            "id": r[0],
            "user_id": r[1],
            "model": r[2],
            "task": r[3],
            "prompt_tokens": r[4],
            "completion_tokens": r[5],
            "created_at": r[6].isoformat() if hasattr(r[6], "isoformat") else str(r[6]),
        }
        for r in rows
    ]
    return UsageLogsDebugResponse(
        table_exists=True,
        total_rows=int(total_rows),
        null_user_id_rows=int(null_user_id_rows),
        last_rows=last_rows,
    )


@router.get("/logs/usage", response_model=UsageLogsResponse)
def get_usage_logs(
    period: str = Query(default="week", pattern="^(today|week|month)$"),
    username: str | None = Query(default=None),
    _current_user=Depends(require_full_admin()),
    db: Session = Depends(get_db),
):
    from sqlalchemy import inspect as sa_inspect

    insp = sa_inspect(db.bind)
    if "ai_usage_logs" not in insp.get_table_names():
        return UsageLogsResponse(stats=[])

    today = date.today()
    if period == "today":
        start_date = today
        days = 1
    elif period == "week":
        start_date = today - timedelta(days=6)
        days = 7
    else:
        start_date = today.replace(day=1)
        days = (today - start_date).days + 1

    stats: list[UsageStatEntry] = []
    for i in range(days):
        day = start_date + timedelta(days=i)
        sql = (
            "SELECT COUNT(*) as calls, "
            "COALESCE(SUM(prompt_tokens), 0) as pt, "
            "COALESCE(SUM(completion_tokens), 0) as ct "
            "FROM ai_usage_logs WHERE DATE(created_at) = :d"
        )
        params: dict = {"d": day}
        if username:
            sql += " AND user_id = (SELECT id FROM users WHERE username = :uname LIMIT 1)"
            params["uname"] = username

        row = db.execute(text(sql), params).fetchone()
        stats.append(UsageStatEntry(
            period=period,
            date_label=day.isoformat(),
            calls=row[0] or 0,
            prompt_tokens=row[1] or 0,
            completion_tokens=row[2] or 0,
            total_tokens=(row[1] or 0) + (row[2] or 0),
        ))

    user_detail = None
    if username:
        detail_sql = (
            "SELECT DATE(created_at) as day, model, task, "
            "COUNT(*) as calls, SUM(prompt_tokens) as pt, SUM(completion_tokens) as ct "
            "FROM ai_usage_logs "
            "WHERE user_id = (SELECT id FROM users WHERE username = :uname LIMIT 1) "
            "AND DATE(created_at) >= :start "
            "GROUP BY day, model, task ORDER BY day DESC"
        )
        rows = db.execute(text(detail_sql), {"uname": username, "start": start_date}).fetchall()
        user_detail = [
            {"day": r[0].isoformat() if hasattr(r[0], "isoformat") else str(r[0]),
             "model": r[1], "task": r[2], "calls": r[3], "prompt_tokens": r[4], "completion_tokens": r[5]}
            for r in rows
        ]

    return UsageLogsResponse(stats=stats, user_detail=user_detail)
