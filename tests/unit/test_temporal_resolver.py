"""
Unit tests for TemporalResolver.

Follows TDD approach to define expected behavior of the temporal state engine.
"""

import pytest

from src.core.entities import Entity
from src.core.temporal_resolver import TemporalResolver


@pytest.fixture
def resolver():
    return TemporalResolver()


@pytest.fixture
def base_entity():
    """Returns a dummy entity with base state."""
    return Entity(
        id="entity_1",
        name="Jon Snow",
        type="character",
        attributes={"status": "Alive", "location": "Winterfell", "rank": "Bastard"},
    )


def test_resolve_entity_state_no_relations(resolver, base_entity):
    """Test that resolving with no relations returns base state."""
    state = resolver.resolve_entity_state(base_entity, [], time=100.0)
    assert state == base_entity.attributes


def test_resolve_entity_state_basic_override(resolver, base_entity):
    """Test simple override from a relation valid at the time."""
    relations = [
        {
            "id": "rel_1",
            "attributes": {"valid_from": 50.0, "payload": {"status": "Dead"}},
        }
    ]

    # Check before event
    state_before = resolver.resolve_entity_state(base_entity, relations, time=40.0)
    assert state_before["status"] == "Alive"

    # Check after event
    state_after = resolver.resolve_entity_state(base_entity, relations, time=60.0)
    assert state_after["status"] == "Dead"
    # Unchanged fields should remain from base
    assert state_after["location"] == "Winterfell"


def test_resolve_entity_state_time_scope(resolver, base_entity):
    """Test valid_from and valid_to bounds."""
    relations = [
        {
            "id": "rel_1",
            "attributes": {
                "valid_from": 100.0,
                "valid_to": 200.0,
                "payload": {"status": "Temporary King"},
            },
        }
    ]

    # Before
    assert (
        resolver.resolve_entity_state(base_entity, relations, 99.0)["status"] == "Alive"
    )
    # During
    assert (
        resolver.resolve_entity_state(base_entity, relations, 100.0)["status"]
        == "Temporary King"
    )
    assert (
        resolver.resolve_entity_state(base_entity, relations, 150.0)["status"]
        == "Temporary King"
    )
    # After (exclusive)
    assert (
        resolver.resolve_entity_state(base_entity, relations, 200.01)["status"]
        == "Alive"
    )


def test_resolve_entity_state_priority(resolver, base_entity):
    """Test that manual priority overrides event priority, or later overrides earlier."""
    relations = [
        # Earlier manual override
        {
            "id": "rel_manual",
            "attributes": {
                "valid_from": 10.0,
                "priority": "manual",
                "payload": {"rank": "Overridden Manually"},
            },
        },
        # Later event override
        {
            "id": "rel_event",
            "attributes": {
                "valid_from": 20.0,
                "priority": "event",
                "payload": {"rank": "Event Rank"},
            },
        },
    ]

    # At T=30, both are valid.
    # Logic: Sort by ValidFrom (10, 20).
    # Event (20) applies AFTER Manual (10) based purely on time?
    # NO: Design says Priority > Time.
    # Manual (priority=2) should win over Event (priority=1) if we implement that.
    # Let's check the design requirement.
    # Design doc: "Sort by valid_from... Manual overrides Event."

    # Scenario A: If Manual is meant to stick REGARDLESS of future events (like a forceful fix),
    # it needs higher sort index.

    state = resolver.resolve_entity_state(base_entity, relations, time=30.0)
    # Based on tuple sort (Time, Priority), (10, 2) < (20, 1), so Event is last.
    assert state["rank"] == "Event Rank"

    # If our sort key is (Time, Priority), then:
    # rel_manual: (10, 2)
    # rel_event: (20, 1)
    # Tuple comparison: (10, 2) < (20, 1) because 10 < 20.
    # So Event applies LAST.
    # Result: "Event Rank".

    # WAIT regarding "Priority > Time" in design:
    # If I want manual fix to override an event, I usually set it at the SAME time or just expect it to win.

    # Let's test "Same Time" conflict to be sure of priority.
    relations_same_time = [
        {
            "id": "rel_manual_2",
            "attributes": {
                "valid_from": 50.0,
                "priority": "manual",
                "payload": {"location": "Manual Loc"},
            },
        },
        {
            "id": "rel_event_2",
            "attributes": {
                "valid_from": 50.0,
                "priority": "event",
                "payload": {"location": "Event Loc"},
            },
        },
    ]

    state_conflict = resolver.resolve_entity_state(
        base_entity, relations_same_time, time=60.0
    )
    # Manual (priority 2) > Event (priority 1)
    # So Manual applies Last.
    assert state_conflict["location"] == "Manual Loc"


def test_stepwise_history(resolver, base_entity):
    """Test a sequence of events building up state."""
    relations = [
        {"attributes": {"valid_from": 100, "payload": {"location": "Castle Black"}}},
        {"attributes": {"valid_from": 200, "payload": {"status": "Wounded"}}},
        {
            "attributes": {
                "valid_from": 300,
                "payload": {"location": "Winterfell", "status": "Healing"},
            }
        },
    ]

    assert (
        resolver.resolve_entity_state(base_entity, relations, 150)["location"]
        == "Castle Black"
    )
    assert (
        resolver.resolve_entity_state(base_entity, relations, 250)["status"]
        == "Wounded"
    )
    assert (
        resolver.resolve_entity_state(base_entity, relations, 250)["location"]
        == "Castle Black"
    )  # Persists

    final = resolver.resolve_entity_state(base_entity, relations, 350)
    assert final["location"] == "Winterfell"
    assert final["status"] == "Healing"


def test_multi_edge_relations(resolver, base_entity):
    """Test multiple relations from same event (same time/source)."""
    relations = [
        {
            "id": "rel_rank",
            "attributes": {
                "valid_from": 100,
                "payload": {"rank": "Commander"},
                "modified_at": 1000,
            },
        },
        {
            "id": "rel_status",
            "attributes": {
                "valid_from": 100,
                "payload": {"status": "Busy"},
                "modified_at": 1001,  # Created slightly later
            },
        },
    ]

    state = resolver.resolve_entity_state(base_entity, relations, 100)
    assert state["rank"] == "Commander"
    assert state["status"] == "Busy"
