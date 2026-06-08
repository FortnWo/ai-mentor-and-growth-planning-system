from __future__ import annotations

from app.core.config import settings
from app.services import system_config_service as scs


def test_resolve_llm_system_prompt_uses_settings_default(db_session):
    assert scs.resolve_llm_system_prompt(db_session) == settings.LLM_SYSTEM_PROMPT


def test_resolve_llm_system_prompt_prefers_db_override(db_session):
    scs.set(db_session, "llm_system_prompt", "DB mentor prompt")
    assert scs.resolve_llm_system_prompt(db_session) == "DB mentor prompt"


def test_resolve_admin_llm_system_prompt_uses_settings_default(db_session):
    assert scs.resolve_admin_llm_system_prompt(db_session) == settings.ADMIN_LLM_SYSTEM_PROMPT


def test_resolve_admin_llm_system_prompt_prefers_db_override(db_session):
    scs.set(db_session, "admin_llm_system_prompt", "DB admin prompt")
    assert scs.resolve_admin_llm_system_prompt(db_session) == "DB admin prompt"
