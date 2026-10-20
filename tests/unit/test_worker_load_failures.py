"""Contracts for the bounded simple-load failure reporting family."""

import logging
import sqlite3
from unittest.mock import MagicMock, call

import pytest

from src.services.db_service import DatabaseService
from src.services.worker import DatabaseWorker

pytestmark = pytest.mark.ci_fast


@pytest.mark.parametrize("family", ["events", "entities", "maps"])
@pytest.mark.parametrize(
    "scenario",
    ["data", "empty", "unavailable", "refresh", "operational", "unexpected"],
)
def test_simple_load_contract(family, scenario, caplog, tmp_path):
    """Success, absence and failure have distinct ordered signal contracts."""
    secret = "PRIVATE_MANUSCRIPT_TOKEN_url?credential=secret"
    database_path = tmp_path / "PRIVATE_DATABASE_PATH.kraken"
    worker = DatabaseWorker(str(database_path))
    database = MagicMock(spec=DatabaseService)
    worker.db_service = None if scenario == "unavailable" else database
    observed = []
    payload = (
        [{"id": "synthetic-id", "description": secret}] if scenario == "data" else []
    )
    error = (
        RuntimeError(secret)
        if scenario == "unexpected"
        else sqlite3.OperationalError(secret)
    )

    def refresh():
        observed.append(("refresh", None))
        if scenario == "refresh":
            raise error

    def query():
        observed.append(("query", None))
        if scenario in {"operational", "unexpected"}:
            raise error
        return payload

    database.ensure_fresh_view.side_effect = refresh
    getattr(database, f"get_all_{family}").side_effect = query
    signals = {
        "operation_started": "started",
        f"{family}_loaded": "loaded",
        "operation_finished": "finished",
        "error_occurred": "error",
        "dataset_load_failed": "failed",
    }
    for signal, label in signals.items():
        getattr(worker, signal).connect(
            lambda value, label=label: observed.append((label, value))
        )

    with caplog.at_level(logging.ERROR, logger="src.services.worker"):
        getattr(worker, f"load_{family}")()

    expected = []
    calls = []
    if scenario != "unavailable":
        calls.append(call.ensure_fresh_view())
        expected.append(("refresh", None))
        if scenario != "refresh":
            calls.append(getattr(call, f"get_all_{family}")())
            expected.extend(
                [("started", f"Loading {family.title()}..."), ("query", None)]
            )
        if scenario in {"data", "empty"}:
            expected.extend(
                [("loaded", payload), ("finished", f"{family.title()} Loaded.")]
            )
        else:
            expected.append(("error", f"Failed to load {family}."))
            expected.append(("failed", family))
    assert observed == expected
    assert database.mock_calls == calls

    records = [r for r in caplog.records if r.name == "src.services.worker"]
    if scenario in {"refresh", "operational", "unexpected"}:
        assert len(records) == 1
        record = records[0]
        message = record.getMessage()
        assert record.levelno == logging.ERROR
        assert f"operation=load_{family}" in message
        assert f"error_type={type(error).__name__}" in message
        frame = "refresh" if scenario == "refresh" else "query"
        assert "stack=worker.py:" in message
        assert f":{frame}" in message
        assert "test_worker_load_failures.py:" in message
        assert record.exc_info is None
        assert record.exc_text is None
        assert secret not in message
        assert str(database_path) not in message
        assert "PRIVATE_DATABASE_PATH" not in message
        assert "raise error" not in message
        assert secret not in repr(observed)
    else:
        assert records == []
