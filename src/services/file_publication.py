"""Bounded retry for transient Windows sharing locks during staged publication."""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")
_RETRY_DELAYS = (0.025, 0.05, 0.1, 0.2, 0.4)


def publish_with_retry(operation: Callable[[], T]) -> T:
    """Retry only sharing/access failures; retain existing staging and rollback."""
    for delay in _RETRY_DELAYS:
        try:
            return operation()
        except PermissionError:
            if os.name != "nt":
                raise
            time.sleep(delay)
    return operation()
