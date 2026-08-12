"""Coordinate calendar configuration and current lore time."""

import logging
from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import Q_ARG, Slot

from src.app.coordinators.base_coordinator import BaseCoordinator
from src.app.qt_invocation import invoke_queued
from src.core.calendar import CalendarConfig, CalendarConverter

if TYPE_CHECKING:
    from src.app.main_window import MainWindow

logger = logging.getLogger(__name__)


class TimeCoordinator(BaseCoordinator):
    """Coordinator for Time and Playhead management.

    Handles:
    - Playhead state and time synchronization.
    - Time labels updates.
    - Return to Present logic.
    - Resolving temporal entity states.
    """

    def __init__(self, main_window: "MainWindow") -> None:
        """Initialize lore-time and playhead coordination."""
        super().__init__(main_window)
        self._current_playhead_time: Optional[float] = None

    @property
    def current_playhead_time(self) -> Optional[float]:
        """Return the latest timeline playhead value, when available."""
        return self._current_playhead_time

    @Slot(float)
    def on_current_time_changed(self, time: float) -> None:
        """Handler for when current time is changed in the timeline. Saves the new value
        to the database.

        Args:
            time (float): The new current time in lore_date units.

        """
        invoke_queued(
            self.main_window.worker,
            "save_current_time",
            Q_ARG(float, time),
        )
        logger.debug(f"Current time changed to: {time}")

        # Update entity editor's timeline display with NOW marker
        if hasattr(self.main_window, "entity_editor"):
            self.main_window.entity_editor.timeline_display.set_current_time(time)

        self.update_world_time_label(time)

    @Slot(float)
    def update_playhead_time_label(self, time_val: float) -> None:
        """Updates the red playhead time label."""
        text = self._format_time_string(time_val)
        label = getattr(self.main_window, "lbl_playhead_time", None)
        if label is not None:
            label.setText(f"Playhead: {text}")

    @Slot(float)
    def update_world_time_label(self, time_val: float) -> None:
        """Updates the blue world time label."""
        text = self._format_time_string(time_val)
        label = getattr(self.main_window, "lbl_world_time", None)
        if label is not None:
            label.setText(f"World: {text}")

    @Slot()
    def on_return_to_present(self) -> None:
        """Exits "Viewing Past/Future State" mode.

        Hides the playhead and reloads the current entity in editable mode.
        """
        # Set playhead to "Current Time" (Visual indicator that we are at "Now")
        current_time = self.main_window.timeline.get_current_time()
        self.main_window.timeline.set_playhead_time(current_time)

        # Reload entity in normal editable mode
        entity_editor = self.main_window.entity_editor
        if entity_editor.isVisible() and entity_editor._current_entity_id:
            self.main_window.data_coordinator.load_entity_details(
                entity_editor._current_entity_id
            )

    def _format_time_string(self, time_val: float) -> str:
        """Formats time using calendar converter if available."""
        # Access calendar_converter from main_window if it exists
        converter = getattr(self.main_window, "calendar_converter", None)
        if converter:
            return converter.format_date(time_val)
        return f"{time_val:.2f}"

    @Slot(float)
    def on_playhead_changed(self, time: float) -> None:
        """Refreshes entity inspector based on playhead time."""
        # Store current playhead time
        self._current_playhead_time = time

        # We need to access entity_editor via main_window for now
        # Ideally, we should receive the editor or use a manager
        entity_editor = self.main_window.entity_editor

        if entity_editor.isVisible() and entity_editor._current_entity_id:
            invoke_queued(
                self.main_window.worker,
                "resolve_entity_state",
                Q_ARG(str, entity_editor._current_entity_id),
                Q_ARG(float, time),
            )

    @Slot(str, dict)
    def on_entity_state_resolved(self, entity_id: str, attributes: dict) -> None:
        """Updates entity editor with resolved state."""
        # Pass playhead time for timeline highlighting
        self.main_window.entity_editor.display_temporal_state(
            entity_id, attributes, self._current_playhead_time
        )

    # ------------------------------------------------------------------
    # Calendar Configuration
    # ------------------------------------------------------------------

    def request_calendar_config(self) -> None:
        """Requests loading of the active calendar config from the worker."""
        invoke_queued(
            self.main_window.worker,
            "load_calendar_config",
        )

    def request_current_time(self) -> None:
        """Requests loading of the current time from the worker."""
        invoke_queued(
            self.main_window.worker,
            "load_current_time",
        )

    @Slot(object)
    def on_calendar_config_loaded(self, config: CalendarConfig | None) -> None:
        """Handler for calendar config loaded from worker.

        Creates a CalendarConverter and distributes it to all widgets
        that need calendar formatting.

        Args:
            config: CalendarConfig or None.

        """
        try:
            if config:
                converter = CalendarConverter(config)
            else:
                default_config = CalendarConfig.create_default()
                converter = CalendarConverter(default_config)

            self.main_window.event_editor.set_calendar_converter(converter)
            self.main_window.timeline.set_calendar_converter(converter)
            self.main_window.map_widget.set_calendar_converter(converter)
            self.main_window.unified_list.set_calendar_converter(converter)
            self.main_window.longform_editor.content.set_calendar_converter(converter)

            # Set calendar converter for timeline display in entity editor
            from src.gui.widgets.timeline_display_widget import (
                TimelineDisplayWidget,
            )

            TimelineDisplayWidget.set_calendar_converter(converter)

            # Check if UIManager has a pending calendar dialog
            ui_manager = getattr(self.main_window, "ui_manager")
            ui_manager.show_calendar_dialog(config)

            # Save converter for status bar formatting
            setattr(self.main_window, "calendar_converter", converter)

            # Refresh status bar labels now that we have a converter
            if hasattr(self.main_window, "timeline") and hasattr(
                self.main_window, "time_coordinator"
            ):
                self.update_world_time_label(
                    self.main_window.timeline.get_current_time()
                )
                self.update_playhead_time_label(
                    self.main_window.timeline.get_playhead_time()
                )

        except Exception as e:
            logger.warning(f"Failed to initialize calendar converter: {e}")

    @Slot(float)
    def on_current_time_loaded(self, time: float) -> None:
        """Handler for current time loaded from worker.

        Args:
            time: The current time in lore_date units.

        """
        self.main_window.timeline.set_current_time(time)
        logger.debug(f"Current time loaded: {time}")
