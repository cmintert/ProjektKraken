import pytest

from src.commands.event_commands import CreateEventCommand, DeleteEventCommand
from src.core.events import Event
from src.services.db_service import DatabaseService


@pytest.fixture
def db_service():
    service = DatabaseService(":memory:")
    service.connect()
    yield service
    service.close()


def test_create_event_undo(db_service):
    """Test creating an event and then undoing it."""
    event = Event(name="Temporary Event", lore_date=100.0)
    # Pass dict, not object
    cmd = CreateEventCommand(event.to_dict())

    # Execute
    result = cmd.execute(db_service)
    assert result.success is True
    assert db_service.get_event(event.id) is not None

    # Undo
    cmd.undo(db_service)
    assert db_service.get_event(event.id) is None


def test_delete_event_undo(db_service):
    """Test deleting an event and then restoring it via undo."""
    # Setup initial state
    event = Event(name="To Be Deleted", lore_date=200.0)
    db_service.insert_event(event)

    # Verify it exists
    assert db_service.get_event(event.id) is not None

    # Execute Delete
    cmd = DeleteEventCommand(event.id)
    result = cmd.execute(db_service)
    assert result.success is True
    assert db_service.get_event(event.id) is None

    # Undo Delete
    cmd.undo(db_service)
    restored = db_service.get_event(event.id)
    assert restored is not None
    assert restored.name == "To Be Deleted"
