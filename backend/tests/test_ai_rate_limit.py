from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.core.security import hash_password
from app.models.system_config import AIUsageLog
from app.models.user import User, UserRole
from app.services import ai_service, system_config_service as scs
from app.services.ai_rate_limit_service import AIRateLimitExceeded, assert_chat_allowed, sync_user_risk_flag
from tests.test_chat import create_user, login_user


def _make_user(db_session, *, username: str, role: UserRole = UserRole.USER) -> User:
    user = User(
        username=username,
        email=f"{username}@example.com",
        password_hash=hash_password("Student@12345"),
        role=role,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _seed_chat_logs(
    db_session,
    user_id: int,
    count: int,
    *,
    created_at: datetime | None = None,
    task: str = "chat",
) -> None:
    when = created_at or datetime.now()
    for _ in range(count):
        db_session.add(
            AIUsageLog(
                user_id=user_id,
                model="gpt-test",
                prompt_tokens=1,
                completion_tokens=1,
                task=task,
                created_at=when,
            )
        )
    db_session.commit()


def _set_limits(db_session, *, daily: int, weekly: int) -> None:
    scs.set(db_session, "rate_limit_daily", str(daily))
    scs.set(db_session, "rate_limit_weekly", str(weekly))


def test_assert_chat_allowed_under_limit_sets_risk_flag_zero(db_session):
    user = _make_user(db_session, username="student_ok")
    _set_limits(db_session, daily=10, weekly=50)
    _seed_chat_logs(db_session, user.id, 3)

    assert_chat_allowed(db_session, user)

    db_session.refresh(user)
    assert user.risk_flag == 0


def test_warning_threshold_sets_risk_flag_one(db_session):
    user = _make_user(db_session, username="student_warn")
    _set_limits(db_session, daily=10, weekly=50)
    _seed_chat_logs(db_session, user.id, 8)

    assert_chat_allowed(db_session, user)

    db_session.refresh(user)
    assert user.risk_flag == 1


def test_daily_limit_raises_and_sets_risk_flag_two(db_session):
    user = _make_user(db_session, username="student_daily")
    _set_limits(db_session, daily=5, weekly=50)
    _seed_chat_logs(db_session, user.id, 5)

    with pytest.raises(AIRateLimitExceeded) as exc_info:
        assert_chat_allowed(db_session, user)

    assert exc_info.value.reason == "daily"
    db_session.refresh(user)
    assert user.risk_flag == 2


def test_weekly_limit_raises(db_session):
    user = _make_user(db_session, username="student_weekly")
    _set_limits(db_session, daily=100, weekly=5)
    _seed_chat_logs(db_session, user.id, 5)

    with pytest.raises(AIRateLimitExceeded) as exc_info:
        assert_chat_allowed(db_session, user)

    assert exc_info.value.reason == "weekly"


def test_admin_is_exempt(db_session):
    admin = _make_user(db_session, username="admin_user", role=UserRole.ADMIN)
    _set_limits(db_session, daily=1, weekly=1)
    _seed_chat_logs(db_session, admin.id, 10)

    assert_chat_allowed(db_session, admin)


def test_non_chat_tasks_are_not_counted(db_session):
    user = _make_user(db_session, username="student_other_tasks")
    _set_limits(db_session, daily=2, weekly=10)
    _seed_chat_logs(db_session, user.id, 10, task="profile extraction")

    assert_chat_allowed(db_session, user)


def test_cross_day_resets_risk_flag(db_session):
    user = _make_user(db_session, username="student_reset")
    _set_limits(db_session, daily=5, weekly=50)
    yesterday = datetime.now() - timedelta(days=1)
    _seed_chat_logs(db_session, user.id, 5, created_at=yesterday)
    user.risk_flag = 2
    db_session.add(user)
    db_session.commit()

    new_flag = sync_user_risk_flag(db_session, user)

    assert new_flag == 0
    db_session.refresh(user)
    assert user.risk_flag == 0


def test_post_chat_returns_429_when_daily_limit_reached(client, db_session):
    user_id = create_user(client, 1)
    _set_limits(db_session, daily=2, weekly=100)
    _seed_chat_logs(db_session, user_id, 2)

    token = login_user(client, 1)
    response = client.post(
        "/chat",
        json={"message": "one more message"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 429
    assert "CHAT_R001" in response.json()["detail"]


def test_profile_extraction_not_rate_limited(monkeypatch, db_session):
    user = _make_user(db_session, username="student_profile")
    _set_limits(db_session, daily=1, weekly=1)
    _seed_chat_logs(db_session, user.id, 1)

    mock_client = MagicMock()
    mock_client.responses.create.return_value = SimpleNamespace(
        output_text='{"interests":[]}',
        usage=SimpleNamespace(input_tokens=1, output_tokens=1),
        output=[],
    )
    monkeypatch.setattr(ai_service, "_get_ai_client", lambda: mock_client)
    monkeypatch.setattr(ai_service.settings, "LLM_MODEL", "gpt-test", raising=False)

    result = ai_service.build_profile_extraction_response("extract profile")

    assert "interests" in result


def test_invoke_ai_chat_syncs_risk_flag_after_call(monkeypatch, db_session):
    user = _make_user(db_session, username="student_sync")
    _set_limits(db_session, daily=10, weekly=50)
    _seed_chat_logs(db_session, user.id, 8)

    mock_client = MagicMock()
    mock_client.responses.create.return_value = SimpleNamespace(
        output_text="ok",
        usage=SimpleNamespace(input_tokens=1, output_tokens=1),
        output=[],
    )
    monkeypatch.setattr(ai_service, "_get_ai_client", lambda: mock_client)
    monkeypatch.setattr(ai_service.settings, "LLM_MODEL", "gpt-test", raising=False)

    ai_service.build_chat_response("hello", db=db_session, user_id=user.id)

    db_session.refresh(user)
    assert user.risk_flag == 1
