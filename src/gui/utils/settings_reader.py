"""Typed readers for values crossing the ``QSettings`` boundary."""

import logging

from PySide6.QtCore import QSettings

logger = logging.getLogger(__name__)


def _warn_invalid(key: str, value: object, default: object) -> None:
    """Log a malformed persisted value before returning its safe default."""
    logger.warning(
        "Invalid persisted setting %s=%r; using default %r",
        key,
        value,
        default,
    )


def read_bool_setting(settings: QSettings, key: str, default: bool) -> bool:
    """Return a validated boolean setting.

    Native booleans, integer ``0``/``1``, and common serialized boolean strings
    are accepted so settings written by older Qt or test configurations migrate
    safely.
    """
    value = settings.value(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False

    _warn_invalid(key, value, default)
    return default


def read_int_setting(settings: QSettings, key: str, default: int) -> int:
    """Return a validated integer setting without accepting booleans."""
    value = settings.value(key, default)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            pass

    _warn_invalid(key, value, default)
    return default


def read_str_setting(settings: QSettings, key: str, default: str) -> str:
    """Return a string setting, falling back for null or non-string values."""
    value = settings.value(key, default)
    if isinstance(value, str):
        return value

    _warn_invalid(key, value, default)
    return default
