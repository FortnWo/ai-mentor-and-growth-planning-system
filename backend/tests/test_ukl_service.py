import json

import pytest

from app.core.config import settings
from app.core.ukl_constants import REF_TYPE_USER, SCENE_CHAT, SLICE_TYPE_PROFILE
from app.models.ukl_slice import UklSlice
from app.models.user import User
from app.schemas.profile import UserProfileUpdate
from app.services import profile_service, ukl_service


@pytest.fixture
def sample_user(db_session):
    user = User(
        username="ukl_user",
        email="ukl@example.com",
        password_hash="hashed",
        role="user",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_ingest_profile_and_get_latest_slice(db_session, sample_user, monkeypatch):
    monkeypatch.setattr(settings, "UKL_ENABLED", False)

    profile = profile_service.get_or_create_profile_for_user(db_session, sample_user.id)
    profile.interests = ["reading", "math"]
    profile.skills = ["python"]
    db_session.commit()

    profile_service.refresh_portrait_summary_for_user(db_session, sample_user.id)

    row = ukl_service.ingest_profile_from_user(db_session, sample_user.id)
    db_session.commit()

    assert row.slice_type == SLICE_TYPE_PROFILE
    assert row.ref_type == REF_TYPE_USER
    assert row.ref_id == sample_user.id
    assert row.version == 1

    payload = json.loads(row.payload)
    assert payload["fields"]["interests"] == ["reading", "math"]
    assert payload["fields"]["skills"] == ["python"]
    assert payload["snapshot"]

    latest = ukl_service.get_latest_slice(
        db_session,
        sample_user.id,
        SLICE_TYPE_PROFILE,
        ref_type=REF_TYPE_USER,
        ref_id=sample_user.id,
    )
    assert latest is not None
    assert latest.id == row.id


def test_ingest_profile_upserts_and_increments_version(db_session, sample_user, monkeypatch):
    monkeypatch.setattr(settings, "UKL_ENABLED", False)

    first = ukl_service.ingest_profile_from_user(db_session, sample_user.id)
    db_session.commit()
    assert first.version == 1

    profile = profile_service.get_or_create_profile_for_user(db_session, sample_user.id)
    profile.goals = ["graduate school"]
    db_session.commit()
    profile_service.refresh_portrait_summary_for_user(db_session, sample_user.id)

    second = ukl_service.ingest_profile_from_user(db_session, sample_user.id)
    db_session.commit()
    assert second.id == first.id
    assert second.version == 2

    count = db_session.query(UklSlice).filter(UklSlice.user_id == sample_user.id).count()
    assert count == 1


def test_assemble_context_chat_with_profile_slice(db_session, sample_user, monkeypatch):
    monkeypatch.setattr(settings, "UKL_ENABLED", False)

    profile = profile_service.get_or_create_profile_for_user(db_session, sample_user.id)
    profile.personality = ["curious"]
    db_session.commit()
    profile_service.refresh_portrait_summary_for_user(db_session, sample_user.id)
    ukl_service.ingest_profile_from_user(db_session, sample_user.id)
    db_session.commit()

    bundle = ukl_service.assemble_context(db_session, sample_user.id, SCENE_CHAT)
    assert bundle.scene == SCENE_CHAT
    assert len(bundle.narrative_blocks) == 1
    assert bundle.anchors["profile_fields"]["personality"] == ["curious"]
    assert isinstance(bundle.anchors["traits"], list)


def test_assemble_context_chat_empty_when_no_slice(db_session, sample_user):
    bundle = ukl_service.assemble_context(db_session, sample_user.id, SCENE_CHAT)
    assert bundle.scene == SCENE_CHAT
    assert bundle.narrative_blocks == []
    assert bundle.anchors == {}


def test_assemble_context_unknown_scene_raises(db_session, sample_user):
    with pytest.raises(ValueError, match="Unsupported UKL assemble scene"):
        ukl_service.assemble_context(db_session, sample_user.id, "planning_loop")


def test_profile_update_skips_ukl_when_disabled(db_session, sample_user, monkeypatch):
    monkeypatch.setattr(settings, "UKL_ENABLED", False)

    profile_service.update_profile_for_user(
        db_session,
        sample_user.id,
        UserProfileUpdate(interests=["music"]),
    )

    count = db_session.query(UklSlice).filter(UklSlice.user_id == sample_user.id).count()
    assert count == 0


def test_profile_update_writes_ukl_when_enabled(db_session, sample_user, monkeypatch):
    monkeypatch.setattr(settings, "UKL_ENABLED", True)

    profile_service.update_profile_for_user(
        db_session,
        sample_user.id,
        UserProfileUpdate(interests=["music"]),
    )

    row = ukl_service.get_latest_slice(
        db_session,
        sample_user.id,
        SLICE_TYPE_PROFILE,
        ref_type=REF_TYPE_USER,
        ref_id=sample_user.id,
    )
    assert row is not None
    payload = json.loads(row.payload)
    assert payload["fields"]["interests"] == ["music"]
