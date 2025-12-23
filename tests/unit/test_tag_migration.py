"""
Unit tests for tag migration from JSON attributes to normalized tables.
"""

import json
import pytest

from src.core.entities import Entity
from src.core.events import Event


@pytest.mark.unit
class TestTagMigration:
    """Tests for migrating tags from JSON attributes to normalized tables."""

    def test_extract_tags_from_event_attributes(self, db_service):
        """Test extracting tags from event attributes JSON."""
        # Create event with tags in attributes
        event = Event(
            name="Test Event",
            lore_date=100.0,
            description="Event with tags"
        )
        event.tags = ["important", "battle", "main-plot"]
        db_service.insert_event(event)

        # Verify tags are stored in attributes
        loaded_event = db_service.get_event(event.id)
        assert loaded_event.tags == ["important", "battle", "main-plot"]
        assert "_tags" in loaded_event.attributes

    def test_extract_tags_from_entity_attributes(self, db_service):
        """Test extracting tags from entity attributes JSON."""
        # Create entity with tags in attributes
        entity = Entity(
            name="Test Character",
            type="character",
            description="Character with tags"
        )
        entity.tags = ["protagonist", "warrior", "human"]
        db_service.insert_entity(entity)

        # Verify tags are stored in attributes
        loaded_entity = db_service.get_entity(entity.id)
        assert loaded_entity.tags == ["protagonist", "warrior", "human"]
        assert "_tags" in loaded_entity.attributes

    def test_migration_creates_tags_table(self, db_service):
        """Test that migration creates the tags table."""
        # Check if tags table exists after migration
        cursor = db_service._connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='tags'"
        )
        result = cursor.fetchone()
        # Initially, table should not exist
        assert result is None

        # After migration, we'll test this passes
        # This test will be updated once migration is implemented

    def test_migration_creates_event_tags_table(self, db_service):
        """Test that migration creates the event_tags join table."""
        cursor = db_service._connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='event_tags'"
        )
        result = cursor.fetchone()
        # Initially, table should not exist
        assert result is None

    def test_migration_creates_entity_tags_table(self, db_service):
        """Test that migration creates the entity_tags join table."""
        cursor = db_service._connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='entity_tags'"
        )
        result = cursor.fetchone()
        # Initially, table should not exist
        assert result is None

    def test_migration_extracts_and_deduplicates_tags(self, db_service):
        """Test that migration extracts tags and deduplicates them."""
        # Create multiple events and entities with overlapping tags
        event1 = Event(name="Event 1", lore_date=100.0)
        event1.tags = ["important", "battle"]
        db_service.insert_event(event1)

        event2 = Event(name="Event 2", lore_date=200.0)
        event2.tags = ["battle", "victory"]
        db_service.insert_event(event2)

        entity1 = Entity(name="Hero", type="character")
        entity1.tags = ["important", "protagonist"]
        db_service.insert_entity(entity1)

        # After migration, we should have unique tags: important, battle, victory, protagonist
        # This will be tested once migration is implemented

    def test_migration_preserves_tag_associations(self, db_service):
        """Test that migration preserves which tags belong to which events/entities."""
        # Create events and entities with tags
        event = Event(name="Test Event", lore_date=100.0)
        event.tags = ["tag1", "tag2"]
        db_service.insert_event(event)

        entity = Entity(name="Test Entity", type="character")
        entity.tags = ["tag2", "tag3"]
        db_service.insert_entity(entity)

        # After migration:
        # - event should have tag1 and tag2
        # - entity should have tag2 and tag3
        # This will be tested once migration is implemented

    def test_migration_idempotent(self, db_service):
        """Test that migration can be run multiple times safely."""
        # Create data with tags
        event = Event(name="Test Event", lore_date=100.0)
        event.tags = ["test-tag"]
        db_service.insert_event(event)

        # Run migration twice - should not cause errors or duplicate data
        # This will be tested once migration is implemented

    def test_migration_handles_empty_tags(self, db_service):
        """Test that migration handles events/entities with no tags."""
        event = Event(name="Event No Tags", lore_date=100.0)
        db_service.insert_event(event)

        entity = Entity(name="Entity No Tags", type="location")
        db_service.insert_entity(entity)

        # Migration should complete without errors
        # Events/entities with no tags should not create any associations

    def test_migration_handles_duplicate_tags_in_item(self, db_service):
        """Test that migration handles duplicate tags within a single item."""
        event = Event(name="Test Event", lore_date=100.0)
        # Accidentally set duplicate tags
        event.attributes["_tags"] = ["duplicate", "duplicate", "unique"]
        db_service.insert_event(event)

        # After migration, event should only have 2 unique tags
        # This will be tested once migration is implemented

    def test_rollback_restores_tags_to_attributes(self, db_service):
        """Test that rollback can restore tags to attributes JSON."""
        # Create data with tags
        event = Event(name="Test Event", lore_date=100.0)
        event.tags = ["tag1", "tag2"]
        db_service.insert_event(event)

        # After migration and rollback:
        # - tags should be back in attributes
        # - normalized tables can be dropped
        # This will be tested once rollback is implemented
