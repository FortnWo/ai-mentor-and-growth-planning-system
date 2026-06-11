from __future__ import annotations

from datetime import timedelta

from app.services import verification_service as vs
from tests.test_user import admin_headers


def test_create_code_uses_db_expire_minutes(client, db_session):
    headers = admin_headers(client)
    response = client.put(
        "/admin/system/verification-config",
        json={
            "expire_minutes": 25,
            "resend_interval_seconds": 60,
            "code_length": 6,
        },
        headers=headers,
    )
    assert response.status_code == 200

    record = vs.create_code(db_session, user_id=1, code_type="email")
    delta = record.expires_at - record.created_at
    assert abs(delta - timedelta(minutes=25)) < timedelta(seconds=2)


def test_create_code_uses_db_code_length(client, db_session):
    headers = admin_headers(client)
    response = client.put(
        "/admin/system/verification-config",
        json={
            "expire_minutes": 10,
            "resend_interval_seconds": 60,
            "code_length": 8,
        },
        headers=headers,
    )
    assert response.status_code == 200

    record = vs.create_code(db_session, user_id=1, code_type="email")
    assert len(record.code) == 8
