"""
Widget Registry Module.

Provides centralized widget lifecycle management and tracking for the MainWindow.
"""

import weakref
from enum import Enum, auto
from typing import Dict, Optional

from PySide6.QtWidgets import QWidget

from src.core.logging_config import get_logger

logger = get_logger(__name__)


class WidgetState(Enum):
    """Enumeration of widget lifecycle states."""

    CREATED = auto()
    INITIALIZED = auto()
    DESTROYED = auto()


class WidgetRegistry:
    """
    Manages widget lifecycle and provides centralized access.

    Tracks widget states and provides validation to prevent access
    to destroyed or invalid widgets.
    """

    def __init__(self) -> None:
        """Initializes the widget registry."""
        self._widgets: Dict[str, QWidget] = {}
        self._widget_states: Dict[str, WidgetState] = {}

    def register(self, name: str, widget: QWidget) -> None:
        """
        Register a widget with lifecycle tracking.

        Args:
            name: Unique identifier for the widget.
            widget: The QWidget instance to register.
        """
        if name in self._widgets:
            logger.warning(f"Widget '{name}' already registered, replacing")

        self._widgets[name] = widget
        self._widget_states[name] = WidgetState.CREATED

        # Connect to destroyed signal for cleanup
        # Use weakref to avoid circular reference (Registry -> Widget -> Signal -> Lambda -> Registry)
        self_ref = weakref.ref(self)

        def _cleanup() -> None:
            if r := self_ref():
                r._on_widget_destroyed(name)

        widget.destroyed.connect(_cleanup)

        logger.debug(f"Registered widget: {name}")

    def get(self, name: str) -> Optional[QWidget]:
        """
        Get widget by name with state validation.

        Args:
            name: The widget identifier.

        Returns:
            The widget instance if valid, None otherwise.
        """
        widget = self._widgets.get(name)
        if widget is None:
            logger.warning(f"Widget '{name}' not found in registry")
            return None

        state = self._widget_states.get(name)
        if state == WidgetState.DESTROYED:
            logger.error(f"Attempted to access destroyed widget: {name}")
            return None

        return widget

    def mark_initialized(self, name: str) -> None:
        """
        Mark a widget as fully initialized.

        Args:
            name: The widget identifier.
        """
        if name in self._widget_states:
            self._widget_states[name] = WidgetState.INITIALIZED
            logger.debug(f"Widget '{name}' marked as initialized")
        else:
            logger.warning(f"Cannot mark unknown widget '{name}' as initialized")

    def is_initialized(self, name: str) -> bool:
        """
        Check if a widget is fully initialized.

        Args:
            name: The widget identifier.

        Returns:
            True if widget is initialized, False otherwise.
        """
        state = self._widget_states.get(name)
        return state == WidgetState.INITIALIZED

    def get_state(self, name: str) -> Optional[WidgetState]:
        """
        Get the current state of a widget.

        Args:
            name: The widget identifier.

        Returns:
            The widget state, or None if not found.
        """
        return self._widget_states.get(name)

    def _on_widget_destroyed(self, name: str) -> None:
        """
        Handle widget destruction.

        Args:
            name: The widget identifier.
        """
        if name in self._widget_states:
            self._widget_states[name] = WidgetState.DESTROYED
            try:
                if logger:
                    logger.debug(f"Widget '{name}' destroyed")
            except Exception:
                # Ignore errors during destruction logging (e.g. at shutdown)
                pass

    def cleanup_all(self) -> None:
        """Cleanup all registered widgets."""
        for name, widget in list(self._widgets.items()):
            if widget and self._widget_states.get(name) != WidgetState.DESTROYED:
                widget.deleteLater()
                self._widget_states[name] = WidgetState.DESTROYED
                logger.debug(f"Cleaned up widget: {name}")

        logger.info("All widgets cleaned up")

    def get_all_names(self) -> list[str]:
        """
        Get names of all registered widgets.

        Returns:
            List of widget names.
        """
        return list(self._widgets.keys())

    def get_widget_count(self) -> int:
        """
        Get count of registered widgets.

        Returns:
            Number of widgets in registry.
        """
        return len(self._widgets)
