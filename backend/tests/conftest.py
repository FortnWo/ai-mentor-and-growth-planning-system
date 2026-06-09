import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ["UKL_ENABLED"] = "false"
os.environ["CHAT_SESSION_SUMMARY_ENABLED"] = "false"
os.environ["ACTION_PLAN_COMPLETION_ASYNC"] = "false"
os.environ.setdefault("AUTH_SECRET_KEY", "test-secret-key-test-secret-key-test-secret-key")
os.environ.setdefault("AUTH_ALGORITHM", "HS256")
os.environ.setdefault("AUTH_ACCESS_TOKEN_EXPIRES_MINUTES", "120")
os.environ.setdefault("BOOTSTRAP_ADMIN_USERNAME", "admin")
os.environ.setdefault("BOOTSTRAP_ADMIN_EMAIL", "admin@example.com")
os.environ.setdefault("BOOTSTRAP_ADMIN_PASSWORD", "Admin@12345")
os.environ.setdefault("BOOTSTRAP_ADMIN_FULL_NAME", "System Administrator")

from app.core.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import ChatMessage, ChatSession, User  # noqa: F401, E402
from app.models.system_config import AIUsageLog, SystemConfig  # noqa: F401, E402
from app.models.ukl_slice import UklSlice  # noqa: F401, E402
from app.models.chat_session_summary import ChatSessionSummary  # noqa: F401, E402
import app.core.database as database_module  # noqa: E402
import app.core.bootstrap as bootstrap_module  # noqa: E402
import app.main as app_module  # noqa: E402

TEST_DATABASE_URL = "sqlite+pysqlite:///:memory:"
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

database_module.engine = engine
database_module.SessionLocal = TestingSessionLocal
bootstrap_module.SessionLocal = TestingSessionLocal
app_module.engine = engine


@pytest.fixture(autouse=True)
def sync_ai_worker(monkeypatch):
    """Run queued AI worker tasks inline (after the HTTP request releases DB sessions)."""
    from concurrent.futures import Future

    import app.core.ai_worker as ai_worker_module

    def submit_sync(fn, /, *args, **kwargs):
        future: Future = Future()
        try:
            future.set_result(fn(*args, **kwargs))
        except Exception as exc:
            future.set_exception(exc)
        return future

    monkeypatch.setattr(ai_worker_module, "submit_ai_task", submit_sync)


@pytest.fixture()
def db_session():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def client(db_session):
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
