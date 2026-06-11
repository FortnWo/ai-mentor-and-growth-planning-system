"""Tests for LLM preset management and masked AI config read."""

from app.core.config import settings
from app.services import system_config_service as scs

from tests.test_user import admin_headers, make_student_payload

FULL_SECRET = "sk-test-secret-key-abcdefghijklmnop"


def _seed_active_ai_config(client):
    response = client.put(
        "/admin/system/ai-config",
        json={
            "llm_api_key": FULL_SECRET,
            "llm_api_base_url": "https://api.openai.com/v1",
            "llm_model": "gpt-4o",
        },
        headers=admin_headers(client),
    )
    assert response.status_code == 200


def test_ai_config_returns_masked_key_not_plaintext(client):
    _seed_active_ai_config(client)
    response = client.get("/admin/system/ai-config", headers=admin_headers(client))
    assert response.status_code == 200
    data = response.json()
    assert data["llm_api_key_set"] is True
    assert data["llm_api_key_masked"] is not None
    assert FULL_SECRET not in data["llm_api_key_masked"]
    assert data["llm_api_key_masked"].startswith("sk-t")
    assert data["llm_api_key_masked"].endswith("mnop")


def test_llm_preset_crud_activate(client, db_session):
    _seed_active_ai_config(client)
    headers = admin_headers(client)

    create_response = client.post(
        "/admin/system/llm-presets",
        json={
            "name": "OpenAI Primary",
            "llm_api_key": "sk-preset-only-key-12345678",
            "llm_api_base_url": "https://api.example.com/v1",
            "llm_model": "gpt-4o-mini",
        },
        headers=headers,
    )
    assert create_response.status_code == 201
    preset = create_response.json()
    preset_id = preset["id"]
    assert preset["name"] == "OpenAI Primary"
    assert preset["llm_model"] == "gpt-4o-mini"
    assert FULL_SECRET not in (preset.get("llm_api_key_masked") or "")
    assert "sk-p" in preset["llm_api_key_masked"]

    list_response = client.get("/admin/system/llm-presets", headers=headers)
    assert list_response.status_code == 200
    presets = list_response.json()["presets"]
    assert len(presets) == 1
    assert FULL_SECRET not in str(presets)

    activate_response = client.post(
        f"/admin/system/llm-presets/{preset_id}/activate",
        headers=headers,
    )
    assert activate_response.status_code == 200

    cfg_response = client.get("/admin/system/ai-config", headers=headers)
    cfg = cfg_response.json()
    assert cfg["llm_model"] == "gpt-4o-mini"
    assert cfg["llm_api_base_url"] == "https://api.example.com/v1"
    assert cfg["active_preset_id"] == preset_id
    assert scs.get(db_session, "llm_model") == "gpt-4o-mini"

    delete_response = client.delete(
        f"/admin/system/llm-presets/{preset_id}",
        headers=headers,
    )
    assert delete_response.status_code == 200
    assert client.get("/admin/system/llm-presets", headers=headers).json()["presets"] == []


def test_create_preset_reuses_active_key_when_omitted(client):
    _seed_active_ai_config(client)
    headers = admin_headers(client)

    response = client.post(
        "/admin/system/llm-presets",
        json={
            "name": "From Active",
            "llm_api_base_url": "https://api.openai.com/v1",
            "llm_model": "gpt-4o",
        },
        headers=headers,
    )
    assert response.status_code == 201
    assert response.json()["llm_api_key_set"] is True


def test_duplicate_preset_name_returns_409(client):
    _seed_active_ai_config(client)
    headers = admin_headers(client)
    payload = {
        "name": "Duplicate",
        "llm_api_key": "sk-dup-key-1234567890",
        "llm_model": "gpt-4o",
    }
    assert client.post("/admin/system/llm-presets", json=payload, headers=headers).status_code == 201
    dup = client.post("/admin/system/llm-presets", json=payload, headers=headers)
    assert dup.status_code == 409


def test_max_presets_limit(client):
    _seed_active_ai_config(client)
    headers = admin_headers(client)
    for i in range(10):
        response = client.post(
            "/admin/system/llm-presets",
            json={
                "name": f"Preset {i}",
                "llm_api_key": f"sk-preset-{i:02d}-abcdefghij",
                "llm_model": f"model-{i}",
            },
            headers=headers,
        )
        assert response.status_code == 201

    overflow = client.post(
        "/admin/system/llm-presets",
        json={
            "name": "Preset 11",
            "llm_api_key": "sk-preset-11-abcdefghij",
            "llm_model": "model-11",
        },
        headers=headers,
    )
    assert overflow.status_code == 400


def test_activate_preset_effective_when_env_empty(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "LLM_API_KEY", None)
    monkeypatch.setattr(settings, "LLM_API_BASE_URL", None)
    monkeypatch.setattr(settings, "LLM_MODEL", None)
    headers = admin_headers(client)

    create_response = client.post(
        "/admin/system/llm-presets",
        json={
            "name": "DB Only",
            "llm_api_key": "sk-preset-only-key-12345678",
            "llm_api_base_url": "https://preset.example.com/v1",
            "llm_model": "preset-model",
        },
        headers=headers,
    )
    assert create_response.status_code == 201
    preset_id = create_response.json()["id"]

    activate_response = client.post(
        f"/admin/system/llm-presets/{preset_id}/activate",
        headers=headers,
    )
    assert activate_response.status_code == 200

    assert scs.resolve_llm_model(db_session) == "preset-model"
    assert scs.resolve_llm_api_base_url(db_session) == "https://preset.example.com/v1"
    assert scs.is_llm_configured(db_session) is True

    cfg = client.get("/admin/system/ai-config", headers=headers).json()
    assert cfg["effective_llm_model"] == "preset-model"
    assert cfg["effective_llm_api_base_url"] == "https://preset.example.com/v1"
    assert cfg["effective_llm_api_key_set"] is True
    assert cfg["llm_config_source"]["llm_model"] == "db"


def test_limited_admin_cannot_manage_llm_presets(client):
    headers = admin_headers(client)
    create_user = client.post(
        "/admin/users",
        json=make_student_payload(11),
        headers=headers,
    )
    user_id = create_user.json()["id"]
    client.patch(
        f"/admin/users/{user_id}/admin-access",
        json={"permission_level": "limited", "permissions": ["user.read"]},
        headers=headers,
    )
    limited_login = client.post(
        "/auth/login",
        json={"username": "2022025311", "password": "Student@12345"},
    )
    limited_headers = {"Authorization": f"Bearer {limited_login.json()['access_token']}"}

    assert client.get("/admin/system/llm-presets", headers=limited_headers).status_code == 403
    assert (
        client.post(
            "/admin/system/llm-presets",
            json={"name": "X", "llm_api_key": "sk-x", "llm_model": "m"},
            headers=limited_headers,
        ).status_code
        == 403
    )
