from __future__ import annotations

from app.core.config import settings
from app.services import system_config_service as scs


def test_resolve_llm_model_prefers_env_over_db(db_session, monkeypatch):
    monkeypatch.setattr(settings, "LLM_MODEL", "env-model")
    scs.set(db_session, "llm_model", "db-model")
    assert scs.resolve_llm_model(db_session) == "env-model"
    assert scs.get_llm_config_source(db_session)["llm_model"] == "env"


def test_resolve_llm_model_uses_db_when_env_empty(db_session, monkeypatch):
    monkeypatch.setattr(settings, "LLM_MODEL", None)
    scs.set(db_session, "llm_model", "db-model")
    assert scs.resolve_llm_model(db_session) == "db-model"
    assert scs.get_llm_config_source(db_session)["llm_model"] == "db"


def test_is_llm_configured_false_when_all_unset(db_session, monkeypatch):
    monkeypatch.setattr(settings, "LLM_API_KEY", None)
    monkeypatch.setattr(settings, "LLM_API_BASE_URL", None)
    monkeypatch.setattr(settings, "LLM_MODEL", None)
    assert scs.is_llm_configured(db_session) is False


def test_is_llm_configured_true_from_db_only(db_session, monkeypatch):
    monkeypatch.setattr(settings, "LLM_API_KEY", None)
    monkeypatch.setattr(settings, "LLM_API_BASE_URL", None)
    monkeypatch.setattr(settings, "LLM_MODEL", None)
    scs.set(db_session, "llm_api_key", "sk-db-only-key-12345678")
    scs.set(db_session, "llm_api_base_url", "https://db.example.com/v1")
    scs.set(db_session, "llm_model", "db-only-model")
    assert scs.is_llm_configured(db_session) is True


def test_get_effective_ai_config_matches_resolve(db_session, monkeypatch):
    monkeypatch.setattr(settings, "LLM_API_KEY", None)
    monkeypatch.setattr(settings, "LLM_API_BASE_URL", "https://env.example.com/v1")
    monkeypatch.setattr(settings, "LLM_MODEL", None)
    scs.set(db_session, "llm_api_key", "sk-db-key-123456789012")
    scs.set(db_session, "llm_model", "db-model")

    effective = scs.get_effective_ai_config(db_session)
    assert effective["llm_api_key"] == "sk-db-key-123456789012"
    assert effective["llm_api_base_url"] == "https://env.example.com/v1"
    assert effective["llm_model"] == "db-model"
