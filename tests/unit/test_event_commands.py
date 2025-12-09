"""
Unit tests for event commands.
"""

import pytest
from unittest.mock import MagicMock
from src.commands.event_commands import (
    CreateEventCommand,
    UpdateEventCommand,
    DeleteEventCommand,
)
from src.core.events import Event


@pytest.fixture
def mock_db():
    """Mock database service."""
    return MagicMock()


@pytest.fixture
def sample_event():
    """Sample event for testing."""
    return Event(name="Test Event", lore_date=1000.0, type="generic")


def test_create_event_success(mock_db, sample_event):
    """Test successful event creation."""
    cmd = CreateEventCommand(sample_event)

    result = cmd.execute(mock_db)

    assert result is True
    mock_db.insert_event.assert_called_once_with(sample_event)
    assert cmd._is_executed is True


def test_create_event_failure(mock_db, sample_event):
    """Test event creation failure."""
    mock_db.insert_event.side_effect = Exception("DB Error")
    cmd = CreateEventCommand(sample_event)

    result = cmd.execute(mock_db)

    assert result is False
    assert cmd._is_executed is False


def test_create_event_undo(mock_db, sample_event):
    """Test undoing event creation."""
    cmd = CreateEventCommand(sample_event)
    cmd.execute(mock_db)

    cmd.undo(mock_db)

    mock_db.delete_event.assert_called_once_with(sample_event.id)
    assert cmd._is_executed is False


def test_create_event_undo_not_executed(mock_db, sample_event):
    """Test undo does nothing if not executed."""
    cmd = CreateEventCommand(sample_event)

    cmd.undo(mock_db)

    mock_db.delete_event.assert_not_called()


def test_update_event_success(mock_db):
    """Test successful event update."""
    old_event = Event(id="test-id", name="Old Name", lore_date=1000.0, type="generic")
    update_data = {"name": "New Name", "lore_date": 2000.0, "type": "combat"}

    mock_db.get_event.return_value = old_event
    cmd = UpdateEventCommand("test-id", update_data)

    result = cmd.execute(mock_db)

    assert result is True
    # Verify DB was called with a new event object containing updated values
    args, _ = mock_db.insert_event.call_args
    updated_event = args[0]
    assert updated_event.id == "test-id"
    assert updated_event.name == "New Name"
    assert updated_event.lore_date == 2000.0
    assert updated_event.type == "combat"
    assert cmd._is_executed is True
    assert cmd._previous_event == old_event


def test_update_event_not_found(mock_db):
    """Test updating non-existent event."""
    mock_db.get_event.return_value = None
    cmd = UpdateEventCommand("test-id", {"name": "New"})

    result = cmd.execute(mock_db)

    assert result is False
    mock_db.insert_event.assert_not_called()


def test_update_event_db_error(mock_db):
    """Test update with database error."""
    old_event = Event(id="test-id", name="Old", lore_date=1000.0, type="generic")

    mock_db.get_event.return_value = old_event
    mock_db.insert_event.side_effect = Exception("DB Error")
    cmd = UpdateEventCommand("test-id", {"name": "New"})

    result = cmd.execute(mock_db)

    assert result is False
    assert cmd._is_executed is False


def test_update_event_undo(mock_db):
    """Test undoing event update."""
    old_event = Event(id="test-id", name="Old", lore_date=1000.0, type="generic")
    update_data = {"name": "New"}

    mock_db.get_event.return_value = old_event
    cmd = UpdateEventCommand("test-id", update_data)
    cmd.execute(mock_db)
    mock_db.insert_event.reset_mock()

    cmd.undo(mock_db)

    mock_db.insert_event.assert_called_once_with(old_event)
    assert cmd._is_executed is False


def test_update_event_undo_not_executed(mock_db):
    """Test undo does nothing if update not executed."""
    cmd = UpdateEventCommand("test-id", {"name": "New"})

    cmd.undo(mock_db)

    mock_db.insert_event.assert_not_called()


def test_delete_event_success(mock_db, sample_event):
    """Test successful event deletion."""
    mock_db.get_event.return_value = sample_event
    cmd = DeleteEventCommand(sample_event.id)

    result = cmd.execute(mock_db)

    assert result is True
    mock_db.delete_event.assert_called_once_with(sample_event.id)
    assert cmd._is_executed is True
    assert cmd._backup_event == sample_event


def test_delete_event_not_found(mock_db):
    """Test deleting non-existent event."""
    mock_db.get_event.return_value = None
    cmd = DeleteEventCommand("nonexistent-id")

    result = cmd.execute(mock_db)

    assert result is False
    mock_db.delete_event.assert_not_called()


def test_delete_event_db_error(mock_db, sample_event):
    """Test deletion with database error."""
    mock_db.get_event.return_value = sample_event
    mock_db.delete_event.side_effect = Exception("DB Error")
    cmd = DeleteEventCommand(sample_event.id)

    result = cmd.execute(mock_db)

    assert result is False
    assert cmd._is_executed is False


def test_delete_event_undo(mock_db, sample_event):
    """Test undoing event deletion."""
    mock_db.get_event.return_value = sample_event
    cmd = DeleteEventCommand(sample_event.id)
    cmd.execute(mock_db)
    mock_db.insert_event.reset_mock()

    cmd.undo(mock_db)

    mock_db.insert_event.assert_called_once_with(sample_event)
    assert cmd._is_executed is False


def test_delete_event_undo_not_executed(mock_db):
    """Test undo does nothing if delete not executed."""
    cmd = DeleteEventCommand("test-id")

    cmd.undo(mock_db)

    mock_db.insert_event.assert_not_called()
