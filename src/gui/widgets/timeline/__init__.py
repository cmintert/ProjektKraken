"""
Timeline Widget Package.

Main entry point for timeline visualization. Provides TimelineWidget wrapper
that combines TimelineView with playback controls.

The timeline components have been refactored into separate modules for better
maintainability:
- timeline/event_item.py - EventItem rendering
- timeline/timeline_scene.py - Scene and playhead components
- timeline/timeline_view.py - Main view with zoom/pan and interaction
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.gui.widgets.timeline.event_item import EventItem
from src.gui.widgets.timeline.timeline_scene import (
    CurrentTimeLineItem,
    PlayheadItem,
    TimelineScene,
)
from src.gui.widgets.timeline.timeline_view import TimelineView


class TimelineWidget(QWidget):
    """
    Wrapper widget for TimelineView + Toolbar.
    """

    event_selected = Signal(str)
    playhead_time_changed = Signal(float)  # Expose playhead signal from view
    current_time_changed = Signal(float)  # Expose current time signal from view
    event_date_changed = Signal(str, float)  # (event_id, new_lore_date)

    def __init__(self, parent=None):
        """
        Initializes the TimelineWidget.

        Args:
            parent (QWidget, optional): The parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(0)
        self.layout.setContentsMargins(0, 0, 0, 0)

        # Toolbar Container (Header)
        self.header_frame = QWidget()
        self.header_frame.setObjectName("TimelineHeader")
        self.toolbar_layout = QHBoxLayout(self.header_frame)
        self.toolbar_layout.setContentsMargins(4, 4, 4, 4)

        # Playback controls
        self.btn_step_back = QPushButton("◄")
        self.btn_step_back.setToolTip("Step Backward")
        self.btn_step_back.setMaximumWidth(40)
        self.btn_step_back.clicked.connect(self.step_backward)
        self.toolbar_layout.addWidget(self.btn_step_back)

        self.btn_play_pause = QPushButton("▶")
        self.btn_play_pause.setToolTip("Play/Pause")
        self.btn_play_pause.setCheckable(True)
        self.btn_play_pause.setMaximumWidth(40)
        self.btn_play_pause.clicked.connect(self.toggle_playback)
        self.toolbar_layout.addWidget(self.btn_play_pause)

        self.btn_step_forward = QPushButton("►")
        self.btn_step_forward.setToolTip("Step Forward")
        self.btn_step_forward.setMaximumWidth(40)
        self.btn_step_forward.clicked.connect(self.step_forward)
        self.toolbar_layout.addWidget(self.btn_step_forward)

        # Separator
        self.toolbar_layout.addSpacing(20)

        # Current time control
        self.btn_set_current_time = QPushButton("Set Current Time")
        self.btn_set_current_time.setToolTip(
            "Set the current time in the world to the playhead position"
        )
        self.btn_set_current_time.clicked.connect(self.set_current_time_to_playhead)
        self.toolbar_layout.addWidget(self.btn_set_current_time)

        self.toolbar_layout.addStretch()

        self.btn_fit = QPushButton("Fit View")
        self.btn_fit.clicked.connect(self.fit_view)
        self.toolbar_layout.addWidget(self.btn_fit)

        self.layout.addWidget(self.header_frame)

        # View
        self.view = TimelineView()
        self.view.event_selected.connect(self.event_selected.emit)
        self.view.playhead_time_changed.connect(self.playhead_time_changed.emit)
        self.view.current_time_changed.connect(self.current_time_changed.emit)
        self.view.event_date_changed.connect(self.event_date_changed.emit)
        self.layout.addWidget(self.view)

    def set_events(self, events):
        """Passes the event list to the view."""
        self.view.set_events(events)

    def focus_event(self, event_id: str):
        """Centers the timeline on the given event."""
        self.view.focus_event(event_id)

    def fit_view(self):
        """Fits all events within the view."""
        self.view.fit_all()

    def toggle_playback(self):
        """
        Toggles playback on/off and updates button state.
        """
        if self.view.is_playing():
            self.view.stop_playback()
            self.btn_play_pause.setText("▶")
            self.btn_play_pause.setChecked(False)
        else:
            self.view.start_playback()
            self.btn_play_pause.setText("■")
            self.btn_play_pause.setChecked(True)

    def step_forward(self):
        """Steps the playhead forward."""
        self.view.step_forward()

    def step_backward(self):
        """Steps the playhead backward."""
        self.view.step_backward()

    def set_playhead_time(self, time: float):
        """
        Sets the playhead to a specific time.

        Args:
            time: Time in lore_date units.
        """
        self.view.set_playhead_time(time)

    def get_playhead_time(self) -> float:
        """
        Gets the current playhead time.

        Returns:
            float: Current time in lore_date units.
        """
        return self.view.get_playhead_time()

    def set_current_time(self, time: float):
        """
        Sets the current time in the world.

        Args:
            time: Time in lore_date units.
        """
        self.view.set_current_time(time)

    def get_current_time(self) -> float:
        """
        Gets the current time in the world.

        Returns:
            float: Current time in lore_date units.
        """
        return self.view.get_current_time()

    def set_current_time_to_playhead(self):
        """
        Sets the current time to match the playhead position.
        This is the typical workflow: move playhead, then set as current time.
        """
        playhead_time = self.get_playhead_time()
        self.set_current_time(playhead_time)

    def set_calendar_converter(self, converter):
        """
        Sets the calendar converter for formatted date display.

        Args:
            converter: CalendarConverter instance or None.
        """
        EventItem.set_calendar_converter(converter)
        # Also configure the ruler for calendar-aware date divisions
        self.view.set_ruler_calendar(converter)
        # Trigger repaint to update existing items
        self.view.viewport().update()

    def update_event_preview(self, event_data: dict):
        """
        Updates the visual representation of an event in real-time.
        Delegates to the view.
        """
        self.view.update_event_preview(event_data)
        self.view.update_event_preview(event_data)

    def set_grouping_config(self, tag_order: list, mode: str = "DUPLICATE"):
        """Sets the timeline grouping configuration."""
        self.view.set_grouping_config(tag_order, mode)

    def clear_grouping(self):
        """Clears the timeline grouping."""
        self.view.clear_grouping()

    def set_db_service(self, db_service):
        """Sets the database service for the timeline view."""
        self.view.set_db_service(db_service)


__all__ = [
    "TimelineWidget",
    "EventItem",
    "TimelineScene",
    "PlayheadItem",
    "CurrentTimeLineItem",
    "TimelineView",
]
