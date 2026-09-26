"""
Integration test for WikiLink navigation in MainWindow.
"""

from unittest.mock import MagicMock

from src.app.main import MainWindow
from src.core.entities import Entity


def test_navigate_to_entity_success(qtbot):
    """Test navigation to an existing entity."""
    from unittest.mock import patch

    with (
        patch("src.app.worker_manager.DatabaseWorker"),
        patch("src.app.main_window.QTimer"),
        patch("src.app.worker_manager.QThread"),
    ):
        window = MainWindow()
        # Mock worker
        window.worker = MagicMock()

        # Setup cache
        target_entity = Entity(id="ent-1", name="Gandalf", type="Character")
        window.data_coordinator._cached_entities = [target_entity]

        # Mock load method on data_coordinator
        window.data_coordinator.load_entity_details = MagicMock()

        # Execute
        window.navigation_coordinator.navigate_to_entity("Gandalf")

        # Verify
        window.data_coordinator.load_entity_details.assert_called_once_with("ent-1")

        window.close()


def test_navigate_to_entity_case_insensitive(qtbot):
    """Test case-insensitive lookup."""
    from unittest.mock import patch

    with (
        patch("src.app.worker_manager.DatabaseWorker"),
        patch("src.app.main_window.QTimer"),
        patch("src.app.worker_manager.QThread"),
    ):
        window = MainWindow()
        window.worker = MagicMock()
        window.data_coordinator._cached_entities = [
            Entity(id="ent-1", name="Gandalf", type="Character")
        ]
        window.data_coordinator.load_entity_details = MagicMock()

        window.navigation_coordinator.navigate_to_entity("gAnDaLf")

        window.data_coordinator.load_entity_details.assert_called_once_with("ent-1")
        window.close()


def test_navigate_to_entity_not_found(qtbot, monkeypatch):
    """Test behavior when entity is not found."""
    from unittest.mock import patch

    with (
        patch("src.app.worker_manager.DatabaseWorker"),
        patch("src.app.main_window.QTimer"),
        patch("src.app.worker_manager.QThread"),
    ):
        window = MainWindow()
        window.worker = MagicMock()
        window.data_coordinator._cached_entities = []
        window.data_coordinator._cached_events = []  # Also need to mock events cache
        window.data_coordinator.load_entity_details = MagicMock()

        mock_peek = MagicMock()
        window.navigation_coordinator.peek_target = mock_peek

        window.navigation_coordinator.navigate_to_entity("Unknown")

        window.data_coordinator.load_entity_details.assert_not_called()
        mock_peek.assert_called_once_with("Unknown")

        window.close()


def test_peek_keeps_dirty_entity_authoring_context(qtbot):
    """Reference lookup does not select or reload another editor."""
    from unittest.mock import patch

    with (
        patch("src.app.worker_manager.DatabaseWorker"),
        patch("src.app.main_window.QTimer"),
        patch("src.app.worker_manager.QThread"),
    ):
        window = MainWindow()
        window.worker = MagicMock()
        try:
            source = Entity(id="source", name="Source", type="Concept")
            target = Entity(id="target", name="Target", type="Place")
            window.data_coordinator._cached_entities = [source, target]
            window.entity_editor.load_entity(source)
            window.entity_editor.desc_edit.set_wiki_text("Draft [[Target]]")
            window.entity_editor.set_dirty(True)
            window.navigation_coordinator.selected_type = "entity"
            window.navigation_coordinator.selected_id = source.id
            revision = window.entity_editor.edit_revision
            text = window.entity_editor.desc_edit.get_wiki_text()

            window.navigation_coordinator.peek_target("Target")

            assert window.workspace.active_panel("right") == "wiki_peek"
            assert window.navigation_coordinator.selected_id == source.id
            assert window.entity_editor.edit_revision == revision
            assert window.entity_editor.desc_edit.get_wiki_text() == text
            assert window.entity_editor.has_unsaved_changes()
            window.navigation_coordinator.close_peek()
            assert window.navigation_coordinator.selected_id == source.id
        finally:
            window.entity_editor.set_dirty(False)
            window.close()


def test_provisional_materialization_is_undoable_without_navigation(qtbot, db_service):
    """Creating a provisional target leaves the draft and selection intact."""
    from unittest.mock import patch

    from src.commands.entity_commands import CreateEntityCommand

    with (
        patch("src.app.worker_manager.DatabaseWorker"),
        patch("src.app.main_window.QTimer"),
        patch("src.app.worker_manager.QThread"),
    ):
        window = MainWindow()
        window.worker = MagicMock()
        try:
            window.navigation_coordinator.selected_type = "entity"
            window.navigation_coordinator.selected_id = "source"
            window.navigation_coordinator.peek_target("Grey Ford")
            # The MainWindow is not shown in this test, so use the signal path.
            commands = []
            window.command_requested.connect(commands.append)
            window.wiki_peek_panel.create_requested.emit("entity", "Grey Ford")
            (command,) = commands
            assert isinstance(command, CreateEntityCommand)
            assert command.select_after_create is False
            assert command.execute(db_service).success
            assert db_service.get_entity(command.entity_id).name == "Grey Ford"
            assert window.navigation_coordinator.selected_id == "source"
            window.data_coordinator._cached_entities = [
                db_service.get_entity(command.entity_id)
            ]
            window.data_coordinator.lore_mutation_applied.emit(
                "entity", command.entity_id, "upsert"
            )
            assert window.wiki_peek_panel.detail.text() == "Entity"
            assert window.wiki_peek_panel.title.text() == "Grey Ford"
            command.undo(db_service)
            assert db_service.get_entity(command.entity_id) is None
        finally:
            window.close()
