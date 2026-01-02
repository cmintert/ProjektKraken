"""
Tests for Entity integration in MainWindow.
"""

from unittest.mock import patch

import pytest

from src.app.main import MainWindow
from src.core.entities import Entity


@pytest.fixture
def main_window(qtbot):
    """Create MainWindow with mocked Worker."""
    with patch("src.app.worker_manager.DatabaseWorker"):
        # Avoid thread start in test and prevent deferred init crash
        with patch("src.app.worker_manager.QThread"), patch("src.app.worker_manager.QTimer"):
            window = MainWindow()
            # window.show()  <-- Removed for headless testing
            qtbot.addWidget(window)
            yield window


def test_entity_docks_exist(main_window):
    """Test that entity docks are created."""
    assert main_window.list_dock is not None
    assert main_window.entity_editor_dock is not None
    # "Project Explorer" is the name of the dock now
    assert main_window.list_dock.toggleViewAction().text() == "Project Explorer"


def test_create_entity(main_window):
    """Test creating an entity."""
    with patch("src.app.main_window.QInputDialog.getText") as mock_input:
        mock_input.return_value = ("Test Entity", True)

        with patch("src.app.main_window.CreateEntityCommand") as MockCmd:
            mock_cmd_instance = MockCmd.return_value

            main_window.create_entity()

            MockCmd.assert_called_once()
            # Check initialization args
            args, _ = MockCmd.call_args
            assert args[0] == {"name": "Test Entity", "type": "Concept"}

            # Should delegate to worker
            main_window.worker.run_command.assert_called_once_with(mock_cmd_instance)


def test_delete_entity(main_window):
    """Test deleting an entity."""
    with patch("src.app.main_window.DeleteEntityCommand") as MockCmd:
        mock_cmd_instance = MockCmd.return_value

        main_window.delete_entity("ent1")

        MockCmd.assert_called_once()
        main_window.worker.run_command.assert_called_once_with(mock_cmd_instance)


def test_update_entity(main_window):
    """Test updating an entity."""
    entity_data = {"id": "ent1", "name": "Updated", "type": "Concept"}

    with patch("src.app.main_window.UpdateEntityCommand") as MockCmd:
        # main_window.update_entity now expects dict
        main_window.update_entity(entity_data)

        MockCmd.assert_called_once_with("ent1", entity_data)
        # Check command sent
        main_window.worker.run_command.assert_called_once()
        args = main_window.worker.run_command.call_args[0]
        assert args[0] == MockCmd.return_value


def test_load_entity_details_signal(main_window):
    """Test response to details loaded signal."""
    entity = Entity(id="ent1", name="Test", type="Concept")
    relations = [{"id": "rel1"}]
    incoming = [{"id": "rel2"}]

    with patch.object(main_window.entity_editor, "load_entity") as mock_load:
        # Simulate signal emission
        main_window.data_handler.on_entity_details_loaded(entity, relations, incoming)

        mock_load.assert_called_once_with(entity, relations, incoming)
        # Check dock raise
        assert not main_window.entity_editor_dock.isHidden()


def test_entity_add_relation(main_window):
    """Test adding a relation from entity editor."""
    main_window.entity_editor._current_entity_id = "src"

    with patch("src.app.main_window.AddRelationCommand") as MockCmd:
        mock_cmd_instance = MockCmd.return_value

        main_window.add_relation("src", "tgt", "caused", bidirectional=True)

        MockCmd.assert_called_once_with(
            "src", "tgt", "caused", attributes=None, bidirectional=True
        )
        main_window.worker.run_command.assert_called_once_with(mock_cmd_instance)


def test_entity_remove_relation(main_window):
    """Test removing a relation from entity editor."""
    with patch("src.app.main_window.RemoveRelationCommand") as MockCmd:
        mock_cmd_instance = MockCmd.return_value

        main_window.remove_relation("rel1")

        MockCmd.assert_called_once_with("rel1")
        main_window.worker.run_command.assert_called_once_with(mock_cmd_instance)


def test_entity_update_relation(main_window):
    """Test updating a relation from entity editor."""
    with patch("src.app.main_window.UpdateRelationCommand") as MockCmd:
        mock_cmd_instance = MockCmd.return_value

        main_window.update_relation("rel1", "tgt", "type")

        MockCmd.assert_called_once_with("rel1", "tgt", "type", attributes=None)
        main_window.worker.run_command.assert_called_once_with(mock_cmd_instance)
