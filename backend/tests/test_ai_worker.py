import threading
import time

from app.core.ai_worker import submit_ai_task


def test_submit_ai_task_runs_function(monkeypatch):
    completed = threading.Event()
    result_box: dict[str, str] = {}

    def worker(value: str) -> None:
        result_box["value"] = value
        completed.set()

    submit_ai_task(worker, "ok")
    assert completed.wait(timeout=2)
    assert result_box["value"] == "ok"
