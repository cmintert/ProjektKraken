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

    from PySide6.QtWidgets import QMessageBox

    with (
        patch("src.app.worker_manager.DatabaseWorker"),
        patch("src.app.worker_manager.QTimer"),
        patch("src.app.worker_manager.QThread"),
        patch(
            "src.app.main_window.QMessageBox.warning", return_value=QMessageBox.Discard
        ),
    ):
        window = MainWindow()
        window.worker = MagicMock()
        yield window
        window.close()


def test_update_event_triggers_commands(qtbot):
    """Test using direct slot connection."""
    from unittest.mock import patch

    from PySide6.QtWidgets import QMessageBox

    with (
        patch("src.app.worker_manager.DatabaseWorker"),
        patch("src.app.worker_manager.QTimer"),
        patch("src.app.worker_manager.QThread"),
        patch(
            "src.app.main_window.QMessageBox.warning", return_value=QMessageBox.Discard
        ),
    ):
        window = MainWindow()
        try:
            mock_slot = MagicMock()
            window.command_requested.connect(mock_slot)

            event_id = "event-123"
            data = {"id": event_id, "description": "See [[Gandalf]]."}

            window.update_event(data)

            assert mock_slot.call_count == 2
            args1 = mock_slot.call_args_list[0][0][0]
            args2 = mock_slot.call_args_list[1][0][0]

            assert isinstance(args1, UpdateEventCommand)
            assert isinstance(args2, ProcessWikiLinksCommand)
            assert args2.source_id == event_id
            assert args2.text_content == "See [[Gandalf]]."
        finally:
            if hasattr(window, "worker_thread") and window.worker_thread.isRunning():
                window.worker_thread.quit()
                window.worker_thread.wait()
            window.close()
