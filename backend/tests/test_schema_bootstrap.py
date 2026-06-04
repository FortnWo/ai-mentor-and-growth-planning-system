from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.core.schema_bootstrap import ensure_database_schema


def test_ensure_database_schema_adds_risk_flag_when_missing():
    engine = MagicMock()
    insp = MagicMock()
    insp.get_table_names.return_value = ["users", "system_config", "ai_usage_logs", "verification_codes"]
    insp.get_columns.return_value = [{"name": "id"}, {"name": "username"}]

    with patch("app.core.schema_bootstrap.inspect", return_value=insp):
        ensure_database_schema(engine)

    assert engine.begin.called
