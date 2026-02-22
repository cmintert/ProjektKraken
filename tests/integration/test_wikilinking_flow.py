"""
Integration test for WikiLinking flow in MainWindow.
"""

from unittest.mock import MagicMock

import pytest

from src.app.main import MainWindow
from src.commands.event_commands import UpdateEventCommand
from src.commands.wiki_commands import ProcessWikiLinksCommand


@pytest.fixture
def mock_window(qtbot):
    """Create a MainWindow with mocked worker."""
    from unittest.mock import patch

    with (
        patch("src.app.worker_manager.DatabaseWorker"),
        patch("src.app.main_window.QTimer"),
        patch("src.app.worker_manager.QThread"),
    ):
        window = MainWindow()
        window.worker = MagicMock()
        yield window
        window.close()


def test_update_event_triggers_commands(qtbot):
    """Test that update_event creates composite command with wiki processing."""
    from unittest.mock import patch

    from src.commands.composite_command import CompositeCommand

    with (
        patch("src.app.worker_manager.DatabaseWorker"),
        patch("src.app.main_window.QTimer"),
        patch("src.app.worker_manager.QThread"),
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

            # EditorCoordinator now wraps update + wiki in a CompositeCommand
            assert isinstance(cmd, CompositeCommand)
            assert len(cmd.commands) == 2
            assert isinstance(cmd.commands[0], UpdateEventCommand)
            assert isinstance(cmd.commands[1], ProcessWikiLinksCommand)
            assert cmd.commands[1].source_id == event_id
            assert cmd.commands[1].text_content == "See [[Gandalf]]."
        finally:
            if hasattr(window, "worker_thread") and window.worker_thread.isRunning():
                window.worker_thread.quit()
                window.worker_thread.wait()
            window.close()
