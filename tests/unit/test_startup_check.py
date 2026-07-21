"""Tests for source-launch environment checks and failure reporting."""

from pathlib import Path
from unittest.mock import patch

from src.app.startup_check import (
    EnvironmentCheck,
    check_environment,
    format_environment_error,
    write_startup_failure,
)


def test_check_environment_accepts_installed_runtime() -> None:
    """The active test environment should satisfy all runtime checks."""
    assert check_environment().ok


def test_check_environment_lists_missing_modules() -> None:
    """Missing modules should be reported with their distribution labels."""
    with patch("src.app.startup_check.importlib.util.find_spec", return_value=None):
        result = check_environment()

    assert not result.ok
    assert "PySide6" in result.errors[-1]
    assert "python-multipart" in result.errors[-1]


def test_format_environment_error_includes_recovery_command() -> None:
    """Preflight errors should tell users how to repair the environment."""
    message = format_environment_error(EnvironmentCheck(("Missing example.",)))

    assert "Missing example." in message
    assert "python -m pip install -r requirements.txt" in message


def test_write_startup_failure_uses_log_directory(tmp_path: Path) -> None:
    """Startup diagnostics should be written to the resolved log directory."""
    with patch("src.app.startup_check.get_log_directory", return_value=tmp_path):
        result = write_startup_failure("Visible message", "Traceback details")

    assert result == tmp_path / "startup_error.log"
    assert result.read_text(encoding="utf-8") == (
        "Visible message\n\nTraceback details\n"
    )
