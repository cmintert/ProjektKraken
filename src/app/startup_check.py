"""Source-launch environment checks and startup failure reporting."""

from __future__ import annotations

import importlib.util
import os
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path

from src.core.paths import get_log_directory

MINIMUM_PYTHON = (3, 13)

# Distribution labels are user-facing; module names are used for lightweight checks.
REQUIRED_MODULES = (
    ("PySide6", "PySide6"),
    ("Pillow", "PIL"),
    ("python-dotenv", "dotenv"),
    ("NumPy", "numpy"),
    ("Requests", "requests"),
    ("Markdown", "markdown"),
    ("python-frontmatter", "frontmatter"),
    ("FastAPI", "fastapi"),
    ("Uvicorn", "uvicorn"),
    ("HTTPX", "httpx"),
    ("PyVis", "pyvis"),
    ("NetworkX", "networkx"),
    ("GeoJSON", "geojson"),
    ("python-multipart", "multipart"),
)


@dataclass(frozen=True)
class EnvironmentCheck:
    """Result of validating a source-development Python environment."""

    errors: tuple[str, ...]

    @property
    def ok(self) -> bool:
        """Return whether all required checks passed."""
        return not self.errors


def check_environment() -> EnvironmentCheck:
    """Check the Python version and required runtime modules without importing Qt."""
    errors: list[str] = []
    current = sys.version_info[:2]
    if current < MINIMUM_PYTHON:
        required = ".".join(str(part) for part in MINIMUM_PYTHON)
        found = ".".join(str(part) for part in current)
        errors.append(f"Python {required}+ is required; found Python {found}.")

    missing = [
        label
        for label, module_name in REQUIRED_MODULES
        if importlib.util.find_spec(module_name) is None
    ]
    if missing:
        errors.append("Missing runtime dependencies: " + ", ".join(missing) + ".")

    return EnvironmentCheck(tuple(errors))


def format_environment_error(check: EnvironmentCheck) -> str:
    """Build an actionable error message for a failed environment check."""
    details = "\n".join(f"- {error}" for error in check.errors)
    return (
        "ProjektKraken cannot start because the Python environment is incomplete.\n\n"
        f"{details}\n\n"
        "From the project folder, create or activate a Python 3.13 virtual "
        "environment and run:\n\n"
        "    python -m pip install -r requirements.txt"
    )


def write_startup_failure(message: str, details: str = "") -> Path | None:
    """Write a startup diagnostic file and return its path when successful."""
    try:
        path = get_log_directory() / "startup_error.log"
        content = message.rstrip()
        if details:
            content += f"\n\n{details.rstrip()}"
        path.write_text(content + "\n", encoding="utf-8")
        return path
    except OSError:
        return None


def report_startup_failure(message: str, details: str = "") -> None:
    """Show a useful startup error and persist the diagnostic details."""
    log_path = write_startup_failure(message, details)
    location = f"\n\nDetails were written to:\n{log_path}" if log_path else ""
    display_message = f"{message}{location}"
    print(display_message, file=sys.stderr)

    if sys.platform != "win32" or os.environ.get("PYTEST_CURRENT_TEST"):
        return

    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(  # type: ignore[attr-defined]
            0,
            display_message,
            "ProjektKraken could not start",
            0x10,
        )
    except (AttributeError, OSError):
        return


def report_unhandled_startup_exception(exc: BaseException) -> None:
    """Report an unexpected exception with a traceback and recovery guidance."""
    message = (
        "ProjektKraken encountered an unexpected startup error.\n\n"
        f"{type(exc).__name__}: {exc}\n\n"
        "If the problem follows a layout or settings change, retry with:\n"
        "    start-kraken.cmd --reset-settings"
    )
    report_startup_failure(message, traceback.format_exc())
