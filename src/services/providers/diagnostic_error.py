"""Bounded, content-free descriptions of provider failures."""

from __future__ import annotations

from typing import Any

_MIN_HTTP_STATUS = 100
_MAX_HTTP_STATUS = 599


def safe_error(exc: BaseException) -> str:
    """Expose only error class and numeric HTTP status, never URL or body."""
    response: Any = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    if isinstance(status, int) and _MIN_HTTP_STATUS <= status <= _MAX_HTTP_STATUS:
        return f"{type(exc).__name__} status={status}"
    return type(exc).__name__
