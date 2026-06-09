from datetime import date

import pytest

from app.core.config import settings
from app.core.ukl_constants import REF_TYPE_RECORD, SCENE_FEEDBACK, SLICE_TYPE_GROWTH_JOURNAL
from app.models.growth_record import GrowthRecord, GrowthRecordType
from app.models.user import User
from app.services import growth_record_service, growth_summary_service, ukl_growth_service, ukl_service


@pytest.fixture
def sample_user(db_session):
    user = User(
        username="ukl3_growth",
        email="ukl3growth@example.com",
        password_hash="hashed",
        role="user",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_ingest_growth_journal_for_record(db_session, sample_user, monkeypatch):
    monkeypatch.setattr(settings, "UKL_ENABLED", True)
    monkeypatch.setattr(settings, "GROWTH_JOURNAL_ENABLED", True)

    from app.services import ai_service

    monkeypatch.setattr(
        ai_service,
        "build_growth_journal_response",
        lambda msg: "今天完成了一次专注学习，状态不错。",
    )

    record = growth_record_service.create_growth_record(
        db_session,
        sample_user.id,
        title="完成阅读",
        summary="读了 20 页",
        record_type=GrowthRecordType.MANUAL.value,
        commit=True,
    )

    ukl_growth_service.ingest_growth_journal_for_record(db_session, sample_user.id, record.id)

    row = ukl_service.get_latest_slice(
        db_session,
        sample_user.id,
        SLICE_TYPE_GROWTH_JOURNAL,
        ref_type=REF_TYPE_RECORD,
        ref_id=record.id,
    )
    assert row is not None
    assert "专注学习" in row.payload or "读了" in row.payload


def test_assemble_context_feedback_includes_records_and_journals(
    db_session, sample_user, monkeypatch
):
    monkeypatch.setattr(settings, "UKL_ENABLED", True)
    monkeypatch.setattr(settings, "GROWTH_JOURNAL_ENABLED", True)

    from app.services import ai_service

    monkeypatch.setattr(
        ai_service,
        "build_growth_journal_response",
        lambda msg: "本周坚持打卡，节奏稳定。",
    )

    start = date(2026, 6, 1)
    end = date(2026, 6, 7)
    record = growth_record_service.create_growth_record(
        db_session,
        sample_user.id,
        title="周记",
        summary="不错的一周",
        record_type=GrowthRecordType.MANUAL.value,
        record_date=start.isoformat(),
        commit=True,
    )
    ukl_growth_service.ingest_growth_journal_for_record(db_session, sample_user.id, record.id)

    bundle = ukl_service.assemble_context(
        db_session,
        sample_user.id,
        SCENE_FEEDBACK,
        start_date=start,
        end_date=end,
    )
    assert bundle.scene == SCENE_FEEDBACK
    records = bundle.anchors.get("entity_hints", {}).get("records", [])
    assert any(r["id"] == record.id for r in records)
    assert bundle.anchors.get("growth_journals")


def test_weekly_summary_ukl_prompt_contains_section(db_session, sample_user, monkeypatch):
    monkeypatch.setattr(settings, "UKL_ENABLED", True)

    from app.services import ai_service

    captured: dict[str, str] = {}

    def _capture(prompt: str) -> str:
        captured["prompt"] = prompt
        return "本周进步明显，下周继续保持。"

    monkeypatch.setattr(ai_service, "build_weekly_summary_response", _capture)

    growth_summary_service.create_weekly_summary(
        db_session,
        sample_user.id,
        date(2026, 6, 1),
        date(2026, 6, 7),
    )
    assert "[UKL 反馈上下文]" in captured.get("prompt", "")


def test_weekly_summary_legacy_when_ukl_disabled(db_session, sample_user, monkeypatch):
    monkeypatch.setattr(settings, "UKL_ENABLED", False)

    from app.services import chat_service

    captured: dict[str, str] = {}

    monkeypatch.setattr(chat_service, "build_ai_response", lambda msg: captured.setdefault("prompt", msg) or "ok")

    growth_summary_service.create_weekly_summary(
        db_session,
        sample_user.id,
        date(2026, 6, 1),
        date(2026, 6, 7),
    )
    assert "compassionate mentor" in captured.get("prompt", "")
    assert "[UKL" not in captured.get("prompt", "")
