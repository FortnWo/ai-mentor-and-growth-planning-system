import pytest
from sqlalchemy import text

from app.core.db_session import session_scope


def test_session_scope_commits(db_session):
    with session_scope() as db:
        db.execute(text("SELECT 1"))

    with session_scope() as db:
        result = db.execute(text("SELECT 1")).scalar()
        assert result == 1


def test_session_scope_rolls_back_on_error(db_session):
    with pytest.raises(RuntimeError):
        with session_scope() as db:
            db.execute(text("SELECT 1"))
            raise RuntimeError("boom")
