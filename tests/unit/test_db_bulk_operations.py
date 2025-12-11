"""
Unit tests for DatabaseService bulk operations and edge cases.

Tests bulk insert functionality, transaction rollbacks, edge cases,
and performance optimizations.
"""

import pytest
import sqlite3

from src.core.events import Event
from src.core.entities import Entity
from src.services.db_service import DatabaseService


@pytest.fixture
def db():
    """Returns an in-memory database service."""
    service = DatabaseService(":memory:")
    service.connect()
    yield service
    service.close()


def test_bulk_insert_events_empty_list(db):
    """Test bulk insert with empty list does not fail."""
    db.insert_events_bulk([])
    events = db.get_all_events()
    assert len(events) == 0


def test_bulk_insert_events_single(db):
    """Test bulk insert with single event."""
    event = Event(name="Event 1", lore_date=100.0)
    db.insert_events_bulk([event])

    retrieved = db.get_event(event.id)
    assert retrieved is not None
    assert retrieved.name == "Event 1"
    assert retrieved.lore_date == 100.0


def test_bulk_insert_events_multiple(db):
    """Test bulk insert with multiple events."""
    events = [
        Event(name=f"Event {i}", lore_date=float(i * 100))
        for i in range(1, 101)
    ]

    db.insert_events_bulk(events)

    # Verify all events were inserted
    all_events = db.get_all_events()
    assert len(all_events) == 100

    # Verify ordering
    assert all_events[0].name == "Event 1"
    assert all_events[99].name == "Event 100"


def test_bulk_insert_events_with_attributes(db):
    """Test bulk insert preserves complex attributes."""
    events = [
        Event(
            name="Event 1",
            lore_date=1.0,
            attributes={"key1": "value1", "nested": {"data": [1, 2, 3]}},
        ),
        Event(
            name="Event 2",
            lore_date=2.0,
            attributes={"key2": "value2", "list": ["a", "b", "c"]},
        ),
    ]

    db.insert_events_bulk(events)

    e1 = db.get_event(events[0].id)
    e2 = db.get_event(events[1].id)

    assert e1.attributes["key1"] == "value1"
    assert e1.attributes["nested"]["data"] == [1, 2, 3]
    assert e2.attributes["key2"] == "value2"
    assert e2.attributes["list"] == ["a", "b", "c"]


def test_bulk_insert_events_upsert(db):
    """Test bulk insert performs upsert correctly."""
    event = Event(name="Original", lore_date=1.0)
    db.insert_event(event)

    # Update via bulk insert
    event.name = "Updated"
    event.description = "New description"
    db.insert_events_bulk([event])

    retrieved = db.get_event(event.id)
    assert retrieved.name == "Updated"
    assert retrieved.description == "New description"

    # Should still only have one event
    all_events = db.get_all_events()
    assert len(all_events) == 1


def test_bulk_insert_entities_empty_list(db):
    """Test bulk insert entities with empty list."""
    db.insert_entities_bulk([])
    entities = db.get_all_entities()
    assert len(entities) == 0


def test_bulk_insert_entities_multiple(db):
    """Test bulk insert with multiple entities."""
    entities = [
        Entity(name=f"Entity {i}", type="character")
        for i in range(1, 51)
    ]

    db.insert_entities_bulk(entities)

    all_entities = db.get_all_entities()
    assert len(all_entities) == 50


def test_bulk_insert_entities_with_attributes(db):
    """Test bulk insert entities preserves attributes."""
    entities = [
        Entity(
            name="Gandalf",
            type="character",
            attributes={"level": 20, "items": ["Staff", "Pipe"]},
        ),
        Entity(
            name="Rivendell",
            type="location",
            attributes={"region": "Eriador", "population": 500},
        ),
    ]

    db.insert_entities_bulk(entities)

    e1 = db.get_entity(entities[0].id)
    e2 = db.get_entity(entities[1].id)

    assert e1.attributes["level"] == 20
    assert e1.attributes["items"] == ["Staff", "Pipe"]
    assert e2.attributes["region"] == "Eriador"
    assert e2.attributes["population"] == 500


def test_bulk_insert_entities_upsert(db):
    """Test bulk insert entities performs upsert."""
    entity = Entity(name="Original", type="character")
    db.insert_entity(entity)

    entity.name = "Updated"
    entity.description = "New description"
    db.insert_entities_bulk([entity])

    retrieved = db.get_entity(entity.id)
    assert retrieved.name == "Updated"
    assert retrieved.description == "New description"

    all_entities = db.get_all_entities()
    assert len(all_entities) == 1


def test_transaction_rollback_on_error(db):
    """Test that transactions rollback on error."""
    # Insert a valid event
    event1 = Event(name="Valid Event", lore_date=1.0)
    db.insert_event(event1)

    # Verify it was inserted
    assert db.get_event(event1.id) is not None

    # Try to execute invalid SQL within a transaction
    try:
        with db.transaction() as conn:
            # Insert a second event
            event2 = Event(name="Second Event", lore_date=2.0)
            conn.execute(
                """
                INSERT INTO events (id, type, name, lore_date, lore_duration,
                                    description, attributes, created_at, modified_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event2.id,
                    event2.type,
                    event2.name,
                    event2.lore_date,
                    event2.lore_duration,
                    event2.description,
                    "{}",
                    event2.created_at,
                    event2.modified_at,
                ),
            )
            # Force an error
            conn.execute("INSERT INTO nonexistent_table VALUES (1)")
    except sqlite3.OperationalError:
        pass  # Expected

    # First event should still exist
    assert db.get_event(event1.id) is not None
    # Second event should NOT exist (transaction rolled back)
    assert db.get_event(event2.id) is None


def test_connection_auto_connects_on_read(db):
    """Test that read operations auto-connect if needed."""
    db.close()

    # Should auto-connect
    event = Event(name="Test", lore_date=1.0)
    db.insert_event(event)

    retrieved = db.get_event(event.id)
    assert retrieved is not None


def test_get_event_nonexistent(db):
    """Test getting a nonexistent event returns None."""
    result = db.get_event("nonexistent-id")
    assert result is None


def test_get_entity_nonexistent(db):
    """Test getting a nonexistent entity returns None."""
    result = db.get_entity("nonexistent-id")
    assert result is None


def test_get_relation_nonexistent(db):
    """Test getting a nonexistent relation returns None."""
    result = db.get_relation("nonexistent-id")
    assert result is None


def test_delete_nonexistent_event(db):
    """Test deleting nonexistent event does not raise error."""
    # Should not raise an exception
    db.delete_event("nonexistent-id")


def test_delete_nonexistent_entity(db):
    """Test deleting nonexistent entity does not raise error."""
    db.delete_entity("nonexistent-id")


def test_delete_nonexistent_relation(db):
    """Test deleting nonexistent relation does not raise error."""
    db.delete_relation("nonexistent-id")


def test_get_name_event(db):
    """Test get_name retrieves event name."""
    event = Event(name="Test Event", lore_date=1.0)
    db.insert_event(event)

    name = db.get_name(event.id)
    assert name == "Test Event"


def test_get_name_entity(db):
    """Test get_name retrieves entity name."""
    entity = Entity(name="Test Entity", type="character")
    db.insert_entity(entity)

    name = db.get_name(entity.id)
    assert name == "Test Entity"


def test_get_name_nonexistent(db):
    """Test get_name returns None for nonexistent ID."""
    name = db.get_name("nonexistent-id")
    assert name is None


def test_foreign_keys_enabled(db):
    """Test that foreign keys are enabled."""
    cursor = db._connection.execute("PRAGMA foreign_keys")
    result = cursor.fetchone()
    assert result[0] == 1


def test_indexes_created(db):
    """Test that performance indexes are created."""
    cursor = db._connection.execute(
        "SELECT name FROM sqlite_master WHERE type='index'"
    )
    indexes = [row[0] for row in cursor.fetchall()]

    assert "idx_events_date" in indexes
    assert "idx_relations_source" in indexes
    assert "idx_relations_target" in indexes


def test_event_ordering_by_lore_date(db):
    """Test that get_all_events returns chronologically ordered events."""
    events = [
        Event(name="Future", lore_date=1000.0),
        Event(name="Past", lore_date=-500.0),
        Event(name="Present", lore_date=0.0),
        Event(name="Recent Past", lore_date=-100.0),
    ]

    for event in events:
        db.insert_event(event)

    sorted_events = db.get_all_events()
    assert sorted_events[0].name == "Past"
    assert sorted_events[1].name == "Recent Past"
    assert sorted_events[2].name == "Present"
    assert sorted_events[3].name == "Future"


def test_incoming_relations(db):
    """Test get_incoming_relations retrieves correct relations."""
    source1 = Event(name="Source 1", lore_date=1.0)
    source2 = Event(name="Source 2", lore_date=2.0)
    target = Event(name="Target", lore_date=3.0)

    db.insert_event(source1)
    db.insert_event(source2)
    db.insert_event(target)

    rel1_id = db.insert_relation(source1.id, target.id, "caused")
    rel2_id = db.insert_relation(source2.id, target.id, "influenced")

    incoming = db.get_incoming_relations(target.id)
    assert len(incoming) == 2

    rel_ids = {rel["id"] for rel in incoming}
    assert rel1_id in rel_ids
    assert rel2_id in rel_ids


def test_relation_attributes_none_default(db):
    """Test insert_relation handles None attributes correctly."""
    source = Event(name="Source", lore_date=1.0)
    target = Event(name="Target", lore_date=2.0)

    db.insert_event(source)
    db.insert_event(target)

    rel_id = db.insert_relation(source.id, target.id, "caused", None)

    rel = db.get_relation(rel_id)
    assert rel is not None
    assert rel["attributes"] == {}


def test_update_relation_attributes_none(db):
    """Test update_relation handles None attributes correctly."""
    source = Event(name="Source", lore_date=1.0)
    target1 = Event(name="Target 1", lore_date=2.0)
    target2 = Event(name="Target 2", lore_date=3.0)

    db.insert_event(source)
    db.insert_event(target1)
    db.insert_event(target2)

    rel_id = db.insert_relation(source.id, target1.id, "caused")

    db.update_relation(rel_id, target2.id, "prevented", None)

    rel = db.get_relation(rel_id)
    assert rel["target_id"] == target2.id
    assert rel["rel_type"] == "prevented"
    assert rel["attributes"] == {}
