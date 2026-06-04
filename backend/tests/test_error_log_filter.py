from __future__ import annotations

from datetime import date

from app.routers.admin_system import _filter_log_lines_by_date, _group_log_lines


def test_group_log_lines_attaches_traceback_to_header():
    lines = [
        "2026-06-04 10:00:00,123 ERROR app.main boom",
        "Traceback (most recent call last):",
        "  File \"app.py\", line 1",
        "2026-06-05 11:00:00,456 ERROR app.main later",
    ]
    groups = _group_log_lines(lines)
    assert len(groups) == 2
    assert len(groups[0]) == 3
    assert groups[0][0].startswith("2026-06-04")


def test_filter_log_lines_by_date_keeps_multiline_entries():
    lines = [
        "2026-06-04 10:00:00,123 ERROR app.main boom",
        "Traceback (most recent call last):",
        "2026-06-05 11:00:00,456 ERROR app.main later",
    ]
    filtered = _filter_log_lines_by_date(lines, date(2026, 6, 4))
    assert filtered == lines[:2]
