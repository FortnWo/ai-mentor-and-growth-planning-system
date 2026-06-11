"""
System config service — encrypted KV store backed by the system_config table.

Encryption: Fernet symmetric encryption (cryptography library).
The encryption key is derived from APP_SECRET_KEY (settings) + a fixed salt.
Sensitive keys are stored encrypted; non-sensitive keys stored as plaintext.

Sensitive config keys (auto-encrypted):
  sms_access_key_secret, email_password

Usage:
  get("llm_api_key")         → plaintext or decrypted value, or None
  set("llm_api_key", "sk-…") → encrypted if sensitive, else plaintext
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import uuid
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.core.database import SessionLocal

logger = logging.getLogger("ai_mentor.system_config")

# Keys that must be encrypted at rest
_SENSITIVE_KEYS: set[str] = {
    "sms_access_key_secret",
    "email_password",
    "llm_api_key",
    "llm_presets",
}

_LLM_PRESETS_KEY = "llm_presets"
_LLM_ACTIVE_PRESET_ID_KEY = "llm_active_preset_id"
_MAX_LLM_PRESETS = 10


def mask_secret(value: str, head: int = 4, tail: int = 4) -> str:
    """Mask a secret, showing only the start and end."""
    if len(value) <= head + tail:
        return "•" * len(value)
    return f"{value[:head]}{'•' * 8}{value[-tail:]}"


def _get_fernet():
    try:
        from cryptography.fernet import Fernet
        from app.core.config import settings
        raw = getattr(settings, "APP_SECRET_KEY", "ai-mentor-default-secret-key-change-me")
        key_bytes = hashlib.sha256(raw.encode()).digest()
        fernet_key = base64.urlsafe_b64encode(key_bytes)
        return Fernet(fernet_key)
    except ImportError as exc:
        raise RuntimeError("cryptography library is not installed. Run: pip install cryptography") from exc


def _encrypt(value: str) -> str:
    return _get_fernet().encrypt(value.encode()).decode()


def _decrypt(value: str) -> str:
    try:
        return _get_fernet().decrypt(value.encode()).decode()
    except Exception as exc:
        logger.error("system_config: decryption failed: %s", exc)
        raise ValueError("配置值解密失败") from exc


# ── CRUD ──────────────────────────────────────────────────────────────────────

def get(db: Session, key: str) -> str | None:
    from app.models.system_config import SystemConfig
    row = db.query(SystemConfig).filter(SystemConfig.key == key).first()
    if not row or row.value is None:
        return None
    if row.is_encrypted:
        return _decrypt(row.value)
    return row.value


def set(db: Session, key: str, value: str | None) -> None:
    from app.models.system_config import SystemConfig
    should_encrypt = key in _SENSITIVE_KEYS
    stored_value = None
    if value is not None:
        stored_value = _encrypt(value) if should_encrypt else value

    row = db.query(SystemConfig).filter(SystemConfig.key == key).first()
    if row:
        row.value = stored_value
        row.is_encrypted = should_encrypt
    else:
        row = SystemConfig(key=key, value=stored_value, is_encrypted=should_encrypt)
        db.add(row)
    db.commit()


def get_all(db: Session, prefix: str | None = None) -> dict[str, str | None]:
    """Return all config entries matching optional key prefix, with sensitive values decrypted."""
    from app.models.system_config import SystemConfig
    query = db.query(SystemConfig)
    if prefix:
        query = query.filter(SystemConfig.key.like(f"{prefix}%"))
    rows = query.all()
    result = {}
    for row in rows:
        v = row.value
        if v and row.is_encrypted:
            try:
                v = _decrypt(v)
            except Exception:
                v = None
        result[row.key] = v
    return result


# ── Domain-specific helpers ───────────────────────────────────────────────────

def get_ai_config(db: Session | None = None) -> dict:
    """Return AI service config as dict."""
    with _db_ctx(db) as session:
        return {
            "llm_api_key": get(session, "llm_api_key"),
            "llm_api_base_url": get(session, "llm_api_base_url"),
            "llm_model": get(session, "llm_model"),
            "llm_system_prompt": get(session, "llm_system_prompt"),
            "admin_llm_system_prompt": get(session, "admin_llm_system_prompt"),
            "llm_active_preset_id": get(session, _LLM_ACTIVE_PRESET_ID_KEY),
        }


def _resolve_prompt(db: Session | None, db_key: str, settings_attr: str) -> str:
    """Resolve a system prompt: DB override (admin panel) > settings (.env / config default)."""
    from sqlalchemy import inspect
    from sqlalchemy.exc import SQLAlchemyError

    from app.core.config import settings

    try:
        with _db_ctx(db) as session:
            if session.bind is not None and "system_config" not in inspect(session.bind).get_table_names():
                return getattr(settings, settings_attr).strip()
            db_value = get(session, db_key)
            if db_value and db_value.strip():
                return db_value.strip()
    except SQLAlchemyError:
        logger.debug("prompt resolve: falling back to settings for %s", db_key, exc_info=True)
    return getattr(settings, settings_attr).strip()


def resolve_llm_system_prompt(db: Session | None = None) -> str:
    """Effective user-facing mentor chat system prompt."""
    return _resolve_prompt(db, "llm_system_prompt", "LLM_SYSTEM_PROMPT")


def resolve_admin_llm_system_prompt(db: Session | None = None) -> str:
    """Effective admin assistant chat system prompt."""
    return _resolve_prompt(db, "admin_llm_system_prompt", "ADMIN_LLM_SYSTEM_PROMPT")


def _non_empty_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _resolve_env_then_db(
    db: Session | None,
    db_key: str,
    settings_attr: str,
) -> str | None:
    """Resolve optional config: .env / settings > DB > unset."""
    from sqlalchemy import inspect
    from sqlalchemy.exc import SQLAlchemyError

    from app.core.config import settings

    env_value = _non_empty_str(getattr(settings, settings_attr, None))
    if env_value:
        return env_value

    try:
        with _db_ctx(db) as session:
            if session.bind is not None and "system_config" not in inspect(session.bind).get_table_names():
                return None
            return _non_empty_str(get(session, db_key))
    except SQLAlchemyError:
        logger.debug("config resolve: falling back for %s", db_key, exc_info=True)
    return None


def _llm_config_source_for(
    db: Session | None,
    db_key: str,
    settings_attr: str,
) -> Literal["env", "db", "unset"]:
    from sqlalchemy import inspect
    from sqlalchemy.exc import SQLAlchemyError

    from app.core.config import settings

    if _non_empty_str(getattr(settings, settings_attr, None)):
        return "env"

    try:
        with _db_ctx(db) as session:
            if session.bind is not None and "system_config" not in inspect(session.bind).get_table_names():
                return "unset"
            if _non_empty_str(get(session, db_key)):
                return "db"
    except SQLAlchemyError:
        logger.debug("config source: falling back for %s", db_key, exc_info=True)
    return "unset"


def resolve_llm_api_key(db: Session | None = None) -> str | None:
    return _resolve_env_then_db(db, "llm_api_key", "LLM_API_KEY")


def resolve_llm_api_base_url(db: Session | None = None) -> str | None:
    return _resolve_env_then_db(db, "llm_api_base_url", "LLM_API_BASE_URL")


def resolve_llm_model(db: Session | None = None) -> str | None:
    return _resolve_env_then_db(db, "llm_model", "LLM_MODEL")


def is_llm_configured(db: Session | None = None) -> bool:
    return bool(
        resolve_llm_api_key(db)
        and resolve_llm_api_base_url(db)
        and resolve_llm_model(db)
    )


def get_effective_ai_config(db: Session | None = None) -> dict:
    api_key = resolve_llm_api_key(db)
    return {
        "llm_api_key": api_key,
        "llm_api_base_url": resolve_llm_api_base_url(db),
        "llm_model": resolve_llm_model(db),
    }


def get_llm_config_source(db: Session | None = None) -> dict[str, Literal["env", "db", "unset"]]:
    return {
        "llm_api_key": _llm_config_source_for(db, "llm_api_key", "LLM_API_KEY"),
        "llm_api_base_url": _llm_config_source_for(db, "llm_api_base_url", "LLM_API_BASE_URL"),
        "llm_model": _llm_config_source_for(db, "llm_model", "LLM_MODEL"),
    }


def _load_llm_presets_raw(db: Session) -> list[dict[str, Any]]:
    raw = get(db, _LLM_PRESETS_KEY)
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("system_config: invalid llm_presets JSON, resetting")
        return []
    if not isinstance(data, list):
        return []
    return data


def _save_llm_presets_raw(db: Session, presets: list[dict[str, Any]]) -> None:
    set(db, _LLM_PRESETS_KEY, json.dumps(presets, ensure_ascii=False))


def _preset_to_public(preset: dict[str, Any]) -> dict[str, Any]:
    key = preset.get("llm_api_key") or ""
    return {
        "id": preset["id"],
        "name": preset["name"],
        "llm_api_base_url": preset.get("llm_api_base_url"),
        "llm_model": preset.get("llm_model"),
        "llm_api_key_set": bool(key),
        "llm_api_key_masked": mask_secret(key) if key else None,
    }


def list_llm_presets(db: Session) -> list[dict[str, Any]]:
    return [_preset_to_public(p) for p in _load_llm_presets_raw(db)]


class LlmPresetError(ValueError):
    """Raised for invalid LLM preset operations."""


def create_llm_preset(
    db: Session,
    *,
    name: str,
    llm_api_key: str | None = None,
    llm_api_base_url: str | None = None,
    llm_model: str | None = None,
) -> dict[str, Any]:
    name = name.strip()
    if not name:
        raise LlmPresetError("预设名称不能为空")

    api_key = (llm_api_key or "").strip() or None
    base_url = (llm_api_base_url or "").strip() or None
    model = (llm_model or "").strip() or None

    if not api_key:
        api_key = get(db, "llm_api_key")

    if not api_key and not base_url and not model:
        raise LlmPresetError("API 密钥、Base URL、模型至少填写一项")

    presets = _load_llm_presets_raw(db)
    if len(presets) >= _MAX_LLM_PRESETS:
        raise LlmPresetError(f"最多允许 {_MAX_LLM_PRESETS} 个预设")

    if any(p.get("name") == name for p in presets):
        raise LlmPresetError(f"预设名称已存在: {name}")

    preset = {
        "id": str(uuid.uuid4()),
        "name": name,
        "llm_api_key": api_key or "",
        "llm_api_base_url": base_url or "",
        "llm_model": model or "",
    }
    presets.append(preset)
    _save_llm_presets_raw(db, presets)
    return _preset_to_public(preset)


def delete_llm_preset(db: Session, preset_id: str) -> None:
    presets = _load_llm_presets_raw(db)
    new_presets = [p for p in presets if p.get("id") != preset_id]
    if len(new_presets) == len(presets):
        raise LlmPresetError("未找到该预设")
    _save_llm_presets_raw(db, new_presets)
    active_id = get(db, _LLM_ACTIVE_PRESET_ID_KEY)
    if active_id == preset_id:
        set(db, _LLM_ACTIVE_PRESET_ID_KEY, None)


def activate_llm_preset(db: Session, preset_id: str) -> None:
    presets = _load_llm_presets_raw(db)
    preset = next((p for p in presets if p.get("id") == preset_id), None)
    if preset is None:
        raise LlmPresetError("未找到该预设")

    if preset.get("llm_api_key"):
        set(db, "llm_api_key", preset["llm_api_key"])
    if preset.get("llm_api_base_url"):
        set(db, "llm_api_base_url", preset["llm_api_base_url"])
    if preset.get("llm_model"):
        set(db, "llm_model", preset["llm_model"])
    set(db, _LLM_ACTIVE_PRESET_ID_KEY, preset_id)


def get_sms_config(db: Session | None = None) -> dict | None:
    with _db_ctx(db) as session:
        cfg = {
            "vendor": get(session, "sms_vendor"),
            "access_key_id": get(session, "sms_access_key_id"),
            "access_key_secret": get(session, "sms_access_key_secret"),
            "endpoint": get(session, "sms_endpoint"),
            "sign_name": get(session, "sms_sign_name"),
            "template_code": get(session, "sms_template_code"),
            "sdk_app_id": get(session, "sms_sdk_app_id"),
            "region": get(session, "sms_region"),
        }
        if not cfg["access_key_id"]:
            return None
        return cfg


def get_smtp_config(db: Session | None = None) -> dict | None:
    with _db_ctx(db) as session:
        cfg = {
            "smtp_host": get(session, "smtp_host"),
            "smtp_port": get(session, "smtp_port"),
            "from_email": get(session, "smtp_from_email"),
            "email_password": get(session, "email_password"),
            "sender_name": get(session, "smtp_sender_name"),
        }
        if not cfg["smtp_host"] or not cfg["from_email"]:
            return None
        return cfg


def get_rate_limit_config(db: Session | None = None) -> dict:
    with _db_ctx(db) as session:
        return {
            "daily_limit": int(get(session, "rate_limit_daily") or 100),
            "weekly_limit": int(get(session, "rate_limit_weekly") or 500),
        }


def get_verification_config(db: Session | None = None) -> dict:
    with _db_ctx(db) as session:
        return {
            "expire_minutes": int(get(session, "vc_expire_minutes") or 10),
            "resend_interval_seconds": int(get(session, "vc_resend_interval_seconds") or 60),
            "code_length": int(get(session, "vc_code_length") or 6),
        }


class _db_ctx:
    """Context manager: use provided session or create a temporary one."""

    def __init__(self, db: Session | None):
        self._db = db
        self._owned = db is None

    def __enter__(self):
        if self._owned:
            self._db = SessionLocal()
        return self._db

    def __exit__(self, *_):
        if self._owned and self._db:
            self._db.close()
