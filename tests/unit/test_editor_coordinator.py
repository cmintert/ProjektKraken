"""Unit tests for EditorCoordinator.

Tests CRUD operations, relation management, and editor state handling
extracted from MainWindow into a focused coordinator.
"""

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QObject, QSettings, Signal

from src.app.constants import SETTINGS_AUTO_RELATION_KEY


class FakeMainWindow(QObject):
    """Minimal fake MainWindow for testing EditorCoordinator."""

    command_requested = Signal(object)

    def __init__(self):
        super().__init__()
        self.event_editor = MagicMock()
        self.entity_editor = MagicMock()
        self.event_editor.has_unsaved_changes.return_value = False
        self.entity_editor.has_unsaved_changes.return_value = False
        self.event_editor._current_event_id = None
        self.entity_editor._current_entity_id = None
        self.navigation_coordinator = MagicMock()
        self.navigation_coordinator.selected_type = None
        self.navigation_coordinator.selected_id = None
        self.ui_manager = MagicMock()
        self.ui_manager.docks = {"event": MagicMock(), "entity": MagicMock()}
        self.status_bar = MagicMock()
        self.worker = MagicMock()


@pytest.fixture
def fake_window(qapp):
    """Create a FakeMainWindow for testing."""
    return FakeMainWindow()


@pytest.fixture
def coordinator(fake_window):
    """Create an EditorCoordinator with a fake MainWindow."""
    from src.app.coordinators.editor_coordinator import EditorCoordinator

    coord = EditorCoordinator(fake_window)
    # Forward coordinator's command_requested to fake_window's
    coord.command_requested.connect(fake_window.command_requested.emit)
    return coord


class TestCreateOperations:
    """Tests for create event/entity operations."""

    @patch("src.app.coordinators.editor_coordinator.QInputDialog")
    def test_create_event_emits_command(self, mock_dialog, coordinator, fake_window):
        """Creating an event should emit a CreateEventCommand."""
        mock_dialog.getText.return_value = ("Test Event", True)

        signals = []
        fake_window.command_requested.connect(lambda cmd: signals.append(cmd))

        coordinator.create_event()

        assert len(signals) == 1
        from src.commands.event_commands import CreateEventCommand

        assert isinstance(signals[0], CreateEventCommand)

    @patch("src.app.coordinators.editor_coordinator.QInputDialog")
    def test_create_event_cancelled(self, mock_dialog, coordinator, fake_window):
        """Cancelling create event dialog should not emit command."""
        mock_dialog.getText.return_value = ("", False)

        signals = []
        fake_window.command_requested.connect(lambda cmd: signals.append(cmd))

        coordinator.create_event()

        assert len(signals) == 0

    @patch("src.app.coordinators.editor_coordinator.QInputDialog")
    def test_create_event_empty_name(self, mock_dialog, coordinator, fake_window):
        """Empty name should not emit command."""
        mock_dialog.getText.return_value = ("  ", True)

        signals = []
        fake_window.command_requested.connect(lambda cmd: signals.append(cmd))

        coordinator.create_event()

        assert len(signals) == 0

    @patch("src.app.coordinators.editor_coordinator.QInputDialog")
    def test_create_entity_emits_command(self, mock_dialog, coordinator, fake_window):
        """Creating an entity should emit a CreateEntityCommand."""
        mock_dialog.getText.return_value = ("Test Entity", True)

        signals = []
        fake_window.command_requested.connect(lambda cmd: signals.append(cmd))

        coordinator.create_entity()

        assert len(signals) == 1
        from src.commands.entity_commands import CreateEntityCommand

        assert isinstance(signals[0], CreateEntityCommand)

    @patch("src.app.coordinators.editor_coordinator.QInputDialog")
    def test_create_entity_cancelled(self, mock_dialog, coordinator, fake_window):
        """Cancelling create entity dialog should not emit command."""
        mock_dialog.getText.return_value = ("", False)

        signals = []
        fake_window.command_requested.connect(lambda cmd: signals.append(cmd))

        coordinator.create_entity()

        assert len(signals) == 0

    @patch("src.app.coordinators.editor_coordinator.QInputDialog")
    def test_create_event_checks_unsaved_changes(
        self, mock_dialog, coordinator, fake_window
    ):
        """Create event should check for unsaved changes first."""
        fake_window.event_editor.has_unsaved_changes.return_value = True

        with patch.object(coordinator, "check_unsaved_changes", return_value=False):
            coordinator.create_event()

        mock_dialog.getText.assert_not_called()


class TestDeleteOperations:
    """Tests for delete event/entity operations."""

    def test_delete_event_emits_command(self, coordinator, fake_window):
        """Deleting an event should emit a DeleteEventCommand."""
        signals = []
        fake_window.command_requested.connect(lambda cmd: signals.append(cmd))

        coordinator.delete_event("evt_123")

        assert len(signals) == 1
        from src.commands.event_commands import DeleteEventCommand

        assert isinstance(signals[0], DeleteEventCommand)

    def test_delete_entity_emits_command(self, coordinator, fake_window):
        """Deleting an entity should emit a DeleteEntityCommand."""
        signals = []
        fake_window.command_requested.connect(lambda cmd: signals.append(cmd))

        coordinator.delete_entity("ent_456")

        assert len(signals) == 1
        from src.commands.entity_commands import DeleteEntityCommand

        assert isinstance(signals[0], DeleteEntityCommand)

    def test_on_item_delete_requested_routes_event(self, coordinator, fake_window):
        """Delete request for 'event' type routes to delete_event."""
        signals = []
        fake_window.command_requested.connect(lambda cmd: signals.append(cmd))

        coordinator.on_item_delete_requested("event", "evt_123")

        from src.commands.event_commands import DeleteEventCommand

        assert isinstance(signals[0], DeleteEventCommand)

    def test_on_item_delete_requested_routes_entity(self, coordinator, fake_window):
        """Delete request for 'entity' type routes to delete_entity."""
        signals = []
        fake_window.command_requested.connect(lambda cmd: signals.append(cmd))

        coordinator.on_item_delete_requested("entity", "ent_456")

        from src.commands.entity_commands import DeleteEntityCommand

        assert isinstance(signals[0], DeleteEntityCommand)


class TestUpdateOperations:
    """Tests for update event/entity operations."""

    def test_update_event_emits_command(self, coordinator, fake_window):
        """Updating an event should emit a command."""
        signals = []
        fake_window.command_requested.connect(lambda cmd: signals.append(cmd))

        coordinator.update_event({"id": "evt_1", "name": "Updated"})

        assert len(signals) == 1

    def test_update_event_with_description_emits_composite(
        self, coordinator, fake_window
    ):
        """Updating event with description should emit CompositeCommand."""
        QSettings().setValue(SETTINGS_AUTO_RELATION_KEY, True)
        signals = []
        fake_window.command_requested.connect(lambda cmd: signals.append(cmd))

        coordinator.update_event(
            {"id": "evt_1", "name": "Updated", "description": "Some text"}
        )

        from src.commands.composite_command import CompositeCommand

        assert isinstance(signals[0], CompositeCommand)

    def test_update_event_no_id_aborts(self, coordinator, fake_window):
        """Update with no ID should not emit command."""
        signals = []
        fake_window.command_requested.connect(lambda cmd: signals.append(cmd))

        coordinator.update_event({"name": "No ID"})

        assert len(signals) == 0

    def test_update_entity_emits_command(self, coordinator, fake_window):
        """Updating an entity should emit a command."""
        signals = []
        fake_window.command_requested.connect(lambda cmd: signals.append(cmd))

        coordinator.update_entity({"id": "ent_1", "name": "Updated"})

        assert len(signals) == 1

    def test_update_entity_with_description_emits_composite(
        self, coordinator, fake_window
    ):
        """Updating entity with description should emit CompositeCommand."""
        QSettings().setValue(SETTINGS_AUTO_RELATION_KEY, True)
        signals = []
        fake_window.command_requested.connect(lambda cmd: signals.append(cmd))

        coordinator.update_entity(
            {"id": "ent_1", "name": "Updated", "description": "Some text"}
        )

        from src.commands.composite_command import CompositeCommand

        assert isinstance(signals[0], CompositeCommand)


class TestRelationOperations:
    """Tests for relation management operations."""

    def test_add_relation_emits_command(self, coordinator, fake_window):
        """Adding a relation should emit AddRelationCommand."""
        signals = []
        fake_window.command_requested.connect(lambda cmd: signals.append(cmd))

        coordinator.add_relation("src", "dst", "relates_to")

        assert len(signals) == 1
        from src.commands.relation_commands import AddRelationCommand

        assert isinstance(signals[0], AddRelationCommand)

    def test_add_relation_bidirectional(self, coordinator, fake_window):
        """Adding a bidirectional relation should pass the flag."""
        signals = []
        fake_window.command_requested.connect(lambda cmd: signals.append(cmd))

        coordinator.add_relation("src", "dst", "allies", bidirectional=True)

        assert signals[0].bidirectional is True

    def test_remove_relation_emits_command(self, coordinator, fake_window):
        """Removing a relation should emit RemoveRelationCommand."""
        signals = []
        fake_window.command_requested.connect(lambda cmd: signals.append(cmd))

        coordinator.remove_relation("rel_123")

        from src.commands.relation_commands import RemoveRelationCommand

        assert isinstance(signals[0], RemoveRelationCommand)

    def test_update_relation_emits_command(self, coordinator, fake_window):
        """Updating a relation should emit UpdateRelationCommand."""
        signals = []
        fake_window.command_requested.connect(lambda cmd: signals.append(cmd))

        coordinator.update_relation("rel_1", "tgt", "new_type")

        from src.commands.relation_commands import UpdateRelationCommand

        assert isinstance(signals[0], UpdateRelationCommand)


class TestEditorState:
    """Tests for editor state management."""

    @patch("src.app.coordinators.editor_coordinator.QMessageBox")
    def test_check_unsaved_no_changes(self, mock_msgbox, coordinator, fake_window):
        """Editor with no changes returns True (safe to proceed)."""
        fake_window.event_editor.has_unsaved_changes.return_value = False

        result = coordinator.check_unsaved_changes(fake_window.event_editor)

        assert result is True
        mock_msgbox.warning.assert_not_called()

    @patch("src.app.coordinators.editor_coordinator.QMessageBox")
    def test_check_unsaved_save(self, mock_msgbox, coordinator, fake_window):
        """User clicking Save returns True and triggers save."""
        from PySide6.QtWidgets import QMessageBox

        fake_window.event_editor.has_unsaved_changes.return_value = True
        mock_msgbox.warning.return_value = QMessageBox.StandardButton.Save
        mock_msgbox.StandardButton = QMessageBox.StandardButton

        result = coordinator.check_unsaved_changes(fake_window.event_editor)

        assert result is True
        fake_window.event_editor._on_save.assert_called_once()

    @patch("src.app.coordinators.editor_coordinator.QMessageBox")
    def test_check_unsaved_discard(self, mock_msgbox, coordinator, fake_window):
        """User clicking Discard returns True."""
        from PySide6.QtWidgets import QMessageBox

        fake_window.event_editor.has_unsaved_changes.return_value = True
        mock_msgbox.warning.return_value = QMessageBox.StandardButton.Discard
        mock_msgbox.StandardButton = QMessageBox.StandardButton

        result = coordinator.check_unsaved_changes(fake_window.event_editor)

        assert result is True

    @patch("src.app.coordinators.editor_coordinator.QMessageBox")
    def test_check_unsaved_cancel(self, mock_msgbox, coordinator, fake_window):
        """User clicking Cancel returns False."""
        from PySide6.QtWidgets import QMessageBox

        fake_window.event_editor.has_unsaved_changes.return_value = True
        mock_msgbox.warning.return_value = QMessageBox.StandardButton.Cancel
        mock_msgbox.StandardButton = QMessageBox.StandardButton

        result = coordinator.check_unsaved_changes(fake_window.event_editor)

        assert result is False

    def test_on_editor_dirty_changed_sets_asterisk(self, coordinator, fake_window):
        """Dirty editor should have asterisk in dock title."""
        coordinator.on_editor_dirty_changed(fake_window.event_editor, True)

        dock = fake_window.ui_manager.docks["event"]
        dock.setWindowTitle.assert_called_with("Event Inspector *")

    def test_on_editor_dirty_changed_clears_asterisk(self, coordinator, fake_window):
        """Clean editor should have no asterisk in dock title."""
        coordinator.on_editor_dirty_changed(fake_window.event_editor, False)

        dock = fake_window.ui_manager.docks["event"]
        dock.setWindowTitle.assert_called_with("Event Inspector")


class TestEventDateChanged:
    """Tests for event date change from timeline dragging."""

    def test_event_date_changed_emits_update(self, coordinator, fake_window):
        """Date change from timeline should emit UpdateEventCommand."""
        signals = []
        fake_window.command_requested.connect(lambda cmd: signals.append(cmd))

        coordinator.on_event_date_changed("evt_1", 42.5)

        from src.commands.event_commands import UpdateEventCommand

        assert isinstance(signals[0], UpdateEventCommand)


class TestMapInlineCreation:
    """Tests for inline entity/event creation from map."""

    def test_on_map_create_entity(self, coordinator, fake_window):
        """Map inline entity creation should emit CreateEntityCommand."""
        signals = []
        fake_window.command_requested.connect(lambda cmd: signals.append(cmd))

        coordinator.on_map_create_entity("new_id", "Map Entity")

        from src.commands.entity_commands import CreateEntityCommand

        assert isinstance(signals[0], CreateEntityCommand)

    def test_on_map_create_event(self, coordinator, fake_window):
        """Map inline event creation should emit CreateEventCommand."""
        signals = []
        fake_window.command_requested.connect(lambda cmd: signals.append(cmd))

        coordinator.on_map_create_event("new_id", "Map Event")

        from src.commands.event_commands import CreateEventCommand

        assert isinstance(signals[0], CreateEventCommand)
