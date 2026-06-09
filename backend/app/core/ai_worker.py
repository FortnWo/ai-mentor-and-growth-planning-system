from __future__ import annotations

import atexit
import logging
from concurrent.futures import Future, ThreadPoolExecutor
from threading import Lock
from typing import Any, Callable

from app.core.config import settings

logger = logging.getLogger("ai_mentor.ai_worker")

_executor: ThreadPoolExecutor | None = None
_lock = Lock()


def _get_executor() -> ThreadPoolExecutor:
    global _executor
    with _lock:
        if _executor is None:
            max_workers = max(int(settings.AI_BACKGROUND_MAX_WORKERS), 1)
            _executor = ThreadPoolExecutor(
                max_workers=max_workers,
                thread_name_prefix="ai-worker",
            )
            atexit.register(shutdown_ai_worker)
        return _executor


def submit_ai_task(fn: Callable[..., Any], /, *args: Any, **kwargs: Any) -> Future[Any]:
    """Submit a background AI-heavy task to the bounded worker pool."""
    return _get_executor().submit(fn, *args, **kwargs)


def shutdown_ai_worker(*, wait: bool = False) -> None:
    global _executor
    with _lock:
        if _executor is not None:
            logger.debug("Shutting down AI worker pool wait=%s", wait)
            _executor.shutdown(wait=wait, cancel_futures=False)
            _executor = None
