"""Unit tests for TimeCoordinator calendar and config methods.

Tests calendar configuration loading and current time loading
extracted from MainWindow into TimeCoordinator.
"""

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication


class FakeMainWindow(QObject):
    """Minimal fake MainWindow for testing TimeCoordinator."""

    command_requested = Signal(object)

    def __init__(self):
        super().__init__()
        self.worker = MagicMock()
        self.event_editor = MagicMock()
        self.entity_editor = MagicMock()
        self.entity_editor._current_entity_id = None
        self.entity_editor.current_entity_id = None
        self.entity_editor.isVisible.return_value = False
        self.timeline = MagicMock()
        self.data_coordinator = MagicMock()
        self.map_widget = MagicMock()
        self.unified_list = MagicMock()
        self.longform_editor = MagicMock()
        self.longform_editor.content = MagicMock()
        self.ui_manager = MagicMock()
        self.workspace = MagicMock()
        self.lbl_world_time = MagicMock()
        self.lbl_playhead_time = MagicMock()
        self.calendar_converter = None
        self.time_coordinator = None  # Will be set after creation


@pytest.fixture
def qapp():
    """Fixture to provide QApplication instance."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def fake_window(qapp):
    """Create a FakeMainWindow for testing."""
    return FakeMainWindow()


@pytest.fixture
def coordinator(fake_window):
    """Create a TimeCoordinator with a fake MainWindow."""
    from src.app.coordinators.time_coordinator import TimeCoordinator

    coord = TimeCoordinator(fake_window)
    fake_window.time_coordinator = coord
    return coord


def test_relation_context_uses_playhead_not_world_time(coordinator, fake_window):
    fake_window.timeline.get_playhead_time.return_value = 125.5
    fake_window.timeline.get_current_time.return_value = 300.0
    fake_window.calendar_converter = object()
    coordinator._refresh_relation_time_context()
    for editor in (fake_window.entity_editor, fake_window.event_editor):
        editor.set_relation_time_context.assert_called_once_with(
            125.5, fake_window.calendar_converter
        )


class TestCalendarConfigLoading:
    """Tests for calendar config loaded handler."""

    def test_on_calendar_config_loaded_with_config(self, coordinator, fake_window):
        """Should create converter from provided config."""
        from src.core.calendar import CalendarConfig

        config = CalendarConfig.create_default()
        coordinator.on_calendar_config_loaded(config)

        # Editors and widgets should get the converter
        fake_window.event_editor.set_calendar_converter.assert_called_once()
        fake_window.timeline.set_calendar_converter.assert_called_once()
        fake_window.map_widget.set_calendar_converter.assert_called_once()
        fake_window.unified_list.set_calendar_converter.assert_called_once()
        fake_window.longform_editor.content.set_calendar_converter.assert_called_once()

    def test_on_calendar_config_loaded_without_config(self, coordinator, fake_window):
        """A failed load must not publish an unpersisted calendar identity."""
        coordinator.on_calendar_config_loaded(None)

        fake_window.event_editor.set_calendar_converter.assert_not_called()
        fake_window.timeline.set_calendar_converter.assert_not_called()
        assert fake_window.calendar_converter is None

    def test_on_calendar_config_loaded_stores_converter(self, coordinator, fake_window):
        """Should store calendar converter on main window."""
        from src.core.calendar import CalendarConfig

        coordinator.on_calendar_config_loaded(CalendarConfig.create_default())
        assert fake_window.calendar_converter is not None


class TestCurrentTimeLoading:
    """Tests for current time loaded handler."""

    def test_on_current_time_loaded(self, coordinator, fake_window):
        """Should set current time on timeline."""
        coordinator.on_current_time_loaded(42.5)
        fake_window.timeline.set_current_time.assert_called_once_with(42.5)


class TestRequestMethods:
    """Tests for request methods that communicate with worker."""

    def test_request_calendar_config(self, coordinator, fake_window):
        """Should invoke worker.load_calendar_config."""
        with patch(
            "src.app.coordinators.time_coordinator.invoke_queued"
        ) as mock_invoke:
            coordinator.request_calendar_config()
            mock_invoke.assert_called_once_with(
                fake_window.worker,
                "load_calendar_config",
            )

    def test_request_current_time(self, coordinator, fake_window):
        """Should invoke worker.load_current_time."""
        with patch(
            "src.app.coordinators.time_coordinator.invoke_queued"
        ) as mock_invoke:
            coordinator.request_current_time()
            mock_invoke.assert_called_once_with(
                fake_window.worker,
                "load_current_time",
            )


def test_stale_temporal_response_cannot_replace_newer_view(coordinator, fake_window):
    coordinator._current_playhead_time = 20.0
    coordinator._resolve_request_id = 3
    coordinator.on_entity_state_resolved(
        "entity-1", {"lore_time": 10.0, "resolve_request_id": 2}
    )
    coordinator.on_entity_state_resolved(
        "entity-1", {"lore_time": 20.0, "resolve_request_id": 2}
    )
    fake_window.entity_editor.display_temporal_state.assert_not_called()
    state = {"lore_time": 20.0, "resolve_request_id": 3}
    coordinator.on_entity_state_resolved("entity-1", state)
    fake_window.entity_editor.display_temporal_state.assert_called_once_with(
        "entity-1", state, 20.0
    )


def test_dirty_scrub_keeps_draft_pinned_until_save(coordinator, fake_window):
    editor = fake_window.entity_editor
    editor._temporal_time = 10.0
    editor._temporal_save_pending = True
    editor.has_unsaved_changes.return_value = True
    fake_window.timeline.get_playhead_time.return_value = 20.0
    with patch("src.app.coordinators.time_coordinator.QMessageBox") as dialog:
        dialog.return_value.addButton.side_effect = ["save", "discard", "cancel"]
        dialog.return_value.clickedButton.return_value = "save"
        coordinator.on_playhead_changed(20.0)
    editor._on_save.assert_called_once()
    assert coordinator._follow_after_save == 20.0
    fake_window.timeline.set_playhead_time.assert_not_called()
    editor.has_unsaved_changes.return_value = False
    editor.current_entity_id = "entity-1"
    with patch("src.app.coordinators.time_coordinator.invoke_queued") as invoke:
        coordinator.on_temporal_save_completed()
    assert coordinator._follow_after_save is None
    assert coordinator.current_playhead_time == 20.0
    invoke.assert_called_once()


def test_go_to_date_uses_playhead_fanout_and_centers(coordinator, fake_window):
    """Exact navigation does not change the world's current time."""
    fake_window.entity_editor.has_unsaved_changes.return_value = False
    fake_window.timeline.set_playhead_time.side_effect = coordinator.on_playhead_changed

    coordinator.go_to_date(42.25)

    fake_window.timeline.set_playhead_time.assert_called_once_with(42.25)
    fake_window.timeline.center_on_date.assert_called_once_with(42.25)
    fake_window.timeline.set_current_time.assert_not_called()
    fake_window.data_coordinator.on_graph_playhead_changed.assert_called_once()


def test_go_to_date_cancelled_by_dirty_guard_does_not_center(
    coordinator, fake_window
):
    editor = fake_window.entity_editor
    editor._temporal_time = 10.0
    editor.has_unsaved_changes.return_value = True
    fake_window.timeline.set_playhead_time.side_effect = coordinator.on_playhead_changed
    with patch("src.app.coordinators.time_coordinator.QMessageBox") as dialog:
        dialog.return_value.addButton.side_effect = ["save", "discard", "cancel"]
        dialog.return_value.clickedButton.return_value = "cancel"
        coordinator.go_to_date(20.0)

    assert fake_window.timeline.set_playhead_time.call_args_list[-1].args == (10.0,)
    fake_window.timeline.center_on_date.assert_not_called()


def test_go_to_date_discarded_draft_centers_target(coordinator, fake_window):
    editor = fake_window.entity_editor
    editor._temporal_time = 10.0
    editor.has_unsaved_changes.return_value = True
    fake_window.timeline.set_playhead_time.side_effect = coordinator.on_playhead_changed
    with patch("src.app.coordinators.time_coordinator.QMessageBox") as dialog:
        dialog.return_value.addButton.side_effect = ["save", "discard", "cancel"]
        dialog.return_value.clickedButton.return_value = "discard"
        coordinator.go_to_date(20.0)

    editor.set_dirty.assert_called_once_with(False)
    fake_window.timeline.center_on_date.assert_called_once_with(20.0)


def test_go_to_date_centers_after_deferred_entity_save(coordinator, fake_window):
    editor = fake_window.entity_editor
    editor._temporal_time = 10.0
    editor._temporal_save_pending = True
    editor.has_unsaved_changes.return_value = True
    fake_window.timeline.set_playhead_time.side_effect = coordinator.on_playhead_changed
    with patch("src.app.coordinators.time_coordinator.QMessageBox") as dialog:
        dialog.return_value.addButton.side_effect = ["save", "discard", "cancel"]
        dialog.return_value.clickedButton.return_value = "save"
        coordinator.go_to_date(20.0)

    fake_window.timeline.center_on_date.assert_not_called()
    editor.has_unsaved_changes.return_value = False
    with patch("src.app.coordinators.time_coordinator.invoke_queued"):
        coordinator.on_temporal_save_completed()
    fake_window.timeline.center_on_date.assert_called_once_with(20.0)


def test_failed_deferred_save_restores_previous_playhead(coordinator, fake_window):
    editor = fake_window.entity_editor
    editor._temporal_time = 10.0
    editor._temporal_save_pending = True
    editor.has_unsaved_changes.return_value = True
    fake_window.timeline.set_playhead_time.side_effect = coordinator.on_playhead_changed
    with patch("src.app.coordinators.time_coordinator.QMessageBox") as dialog:
        dialog.return_value.addButton.side_effect = ["save", "discard", "cancel"]
        dialog.return_value.clickedButton.return_value = "save"
        coordinator.go_to_date(20.0)

    editor._temporal_save_pending = False
    coordinator.on_temporal_save_failed()

    assert fake_window.timeline.set_playhead_time.call_args_list[-1].args == (10.0,)
    fake_window.timeline.center_on_date.assert_not_called()
    assert coordinator._pending_go_to_date is None
