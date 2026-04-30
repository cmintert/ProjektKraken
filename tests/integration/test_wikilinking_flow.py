"""
Integration test for WikiLinking flow in MainWindow.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.app.main import MainWindow
from src.commands.event_commands import UpdateEventCommand
from src.commands.wiki_commands import ProcessWikiLinksCommand


@pytest.fixture
def mock_window(qtbot):
    """Create a MainWindow with mocked worker."""
    with (
        patch("src.app.worker_manager.DatabaseWorker"),
        patch("src.app.main_window.QTimer"),
        patch("src.app.worker_manager.QThread"),
    ):
        window = MainWindow()
        window.worker = MagicMock()
        yield window
        window.close()


def test_update_event_toggle_off_no_wiki_command(qtbot):
    """When the auto-relation toggle is OFF (default), update_event emits only
    UpdateEventCommand — no ProcessWikiLinksCommand is attached.
    """

    mock_settings = MagicMock()
    mock_settings.value.return_value = False

    with (
        patch("src.app.worker_manager.DatabaseWorker"),
        patch("src.app.main_window.QTimer"),
        patch("src.app.worker_manager.QThread"),
        patch(
            "src.app.coordinators.editor_coordinator.QSettings",
            return_value=mock_settings,
        ),
    ):
        window = MainWindow()
        try:
            mock_slot = MagicMock()
            window.editor_coordinator.command_requested.connect(mock_slot)

            data = {"id": "event-1", "description": "See [[Gandalf]]."}
            window.editor_coordinator.update_event(data)

            assert mock_slot.call_count == 1
            cmd = mock_slot.call_args_list[0][0][0]

            # With toggle OFF, we get a plain UpdateEventCommand, not a composite
            assert isinstance(cmd, UpdateEventCommand)
        finally:
            window.close()


def test_update_event_toggle_on_includes_wiki_command(qtbot):
    """When the auto-relation toggle is ON, update_event wraps UpdateEventCommand
    + ProcessWikiLinksCommand in a CompositeCommand.
    """
    from src.commands.composite_command import CompositeCommand

    mock_settings = MagicMock()
    mock_settings.value.return_value = True

    with (
        patch("src.app.worker_manager.DatabaseWorker"),
        patch("src.app.main_window.QTimer"),
        patch("src.app.worker_manager.QThread"),
        patch(
            "src.app.coordinators.editor_coordinator.QSettings",
            return_value=mock_settings,
        ),
    ):
        window = MainWindow()
        try:
            mock_slot = MagicMock()
            window.editor_coordinator.command_requested.connect(mock_slot)

            event_id = "event-123"
            data = {"id": event_id, "description": "See [[Gandalf]]."}
            window.editor_coordinator.update_event(data)

            assert mock_slot.call_count == 1
            cmd = mock_slot.call_args_list[0][0][0]

            assert isinstance(cmd, CompositeCommand)
            assert len(cmd.commands) == 2
            assert isinstance(cmd.commands[0], UpdateEventCommand)
            assert isinstance(cmd.commands[1], ProcessWikiLinksCommand)
            assert cmd.commands[1].source_id == event_id
            assert cmd.commands[1].text_content == "See [[Gandalf]]."
        finally:
            window.close()


def test_update_entity_toggle_off_no_wiki_command(qtbot):
    """When the toggle is OFF, update_entity emits only UpdateEntityCommand."""
    from src.commands.entity_commands import UpdateEntityCommand

    mock_settings = MagicMock()
    mock_settings.value.return_value = False

    with (
        patch("src.app.worker_manager.DatabaseWorker"),
        patch("src.app.main_window.QTimer"),
        patch("src.app.worker_manager.QThread"),
        patch(
            "src.app.coordinators.editor_coordinator.QSettings",
            return_value=mock_settings,
        ),
    ):
        window = MainWindow()
        try:
            mock_slot = MagicMock()
            window.editor_coordinator.command_requested.connect(mock_slot)

            data = {"id": "entity-1", "description": "Mentions [[Frodo]]."}
            window.editor_coordinator.update_entity(data)

            assert mock_slot.call_count == 1
            cmd = mock_slot.call_args_list[0][0][0]
            assert isinstance(cmd, UpdateEntityCommand)
        finally:
            window.close()


def test_update_entity_toggle_on_includes_wiki_command(qtbot):
    """When the toggle is ON, update_entity wraps a CompositeCommand."""
    from src.commands.composite_command import CompositeCommand
    from src.commands.entity_commands import UpdateEntityCommand

    mock_settings = MagicMock()
    mock_settings.value.return_value = True

    with (
        patch("src.app.worker_manager.DatabaseWorker"),
        patch("src.app.main_window.QTimer"),
        patch("src.app.worker_manager.QThread"),
        patch(
            "src.app.coordinators.editor_coordinator.QSettings",
            return_value=mock_settings,
        ),
    ):
        window = MainWindow()
        try:
            mock_slot = MagicMock()
            window.editor_coordinator.command_requested.connect(mock_slot)

            entity_id = "entity-99"
            data = {"id": entity_id, "description": "Mentions [[Frodo]]."}
            window.editor_coordinator.update_entity(data)

            assert mock_slot.call_count == 1
            cmd = mock_slot.call_args_list[0][0][0]

            assert isinstance(cmd, CompositeCommand)
            assert isinstance(cmd.commands[0], UpdateEntityCommand)
            assert isinstance(cmd.commands[1], ProcessWikiLinksCommand)
            assert cmd.commands[1].source_id == entity_id
        finally:
            window.close()
