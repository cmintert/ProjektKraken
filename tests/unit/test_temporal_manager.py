"""
Unit tests for TemporalManager.

Verifies signal handling, caching, and data fetching delegation.
"""

from unittest.mock import Mock

import pytest
from PySide6.QtCore import QObject, Signal

from src.core.entities import Entity
from src.core.temporal_manager import TemporalManager


# Mock Signal Source
class MockSignalSource(QObject):
    relation_changed = Signal(str, str, str)  # rel_id, source_id, target_id
    event_changed = Signal(str)  # event_id


@pytest.fixture
def mock_db_service():
    """Mocks the DB service to provide entities and relations."""
    service = Mock()

    # Setup Entity
    entity = Entity(
        id="e1", name="Test Entity", type="generic", attributes={"status": "Base"}
    )
    service.get_entity.return_value = entity

    # Setup Relations
    # One relation applicable at T=100
    rel = {
        "id": "r1",
        "target_id": "e1",
        "attributes": {"valid_from": 100, "payload": {"status": "Overridden"}},
    }
    service.get_incoming_relations.return_value = [rel]
    service.get_relations.return_value = []  # Default: no outgoing relations

    return service


@pytest.fixture
def signal_source():
    return MockSignalSource()


@pytest.fixture
def manager(mock_db_service, signal_source):
    """Returns manager with mocked dependencies."""
    mgr = TemporalManager(db_service=mock_db_service)
    # Connect signals manually for test
    signal_source.relation_changed.connect(mgr.on_relation_changed)
    signal_source.event_changed.connect(mgr.on_event_changed)
    return mgr


def test_get_state_delegates_to_resolver(manager, mock_db_service):
    """Test that manager fetches data and uses resolver logic."""
    state = manager.get_entity_state_at("e1", time=150.0)

    # Should resolve to "Overridden" because 150 > 100
    assert state["status"] == "Overridden"

    # Verify DB calls
    mock_db_service.get_entity.assert_called_with("e1")
    mock_db_service.get_incoming_relations.assert_called_with("e1")


def test_caching_behavior(manager, mock_db_service):
    """Test that repeated calls use the cache."""
    # First call
    manager.get_entity_state_at("e1", time=150.0)
    assert mock_db_service.get_incoming_relations.call_count == 1

    # Second call - should use cache
    manager.get_entity_state_at("e1", time=150.0)
    assert mock_db_service.get_incoming_relations.call_count == 1

    # Different time - might need re-resolve depending on cache granularity.
    # For MVP, checking if it naively caches by (id, time).
    manager.get_entity_state_at("e1", time=200.0)
    # If caching is (id, time), this is a miss.


def test_invalidation_on_signal(manager, mock_db_service, signal_source):
    """Test that signals clear the cache."""
    # Warm cache
    manager.get_entity_state_at("e1", time=150.0)
    assert mock_db_service.get_incoming_relations.call_count == 1

    # Fire signal targeting e1
    # relation_changed(rel_id, source_id, target_id)
    signal_source.relation_changed.emit("r1", "evt1", "e1")

    # Call again - should re-fetch
    manager.get_entity_state_at("e1", time=150.0)
    assert mock_db_service.get_incoming_relations.call_count == 2


def test_event_change_invalidates_linked_entities(
    manager, mock_db_service, signal_source
):
    """
    Test that when an event changes, all entities linked through that event
    have their caches invalidated.
    """
    # Setup: Event "evt1" has relations to "e1" and "e2"
    mock_db_service.get_relations.return_value = [
        {"id": "r1", "target_id": "e1", "rel_type": "involved"},
        {"id": "r2", "target_id": "e2", "rel_type": "involved"},
    ]

    # Warm cache for e1
    manager.get_entity_state_at("e1", time=150.0)
    assert mock_db_service.get_incoming_relations.call_count == 1

    # Event changes (e.g., date moved)
    signal_source.event_changed.emit("evt1")

    # Verify cache was cleared for e1
    manager.get_entity_state_at("e1", time=150.0)
    assert mock_db_service.get_incoming_relations.call_count == 2


def test_event_change_with_no_relations(manager, mock_db_service, signal_source):
    """Edge case: Event with no outgoing relations should not crash."""
    mock_db_service.get_relations.return_value = []

    # Should not raise
    signal_source.event_changed.emit("orphan_event")


def test_relation_add_invalidates_target(manager, mock_db_service, signal_source):
    """Test that adding a new relation invalidates the target entity's cache."""
    # Warm cache
    manager.get_entity_state_at("e1", time=150.0)
    call_count_before = mock_db_service.get_incoming_relations.call_count

    # New relation added
    signal_source.relation_changed.emit("r_new", "evt1", "e1")

    # Cache should be invalidated
    manager.get_entity_state_at("e1", time=150.0)
    assert mock_db_service.get_incoming_relations.call_count > call_count_before


def test_relation_delete_invalidates_target(manager, mock_db_service, signal_source):
    """Test that deleting a relation invalidates the target entity's cache."""
    # Warm cache
    manager.get_entity_state_at("e1", time=150.0)
    call_count_before = mock_db_service.get_incoming_relations.call_count

    # Relation deleted
    signal_source.relation_changed.emit("r1", "evt1", "e1")

    # Cache should be invalidated
    manager.get_entity_state_at("e1", time=150.0)
    assert mock_db_service.get_incoming_relations.call_count > call_count_before


def test_multiple_time_points_invalidated(manager, mock_db_service, signal_source):
    """
    Test that invalidating an entity clears ALL cached time points.
    Edge case: Entity cached at T=100, T=200, T=300.
    """
    # Warm cache at multiple time points
    manager.get_entity_state_at("e1", time=100.0)
    manager.get_entity_state_at("e1", time=200.0)
    manager.get_entity_state_at("e1", time=300.0)
    assert mock_db_service.get_incoming_relations.call_count == 3

    # Invalidate
    signal_source.relation_changed.emit("r1", "evt1", "e1")

    # All time points should be cleared
    manager.get_entity_state_at("e1", time=100.0)
    manager.get_entity_state_at("e1", time=200.0)
    manager.get_entity_state_at("e1", time=300.0)
    assert mock_db_service.get_incoming_relations.call_count == 6


def test_nuclear_clear_cache(manager, mock_db_service):
    """Test that clear_all_cache() removes all entries."""
    # Warm cache with multiple entities at multiple times
    manager.get_entity_state_at("e1", time=100.0)
    manager.get_entity_state_at("e2", time=200.0)
    assert mock_db_service.get_incoming_relations.call_count == 2

    # Nuclear clear
    manager.clear_all_cache()

    # All should be re-fetched
    manager.get_entity_state_at("e1", time=100.0)
    manager.get_entity_state_at("e2", time=200.0)
    assert mock_db_service.get_incoming_relations.call_count == 4


def test_invalidation_does_not_affect_other_entities(
    manager, mock_db_service, signal_source
):
    """
    Edge case: Invalidating e1 should not invalidate e2's cache.
    """
    # Setup mock for e2
    entity2 = Entity(
        id="e2", name="Other Entity", type="generic", attributes={"status": "Base2"}
    )
    mock_db_service.get_entity.side_effect = lambda eid: (
        entity2
        if eid == "e2"
        else Entity(id="e1", name="Test", type="generic", attributes={"status": "Base"})
    )

    # Warm both caches
    manager.get_entity_state_at("e1", time=100.0)
    manager.get_entity_state_at("e2", time=100.0)
    call_count_after_warm = mock_db_service.get_incoming_relations.call_count

    # Invalidate only e1
    signal_source.relation_changed.emit("r1", "evt1", "e1")

    # e2 should still be cached
    manager.get_entity_state_at("e2", time=100.0)
    # Should not have incremented (still cached)
    assert mock_db_service.get_incoming_relations.call_count == call_count_after_warm

    # e1 should be invalidated
    manager.get_entity_state_at("e1", time=100.0)
    assert (
        mock_db_service.get_incoming_relations.call_count == call_count_after_warm + 1
    )


def test_nonexistent_entity_does_not_crash(manager, mock_db_service):
    """Edge case: Requesting state for entity that doesn't exist."""
    mock_db_service.get_entity.return_value = None

    state = manager.get_entity_state_at("nonexistent", time=100.0)

    # Should return empty dict
    assert state == {}
