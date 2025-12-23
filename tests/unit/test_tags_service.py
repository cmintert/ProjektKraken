"""
Unit tests for TagsService - Tag CRUD operations.
"""

import pytest

from src.core.entities import Entity
from src.core.events import Event


@pytest.mark.unit
class TestTagsService:
    """Tests for TagsService tag management operations."""

    def test_get_all_tags_empty(self, db_service):
        """Test getting all tags when database is empty."""
        tags = db_service.get_all_tags()
        assert tags == []

    def test_create_tag(self, db_service):
        """Test creating a new tag."""
        tag_id = db_service.create_tag("important")
        assert tag_id is not None
        tags = db_service.get_all_tags()
        assert len(tags) == 1
        assert tags[0]["name"] == "important"

    def test_create_duplicate_tag_returns_existing(self, db_service):
        """Test that creating a duplicate tag returns the existing tag ID."""
        tag_id1 = db_service.create_tag("test-tag")
        tag_id2 = db_service.create_tag("test-tag")
        assert tag_id1 == tag_id2
        tags = db_service.get_all_tags()
        assert len(tags) == 1

    def test_assign_tag_to_event(self, db_service):
        """Test assigning a tag to an event."""
        event = Event(name="Test Event", lore_date=100.0)
        db_service.insert_event(event)

        db_service.assign_tag_to_event(event.id, "important")
        tags = db_service.get_tags_for_event(event.id)
        assert len(tags) == 1
        assert tags[0]["name"] == "important"

    def test_assign_multiple_tags_to_event(self, db_service):
        """Test assigning multiple tags to a single event."""
        event = Event(name="Test Event", lore_date=100.0)
        db_service.insert_event(event)

        db_service.assign_tag_to_event(event.id, "important")
        db_service.assign_tag_to_event(event.id, "battle")
        db_service.assign_tag_to_event(event.id, "victory")
        tags = db_service.get_tags_for_event(event.id)
        assert len(tags) == 3
        tag_names = [t["name"] for t in tags]
        assert "important" in tag_names
        assert "battle" in tag_names
        assert "victory" in tag_names

    def test_assign_duplicate_tag_to_event_ignored(self, db_service):
        """Test that assigning the same tag twice to an event is idempotent."""
        event = Event(name="Test Event", lore_date=100.0)
        db_service.insert_event(event)

        db_service.assign_tag_to_event(event.id, "important")
        db_service.assign_tag_to_event(event.id, "important")
        tags = db_service.get_tags_for_event(event.id)
        assert len(tags) == 1

    def test_assign_tag_to_entity(self, db_service):
        """Test assigning a tag to an entity."""
        entity = Entity(name="Test Character", type="character")
        db_service.insert_entity(entity)

        db_service.assign_tag_to_entity(entity.id, "protagonist")
        tags = db_service.get_tags_for_entity(entity.id)
        assert len(tags) == 1
        assert tags[0]["name"] == "protagonist"

    def test_assign_multiple_tags_to_entity(self, db_service):
        """Test assigning multiple tags to a single entity."""
        entity = Entity(name="Test Character", type="character")
        db_service.insert_entity(entity)

        db_service.assign_tag_to_entity(entity.id, "protagonist")
        db_service.assign_tag_to_entity(entity.id, "warrior")
        db_service.assign_tag_to_entity(entity.id, "human")
        tags = db_service.get_tags_for_entity(entity.id)
        assert len(tags) == 3

    def test_remove_tag_from_event(self, db_service):
        """Test removing a tag from an event."""
        event = Event(name="Test Event", lore_date=100.0)
        db_service.insert_event(event)

        db_service.assign_tag_to_event(event.id, "important")
        db_service.assign_tag_to_event(event.id, "battle")
        db_service.remove_tag_from_event(event.id, "important")
        tags = db_service.get_tags_for_event(event.id)
        assert len(tags) == 1
        assert tags[0]["name"] == "battle"

    def test_remove_tag_from_entity(self, db_service):
        """Test removing a tag from an entity."""
        entity = Entity(name="Test Character", type="character")
        db_service.insert_entity(entity)

        db_service.assign_tag_to_entity(entity.id, "protagonist")
        db_service.assign_tag_to_entity(entity.id, "warrior")
        db_service.remove_tag_from_entity(entity.id, "warrior")
        tags = db_service.get_tags_for_entity(entity.id)
        assert len(tags) == 1
        assert tags[0]["name"] == "protagonist"

    def test_delete_tag_removes_all_associations(self, db_service):
        """Test that deleting a tag removes it from all events and entities."""
        event = Event(name="Test Event", lore_date=100.0)
        db_service.insert_event(event)

        entity = Entity(name="Test Entity", type="character")
        db_service.insert_entity(entity)

        db_service.assign_tag_to_event(event.id, "shared-tag")
        db_service.assign_tag_to_entity(entity.id, "shared-tag")
        db_service.delete_tag("shared-tag")
        event_tags = db_service.get_tags_for_event(event.id)
        entity_tags = db_service.get_tags_for_entity(entity.id)
        assert len(event_tags) == 0
        assert len(entity_tags) == 0
        all_tags = db_service.get_all_tags()
        assert "shared-tag" not in [t["name"] for t in all_tags]

    def test_get_events_by_tag(self, db_service):
        """Test retrieving all events with a specific tag."""
        event1 = Event(name="Event 1", lore_date=100.0)
        db_service.insert_event(event1)

        event2 = Event(name="Event 2", lore_date=200.0)
        db_service.insert_event(event2)

        event3 = Event(name="Event 3", lore_date=300.0)
        db_service.insert_event(event3)

        db_service.assign_tag_to_event(event1.id, "important")
        db_service.assign_tag_to_event(event2.id, "important")
        db_service.assign_tag_to_event(event3.id, "other")
        events = db_service.get_events_by_tag("important")
        assert len(events) == 2
        event_ids = [e.id for e in events]
        assert event1.id in event_ids
        assert event2.id in event_ids
        assert event3.id not in event_ids

    def test_get_entities_by_tag(self, db_service):
        """Test retrieving all entities with a specific tag."""
        entity1 = Entity(name="Entity 1", type="character")
        db_service.insert_entity(entity1)

        entity2 = Entity(name="Entity 2", type="character")
        db_service.insert_entity(entity2)

        entity3 = Entity(name="Entity 3", type="location")
        db_service.insert_entity(entity3)

        db_service.assign_tag_to_entity(entity1.id, "protagonist")
        db_service.assign_tag_to_entity(entity2.id, "protagonist")
        db_service.assign_tag_to_entity(entity3.id, "city")
        entities = db_service.get_entities_by_tag("protagonist")
        assert len(entities) == 2
        entity_ids = [e.id for e in entities]
        assert entity1.id in entity_ids
        assert entity2.id in entity_ids
        assert entity3.id not in entity_ids

    def test_get_tags_for_nonexistent_event(self, db_service):
        """Test getting tags for an event that doesn't exist."""
        tags = db_service.get_tags_for_event("nonexistent-id")
        assert tags == []

    def test_get_tags_for_nonexistent_entity(self, db_service):
        """Test getting tags for an entity that doesn't exist."""
        tags = db_service.get_tags_for_entity("nonexistent-id")
        assert tags == []

    def test_tag_name_case_sensitive(self, db_service):
        """Test that tag names are case-sensitive."""
        tag_id1 = db_service.create_tag("Important")
        tag_id2 = db_service.create_tag("important")
        assert tag_id1 != tag_id2
        tags = db_service.get_all_tags()
        assert len(tags) == 2

    def test_tag_name_whitespace_trimmed(self, db_service):
        """Test that tag names have leading/trailing whitespace trimmed."""
        tag_id1 = db_service.create_tag("  test-tag  ")
        tags = db_service.get_all_tags()
        assert len(tags) == 1
        assert tags[0]["name"] == "test-tag"

    def test_empty_tag_name_rejected(self, db_service):
        """Test that empty or whitespace-only tag names are rejected."""
        with pytest.raises(ValueError):
            db_service.create_tag("")
        with pytest.raises(ValueError):
            db_service.create_tag("   ")

    def test_delete_event_removes_tag_associations(self, db_service):
        """Test that deleting an event removes its tag associations."""
        event = Event(name="Test Event", lore_date=100.0)
        db_service.insert_event(event)

        db_service.assign_tag_to_event(event.id, "important")
        tags_before = db_service.get_tags_for_event(event.id)
        assert len(tags_before) == 1

        db_service.delete_event(event.id)

        # After deletion, tag associations should be gone
        tags_after = db_service.get_tags_for_event(event.id)
        assert len(tags_after) == 0

    def test_delete_entity_removes_tag_associations(self, db_service):
        """Test that deleting an entity removes its tag associations."""
        entity = Entity(name="Test Entity", type="character")
        db_service.insert_entity(entity)

        db_service.assign_tag_to_entity(entity.id, "protagonist")
        tags_before = db_service.get_tags_for_entity(entity.id)
        assert len(tags_before) == 1

        db_service.delete_entity(entity.id)

        # After deletion, tag associations should be gone
        tags_after = db_service.get_tags_for_entity(entity.id)
        assert len(tags_after) == 0
