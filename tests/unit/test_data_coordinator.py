"""Unit tests for DataCoordinator.

Tests data loading, signal handler dispatch, graph refresh, and
summary result routing extracted from MainWindow into a focused coordinator.
"""

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication


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
def fake_window(qapp):
    """Create a FakeMainWindow for testing."""
    return FakeMainWindow()


@pytest.fixture
def coordinator(fake_window):
    """Create a DataCoordinator with a fake MainWindow."""
    from src.app.coordinators.data_coordinator import DataCoordinator

    return DataCoordinator(fake_window)


class TestDataLoading:
    """Tests for data loading methods."""

    def test_load_events_invokes_worker(self, coordinator, fake_window):
        """load_events should invoke worker.load_events via QMetaObject."""
        with patch(
            "src.app.coordinators.data_coordinator.QMetaObject"
        ) as mock_meta:
            coordinator.load_events()
            mock_meta.invokeMethod.assert_called_once()
            args = mock_meta.invokeMethod.call_args
            assert args[0][1] == "load_events"

    def test_load_entities_invokes_worker(self, coordinator, fake_window):
        """load_entities should invoke worker.load_entities via QMetaObject."""
        with patch(
            "src.app.coordinators.data_coordinator.QMetaObject"
        ) as mock_meta:
            coordinator.load_entities()
            mock_meta.invokeMethod.assert_called_once()
            args = mock_meta.invokeMethod.call_args
            assert args[0][1] == "load_entities"

    def test_load_event_details_invokes_worker(self, coordinator, fake_window):
        """load_event_details should invoke worker with event_id."""
        with patch(
            "src.app.coordinators.data_coordinator.QMetaObject"
        ) as mock_meta:
            coordinator.load_event_details("evt-123")
            mock_meta.invokeMethod.assert_called_once()
            args = mock_meta.invokeMethod.call_args
            assert args[0][1] == "load_event_details"

    def test_load_entity_details_invokes_worker(self, coordinator, fake_window):
        """load_entity_details should invoke worker with entity_id."""
        with patch(
            "src.app.coordinators.data_coordinator.QMetaObject"
        ) as mock_meta:
            coordinator.load_entity_details("ent-456")
            mock_meta.invokeMethod.assert_called_once()
            args = mock_meta.invokeMethod.call_args
            assert args[0][1] == "load_entity_details"

    def test_load_completer_data_invokes_worker(self, coordinator, fake_window):
        """load_completer_data should invoke worker.load_completer_data."""
        with patch(
            "src.app.coordinators.data_coordinator.QMetaObject"
        ) as mock_meta:
            coordinator.load_completer_data()
            mock_meta.invokeMethod.assert_called_once()
            args = mock_meta.invokeMethod.call_args
            assert args[0][1] == "load_completer_data"

    def test_load_data_calls_all_loaders(self, coordinator, fake_window):
        """load_data should refresh all data and reload active editors."""
        with patch.object(coordinator, "load_events") as m_events, \
             patch.object(coordinator, "load_entities") as m_entities, \
             patch.object(coordinator, "load_completer_data") as m_completer, \
             patch.object(coordinator, "load_graph_data") as m_graph:
            coordinator.load_data()
            m_events.assert_called_once()
            m_entities.assert_called_once()
            m_completer.assert_called_once()
            m_graph.assert_called_once()

    def test_load_data_reloads_active_event_editor(
        self, coordinator, fake_window
    ):
        """load_data should reload the active event editor."""
        fake_window.event_editor._current_event_id = "evt-123"
        with patch.object(coordinator, "load_events"), \
             patch.object(coordinator, "load_entities"), \
             patch.object(coordinator, "load_completer_data"), \
             patch.object(coordinator, "load_graph_data"), \
             patch.object(coordinator, "load_event_details") as m_details:
            coordinator.load_data()
            m_details.assert_called_once_with("evt-123")

    def test_load_data_reloads_active_entity_editor(
        self, coordinator, fake_window
    ):
        """load_data should reload the active entity editor."""
        fake_window.entity_editor._current_entity_id = "ent-456"
        with patch.object(coordinator, "load_events"), \
             patch.object(coordinator, "load_entities"), \
             patch.object(coordinator, "load_completer_data"), \
             patch.object(coordinator, "load_graph_data"), \
             patch.object(coordinator, "load_entity_details") as m_details:
            coordinator.load_data()
            m_details.assert_called_once_with("ent-456")


class TestSignalHandlers:
    """Tests for data-ready signal handlers."""

    def test_on_events_ready_updates_widgets(self, coordinator, fake_window):
        """on_events_ready should update unified_list, timeline, and map."""
        events = [MagicMock(id="e1"), MagicMock(id="e2")]
        coordinator.on_events_ready(events)

        assert coordinator.cached_events == events
        fake_window.unified_list.set_data.assert_called_once()
        fake_window.timeline.set_events.assert_called_once_with(events)
        fake_window.map_widget.set_cached_items.assert_called_once()

    def test_on_entities_ready_updates_widgets(self, coordinator, fake_window):
        """on_entities_ready should update unified_list and map."""
        entities = [MagicMock(id="n1")]
        coordinator.on_entities_ready(entities)

        assert coordinator.cached_entities == entities
        fake_window.unified_list.set_data.assert_called_once()
        fake_window.map_widget.set_cached_items.assert_called_once()

    def test_on_event_details_ready_loads_editor(
        self, coordinator, fake_window
    ):
        """on_event_details_ready should load event into editor."""
        event = MagicMock()
        relations = [MagicMock()]
        incoming = [MagicMock()]
        coordinator.on_event_details_ready(event, relations, incoming)
        fake_window.event_editor.load_event.assert_called_once_with(
            event, relations, incoming
        )

    def test_on_entity_details_ready_loads_editor(
        self, coordinator, fake_window
    ):
        """on_entity_details_ready should load entity into editor."""
        entity = MagicMock()
        relations = [MagicMock()]
        incoming = [MagicMock()]
        coordinator.on_entity_details_ready(entity, relations, incoming)
        fake_window.entity_editor.load_entity.assert_called_once_with(
            entity, relations, incoming
        )

    def test_on_suggestions_update(self, coordinator, fake_window):
        """on_suggestions_update should update both editors."""
        items = [("id1", "Name1", "entity")]
        coordinator.on_suggestions_update(items)
        fake_window.event_editor.update_suggestions.assert_called_once_with(
            items=items
        )
        fake_window.entity_editor.update_suggestions.assert_called_once_with(
            items=items
        )

    def test_on_dock_raise_requested(self, coordinator, fake_window):
        """on_dock_raise_requested should raise the requested dock."""
        coordinator.on_dock_raise_requested("event")
        fake_window.ui_manager.docks["event"].raise_.assert_called_once()

    def test_on_dock_raise_requested_unknown_dock(
        self, coordinator, fake_window
    ):
        """on_dock_raise_requested should handle unknown dock names safely."""
        # Should not raise
        coordinator.on_dock_raise_requested("unknown_dock")

    def test_on_selection_requested(self, coordinator, fake_window):
        """on_selection_requested should select item in unified list."""
        coordinator.on_selection_requested("event", "evt-123")
        fake_window.unified_list.select_item.assert_called_once_with(
            "event", "evt-123"
        )

    def test_on_command_failed_shows_warning(self, coordinator, fake_window):
        """on_command_failed should show a warning message box."""
        with patch(
            "src.app.coordinators.data_coordinator.QMessageBox"
        ) as mock_box:
            coordinator.on_command_failed("Something failed")
            mock_box.warning.assert_called_once()

    def test_on_filter_results_ready(self, coordinator, fake_window):
        """on_filter_results_ready should update unified list."""
        events = [MagicMock()]
        entities = [MagicMock(), MagicMock()]
        coordinator.on_filter_results_ready(events, entities)
        fake_window.unified_list.set_data.assert_called_once_with(
            events, entities
        )
        fake_window.status_bar.showMessage.assert_called_once()


class TestGraphData:
    """Tests for graph data loading and refresh."""

    def test_on_graph_data_ready_updates_widget(
        self, coordinator, fake_window
    ):
        """on_graph_data_ready should display graph data."""
        nodes = [{"id": "n1"}]
        edges = [{"source": "n1", "target": "n2"}]
        coordinator.on_graph_data_ready(nodes, edges)
        fake_window.graph_widget.display_graph.assert_called_once()

    def test_on_graph_metadata_ready_updates_widget(
        self, coordinator, fake_window
    ):
        """on_graph_metadata_ready should set available tags and types."""
        tags = ["tag1", "tag2"]
        rel_types = ["relates_to"]
        coordinator.on_graph_metadata_ready(tags, rel_types)
        fake_window.graph_widget.set_available_tags.assert_called_once_with(
            tags
        )
        fake_window.graph_widget.set_available_relation_types.assert_called_once_with(
            rel_types
        )

    def test_load_graph_data_emits_signal(self, coordinator, fake_window):
        """load_graph_data should emit load_graph_data_requested signal."""
        fake_window.graph_widget.get_filter_config.return_value = {
            "tags": ["tag1"],
            "rel_types": ["type1"],
        }
        signals = []
        fake_window.load_graph_data_requested.connect(
            lambda t, r: signals.append((t, r))
        )
        coordinator.load_graph_data()
        assert len(signals) == 1


class TestReloadActiveEditorRelations:
    """Tests for reloading active editor relations."""

    def test_reload_event_relations(self, coordinator, fake_window):
        """Should reload event details when event editor is active."""
        fake_window.navigation_coordinator.selected_type = "event"
        fake_window.event_editor._current_event_id = "evt-123"
        with patch.object(coordinator, "load_event_details") as m:
            coordinator.on_reload_active_editor_relations()
            m.assert_called_once_with("evt-123")

    def test_reload_entity_relations(self, coordinator, fake_window):
        """Should reload entity details when entity editor is active."""
        fake_window.navigation_coordinator.selected_type = "entity"
        fake_window.entity_editor._current_entity_id = "ent-456"
        with patch.object(coordinator, "load_entity_details") as m:
            coordinator.on_reload_active_editor_relations()
            m.assert_called_once_with("ent-456")

    def test_no_reload_when_no_active_editor(self, coordinator, fake_window):
        """Should not crash when no editor is active."""
        fake_window.navigation_coordinator.selected_type = None
        with patch.object(coordinator, "load_event_details") as m_evt, \
             patch.object(coordinator, "load_entity_details") as m_ent:
            coordinator.on_reload_active_editor_relations()
            m_evt.assert_not_called()
            m_ent.assert_not_called()


class TestCompleterData:
    """Tests for completer data handling."""

    def test_on_completer_data_loaded(self, coordinator, fake_window):
        """Should update tag, attr, rel_type, and entity_type suggestions."""
        coordinator.on_completer_data_loaded(
            tags=["tag1"],
            rel_types=["relates_to"],
            attr_keys=["key1"],
            entity_types=["Person"],
        )
        fake_window.entity_editor.update_tag_suggestions.assert_called_once_with(
            ["tag1"]
        )
        fake_window.entity_editor.update_attribute_suggestions.assert_called_once_with(
            ["key1"]
        )
        fake_window.entity_editor.update_relation_type_suggestions.assert_called_once_with(
            ["relates_to"]
        )
        fake_window.entity_editor.update_entity_type_suggestions.assert_called_once_with(
            ["Person"]
        )
        fake_window.event_editor.update_tag_suggestions.assert_called_once_with(
            ["tag1"]
        )
        fake_window.event_editor.update_attribute_suggestions.assert_called_once_with(
            ["key1"]
        )
        fake_window.event_editor.update_relation_type_suggestions.assert_called_once_with(
            ["relates_to"]
        )


class TestSummaryResult:
    """Tests for summary generation result routing."""

    def test_summary_routed_to_entity_editor(self, coordinator, fake_window):
        """Summary should be routed to entity editor when it holds the ID."""
        fake_window.entity_editor._current_entity_id = "ent-123"
        fake_window.event_editor._current_event_id = None
        summary_data = MagicMock()

        coordinator.on_summary_generated_result("ent-123", summary_data)
        fake_window.entity_editor.on_summary_generated.assert_called_once_with(
            summary_data
        )

    def test_summary_routed_to_event_editor(self, coordinator, fake_window):
        """Summary should be routed to event editor when it holds the ID."""
        fake_window.entity_editor._current_entity_id = None
        fake_window.event_editor._current_event_id = "evt-456"
        summary_data = MagicMock()

        coordinator.on_summary_generated_result("evt-456", summary_data)
        fake_window.event_editor.on_summary_generated.assert_called_once_with(
            summary_data
        )

    def test_summary_no_matching_editor(self, coordinator, fake_window):
        """When no editor holds the ID, should show error."""
        fake_window.entity_editor._current_entity_id = None
        fake_window.event_editor._current_event_id = None
        summary_data = MagicMock()

        # Should not raise
        coordinator.on_summary_generated_result("unknown-id", summary_data)
