"""
Tests for Entity integration via EditorCoordinator.
"""

from unittest.mock import patch

import pytest

from src.app.main import MainWindow


@pytest.fixture
def main_window(qtbot):
    """Create MainWindow with mocked Worker."""
    with patch("src.app.worker_manager.DatabaseWorker"):
        # Avoid thread start in test and prevent deferred init crash
        with (
            patch("src.app.worker_manager.QThread"),
            patch("src.app.main_window.QTimer"),
        ):
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


def test_create_entity(main_window, qtbot):
    """Test creating an entity via editor_coordinator."""
    with patch(
        "src.app.coordinators.editor_coordinator.QInputDialog.getText"
    ) as mock_input:
        mock_input.return_value = ("Test Entity", True)

        with patch(
            "src.app.coordinators.editor_coordinator.CreateEntityCommand"
        ) as MockCmd:
            with qtbot.waitSignal(
                main_window.editor_coordinator.command_requested, timeout=1000
            ):
                main_window.editor_coordinator.create_entity()

            MockCmd.assert_called_once()
            args, _ = MockCmd.call_args
            assert args[0] == {"name": "Test Entity", "type": "Concept"}


def test_delete_entity(main_window, qtbot):
    """Test deleting an entity via editor_coordinator."""
    with patch(
        "src.app.coordinators.editor_coordinator.DeleteEntityCommand"
    ) as MockCmd:
        with qtbot.waitSignal(
            main_window.editor_coordinator.command_requested, timeout=1000
        ):
            main_window.editor_coordinator.delete_entity("ent1")

        MockCmd.assert_called_once()


def test_update_entity(main_window, qtbot):
    """Test updating an entity via editor_coordinator."""
    entity_data = {"id": "ent1", "name": "Updated", "type": "Concept"}

    with patch(
        "src.app.coordinators.editor_coordinator.UpdateEntityCommand"
    ) as MockCmd:
        with qtbot.waitSignal(
            main_window.editor_coordinator.command_requested, timeout=1000
        ):
            main_window.editor_coordinator.update_entity(entity_data)

        MockCmd.assert_called_once_with("ent1", entity_data)


def test_entity_add_relation(main_window, qtbot):
    """Test adding a relation via editor_coordinator."""
    with patch("src.app.coordinators.editor_coordinator.AddRelationCommand") as MockCmd:
        with qtbot.waitSignal(
            main_window.editor_coordinator.command_requested, timeout=1000
        ):
            main_window.editor_coordinator.add_relation(
                "src", "tgt", "caused", bidirectional=True
            )

        MockCmd.assert_called_once_with(
            "src", "tgt", "caused", attributes=None, bidirectional=True
        )


def test_entity_remove_relation(main_window, qtbot):
    """Test removing a relation via editor_coordinator."""
    with patch(
        "src.app.coordinators.editor_coordinator.RemoveRelationCommand"
    ) as MockCmd:
        with qtbot.waitSignal(
            main_window.editor_coordinator.command_requested, timeout=1000
        ):
            main_window.editor_coordinator.remove_relation("rel1")

        MockCmd.assert_called_once_with("rel1")


def test_entity_update_relation(main_window, qtbot):
    """Test updating a relation via editor_coordinator."""
    with patch(
        "src.app.coordinators.editor_coordinator.UpdateRelationCommand"
    ) as MockCmd:
        with qtbot.waitSignal(
            main_window.editor_coordinator.command_requested, timeout=1000
        ):
            main_window.editor_coordinator.update_relation("rel1", "tgt", "type")

        MockCmd.assert_called_once_with("rel1", "tgt", "type", attributes=None)
