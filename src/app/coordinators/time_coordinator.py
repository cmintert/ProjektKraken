import logging
from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import Q_ARG, QMetaObject, Qt, Slot

from src.app.coordinators.base_coordinator import BaseCoordinator

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
        super().__init__(main_window)
        self._current_playhead_time: Optional[float] = None

    @property
    def current_playhead_time(self) -> Optional[float]:
        return self._current_playhead_time

    @Slot(float)
    def on_current_time_changed(self, time: float) -> None:
        """Handler for when current time is changed in the timeline. Saves the new value
        to the database.

        Args:
            time (float): The new current time in lore_date units.

        """
        QMetaObject.invokeMethod(
            self.main_window.worker,
            "save_current_time",
            Qt.ConnectionType.QueuedConnection,
            Q_ARG(float, time),
        )
        logger.debug(f"Current time changed to: {time}")

        # Update entity editor's timeline display with NOW marker
        if hasattr(self.main_window, "entity_editor"):
            self.main_window.entity_editor.timeline_display.set_current_time(time)

        self.update_world_time_label(time)

    @Slot(str)
    def update_playhead_time_label(self, time_val: float) -> None:
        """Updates the red playhead time label."""
        text = self._format_time_string(time_val)
        if hasattr(self.main_window, "lbl_playhead_time"):
            self.main_window.lbl_playhead_time.setText(f"Playhead: {text}")

    @Slot(float)
    def update_world_time_label(self, time_val: float) -> None:
        """Updates the blue world time label."""
        text = self._format_time_string(time_val)
        if hasattr(self.main_window, "lbl_world_time"):
            self.main_window.lbl_world_time.setText(f"World: {text}")

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
            self.main_window.load_entity_details(entity_editor._current_entity_id)

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
            QMetaObject.invokeMethod(
                self.main_window.worker,
                "resolve_entity_state",
                Qt.ConnectionType.QueuedConnection,
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
