from unittest.mock import patch

import pytest

from src.app.main import MainWindow
from src.core.entities import Entity
from src.core.events import Event
from src.gui.models.explorer_model import ExplorerModel


@pytest.fixture
def main_window(qtbot):
    """Create MainWindow with mocked Worker."""
    from PySide6.QtWidgets import QMessageBox

    with patch("src.app.worker_manager.DatabaseWorker") as MockWorker:
        with (
            patch("src.app.worker_manager.QThread"),
            patch("src.app.main_window.QTimer"),
            patch(
                "src.app.coordinators.editor_coordinator.QMessageBox.warning",
                return_value=QMessageBox.Discard,
            ),
        ):
            # Mock worker and DB
            mock_worker = MockWorker.return_value
            mock_worker.db_service.get_all_events.return_value = []

            window = MainWindow()
            # window.show()  # needed for visibility checks often
            qtbot.addWidget(window)
            yield window


def _connect_creation_flow(window):
    """Connect the deferred signals used by creation in the test window."""
    window.unified_list.create_entity_requested.connect(
        window.editor_coordinator.create_entity
    )
    window.data_handler.lore_mutation_ready.connect(
        window.data_coordinator.on_lore_mutation_ready
    )
    window.data_handler.selection_requested.connect(
        window.data_coordinator.on_selection_requested
    )


def test_create_cancel_does_nothing(main_window):
    """Test cancelling creation."""
    with patch(
        "src.app.coordinators.editor_coordinator.QInputDialog.getText"
    ) as mock_input:
        mock_input.return_value = ("", False)

        with patch(
            "src.app.coordinators.editor_coordinator.CreateEntityCommand"
        ) as MockCmd:
            main_window.editor_coordinator.create_entity()
            MockCmd.assert_not_called()
            main_window.worker.run_command.assert_not_called()


def test_explorer_create_opens_new_entity(main_window, db_service):
    """A confirmed Explorer creation becomes the active editable context."""
    _connect_creation_flow(main_window)
    commands = []
    main_window.editor_coordinator.command_requested.connect(commands.append)
    with (
        patch(
            "src.app.coordinators.editor_coordinator.QInputDialog.getText",
            return_value=("Tasgillia", True),
        ),
        patch.object(main_window.data_coordinator, "load_entity_details") as load,
    ):
        main_window.unified_list.create_entity_requested.emit()
        assert len(commands) == 1
        result = commands[0].execute(db_service)
        assert result.success
        main_window.data_handler.on_command_finished(result)
        main_window.data_coordinator.on_entity_details_ready(
            db_service.get_entity(commands[0].entity_id), [], []
        )

    entity_id = commands[0].entity_id
    navigation = main_window.navigation_coordinator
    assert navigation.selected_type == "entity"
    assert navigation.selected_id == entity_id
    assert main_window.workspace.active_panel(
        main_window.workspace.panel_zone("entity")
    ) == "entity"
    load.assert_called_once_with(entity_id)
    assert main_window.entity_editor.current_entity_id == entity_id
    current = main_window.unified_list.list_widget.currentIndex()
    source = main_window.unified_list._proxy_model.mapToSource(current)
    assert main_window.unified_list._model.data(
        source, ExplorerModel.ItemIdRole
    ) == entity_id


def test_provisional_create_keeps_origin(main_window, db_service):
    """Quick Capture updates the model without changing editing context."""
    _connect_creation_flow(main_window)
    navigation = main_window.navigation_coordinator
    original_panel = main_window.workspace.active_panel(
        main_window.workspace.panel_zone("entity")
    )
    commands = []
    main_window.command_requested.connect(commands.append)
    with patch.object(main_window.data_coordinator, "load_entity_details") as load:
        navigation._materialize_provisional("entity", "Grey Ford")
        assert len(commands) == 1
        assert commands[0].select_after_create is False
        result = commands[0].execute(db_service)
        assert result.success
        main_window.data_handler.on_command_finished(result)

    assert navigation.selected_id is None
    assert main_window.workspace.active_panel(
        main_window.workspace.panel_zone("entity")
    ) == original_panel
    load.assert_not_called()
    assert any(
        entity.id == commands[0].entity_id
        for entity in main_window.data_coordinator.cached_entities
    )


def test_explorer_create_reveals_entity_hidden_by_search(main_window, db_service):
    """A search from the prior context cannot hide the new selection."""
    _connect_creation_flow(main_window)
    main_window.unified_list.search_bar.setText("unmatched")
    commands = []
    main_window.editor_coordinator.command_requested.connect(commands.append)
    with (
        patch(
            "src.app.coordinators.editor_coordinator.QInputDialog.getText",
            return_value=("Tasgillia", True),
        ),
        patch.object(main_window.data_coordinator, "load_entity_details"),
    ):
        main_window.unified_list.create_entity_requested.emit()
        result = commands[0].execute(db_service)
        main_window.data_handler.on_command_finished(result)

    assert main_window.unified_list.search_bar.text() == ""
    assert main_window.unified_list.list_widget.currentIndex().isValid()
    assert main_window.navigation_coordinator.selected_id == commands[0].entity_id


def test_explorer_create_reveals_entity_hidden_by_advanced_filter(
    main_window, db_service
):
    """The selected new entity remains visible despite a previous tag filter."""
    _connect_creation_flow(main_window)
    main_window.unified_list.set_advanced_filter({"include": ["missing"]})
    commands = []
    main_window.editor_coordinator.command_requested.connect(commands.append)
    with (
        patch(
            "src.app.coordinators.editor_coordinator.QInputDialog.getText",
            return_value=("Tasgillia", True),
        ),
        patch.object(main_window.data_coordinator, "load_entity_details"),
    ):
        main_window.unified_list.create_entity_requested.emit()
        result = commands[0].execute(db_service)
        main_window.data_handler.on_command_finished(result)

    assert main_window.unified_list.get_advanced_filter_config() == {}
    assert main_window.unified_list.list_widget.currentIndex().isValid()
    assert main_window.navigation_coordinator.selected_id == commands[0].entity_id


def test_select_item_switches_filter_if_needed(main_window):
    """Verify that select_item switches selection if item is hidden."""
    # Use real objects to avoid MagicMock 'name' comparison issues
    test_entity = Entity(id="ent1", name="Entity 1", type="Concept")
    test_event = Event(id="evt1", name="Event 1", lore_date=10.0, type="generic")

    # Pre-populate
    main_window.data_coordinator._cached_entities = [test_entity]
    main_window.data_coordinator._cached_events = [test_event]

    # Set data on unified_list
    main_window.unified_list.set_data(
        main_window.data_coordinator.cached_events,
        main_window.data_coordinator.cached_entities,
    )

    # 1. Set filter to "Entities Only"
    main_window.unified_list.filter_combo.setCurrentText("Entities Only")
    # Verify count - Entities Only shows entities
    model = main_window.unified_list._proxy_model
    assert model.rowCount() == 1

    # 2. Select Event (which is hidden)
    # Patch list_widget.setCurrentIndex to verify it gets called
    with patch.object(
        main_window.unified_list.list_widget, "setCurrentIndex"
    ) as mock_set:
        with patch.object(main_window.unified_list.list_widget, "scrollTo"):
            main_window.unified_list.select_item("event", "evt1")

            # Should have switched filter
            assert main_window.unified_list.filter_combo.currentText() == "All Items"
            assert mock_set.called
