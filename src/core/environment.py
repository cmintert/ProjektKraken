"""Typed environment-variable readers shared across application layers."""

import os


def env_bool(name: str, default: bool) -> bool:
    """Read a boolean environment variable with a fallback value."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_float(name: str, default: float) -> float:
    """Read a float environment variable with a fallback value."""
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default
