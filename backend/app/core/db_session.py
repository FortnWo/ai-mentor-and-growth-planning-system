"""数据库会话上下文管理。

后台 AI 任务与编排器使用 session_scope 获取独立短生命周期 Session，
避免与请求级 get_db 会话混用；默认退出时 commit，异常时 rollback。
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy.orm import Session


@contextmanager
def session_scope(*, commit: bool = True) -> Iterator[Session]:
    """提供短生命周期数据库会话，正常退出时 commit，异常时 rollback 并关闭。"""
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
