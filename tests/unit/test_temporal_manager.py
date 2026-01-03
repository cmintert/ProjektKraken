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


def test_invalidation_on_event_change(manager, mock_db_service, signal_source):
    """
    Events changing (e.g. date moved) might affect relations.
    Since we don't easily know which entities an event touches without querying,
    the manager might need to be smart or conservative (clear all? or query deps?).

    For MVP Stage 0, let's assume conservative: we might not implement Granular
    Event->Entity invalidation yet, or we assume the signal carries info?

    Actually, db_service.py usually emits signals.
    If event changes, we technically don't know who is affected unless we look up relations.

    Let's stick to relation_changed for now which has target_id.
    """
    pass
