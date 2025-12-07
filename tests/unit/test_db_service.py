import pytest
import sqlite3
import time
from src.services.db_service import DatabaseService
from src.core.events import Event
from src.core.entities import Entity


@pytest.fixture
def db_service():
    service = DatabaseService(":memory:")
    service.connect()
    yield service
    service.close()


def test_event_crud(db_service):
    """Test Create, Read, Update, Delete for Events."""
    # Create
    event = Event(name="Battle of Hastings", lore_date=1066.0)
    event.attributes["weather"] = "foggy"
    db_service.insert_event(event)

    # Read
    fetched = db_service.get_event(event.id)
    assert fetched is not None
    assert fetched.name == "Battle of Hastings"
    assert fetched.lore_date == 1066.0
    assert fetched.attributes["weather"] == "foggy"

    # Update
    event.name = "The Battle of Hastings (Revised)"
    db_service.insert_event(event)  # Should upsert
    fetched_updated = db_service.get_event(event.id)
    assert fetched_updated.name == "The Battle of Hastings (Revised)"

    # Delete
    db_service.delete_event(event.id)
    assert db_service.get_event(event.id) is None


def test_entity_crud(db_service):
    """Test Create, Read for Entities."""
    # Create
    entity = Entity(name="Excalibur", type="artifact")
    entity.description = "A sword."
    db_service.insert_entity(entity)

    # Read
    fetched = db_service.get_entity(entity.id)
    assert fetched is not None
    assert fetched.name == "Excalibur"
    assert fetched.type == "artifact"
    assert fetched.description == "A sword."


def test_get_all_events(db_service):
    """Test fetching all events ordered by date."""
    e1 = Event(name="Future", lore_date=5000.0)
    e2 = Event(name="Ancient Past", lore_date=-1000.0)
    e3 = Event(name="Present", lore_date=2025.0)

    db_service.insert_event(e1)
    db_service.insert_event(e2)
    db_service.insert_event(e3)

    initial_list = [e1, e2, e3]

    events = db_service.get_all_events()
    assert len(events) == 3
    assert events[0].name == "Ancient Past"
    assert events[1].name == "Present"
    assert events[2].name == "Future"
