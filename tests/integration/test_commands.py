import pytest
from src.services.db_service import DatabaseService
from src.core.events import Event
from src.commands.event_commands import CreateEventCommand, DeleteEventCommand


@pytest.fixture
def db_service():
    service = DatabaseService(":memory:")
    service.connect()
    yield service
    service.close()


def test_create_event_undo(db_service):
    """Test creating an event and then undoing it."""
    event = Event(name="Temporary Event", lore_date=100.0)
    cmd = CreateEventCommand(db_service, event)

    # Execute
    assert cmd.execute() is True
    assert db_service.get_event(event.id) is not None

    # Undo
    cmd.undo()
    assert db_service.get_event(event.id) is None


def test_delete_event_undo(db_service):
    """Test deleting an event and then restoring it via undo."""
    # Setup initial state
    event = Event(name="To Be Deleted", lore_date=200.0)
    db_service.insert_event(event)

    # Verify it exists
    assert db_service.get_event(event.id) is not None

    # Execute Delete
    cmd = DeleteEventCommand(db_service, event.id)
    assert cmd.execute() is True
    assert db_service.get_event(event.id) is None

    # Undo Delete
    cmd.undo()
    restored = db_service.get_event(event.id)
    assert restored is not None
    assert restored.name == "To Be Deleted"
