import pytest

from src.core.entities import Entity
from src.core.events import Event
from src.core.temporal_manager import TemporalManager
from src.services.db_service import DatabaseService


@pytest.fixture
def db_service():
    service = DatabaseService(":memory:")
    service.connect()
    return service


@pytest.fixture
def temporal_manager(db_service):
    return TemporalManager(db_service)


def test_temporal_resolution_flow(db_service, temporal_manager):
    """
    Integration test:
    1. Create an Entity.
    2. Create an Event with a Relation to that Entity (temporal).
    3. Resolve state via TemporalManager at different times.
    """

    # 1. Create Entity
    entity = Entity(
        id="e1",
        name="Jon Snow",
        type="Character",
        attributes={"status": "Alive", "location": "Winterfell"},
    )
    db_service.insert_entity(entity)

    # 2. Create Event
    event = Event(
        id="ev1",
        name="Battle of the Bastards",
        lore_date=300.0,
        # date logic usually handled by relation VALID_FROM, but event date provides context
    )
    db_service.insert_event(event)

    # 3. Create Relation (Temporal Override)
    # Relation: valid_from=300, valid_to=None, payload={status: 'King in the North'}
    relation_attrs = {
        "valid_from": 300.0,
        "payload": {"status": "King in the North", "location": "Winterfell"},
    }

    db_service.insert_relation(
        source_id="ev1",
        target_id="e1",
        rel_type="participated_in",
        attributes=relation_attrs,
    )

    # 4. Resolve State via Manager

    # T=200 (Before Event)
    state_before = temporal_manager.get_entity_state_at("e1", 200.0)
    assert state_before["status"] == "Alive"

    # T=300 (At Event)
    state_at = temporal_manager.get_entity_state_at("e1", 300.0)
    assert state_at["status"] == "King in the North"

    # T=400 (After Event)
    state_after = temporal_manager.get_entity_state_at("e1", 400.0)
    assert state_after["status"] == "King in the North"


def test_temporal_invalidation(db_service, temporal_manager):
    """
    Test that modifying a relation invalidates the cache.
    """
    # Setup
    entity = Entity(id="e2", name="Ghost", type="Wolf", attributes={"color": "White"})
    db_service.insert_entity(entity)

    event = Event(id="ev2", name="Battle", lore_date=100.0)
    db_service.insert_event(event)

    # Initial Relation
    db_service.insert_relation(
        source_id="ev2",
        target_id="e2",
        rel_type="owned_by",
        attributes={"valid_from": 100.0, "payload": {"color": "Dirty White"}},
    )

    # Cache Prime
    state_1 = temporal_manager.get_entity_state_at("e2", 150.0)
    assert state_1["color"] == "Dirty White"

    # Need to simulate invalidation manually since signals aren't wired up in integration test
    temporal_manager.invalidate_entity("e2")

    # New Relation overriding
    db_service.insert_relation(
        source_id="ev2",
        target_id="e2",
        rel_type="cleaned",
        attributes={"valid_from": 101.0, "payload": {"color": "Sparkling White"}},
    )

    # Fetch again
    state_2 = temporal_manager.get_entity_state_at("e2", 150.0)
    assert state_2["color"] == "Sparkling White"
