"""Basic smoke tests for the FastAPI application (no DB required)."""
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_ping():
    response = client.get("/ping")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["message"] == "pong"
