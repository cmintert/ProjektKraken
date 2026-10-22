"""Timeline Widget Package.

Main entry point for timeline visualization. Provides TimelineWidget wrapper
that combines TimelineView with playback controls.

The timeline components have been refactored into separate modules for better
maintainability:
- timeline/event_item.py - EventItem rendering
- timeline/timeline_scene.py - Scene and playhead components
- timeline/timeline_view.py - Main view with zoom/pan and interaction
"""

from collections.abc import Callable
from typing import Any, Optional, cast

from PySide6.QtCore import QSettings, QSize, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLayout,
    QMenu,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.core.theme_manager import ThemeManager
from src.gui.utils.help_context import declare_inspection
from src.gui.utils.style_helper import StyleHelper
from src.gui.widgets.menu_caret import PhosphorPushMenuButton
from src.gui.widgets.overflow_toolbar import OverflowToolBar
from src.gui.widgets.standard_buttons import StandardButton as QPushButton
from src.gui.widgets.timeline.event_item import EventItem
from src.gui.widgets.timeline.time_indicators import TimelineTimeStatus
from src.gui.widgets.timeline.timeline_scene import (
    CurrentTimeLineItem,
    PlayheadItem,
    TimelineScene,
)
from src.gui.widgets.timeline.timeline_view import TimelineView


class TimelineWidget(QWidget):
    """Wrapper widget for TimelineView + Toolbar."""

    event_selected = Signal(str)
    playhead_time_changed = Signal(float)  # Expose playhead signal from view
    current_time_changed = Signal(float)  # Expose current time signal from view
    event_date_changed = Signal(str, float)  # (event_id, new_lore_date)
    create_event_requested = Signal()  # Expose empty state action from view
    go_to_date_requested = Signal()
    selected_event_date_requested = Signal(str)
    date_navigation_menu_requested = Signal()
    navigation_context_changed = Signal(dict)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initializes the TimelineWidget.

        Args:
            parent (QWidget, optional): The parent widget. Defaults to None.

        """
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        # Expanding size policy prevents dock collapse during resize.
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        main_layout = QVBoxLayout(self)
        main_layout.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Toolbar Container (Header)
        self.header_frame = QWidget()
        self.header_frame.setObjectName("TimelineHeader")
        header_layout = QHBoxLayout(self.header_frame)
        header_layout.setContentsMargins(4, 4, 4, 4)
        StyleHelper.apply_panel_top_spacing(header_layout)
        self.action_toolbar = OverflowToolBar(self.header_frame)
        header_layout.addWidget(self.action_toolbar)

        # Playback controls
        self.btn_step_back = declare_inspection(
            QPushButton("◄"),
            "src-gui-widgets-timeline-init-timelinewidget-init-self-btn-step-back|timeline.viewing|help-inspect-src-gui-widgets-timeline-init-timelinewidget-init-self-btn-step-back",
        )
        self.btn_step_back.setToolTip("Step Backward")
        self.btn_step_back.setAccessibleName("Step backward")
        self.btn_step_back.setProperty("toolbarActionLabel", "Step backward")
        self.btn_step_back.clicked.connect(self.step_backward)
        self.action_toolbar.add_button(self.btn_step_back, priority=80)

        self.btn_play_pause = declare_inspection(
            QPushButton("▶"),
            "src-gui-widgets-timeline-init-timelinewidget-init-self-btn-play-pause|timeline.viewing|help-inspect-src-gui-widgets-timeline-init-timelinewidget-init-self-btn-play-pause",
        )
        self.btn_play_pause.setToolTip("Play/Pause")
        self.btn_play_pause.setCheckable(True)
        self.btn_play_pause.setAccessibleName("Play or pause timeline")
        self.btn_play_pause.setProperty("toolbarActionLabel", "Play or pause timeline")
        self.btn_play_pause.clicked.connect(self.toggle_playback)
        self.action_toolbar.add_button(
            self.btn_play_pause,
            priority=100,
            pinned=True,
        )

        self.btn_step_forward = declare_inspection(
            QPushButton("►"),
            "src-gui-widgets-timeline-init-timelinewidget-init-self-btn-step-forward|timeline.viewing|help-inspect-src-gui-widgets-timeline-init-timelinewidget-init-self-btn-step-forward",
        )
        self.btn_step_forward.setToolTip("Step Forward")
        self.btn_step_forward.setAccessibleName("Step forward")
        self.btn_step_forward.setProperty("toolbarActionLabel", "Step forward")
        self.btn_step_forward.clicked.connect(self.step_forward)
        self.action_toolbar.add_button(self.btn_step_forward, priority=80)

        # Current time control
        self.btn_set_current_time = declare_inspection(
            QPushButton("Set Current Time"),
            "src-gui-widgets-timeline-init-timelinewidget-init-self-btn-set-current-time|timeline.viewing|help-inspect-src-gui-widgets-timeline-init-timelinewidget-init-self-btn-set-current-time",
        )
        self.btn_set_current_time.setToolTip(
            "Set the current time in the world to the playhead position"
        )
        self.btn_set_current_time.clicked.connect(self.set_current_time_to_playhead)
        self.action_toolbar.add_button(self.btn_set_current_time, priority=50)

        self.btn_return_present = declare_inspection(
            QPushButton("Return to Current Time"),
            "src-gui-widgets-timeline-init-timelinewidget-init-self-btn-return-present|timeline.viewing|help-inspect-src-gui-widgets-timeline-init-timelinewidget-init-self-btn-return-present",
        )
        self.btn_return_present.setToolTip(
            "Move the playhead to the current story time"
        )
        self.btn_return_present.clicked.connect(self.return_to_present)
        self.action_toolbar.add_button(self.btn_return_present, priority=70)

        self.btn_go_to_date = declare_inspection(
            PhosphorPushMenuButton("Go to date"),
            "src-gui-widgets-timeline-init-timelinewidget-init-self-btn-go-to-date|timeline.viewing|help-inspect-src-gui-widgets-timeline-init-timelinewidget-init-self-btn-go-to-date",
        )
        self.btn_go_to_date.setToolTip(
            "Move the playhead to the selected event or enter an exact date"
        )
        self._selected_navigation_event_id: str | None = None
        self.date_navigation_menu = declare_inspection(
            QMenu(self),
            "src-gui-widgets-timeline-init-timelinewidget-init-self-date-navigation-menu|timeline.viewing|help-inspect-src-gui-widgets-timeline-init-timelinewidget-init-self-date-navigation-menu",
        )
        self.selected_event_date_action = declare_inspection(
            self.date_navigation_menu.addAction("Go to selected event"),
            "src-gui-widgets-timeline-init-timelinewidget-init-self-selected-event-date-action|timeline.viewing|help-inspect-src-gui-widgets-timeline-init-timelinewidget-init-self-selected-event-date-action",
        )
        self.selected_event_date_action.setEnabled(False)
        self.enter_date_action = declare_inspection(
            self.date_navigation_menu.addAction("Enter a date…"),
            "src-gui-widgets-timeline-init-timelinewidget-init-self-enter-date-action|timeline.viewing|help-inspect-src-gui-widgets-timeline-init-timelinewidget-init-self-enter-date-action",
        )
        self.enter_date_action.setEnabled(False)
        self.enter_date_action.triggered.connect(self.go_to_date_requested.emit)
        self.selected_event_date_action.triggered.connect(
            self._request_selected_event_date
        )
        self.date_navigation_menu.aboutToShow.connect(
            self.date_navigation_menu_requested.emit
        )
        self.btn_go_to_date.setMenu(self.date_navigation_menu)
        self.btn_go_to_date.setEnabled(False)
        self.action_toolbar.add_button(self.btn_go_to_date, priority=65)

        settings = QSettings()
        snap_to_events = cast(
            bool,
            settings.value("timeline/snap_playhead_to_events", False, type=bool),
        )
        self.chk_snap_playhead_to_events = declare_inspection(
            QCheckBox("Snap to Events"),
            "src-gui-widgets-timeline-init-timelinewidget-init-self-chk-snap-playhead-to-events|timeline.viewing|help-inspect-src-gui-widgets-timeline-init-timelinewidget-init-self-chk-snap-playhead-to-events",
        )
        self.chk_snap_playhead_to_events.setToolTip(
            "Snap manual playhead drags and ruler clicks to nearby event dates."
        )
        self.chk_snap_playhead_to_events.setChecked(snap_to_events)
        self.action_toolbar.add_button(
            self.chk_snap_playhead_to_events,
            priority=20,
        )

        self.btn_fit = declare_inspection(
            QPushButton("Fit View"),
            "src-gui-widgets-timeline-init-timelinewidget-init-self-btn-fit|timeline.viewing|help-inspect-src-gui-widgets-timeline-init-timelinewidget-init-self-btn-fit",
        )
        self.btn_fit.clicked.connect(self.fit_view)
        self.action_toolbar.add_button(self.btn_fit, priority=60)

        main_layout.addWidget(self.header_frame)

        # View
        self.view = declare_inspection(
            TimelineView(),
            "view.src-gui-widgets-timeline-init-timelinewidget-init-self-view|timeline.viewing|help-inspect-view-src-gui-widgets-timeline-init-timelinewidget-init-self-view",
        )
        self.view.set_playhead_event_snapping(snap_to_events)
        self.chk_snap_playhead_to_events.toggled.connect(
            self.set_playhead_event_snapping
        )
        self.view.event_selected.connect(self.event_selected.emit)
        self.view.playhead_time_changed.connect(self.playhead_time_changed.emit)
        self.view.current_time_changed.connect(self.current_time_changed.emit)
        self.view.navigation_context_changed.connect(
            self.navigation_context_changed.emit
        )
        self.view.event_date_changed.connect(self.event_date_changed.emit)
        self.view.create_event_requested.connect(self.create_event_requested.emit)
        self.time_status = TimelineTimeStatus(self)
        main_layout.addWidget(self.time_status)
        main_layout.addWidget(self.view)
        self.view.time_indicators.status = self.time_status
        self._apply_theme()
        ThemeManager().theme_changed.connect(self._apply_theme)
        self.view.time_indicators.refresh()
        self._next_navigation_context: dict[str, Any] | None = None

    def _apply_theme(self, theme: dict[str, str] | None = None) -> None:
        """Share normal, disabled, checked and keyboard-focus action presentation."""
        self.action_toolbar.setStyleSheet(
            StyleHelper.get_action_role_style("secondary", "QPushButton")
        )
        self.view.time_indicators.refresh()

    def set_navigation_acceptor(self, accepts: Callable[[float], bool]) -> None:
        """Use the existing application guard as the acceptance authority."""
        self.view.time_indicators.accepts = accepts

    def accept_navigation_context(self) -> None:
        """Complete disclosure after a deferred save accepts its viewing date."""
        self.view.time_indicators.settle()

    def queue_navigation_context(self, context: dict[str, Any]) -> None:
        """Associate a serializable target snapshot with the next float time request."""
        self._next_navigation_context = dict(context)

    def set_data_provider(self, provider: Any) -> None:
        """Sets the data provider for timeline grouping features.

        Args:
            provider: Object implementing the data provider interface.

        """
        self.view.set_data_provider(provider)

    def set_events(self, events: list) -> None:
        """Passes the event list to the view."""
        self.view.set_events(events)

    def apply_event_effects(self, effects: list) -> None:
        """Apply worker-confirmed Event mutations to the timeline."""
        self.view.apply_event_effects(effects)

    def focus_event(self, event_id: str) -> None:
        """Centers the timeline on the given event."""
        self.view.focus_event(event_id)

    def center_on_date(self, date: float) -> None:
        """Reveal a lore date without changing zoom or event selection."""
        self.view.center_on_date(date)

    def clear_event_selection(self) -> None:
        """Clear a timeline click rejected by guarded navigation."""
        self.view.graphics_scene.clearSelection()

    def fit_view(self) -> None:
        """Fits all events within the view."""
        self.view.fit_all()

    def toggle_playback(self) -> None:
        """Toggles playback on/off and updates button state."""
        if self.view.is_playing():
            self.view.stop_playback()
            self.btn_play_pause.setText("▶")
            self.btn_play_pause.setChecked(False)
        else:
            self.view.start_playback()
            self.btn_play_pause.setText("■")
            self.btn_play_pause.setChecked(True)

    def step_forward(self) -> None:
        """Steps the playhead forward."""
        self.view.step_forward()

    def step_backward(self) -> None:
        """Steps the playhead backward."""
        self.view.step_backward()

    def set_playhead_event_snapping(self, enabled: bool) -> None:
        """Apply and persist the manual playhead event-snapping preference."""
        self.view.set_playhead_event_snapping(enabled)
        QSettings().setValue("timeline/snap_playhead_to_events", enabled)

    def set_playhead_time(
        self, time: float, navigation_context: dict[str, Any] | None = None
    ) -> None:
        """Sets the playhead to a specific time.

        Args:
            time: Time in lore_date units.

        """
        context = navigation_context or self._next_navigation_context
        self._next_navigation_context = None
        self.view.set_playhead_time(time, context)

    def get_playhead_time(self) -> float:
        """Gets the current playhead time.

        Returns:
            float: Current time in lore_date units.

        """
        return self.view.get_playhead_time()

    def set_current_time(self, time: float) -> None:
        """Sets the current time in the world.

        Args:
            time: Time in lore_date units.

        """
        self.view.set_current_time(time)

    def get_current_time(self) -> float:
        """Gets the current time in the world.

        Returns:
            float: Current time in lore_date units.

        """
        return self.view.get_current_time()

    def set_current_time_to_playhead(self) -> None:
        """Sets the current time to match the playhead position.

        This is the typical workflow: move playhead, then set as current time.
        """
        playhead_time = self.get_playhead_time()
        self.set_current_time(playhead_time)

    def return_to_present(self) -> None:
        """Sets the playhead position to match the current story time."""
        current_time = self.get_current_time()
        self.set_playhead_time(current_time)

    def set_calendar_converter(self, converter: Any) -> None:
        """Sets the calendar converter for formatted date display.

        Args:
            converter: CalendarConverter instance or None.

        """
        EventItem.set_calendar_converter(converter)
        # Also configure the ruler for calendar-aware date divisions
        self.view.set_ruler_calendar(converter)
        self.view.time_indicators.converter = converter
        self.view.time_indicators.settle()
        if self.view._band_manager is not None:
            self.view._band_manager.refresh_occurrences(converter)
        self.view.repack_events()
        self.enter_date_action.setEnabled(converter is not None)
        self._refresh_date_navigation_enabled()
        # Trigger repaint to update existing items
        self.view.viewport().update()

    def set_selected_event_navigation(self, event_id: str | None, caption: str) -> None:
        """Render a coordinator-prepared saved navigation target."""
        self._selected_navigation_event_id = event_id
        self.selected_event_date_action.setEnabled(event_id is not None)
        self.selected_event_date_action.setToolTip(caption)
        self._refresh_date_navigation_enabled()

    def _refresh_date_navigation_enabled(self) -> None:
        """Keep the menu reachable whenever one destination is available."""
        self.btn_go_to_date.setEnabled(
            self.selected_event_date_action.isEnabled()
            or self.enter_date_action.isEnabled()
        )

    def _request_selected_event_date(self) -> None:
        """Emit the displayed target for coordinator revalidation."""
        if self._selected_navigation_event_id is not None:
            self.selected_event_date_requested.emit(self._selected_navigation_event_id)

    def update_event_preview(self, event_data: dict) -> None:
        """Updates the visual representation of an event in real-time.

        Delegates to the view.
        """
        self.view.update_event_preview(event_data)
        self.view.update_event_preview(event_data)

    def set_grouping_config(self, tag_order: list, mode: str = "DUPLICATE") -> None:
        """Sets the timeline grouping configuration."""
        self.view.set_grouping_config(tag_order, mode)

    def clear_grouping(self) -> None:
        """Clears the timeline grouping."""
        self.view.clear_grouping()

    def save_state(self) -> None:
        """Saves the current state of the timeline widget (e.g. playhead time)."""
        self.view.save_state()

    # -- Size hints ----------------------------------------------------------

    def minimumSizeHint(self) -> QSize:
        """Allow the widget to shrink inside its dock.

        Returns:
            QSize: Minimum usable size for the timeline.
        """
        return QSize(200, 100)

    def sizeHint(self) -> QSize:
        """Preferred size for the timeline widget.

        Returns:
            QSize: Comfortable working size for the timeline.
        """
        return QSize(600, 200)


__all__ = [
    "TimelineWidget",
    "EventItem",
    "TimelineScene",
    "PlayheadItem",
    "CurrentTimeLineItem",
    "TimelineView",
]
