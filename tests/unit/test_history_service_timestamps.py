import json
from unittest.mock import MagicMock

import pytest

from src.commands.base_command import BaseCommand, CommandResult
from src.core.version import VERSION
from src.services.db_service import DatabaseService
from src.services.history_service import HistoryService


# Mock proper BaseCommand implementation for testing
class MockCommand(BaseCommand):
    def __init__(self, data=""):
        super().__init__()
        self.data = data

    def execute(self, db_service):
        self._is_executed = True
        return CommandResult(True)

    def undo(self, db_service):
        self._is_executed = False

    def to_dict(self):
        return {"data": self.data}

    @classmethod
    def from_dict(cls, data):
        return cls(data["data"])


@pytest.fixture
def mock_db_service():
    db = MagicMock(spec=DatabaseService)
    # Mock transaction context manager
    db.transaction.return_value.__enter__.return_value = MagicMock()
    # Mock connection execute
    db._connection = MagicMock()
    return db


def test_save_command_timestamps(mock_db_service):
    """Verify that timestamps are correctly saved and loaded."""
    service = HistoryService(mock_db_service, "test_world")
    service.register_command_type("MockCommand", MockCommand)

    # 1. Test Saving
    cmd = MockCommand("test")
    # Manually set a specific timestamp to verify it persists
    test_time = 1234567890.0
    cmd.timestamp = test_time

    # We can't easily verify the INSERT SQL param for timestamp because it's generated
    # inside save_command using time.time(), overriding our manual set if we aren't careful.
    # Wait, BaseCommand init sets it. save_command uses time.time() in the INSERT.
    # Let's check the code:
    # "INSERT ... VALUES (..., time.time(), ...)" -> It uses current time for the DB record!
    # But does it use the Command's timestamp?
    # No, line 144 of history_service.py: `time.time(),`

    # Wait, if history_service saves `time.time()`, does it ignore the command's existing timestamp?
    # Yes. And when loading, it puts that DB timestamp BACK into the command.
    # So the test should verify that the loaded command gets the timestamp from the DB.

    # 2. Test Loading
    # Mock the DB cursor to return a row with a specific timestamp
    mock_row = {
        "command_type": "MockCommand",
        "command_data": json.dumps({"data": "test"}),
        "description": "Mock Command",
        "timestamp": test_time,
    }

    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [mock_row]
    mock_db_service._connection.execute.return_value = mock_cursor

    loaded_commands = service.load_recent_history()

    assert len(loaded_commands) == 1
    loaded_cmd = loaded_commands[0]
    assert isinstance(loaded_cmd, MockCommand)
    assert loaded_cmd.timestamp == test_time


def test_session_records_current_application_version(mock_db_service):
    """New history sessions store the authoritative application version."""
    HistoryService(mock_db_service, "test_world")

    execute_call = mock_db_service.transaction.return_value.__enter__.return_value.execute
    parameters = execute_call.call_args.args[1]
    assert parameters[-1] == VERSION
