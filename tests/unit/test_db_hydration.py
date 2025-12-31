import pytest

from src.core.entities import Entity
from src.core.events import Event


@pytest.mark.unit
class TestDBHydration:
    """Tests for fetching objects by IDs (Hydration)."""

    def test_get_objects_by_ids_empty(self, db_service):
        """Test with empty ID list."""
        events, entities = db_service.get_objects_by_ids([])
        assert events == []
        assert entities == []

    def test_get_objects_by_ids_mixed(self, db_service):
        """Test retrieving both events and entities."""
        # Setup data
        e1 = Entity(name="E1", type="char")
        e2 = Entity(name="E2", type="loc")
        ev1 = Event(name="Ev1", lore_date=10)
        ev2 = Event(name="Ev2", lore_date=20)

        db_service.insert_entity(e1)
        db_service.insert_entity(e2)
        db_service.insert_event(ev1)
        db_service.insert_event(ev2)

        # Request specific IDs
        request_ids = [("entity", e1.id), ("event", ev2.id)]

        # Execute
        ret_events, ret_entities = db_service.get_objects_by_ids(request_ids)

        # Verify
        assert len(ret_entities) == 1
        assert ret_entities[0].id == e1.id
        assert ret_entities[0].name == "E1"

        assert len(ret_events) == 1
        assert ret_events[0].id == ev2.id
        assert ret_events[0].name == "Ev2"

    def test_get_objects_by_ids_preserves_order(self, db_service):
        """
        Test that retrieved objects are sorted appropriately?
        Actually, the filtered ID list might come in sorted by the filter logic,
        but typically we want events by lore_date and entities by name in the UI.
        The current spec says UnifiedListWidget handles sorting or assumes simple append.

        Ideally, the DB service should return them sorted by their natural order
        (Events: lore_date, Entities: name) regardless of input ID order,
        OR satisfy the input order.

        Let's assume for now we want them naturally sorted to match expected UI behavior.
        """
        ev1 = Event(name="A", lore_date=20)
        ev2 = Event(name="B", lore_date=10)

        db_service.insert_event(ev1)
        db_service.insert_event(ev2)

        request_ids = [("event", ev1.id), ("event", ev2.id)]

        events, _ = db_service.get_objects_by_ids(request_ids)

        # Should be sorted by date: ev2 (10), then ev1 (20)
        assert len(events) == 2
        assert events[0].id == ev2.id
        assert events[1].id == ev1.id

    def test_get_objects_by_ids_ignores_missing(self, db_service):
        """Test that missing IDs are ignored gracefully."""
        e1 = Entity(name="E1", type="char")
        db_service.insert_entity(e1)

        request_ids = [
            ("entity", e1.id),
            ("entity", "missing-uuid"),
            ("event", "missing-uuid-2"),
        ]

        events, entities = db_service.get_objects_by_ids(request_ids)

        assert len(entities) == 1
        assert entities[0].id == e1.id
        assert len(events) == 0
