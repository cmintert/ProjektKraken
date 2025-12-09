"""
Integration test for WikiLinking flow in MainWindow.
"""

import pytest
from unittest.mock import MagicMock, call
from src.app.main import MainWindow
from src.commands.wiki_commands import ProcessWikiLinksCommand
from src.commands.event_commands import UpdateEventCommand


@pytest.fixture
def mock_window(qtbot):
    """Create a MainWindow with mocked worker."""
    window = MainWindow()
    window.worker = MagicMock()
    # Prevent actual startup logic interference if any
    return window


def test_update_event_triggers_commands(qtbot):
    """Test using direct slot connection."""
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
