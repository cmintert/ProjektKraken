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
    db.is_connected.return_value = True
    db.require_connection.return_value = MagicMock()
    return db


def test_save_command_timestamps(db_service):
    """Recorded command identity and timestamps survive ordered-stack restoration."""
    service = HistoryService(db_service, "test_world")
    service.register_command_type("MockCommand", MockCommand)
    cmd = MockCommand("test")
    cmd.timestamp = 1234567890.0
    cmd.execute(db_service)
    service.save_command(cmd)
    (loaded,) = service.load_recent_history()
    assert loaded.timestamp == cmd.timestamp
    assert loaded.command_id == cmd.command_id
    assert loaded.is_executed


def test_session_records_current_application_version(mock_db_service):
    """New history sessions store the authoritative application version."""
    HistoryService(mock_db_service, "test_world")

    execute_call = (
        mock_db_service.transaction.return_value.__enter__.return_value.execute
    )
    parameters = execute_call.call_args.args[1]
    assert parameters[-1] == VERSION
