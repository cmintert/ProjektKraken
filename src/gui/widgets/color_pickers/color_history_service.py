"""Recent value / colour history service.

Stores the last N picks per context key (e.g. ``"raster.paint_value"``,
``"palette.color"``) in ``QSettings`` so history survives across
sessions.  Other widgets read from and push to this service.
"""

import json
import logging
from typing import Any, List, Optional

from PySide6.QtCore import QObject, QSettings, Signal

logger = logging.getLogger(__name__)

_ORG = "ProjektKraken"
_APP = "ColorHistory"
_DEFAULT_LIMIT = 12


class ColorHistoryService(QObject):
    """Per-context ring-buffer of recently used values or colours.

    The service is a singleton — callers typically do
    ``ColorHistoryService.instance().push(...)``.

    Signals:
        history_changed: Emitted after ``push`` or ``clear``.  Payload is
            the context string so subscribers can filter.
    """

    history_changed = Signal(str)

    _instance: Optional["ColorHistoryService"] = None

    @classmethod
    def instance(cls) -> "ColorHistoryService":
        """Return the singleton instance, creating it on first call."""
        if cls._instance is None:
            cls._instance = ColorHistoryService()
        return cls._instance

    def __init__(self) -> None:
        super().__init__()
        self._settings = QSettings(_ORG, _APP)
        self._cache: dict[str, List[Any]] = {}

    def push(self, context: str, value: Any, limit: int = _DEFAULT_LIMIT) -> None:
        """Record *value* as the most-recent entry for *context*.

        Duplicates are removed before insertion so each value appears at
        most once; the list is kept to *limit* items.

        Args:
            context: Namespace key (e.g. ``"raster.paint_value"``).
            value: JSON-serialisable value (int, str, float, list, dict).
            limit: Maximum number of entries retained for this context.
        """
        items = self.recent(context, limit)
        items = [v for v in items if v != value]
        items.insert(0, value)
        items = items[:limit]
        self._cache[context] = items
        self._settings.setValue(self._key(context), json.dumps(items))
        self.history_changed.emit(context)

    def recent(self, context: str, limit: int = _DEFAULT_LIMIT) -> List[Any]:
        """Return the most-recent entries for *context*, newest first.

        Args:
            context: Namespace key.
            limit: Maximum number of entries returned.

        Returns:
            List of up to *limit* values, newest first.  Empty if the
            context has no history yet.
        """
        if context in self._cache:
            return list(self._cache[context])[:limit]
        raw = self._settings.value(self._key(context), "")
        if not raw:
            return []
        try:
            items = json.loads(str(raw))
            if isinstance(items, list):
                self._cache[context] = items
                return list(items)[:limit]
        except (ValueError, TypeError):
            logger.warning("ColorHistoryService: malformed history for %s", context)
        return []

    def clear(self, context: str) -> None:
        """Delete all recent entries for *context*."""
        self._cache.pop(context, None)
        self._settings.remove(self._key(context))
        self.history_changed.emit(context)

    @staticmethod
    def _key(context: str) -> str:
        return f"history/{context}"
