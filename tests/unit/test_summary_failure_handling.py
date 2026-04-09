"""Tests for summary generation failure handling.

Verifies that when summary generation fails, the UI button state is properly reset.
"""

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

from src.app.coordinators.data_coordinator import DataCoordinator
from src.core.entities import Entity
from src.core.events import Event
from src.gui.widgets.entity_editor import EntityEditorWidget
from src.gui.widgets.event_editor import EventEditorWidget


class FakeMainWindow(QObject):
    """Minimal fake MainWindow for testing DataCoordinator."""

    command_requested = Signal(object)
    load_graph_data_requested = Signal(object, object)

    def __init__(self):
        super().__init__()
        self.worker = MagicMock()
        self.event_editor = MagicMock()
        self.entity_editor = MagicMock()
        self.entity_editor._current_entity_id = None
        self.event_editor._current_event_id = None
        self.unified_list = MagicMock()
        self.timeline = MagicMock()
        self.map_widget = MagicMock()
        self.graph_widget = MagicMock()
        self.longform_editor = MagicMock()
        self.longform_manager = MagicMock()
        self.status_bar = MagicMock()
        self.ui_manager = MagicMock()
        self.ui_manager.docks = {
            "event": MagicMock(),
            "entity": MagicMock(),
            "list": MagicMock(),
            "timeline": MagicMock(),
        }
        self.navigation_coordinator = MagicMock()
        self.navigation_coordinator.selected_type = None
        self.navigation_coordinator.selected_id = None


@pytest.fixture
def qapp():
    """Fixture to provide QApplication instance."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def mock_main_window(qapp):
    """Create a mock main window with entity and event editors."""
    return FakeMainWindow()


@pytest.fixture
def coordinator(mock_main_window):
    """Create a DataCoordinator with a fake MainWindow."""
    return DataCoordinator(mock_main_window)


class TestSummaryFailureHandling:
    """Tests for summary generation failure signal routing."""

    def test_failure_routed_to_entity_editor(self, coordinator, mock_main_window):
        """When entity is active, failure should be routed to entity editor."""
        mock_main_window.entity_editor._current_entity_id = "test_entity_1"
        mock_main_window.event_editor._current_event_id = None

        coordinator.on_summary_generation_failed("test_entity_1")

        mock_main_window.entity_editor.on_summary_generation_failed.assert_called_once()
        mock_main_window.event_editor.on_summary_generation_failed.assert_not_called()

    def test_failure_routed_to_event_editor(self, coordinator, mock_main_window):
        """When event is active, failure should be routed to event editor."""
        mock_main_window.entity_editor._current_entity_id = None
        mock_main_window.event_editor._current_event_id = "test_event_1"

        coordinator.on_summary_generation_failed("test_event_1")

        mock_main_window.event_editor.on_summary_generation_failed.assert_called_once()
        mock_main_window.entity_editor.on_summary_generation_failed.assert_not_called()

    def test_failure_no_matching_editor(self, coordinator, mock_main_window):
        """When item is not active, no editor handler should be called."""
        mock_main_window.entity_editor._current_entity_id = "other_entity"
        mock_main_window.event_editor._current_event_id = "other_event"

        coordinator.on_summary_generation_failed("unrelated_item")

        mock_main_window.entity_editor.on_summary_generation_failed.assert_not_called()
        mock_main_window.event_editor.on_summary_generation_failed.assert_not_called()


class TestEntityEditorSummaryFailure:
    """Tests for entity editor failure handler."""

    def test_on_summary_generation_failed_resets_button(self):
        """When generation fails, button should be enabled and text reset."""
        editor = MagicMock(spec=EntityEditorWidget)
        editor.summary_widget = MagicMock()
        editor.summary_widget.generate_btn = MagicMock()
        editor.summary_widget.generate_btn.text.return_value = "Generating..."

        # Call the actual method
        EntityEditorWidget.on_summary_generation_failed(editor)

        editor.summary_widget.generate_btn.setEnabled.assert_called_with(True)
        editor.summary_widget.generate_btn.setText.assert_called_with("Generate")

    def test_button_text_only_reset_if_generating(self):
        """Button text should only be reset if it says 'Generating...'."""
        editor = MagicMock(spec=EntityEditorWidget)
        editor.summary_widget = MagicMock()
        editor.summary_widget.generate_btn = MagicMock()
        editor.summary_widget.generate_btn.text.return_value = "Regenerate"

        # Call the actual method
        EntityEditorWidget.on_summary_generation_failed(editor)

        editor.summary_widget.generate_btn.setEnabled.assert_called_with(True)
        # setText should not be called if text is not "Generating..."
        editor.summary_widget.generate_btn.setText.assert_not_called()


class TestEventEditorSummaryFailure:
    """Tests for event editor failure handler."""

    def test_on_summary_generation_failed_resets_button(self):
        """When generation fails, button should be enabled and text reset."""
        editor = MagicMock(spec=EventEditorWidget)
        editor.summary_widget = MagicMock()
        editor.summary_widget.generate_btn = MagicMock()
        editor.summary_widget.generate_btn.text.return_value = "Generating..."

        # Call the actual method
        EventEditorWidget.on_summary_generation_failed(editor)

        editor.summary_widget.generate_btn.setEnabled.assert_called_with(True)
        editor.summary_widget.generate_btn.setText.assert_called_with("Generate")

    def test_button_text_only_reset_if_generating(self):
        """Button text should only be reset if it says 'Generating...'."""
        editor = MagicMock(spec=EventEditorWidget)
        editor.summary_widget = MagicMock()
        editor.summary_widget.generate_btn = MagicMock()
        editor.summary_widget.generate_btn.text.return_value = "Regenerate"

        # Call the actual method
        EventEditorWidget.on_summary_generation_failed(editor)

        editor.summary_widget.generate_btn.setEnabled.assert_called_with(True)
        # setText should not be called if text is not "Generating..."
        editor.summary_widget.generate_btn.setText.assert_not_called()
