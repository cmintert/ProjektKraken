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
        self.entity_editor.isVisible.return_value = False
        self.timeline = MagicMock()
        self.map_widget = MagicMock()
        self.unified_list = MagicMock()
        self.ui_manager = MagicMock()
        self.ui_manager.docks = {"event": MagicMock(), "entity": MagicMock()}
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


class TestCalendarConfigLoading:
    """Tests for calendar config loaded handler."""

    def test_on_calendar_config_loaded_with_config(
        self, coordinator, fake_window
    ):
        """Should create converter from provided config."""
        from src.core.calendar import CalendarConfig

        config = CalendarConfig.create_default()
        coordinator.on_calendar_config_loaded(config)

        # Editors and widgets should get the converter
        fake_window.event_editor.set_calendar_converter.assert_called_once()
        fake_window.timeline.set_calendar_converter.assert_called_once()
        fake_window.map_widget.set_calendar_converter.assert_called_once()
        fake_window.unified_list.set_calendar_converter.assert_called_once()

    def test_on_calendar_config_loaded_without_config(
        self, coordinator, fake_window
    ):
        """Should create default converter when no config provided."""
        coordinator.on_calendar_config_loaded(None)

        # Should still set converters using default
        fake_window.event_editor.set_calendar_converter.assert_called_once()
        fake_window.timeline.set_calendar_converter.assert_called_once()

    def test_on_calendar_config_loaded_stores_converter(
        self, coordinator, fake_window
    ):
        """Should store calendar converter on main window."""
        coordinator.on_calendar_config_loaded(None)
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
            "src.app.coordinators.time_coordinator.QMetaObject"
        ) as mock_meta:
            coordinator.request_calendar_config()
            mock_meta.invokeMethod.assert_called_once()
            args = mock_meta.invokeMethod.call_args
            assert args[0][1] == "load_calendar_config"

    def test_request_current_time(self, coordinator, fake_window):
        """Should invoke worker.load_current_time."""
        with patch(
            "src.app.coordinators.time_coordinator.QMetaObject"
        ) as mock_meta:
            coordinator.request_current_time()
            mock_meta.invokeMethod.assert_called_once()
            args = mock_meta.invokeMethod.call_args
            assert args[0][1] == "load_current_time"
