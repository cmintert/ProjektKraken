"""
Tests for Entity integration in MainWindow.
"""

import pytest
from unittest.mock import patch, MagicMock
from src.app.main import MainWindow
from src.core.entities import Entity


@pytest.fixture
def main_window(qtbot):
    """Create MainWindow with mocked DB."""
    with patch("src.app.main.DatabaseService") as MockDB:
        mock_db = MockDB.return_value
        mock_db.get_all_events.return_value = []
        mock_db.get_all_entities.return_value = []

        # Prevent actual constructor side effects if any, though MainWindow seems safe
        window = MainWindow()
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
        mock_cmd = MockCmd.return_value
        mock_cmd.execute.return_value = True

        main_window.create_entity()

        MockCmd.assert_called_once()
        mock_cmd.execute.assert_called_once()

        # It should reload entities
        main_window.db_service.get_all_entities.assert_called()


def test_delete_entity(main_window):
    """Test deleting an entity."""
    with patch("src.app.main.DeleteEntityCommand") as MockCmd:
        mock_cmd = MockCmd.return_value
        mock_cmd.execute.return_value = True

        main_window.delete_entity("ent1")

        MockCmd.assert_called_once()
        mock_cmd.execute.assert_called_once()
        main_window.db_service.get_all_entities.assert_called()


def test_update_entity(main_window):
    """Test updating an entity."""
    entity = Entity(id="ent1", name="Updated", type="Concept")

    with patch("src.app.main.UpdateEntityCommand") as MockCmd:
        mock_cmd = MockCmd.return_value
        mock_cmd.execute.return_value = True

        main_window.update_entity(entity)

        MockCmd.assert_called_once()
        mock_cmd.execute.assert_called_once()
        main_window.db_service.get_all_entities.assert_called()


def test_seed_entities(main_window):
    """Test that entities are seeded if empty."""
    # Setup DB to return empty entities initially
    main_window.db_service.get_all_entities.side_effect = [[], ["seeded"]]

    with patch("src.app.main.CreateEntityCommand") as MockCmd:
        mock_cmd = MockCmd.return_value
        mock_cmd.execute.return_value = True

        main_window.seed_data()

        # Should call create twice (Gandalf and Shire)
        assert MockCmd.call_count >= 2
