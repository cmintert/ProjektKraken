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


def test_dynamic_event_timing(db_service, temporal_manager):
    """
    Test that relations with 'valid_from_event=True' follow the Event's date.
    """
    # 1. Setup Data
    entity = Entity(
        id="e1", name="Hero", type="Character", attributes={"status": "Healthy"}
    )
    db_service.insert_entity(entity)

    event = Event(id="ev1", name="Injury Event", lore_date=100.0)
    db_service.insert_event(event)

    # 2. Insert Relation with Dynamic "Starts Here" flag
    # Note: We do NOT set specific valid_from date, or set it to dummy value
    # The Resolver should ignore valid_from if valid_from_event is True
    relation_attrs = {
        "valid_from": 0.0,  # Dummy value, should be ignored
        "valid_from_event": True,
        "payload": {"status": "Injured"},
    }

    db_service.insert_relation(
        source_id="ev1",
        target_id="e1",
        rel_type="affected_by",
        attributes=relation_attrs,
    )

    # 3. Initial Verification (Event at 100)

    # T=50 (Before)
    state_50 = temporal_manager.get_entity_state_at("e1", 50.0)
    assert state_50["status"] == "Healthy"

    # T=150 (After)
    state_150 = temporal_manager.get_entity_state_at("e1", 150.0)
    assert state_150["status"] == "Injured"

    # 4. Move the Event!
    # Update Event Date to 200
    # Update Event Date to 200
    # Create revised event object with same ID
    updated_event = Event(id="ev1", name="Injury Event Moved", lore_date=200.0)
    db_service._event_repo.insert(updated_event)

    # Invalidate Cache (since signals aren't auto-wired in this constrained test)
    temporal_manager.invalidate_entity("e1")

    # 5. Verify Shift logic

    # T=150 (Now Before the event)
    state_150_new = temporal_manager.get_entity_state_at("e1", 150.0)
    assert state_150_new["status"] == "Healthy", (
        "Relation should have moved with event to T=200"
    )

    # T=250 (Now After the event)
    state_250 = temporal_manager.get_entity_state_at("e1", 250.0)
    assert state_250["status"] == "Injured"
