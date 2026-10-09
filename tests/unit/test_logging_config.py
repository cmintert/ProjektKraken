"""Focused regression tests for best-effort application logging."""

import logging
import os
from unittest.mock import patch

import pytest

from src.core import logging_config


@pytest.fixture(autouse=True)
def restore_logging():
    """Keep logging configuration changes local to each test."""
    root = logging.getLogger()
    original_level = root.level
    yield
    for logger in list(logging_config._owned_handlers):
        logging_config._replace_owned_handlers(logger)
    root.setLevel(original_level)


def test_reconfiguration_closes_owned_files_and_preserves_foreign_handler(tmp_path):
    """Repeated setup closes old files and keeps unrelated root handlers."""
    foreign = logging.NullHandler()
    root = logging.getLogger()
    root.addHandler(foreign)
    try:
        with patch.object(logging_config, "LOG_DIR", str(tmp_path)):
            logging_config.setup_logging(log_to_console=False)
            first = logging_config._owned_handlers[root][0]
            assert first.stream is not None
            logging_config.setup_logging(log_to_console=False)
            second = logging_config._owned_handlers[root][0]
            assert first is not second
            assert first.stream is None
            assert root.handlers.count(second) == 1
            assert foreign in root.handlers
    finally:
        root.removeHandler(foreign)


def test_rotation_suspends_and_retries_without_growing_file(tmp_path, monkeypatch):
    """A persistent rollover lock drops records until a timed retry succeeds."""
    path = tmp_path / "kraken.test.log"
    handler = logging_config.SafeRotatingFileHandler(
        str(path), maxBytes=80, backupCount=1, encoding="utf-8", delay=False
    )
    handler.setFormatter(logging.Formatter("%(message)s"))
    clock = [100.0]
    monkeypatch.setattr(logging_config.time, "monotonic", lambda: clock[0])
    record = logging.makeLogRecord({"msg": "x" * 60, "levelno": logging.INFO})
    try:
        handler.emit(record)
        original_size = path.stat().st_size
        with patch.object(
            handler, "doRollover", side_effect=PermissionError("locked")
        ) as roll:
            for _ in range(5):
                handler.emit(record)
            assert roll.call_count == 1
            assert path.stat().st_size == original_size
            assert path.with_suffix(".logging-error.txt").exists()
            clock[0] += logging_config.ROTATION_RETRY_SECONDS
            handler.emit(record)
            assert roll.call_count == 2
            assert path.stat().st_size == original_size
        clock[0] += logging_config.ROTATION_RETRY_SECONDS
        handler.emit(record)
        assert path.stat().st_size == original_size
        assert (tmp_path / "kraken.test.log.1").exists()
    finally:
        handler.close()


def test_unwritable_portable_directory_uses_user_data(tmp_path, monkeypatch):
    """The fallback path is stable and never depends on the current directory."""
    fallback = tmp_path / "user-data"

    def inaccessible() -> str:
        raise PermissionError("portable logs denied")

    monkeypatch.setattr(logging_config, "_resolve_log_directory", inaccessible)
    monkeypatch.setattr(
        logging_config, "get_user_data_path", lambda filename: str(fallback / filename)
    )
    logging_config.setup_logging(log_to_console=False)
    handler = logging_config._owned_handlers[logging.getLogger()][0]
    assert os.path.dirname(handler.baseFilename) == str(fallback / "logs")
    assert not (tmp_path / logging_config.LOG_FILENAME).exists()


def test_missing_stderr_and_unwritable_destinations_do_not_raise(monkeypatch):
    """A GUI process without stderr remains usable when all logging fails."""
    monkeypatch.setattr(logging_config.sys, "stderr", None)
    monkeypatch.setattr(
        logging_config,
        "_resolve_log_directory",
        lambda: (_ for _ in ()).throw(PermissionError("portable denied")),
    )
    monkeypatch.setattr(
        logging_config,
        "get_user_data_path",
        lambda filename: (_ for _ in ()).throw(PermissionError("fallback denied")),
    )
    logging_config.setup_logging(log_to_console=True)
    logging.getLogger("test-logging-failure").error("save still succeeds")


def test_processes_get_distinct_diagnostic_and_audit_paths(tmp_path):
    """Two process identities must never select the same rotation destination."""
    with patch.object(logging_config, "LOG_DIR", str(tmp_path)):
        with patch.object(logging_config.os, "getpid", return_value=100):
            logging_config.setup_logging(log_to_console=False)
            first = logging_config._owned_handlers[logging.getLogger()][0].baseFilename
            first_audit = logging_config.get_world_audit_log_path("/world/test.kraken")
        with patch.object(logging_config.os, "getpid", return_value=200):
            logging_config.setup_logging(log_to_console=False)
            second = logging_config._owned_handlers[logging.getLogger()][0].baseFilename
            second_audit = logging_config.get_world_audit_log_path("/world/test.kraken")
    assert first != second
    assert first_audit != second_audit
