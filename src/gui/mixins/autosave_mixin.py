"""
AutoSave Mixin Module.
Provides debounce logic for automatic saving of editor widgets.
"""

import logging
from typing import Protocol, runtime_checkable

from PySide6.QtCore import QObject, QTimer

from src.app.constants import AUTOSAVE_DELAY_MS

logger = logging.getLogger(__name__)


@runtime_checkable
class AutoSaveSource(Protocol):
    """Protocol defining requirements for AutoSaveManager target."""

    def has_unsaved_changes(self) -> bool: ...
    def _on_save(self) -> None: ...


class AutoSaveManager(QObject):
    """
    Manager to handle debounced autosave functionality via composition.
    """

    def __init__(
        self, target: AutoSaveSource, delay_ms: int = AUTOSAVE_DELAY_MS
    ) -> None:
        """
        Initialize the autosave manager.

        Args:
            target: The object to auto-save (must satisfy AutoSaveSource protocol)
            delay_ms: Debounce delay in milliseconds. Defaults to constant.
        """
        super().__init__(parent=target if isinstance(target, QObject) else None)
        self._target = target
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setInterval(delay_ms)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.timeout.connect(self._perform_autosave)
        self._autosave_enabled = True

    def start_timer(self) -> None:
        """Starts or restarts the autosave debounce timer if enabled."""
        if self._autosave_enabled:
            self._autosave_timer.start()

    def stop_timer(self) -> None:
        """Stops the autosave timer (e.g., if saved manually or dirty cleared)."""
        self._autosave_timer.stop()

    def set_enabled(self, enabled: bool) -> None:
        """Enables or disables autosave functionality."""
        self._autosave_enabled = enabled
        if not enabled:
            self.stop_timer()

    def _perform_autosave(self) -> None:
        """
        Called when timer expires. Triggers save if still dirty.
        """
        if self._target.has_unsaved_changes():
            logger.debug(f"[{self._target.__class__.__name__}] Autosave triggered.")
            self._target._on_save()
        else:
            logger.debug(
                f"[{self._target.__class__.__name__}] Autosave timer expired but no changes to save."
            )
