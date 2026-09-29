"""Resolve the source revision shown in the application window title."""

import json
import re
import subprocess
import sys

from src.core.paths import get_executable_dir


def _short_commit(value: object) -> str | None:
    """Return a compact Git revision only for a valid hexadecimal hash."""
    if isinstance(value, str) and re.fullmatch(r"[0-9a-fA-F]{8,64}", value):
        return value[:8].lower()
    return None


def get_commit_id() -> str | None:
    """Read the packaged build revision or the development checkout's HEAD."""
    if getattr(sys, "frozen", False):
        try:
            path = get_executable_dir() / "build-info.json"
            build_info = json.loads(path.read_text(encoding="utf-8-sig"))
            return _short_commit(build_info.get("commit"))
        except (AttributeError, OSError, ValueError):
            return None

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short=8", "HEAD"],
            cwd=get_executable_dir(),
            capture_output=True,
            text=True,
            timeout=1,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return _short_commit(result.stdout.strip())


def window_title(base_title: str, world_name: str) -> str:
    """Place the available revision between the version and world name."""
    commit = get_commit_id()
    if commit:
        return f"{base_title} - {commit} - {world_name}"
    return f"{base_title} - {world_name}"
