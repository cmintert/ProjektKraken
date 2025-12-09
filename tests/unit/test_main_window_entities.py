"""
Tests for Entity integration in MainWindow.
"""

import pytest
from unittest.mock import patch, MagicMock
from src.app.main import MainWindow
from src.core.entities import Entity


@pytest.fixture
def main_window(qtbot):
    """Create MainWindow with mocked Worker."""
    with patch("src.app.main.DatabaseWorker") as MockWorker:
        # Avoid thread start in test
        with patch("src.app.main.QThread"):
            window = MainWindow()
            window.show()
            qtbot.addWidget(window)
            yield window


def test_entity_docks_exist(main_window):
    """Test that entity docks are created."""
    assert main_window.entity_list_dock is not None
    assert main_window.entity_editor_dock is not None
    assert main_window.entity_list_dock.toggleViewAction().text() == "Entities List"


def test_create_entity(main_window):
    """Test creating an entity."""
    with patch("src.app.main.CreateEntityCommand") as MockCmd:
        mock_cmd_instance = MockCmd.return_value

        main_window.create_entity()

        MockCmd.assert_called_once()
        # Should delegate to worker
        main_window.worker.run_command.assert_called_once_with(mock_cmd_instance)


def test_delete_entity(main_window):
    """Test deleting an entity."""
    with patch("src.app.main.DeleteEntityCommand") as MockCmd:
        mock_cmd_instance = MockCmd.return_value

        main_window.delete_entity("ent1")

        MockCmd.assert_called_once()
        main_window.worker.run_command.assert_called_once_with(mock_cmd_instance)


def test_update_entity(main_window):
    """Test updating an entity."""
    entity = Entity(id="ent1", name="Updated", type="Concept")

    with patch("src.app.main.UpdateEntityCommand") as MockCmd:
        mock_cmd_instance = MockCmd.return_value

        main_window.update_entity(entity)

        MockCmd.assert_called_once()
        main_window.worker.run_command.assert_called_once_with(mock_cmd_instance)


def test_load_entity_details_signal(main_window):
    """Test response to details loaded signal."""
    entity = Entity(id="ent1", name="Test", type="Concept")
    relations = [{"id": "rel1"}]
    incoming = [{"id": "rel2"}]

    with patch.object(main_window.entity_editor, "load_entity") as mock_load:
        # Simulate signal emission
        main_window.on_entity_details_loaded(entity, relations, incoming)

        mock_load.assert_called_once_with(entity, relations, incoming)
        # Check dock raise
        assert main_window.entity_editor_dock.isVisible()


def test_entity_add_relation(main_window):
    """Test adding a relation from entity editor."""
    main_window.entity_editor._current_entity_id = "src"

    with patch("src.app.main.AddRelationCommand") as MockCmd:
        mock_cmd_instance = MockCmd.return_value

        main_window.add_relation("src", "tgt", "caused", True)

        MockCmd.assert_called_once_with("src", "tgt", "caused", bidirectional=True)
        main_window.worker.run_command.assert_called_once_with(mock_cmd_instance)


def test_entity_remove_relation(main_window):
    """Test removing a relation from entity editor."""
    with patch("src.app.main.RemoveRelationCommand") as MockCmd:
        mock_cmd_instance = MockCmd.return_value

        main_window.remove_relation("rel1")

        MockCmd.assert_called_once_with("rel1")
        main_window.worker.run_command.assert_called_once_with(mock_cmd_instance)


def test_entity_update_relation(main_window):
    """Test updating a relation from entity editor."""
    with patch("src.app.main.UpdateRelationCommand") as MockCmd:
        mock_cmd_instance = MockCmd.return_value

        main_window.update_relation("rel1", "tgt", "type")

        MockCmd.assert_called_once_with("rel1", "tgt", "type")
        main_window.worker.run_command.assert_called_once_with(mock_cmd_instance)
