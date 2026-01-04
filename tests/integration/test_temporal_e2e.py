"""
End-to-End Integration Tests for Temporal Relations.

Tests the full flow from:
1. Creating Entities and Events.
2. Linking them with temporal payloads.
3. Resolving state at different times (past/present/future).
4. Verifying state updates when upstream events change.
"""

import pytest

from src.commands.event_commands import UpdateEventCommand
from src.core.entities import Entity
from src.core.events import Event
from src.core.temporal_manager import TemporalManager
from src.services.db_service import DatabaseService


@pytest.fixture
def db_service(tmp_path):
    """Create a temporary database for testing."""
    db_path = str(tmp_path / "e2e_temporal.kraken")
    service = DatabaseService(db_path)
    service.connect()
    yield service
    service.close()


@pytest.fixture
def temporal_manager(db_service):
    """Create a TemporalManager with the test database."""
    return TemporalManager(db_service=db_service)


def test_entity_state_evolution_over_time(db_service, temporal_manager):
    """
    Scenario: An entity evolves over time via multiple events.
    Flow:
    1. Create Gandalf (Base: Grey).
    2. Event 1 (3019.0): Fights Balrog -> Status: Missing.
    3. Event 2 (3019.1): Returns -> Status: White.
    """
    # 1. Base Entity
    gandalf = Entity(
        id="gandalf", name="Gandalf", type="Wizard", attributes={"color": "Grey"}
    )
    db_service.insert_entity(gandalf)

    # 2. Events
    fight = Event(id="fight", name="Battle of the Peak", lore_date=3019.0)
    return_event = Event(id="return", name="Gandalf Returns", lore_date=3019.1)
    db_service.insert_events_bulk([fight, return_event])

    # 3. Relations/Payloads
    # Relation 1: Fights Balrog -> Missing
    db_service.insert_relation(
        source_id="fight",
        target_id="gandalf",
        rel_type="involved",
        attributes={"valid_from": 3019.0, "payload": {"status": "Missing"}},
    )

    # Relation 2: Returns -> White
    db_service.insert_relation(
        source_id="return",
        target_id="gandalf",
        rel_type="involved",
        attributes={
            "valid_from": 3019.1,
            "payload": {"color": "White", "status": "Active"},
        },
    )

    # 4. Verify Time Travel

    # Before Fight (3018.9) -> Base State
    state_early = temporal_manager.get_entity_state_at("gandalf", 3018.9)
    assert state_early["color"] == "Grey"
    assert "status" not in state_early

    # During Missing Period (3019.05) -> Missing, but still Grey (unless overwritten)
    # Payload only had status: Missing. Color remains Grey.
    state_mid = temporal_manager.get_entity_state_at("gandalf", 3019.05)
    assert state_mid["status"] == "Missing"
    assert state_mid["color"] == "Grey"

    # After Return (3019.2) -> White and Active
    state_late = temporal_manager.get_entity_state_at("gandalf", 3019.2)
    assert state_late["color"] == "White"
    assert state_late["status"] == "Active"


def test_upstream_event_change_propagates(db_service, temporal_manager):
    """
    Scenario: Changing an event's date shifts when the state change happens.
    Flow:
    1. Event A causes 'Wounded' at t=100.
    2. Verify t=90 is clean, t=110 is Wounded.
    3. Move Event A to t=80.
    4. Verify t=90 is now Wounded.
    """
    hero = Entity(id="hero", name="Hero", type="Character")
    db_service.insert_entity(hero)

    event = Event(id="ambush", name="Ambush", lore_date=100.0)
    db_service.insert_event(event)

    db_service.insert_relation(
        source_id="ambush",
        target_id="hero",
        rel_type="affects",
        attributes={
            "valid_from": 100.0,
            "valid_from_event": True,
            "payload": {"health": "Low"},
        },
    )

    # Check initial state
    assert "health" not in temporal_manager.get_entity_state_at("hero", 90.0)
    assert temporal_manager.get_entity_state_at("hero", 110.0)["health"] == "Low"

    # Move Event to 80.0
    # Note: We must update the relation's cached valid_from or rely on dynamic resolution if `valid_from_event` is used.
    # The TemporalResolver logic (as implemented in Stage 2) joins on cache/db.
    # The `valid_from_event` flag tells resolver to use event.lore_date.

    cmd = UpdateEventCommand("ambush", {"lore_date": 80.0})
    cmd.execute(db_service)

    # Manually trigger invalidation (in real app, signals handle this)
    temporal_manager.on_event_changed("ambush")

    # Verify Propagation
    # t=90 should now be Low health because event happened at 80
    assert temporal_manager.get_entity_state_at("hero", 90.0)["health"] == "Low"
