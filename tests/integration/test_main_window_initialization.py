"""
Integration Tests for Initialization and Layout Components.

Tests the initialization helpers and layout restoration logic.
"""

import logging
import pytest
from PySide6.QtCore import QSettings, QTimer
from PySide6.QtWidgets import QApplication
from unittest.mock import Mock, patch

from src.app.connection_manager import ConnectionManager
from src.app.constants import (
    WINDOW_SETTINGS_KEY,
    WINDOW_SETTINGS_APP,
    SETTINGS_LAYOUT_VERSION_KEY,
    LAYOUT_VERSION,
)


@pytest.fixture
def qapp():
    """Fixture to provide QApplication instance."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def clean_settings():
    """Clean QSettings before and after test."""
    settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
    settings.clear()
    yield settings
    settings.clear()


@pytest.fixture
def mock_main_window(qapp):
    """Create a minimal mock MainWindow for testing."""
    from PySide6.QtWidgets import QMainWindow

    window = QMainWindow()

    # Add required attributes for ConnectionManager
    window.data_handler = Mock()
    window.unified_list = Mock()
    window.event_editor = Mock()
    window.entity_editor = Mock()
    window.timeline = Mock()
    window.longform_editor = Mock()
    window.map_widget = Mock()
    window.ai_search_panel = Mock()
    window.graph_widget = Mock()
    window.worker = Mock()
    window.longform_manager = Mock()
    window.map_handler = Mock()
    window.status_bar = Mock()

    # Add all required methods
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
    window.create_event = Mock()
    window.create_entity = Mock()
    window._on_item_delete_requested = Mock()
    window._on_item_selected = Mock()
    window.show_filter_dialog = Mock()
    window.clear_filter = Mock()
    window.add_relation = Mock()
    window.update_event = Mock()
    window.update_entity = Mock()
    window.navigate_to_entity = Mock()
    window.remove_relation = Mock()
    window.update_relation = Mock()
    window.on_return_to_present = Mock()
    window.load_event_details = Mock()
    window.load_entity_details = Mock()
    window.on_current_time_changed = Mock()
    window.update_playhead_time_label = Mock()
    window._on_playhead_changed = Mock()
    window._on_event_date_changed = Mock()
    window._on_tag_color_change_requested = Mock()
    window._on_remove_from_grouping_requested = Mock()
    window.promote_longform_entry = Mock()
    window.demote_longform_entry = Mock()
    window.export_longform_document = Mock()
    window.move_longform_entry = Mock()
    window.show_longform_filter_dialog = Mock()
    window.clear_longform_filter = Mock()
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
    window.perform_semantic_search = Mock()
    window._on_search_result_selected = Mock()
    window.load_graph_data = Mock()
    window.load_data = Mock()  # For unified_list refresh

    return window


class TestConnectionManagerIntegration:
    """Integration tests for ConnectionManager."""

    def test_connect_all_returns_statistics(self, mock_main_window):
        """Test that connect_all returns proper statistics."""
        manager = ConnectionManager(mock_main_window)

        stats = manager.connect_all()

        assert isinstance(stats, dict)
        assert "total_attempted" in stats
        assert "total_succeeded" in stats
        assert "total_failed" in stats
        assert stats["total_attempted"] > 0
        assert stats["total_succeeded"] >= 0
        assert stats["total_failed"] >= 0
        assert (
            stats["total_succeeded"] + stats["total_failed"] == stats["total_attempted"]
        )

    def test_connect_all_logs_summary(self, mock_main_window, caplog):
        """Test that connect_all logs connection summary."""
        caplog.set_level(logging.INFO)

        manager = ConnectionManager(mock_main_window)
        manager.connect_all()

        assert any(
            "Signal connections complete" in record.message for record in caplog.records
        )

    def test_individual_connect_methods_return_counts(self, mock_main_window):
        """Test that individual connect methods return failure counts."""
        manager = ConnectionManager(mock_main_window)

        # Test each method returns an int
        data_handler_failures = manager.connect_data_handler()
        assert isinstance(data_handler_failures, int)

        unified_list_failures = manager.connect_unified_list()
        assert isinstance(unified_list_failures, int)

        editor_failures = manager.connect_editors()
        assert isinstance(editor_failures, int)

        timeline_failures = manager.connect_timeline()
        assert isinstance(timeline_failures, int)

        longform_failures = manager.connect_longform_editor()
        assert isinstance(longform_failures, int)

        map_failures = manager.connect_map_widget()
        assert isinstance(map_failures, int)

        ai_failures = manager.connect_ai_search_panel()
        assert isinstance(ai_failures, int)

        graph_failures = manager.connect_graph_widget()
        assert isinstance(graph_failures, int)


class TestLayoutVersioning:
    """Tests for layout versioning logic."""

    def test_layout_version_constant_exists(self):
        """Test that LAYOUT_VERSION constant is defined."""
        assert LAYOUT_VERSION is not None
        assert isinstance(LAYOUT_VERSION, str)
        assert len(LAYOUT_VERSION) > 0

    def test_settings_key_constant_exists(self):
        """Test that settings key constant is defined."""
        assert SETTINGS_LAYOUT_VERSION_KEY is not None
        assert isinstance(SETTINGS_LAYOUT_VERSION_KEY, str)


class TestSignalValidation:
    """Tests for signal connection validation."""

    def test_safe_connection_with_missing_signal(self, mock_main_window):
        """Test that safe connection handles missing signals."""
        manager = ConnectionManager(mock_main_window)

        # Create object without signal
        obj = Mock(spec=[])  # Empty spec, no attributes

        result = manager._connect_signal_safe(
            obj, "nonexistent_signal", Mock(), "TestObject"
        )

        assert result is False

    def test_safe_connection_with_valid_signal(self, mock_main_window):
        """Test that safe connection succeeds with valid signal."""
        from PySide6.QtCore import QObject, Signal

        class TestObject(QObject):
            test_signal = Signal()

        manager = ConnectionManager(mock_main_window)
        obj = TestObject()
        slot = Mock()

        result = manager._connect_signal_safe(obj, "test_signal", slot, "TestObject")

        assert result is True

    def test_safe_connection_with_none_object(self, mock_main_window):
        """Test that safe connection handles None object."""
        manager = ConnectionManager(mock_main_window)

        result = manager._connect_signal_safe(None, "test_signal", Mock(), "NoneObject")

        assert result is False

    def test_safe_connection_with_invalid_slot(self, mock_main_window):
        """Test that safe connection handles invalid slot."""
        from PySide6.QtCore import QObject, Signal

        class TestObject(QObject):
            test_signal = Signal()

        manager = ConnectionManager(mock_main_window)
        obj = TestObject()

        result = manager._connect_signal_safe(
            obj, "test_signal", "not_callable", "TestObject"
        )

        assert result is False
