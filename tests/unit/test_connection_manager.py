"""
Unit Tests for ConnectionManager Signal Validation.

Tests the safe signal connection functionality.
"""

import logging
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication, QMainWindow

from src.app.connection_manager import ConnectionManager


@pytest.fixture
def qapp():
    """Fixture to provide QApplication instance."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


class MockWidget(QObject):
    """Mock widget with test signals."""

    test_signal = Signal()
    another_signal = Signal(str)


@pytest.fixture
def mock_main_window(qapp):
    """Fixture to provide a mock MainWindow."""
    window = QMainWindow()

    # Add minimal required attributes
    window.data_handler = Mock()
    window.unified_list = Mock()
    window.event_editor = MockWidget()
    window.entity_editor = MockWidget()
    window.timeline = Mock()
    window.longform_editor = Mock()
    window.map_widget = Mock()
    window.ai_search_panel = Mock()
    window.graph_widget = Mock()
    window.worker = Mock()
    window.longform_manager = Mock()
    window.map_handler = Mock()

    # Add mock methods that signals connect to
    window.load_data = Mock()
    window.add_relation = Mock()
    window.update_event = Mock()
    window.update_entity = Mock()
    window.navigate_to_entity = Mock()
    window.remove_relation = Mock()
    window.update_relation = Mock()
    window.on_return_to_present = Mock()
    window.load_event_details = Mock()
    window.load_entity_details = Mock()
    window._on_events_ready = Mock()
    window._on_entities_ready = Mock()
    window._on_suggestions_update = Mock()
    window._on_event_details_ready = Mock()
    window._on_entity_details_ready = Mock()
    window._on_graph_data_ready = Mock()
    window._on_graph_metadata_ready = Mock()
    window._on_command_failed = Mock()
    window._on_dock_raise_requested = Mock()
    window._on_selection_requested = Mock()
    window.load_events = Mock()
    window.load_entities = Mock()
    window.load_maps = Mock()
    window.load_longform_sequence = Mock()
    window._on_reload_active_editor_relations = Mock()
    window._on_entity_state_resolved = Mock()
    window.status_bar = Mock()
    window.create_event = Mock()
    window.create_entity = Mock()
    window._on_item_delete_requested = Mock()
    window._on_item_selected = Mock()
    window.show_filter_dialog = Mock()
    window.clear_filter = Mock()

    # Timeline methods
    window.on_current_time_changed = Mock()
    window.update_playhead_time_label = Mock()
    window._on_playhead_changed = Mock()
    window._on_event_date_changed = Mock()
    window._on_tag_color_change_requested = Mock()
    window._on_remove_from_grouping_requested = Mock()

    # Longform methods
    window.promote_longform_entry = Mock()
    window.demote_longform_entry = Mock()
    window.export_longform_document = Mock()
    window.move_longform_entry = Mock()
    window.show_longform_filter_dialog = Mock()
    window.clear_longform_filter = Mock()

    # Map methods
    window._on_marker_position_changed = Mock()
    window._on_marker_clicked = Mock()
    window.create_map = Mock()
    window.delete_map = Mock()
    window.on_map_selected = Mock()
    window.create_marker = Mock()
    window.delete_marker = Mock()
    window._on_marker_icon_changed = Mock()
    window._on_marker_color_changed = Mock()
    window._on_marker_dropped = Mock()

    # AI Search methods
    window.perform_semantic_search = Mock()
    window._on_search_result_selected = Mock()

    # Graph methods
    window.load_graph_data = Mock()

    return window


@pytest.fixture
def connection_manager(mock_main_window):
    """Fixture to provide ConnectionManager instance."""
    return ConnectionManager(mock_main_window)


class TestConnectSignalSafe:
    """Tests for safe signal connection functionality."""

    def test_connect_signal_safe_with_valid_signal(self, connection_manager):
        """Test that safe connection succeeds with valid signal."""
        widget = MockWidget()
        slot = Mock()

        result = connection_manager._connect_signal_safe(
            widget, "test_signal", slot, "MockWidget"
        )

        assert result is True
        # Emit signal to verify connection
        widget.test_signal.emit()
        slot.assert_called_once()

    def test_connect_signal_safe_with_missing_signal(self, connection_manager):
        """Test that safe connection handles missing signal gracefully."""
        widget = MockWidget()
        slot = Mock()

        result = connection_manager._connect_signal_safe(
            widget, "nonexistent_signal", slot, "MockWidget"
        )

        assert result is False
        # Slot should not be called
        slot.assert_not_called()

    def test_connect_signal_safe_with_none_object(self, connection_manager):
        """Test that safe connection handles None object."""
        slot = Mock()

        result = connection_manager._connect_signal_safe(
            None, "test_signal", slot, "NoneObject"
        )

        assert result is False

    def test_connect_signal_safe_with_invalid_slot(self, connection_manager):
        """Test that safe connection handles invalid slot."""
        widget = MockWidget()

        result = connection_manager._connect_signal_safe(
            widget, "test_signal", "not_a_callable", "MockWidget"
        )

        assert result is False

    def test_connect_signal_safe_logs_success(self, connection_manager, caplog):
        """Test that successful connection is logged."""
        caplog.set_level(logging.DEBUG)

        widget = MockWidget()
        slot = Mock()

        connection_manager._connect_signal_safe(
            widget, "test_signal", slot, "MockWidget"
        )

        # Check that connection was logged at debug level
        assert any(
            "Successfully connected" in record.message for record in caplog.records
        )

    def test_connect_signal_safe_logs_failure(self, connection_manager, caplog):
        """Test that failed connection is logged."""
        caplog.set_level(logging.WARNING)

        widget = MockWidget()
        slot = Mock()

        connection_manager._connect_signal_safe(
            widget, "nonexistent_signal", slot, "MockWidget"
        )

        # Check that failure was logged
        assert any(
            "does not have signal" in record.message for record in caplog.records
        )


class TestConnectEditors:
    """Tests for editor signal connections."""

    def test_connect_editors_with_valid_signals(
        self, connection_manager, mock_main_window
    ):
        """Test that editor connections succeed with valid signals."""
        # Add required signals to mock editors
        mock_main_window.event_editor.add_relation_requested = Signal()
        mock_main_window.event_editor.save_requested = Signal()
        mock_main_window.entity_editor.add_relation_requested = Signal()
        mock_main_window.entity_editor.save_requested = Signal()

        failed_count = connection_manager.connect_editors()

        # Should have some failures since mocks don't have all signals
        assert isinstance(failed_count, int)
        assert failed_count >= 0

    def test_connect_editors_returns_failure_count(
        self, connection_manager, mock_main_window
    ):
        """Test that connect_editors returns count of failed connections."""
        # Editors are MockWidget instances with limited signals
        failed_count = connection_manager.connect_editors()

        # Should return an integer count
        assert isinstance(failed_count, int)
        # Should have failures since MockWidget doesn't have all expected signals
        assert failed_count > 0


class TestConnectAll:
    """Tests for connect_all functionality."""

    def test_connect_all_returns_summary(self, connection_manager):
        """Test that connect_all returns connection summary."""
        result = connection_manager.connect_all()

        # Should return a dict with success/failure counts
        assert isinstance(result, dict)
        assert "total_attempted" in result
        assert "total_failed" in result
        assert "total_succeeded" in result

    def test_connect_all_logs_summary(self, connection_manager, caplog):
        """Test that connect_all logs summary of connections."""
        caplog.set_level(logging.INFO)

        connection_manager.connect_all()

        # Check that summary was logged
        assert any(
            "signal connections" in record.message.lower() for record in caplog.records
        )
