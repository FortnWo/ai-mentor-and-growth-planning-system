from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy.orm import Session


@contextmanager
def session_scope(*, commit: bool = True) -> Iterator[Session]:
    """Provide a short-lived database session with automatic commit/rollback/close."""
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        yield db
        if commit:
            db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
