"""
Tests for Entity integration in MainWindow.
"""

import pytest
from unittest.mock import patch
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


def test_load_entity_with_relations(main_window):
    """Test loading entity details including relations."""
    entity = Entity(id="ent1", name="Test", type="Concept")
    main_window.db_service.get_entity.return_value = entity
    main_window.db_service.get_relations.return_value = [{"id": "rel1"}]
    main_window.db_service.get_incoming_relations.return_value = [{"id": "rel2"}]

    with patch.object(main_window.entity_editor, "load_entity") as mock_load:
        main_window.load_entity_details("ent1")

        mock_load.assert_called_once_with(entity, [{"id": "rel1"}], [{"id": "rel2"}])


def test_entity_add_relation(main_window):
    """Test adding a relation from entity editor."""
    # Setup state
    main_window.entity_editor._current_entity_id = "src"

    # Mock entity return so UI update doesn't crash on setText(MagicMock)
    # Using real object is safer than generic Mock for properties accessed by QT
    mock_entity = Entity(id="src", name="Source", type="Concept")
    main_window.db_service.get_entity.return_value = mock_entity
    main_window.db_service.get_relations.return_value = []
    main_window.db_service.get_incoming_relations.return_value = []

    with patch("src.app.main.AddRelationCommand") as MockCmd:
        mock_cmd = MockCmd.return_value
        mock_cmd.execute.return_value = True

        main_window.add_relation("src", "tgt", "caused", True)

        MockCmd.assert_called_once_with(
            main_window.db_service, "src", "tgt", "caused", bidirectional=True
        )
        mock_cmd.execute.assert_called_once()
        # Should refresh details
        main_window.db_service.get_entity.assert_called()


def test_entity_remove_relation(main_window):
    """Test removing a relation from entity editor."""
    # Setup state
    main_window.entity_editor._current_entity_id = "ent1"

    mock_entity = Entity(id="ent1", name="Source", type="Concept")
    main_window.db_service.get_entity.return_value = mock_entity
    main_window.db_service.get_relations.return_value = []
    main_window.db_service.get_incoming_relations.return_value = []

    with patch("src.app.main.RemoveRelationCommand") as MockCmd:
        mock_cmd = MockCmd.return_value
        mock_cmd.execute.return_value = True

        main_window.remove_relation("rel1")

        MockCmd.assert_called_once_with(main_window.db_service, "rel1")
        mock_cmd.execute.assert_called_once()
        # Should refresh
        main_window.db_service.get_entity.assert_called()


def test_entity_update_relation(main_window):
    """Test updating a relation from entity editor."""
    main_window.entity_editor._current_entity_id = "ent1"

    mock_entity = Entity(id="ent1", name="Source", type="Concept")
    main_window.db_service.get_entity.return_value = mock_entity
    main_window.db_service.get_relations.return_value = []
    main_window.db_service.get_incoming_relations.return_value = []

    with patch("src.app.main.UpdateRelationCommand") as MockCmd:
        mock_cmd = MockCmd.return_value
        mock_cmd.execute.return_value = True

        main_window.update_relation("rel1", "tgt", "type")

        MockCmd.assert_called_once_with(main_window.db_service, "rel1", "tgt", "type")
        mock_cmd.execute.assert_called_once()
