"""
Integration tests for tag normalization and migration.
"""

import pytest

from migrate_tags import TagMigration
from src.commands.entity_commands import CreateEntityCommand, UpdateEntityCommand
from src.commands.event_commands import CreateEventCommand, UpdateEventCommand
from src.core.entities import Entity
from src.core.events import Event


@pytest.mark.integration
class TestTagNormalizationIntegration:
    """Integration tests for tag normalization across the system."""

    def test_create_event_with_tags_syncs_to_normalized_tables(self, db_service):
        """Test that creating an event with tags syncs to normalized tables."""
        event_data = {
            "name": "Test Event",
            "lore_date": 100.0,
            "attributes": {"_tags": ["important", "battle"]},
        }
        
        cmd = CreateEventCommand(event_data)
        result = cmd.execute(db_service)
        
        assert result.success
        
        # Check normalized tables
        tags = db_service.get_tags_for_event(cmd.event.id)
        tag_names = sorted([t["name"] for t in tags])
        assert tag_names == ["battle", "important"]
        
        # Check JSON attributes still have tags
        loaded_event = db_service.get_event(cmd.event.id)
        assert sorted(loaded_event.tags) == ["battle", "important"]

    def test_update_event_tags_syncs_to_normalized_tables(self, db_service):
        """Test that updating event tags syncs changes to normalized tables."""
        # Create event with initial tags
        event = Event(name="Test Event", lore_date=100.0)
        event.tags = ["tag1", "tag2"]
        db_service.insert_event(event)
        
        # Sync initial tags
        for tag in event.tags:
            db_service.assign_tag_to_event(event.id, tag)
        
        # Update tags via command
        update_data = {
            "attributes": {"_tags": ["tag2", "tag3"]},
        }
        cmd = UpdateEventCommand(event.id, update_data)
        result = cmd.execute(db_service)
        
        assert result.success
        
        # Check normalized tables
        tags = db_service.get_tags_for_event(event.id)
        tag_names = sorted([t["name"] for t in tags])
        assert tag_names == ["tag2", "tag3"]
        
        # Verify tag1 was removed and tag3 was added
        all_event_tags = db_service.get_tags_for_event(event.id)
        assert "tag1" not in [t["name"] for t in all_event_tags]
        assert "tag3" in [t["name"] for t in all_event_tags]

    def test_create_entity_with_tags_syncs_to_normalized_tables(self, db_service):
        """Test that creating an entity with tags syncs to normalized tables."""
        entity_data = {
            "name": "Test Character",
            "type": "character",
            "attributes": {"_tags": ["protagonist", "warrior"]},
        }
        
        cmd = CreateEntityCommand(entity_data)
        result = cmd.execute(db_service)
        
        assert result.success
        
        # Check normalized tables
        tags = db_service.get_tags_for_entity(cmd._entity.id)
        tag_names = sorted([t["name"] for t in tags])
        assert tag_names == ["protagonist", "warrior"]
        
        # Check JSON attributes still have tags
        loaded_entity = db_service.get_entity(cmd._entity.id)
        assert sorted(loaded_entity.tags) == ["protagonist", "warrior"]

    def test_update_entity_tags_syncs_to_normalized_tables(self, db_service):
        """Test that updating entity tags syncs changes to normalized tables."""
        # Create entity with initial tags
        entity = Entity(name="Test Character", type="character")
        entity.tags = ["tag1", "tag2"]
        db_service.insert_entity(entity)
        
        # Sync initial tags
        for tag in entity.tags:
            db_service.assign_tag_to_entity(entity.id, tag)
        
        # Update tags via command
        update_data = {
            "attributes": {"_tags": ["tag2", "tag3"]},
        }
        cmd = UpdateEntityCommand(entity.id, update_data)
        result = cmd.execute(db_service)
        
        assert result.success
        
        # Check normalized tables
        tags = db_service.get_tags_for_entity(entity.id)
        tag_names = sorted([t["name"] for t in tags])
        assert tag_names == ["tag2", "tag3"]

    def test_migration_preserves_existing_tags(self, db_service):
        """Test that migration preserves tags from JSON attributes."""
        # Create events and entities with tags (old format)
        event = Event(name="Event", lore_date=100.0)
        event.tags = ["event-tag1", "event-tag2"]
        db_service.insert_event(event)
        
        entity = Entity(name="Entity", type="character")
        entity.tags = ["entity-tag1", "entity-tag2"]
        db_service.insert_entity(entity)
        
        # Run migration
        migration = TagMigration(db_service)
        success = migration.run(dry_run=False)
        
        assert success
        
        # Verify tags were migrated
        event_tags = db_service.get_tags_for_event(event.id)
        event_tag_names = sorted([t["name"] for t in event_tags])
        assert event_tag_names == ["event-tag1", "event-tag2"]
        
        entity_tags = db_service.get_tags_for_entity(entity.id)
        entity_tag_names = sorted([t["name"] for t in entity_tags])
        assert entity_tag_names == ["entity-tag1", "entity-tag2"]
        
        # Verify JSON attributes still have tags (backward compatibility)
        loaded_event = db_service.get_event(event.id)
        assert sorted(loaded_event.tags) == ["event-tag1", "event-tag2"]
        
        loaded_entity = db_service.get_entity(entity.id)
        assert sorted(loaded_entity.tags) == ["entity-tag1", "entity-tag2"]

    def test_migration_idempotent(self, db_service):
        """Test that migration can be run multiple times safely."""
        # Create test data
        event = Event(name="Event", lore_date=100.0)
        event.tags = ["test-tag"]
        db_service.insert_event(event)
        
        # Run migration twice
        migration1 = TagMigration(db_service)
        success1 = migration1.run(dry_run=False)
        assert success1
        
        migration2 = TagMigration(db_service)
        success2 = migration2.run(dry_run=False)
        assert success2
        
        # Verify no duplicate tags or associations
        all_tags = db_service.get_all_tags()
        tag_names = [t["name"] for t in all_tags]
        assert tag_names.count("test-tag") == 1
        
        event_tags = db_service.get_tags_for_event(event.id)
        assert len(event_tags) == 1
        assert event_tags[0]["name"] == "test-tag"

    def test_get_events_by_tag_after_migration(self, db_service):
        """Test querying events by tag after migration."""
        # Create events with tags
        event1 = Event(name="Event 1", lore_date=100.0)
        event1.tags = ["important"]
        db_service.insert_event(event1)
        
        event2 = Event(name="Event 2", lore_date=200.0)
        event2.tags = ["important", "battle"]
        db_service.insert_event(event2)
        
        event3 = Event(name="Event 3", lore_date=300.0)
        event3.tags = ["other"]
        db_service.insert_event(event3)
        
        # Run migration
        migration = TagMigration(db_service)
        migration.run(dry_run=False)
        
        # Query events by tag
        important_events = db_service.get_events_by_tag("important")
        assert len(important_events) == 2
        event_names = sorted([e.name for e in important_events])
        assert event_names == ["Event 1", "Event 2"]

    def test_get_entities_by_tag_after_migration(self, db_service):
        """Test querying entities by tag after migration."""
        # Create entities with tags
        entity1 = Entity(name="Entity 1", type="character")
        entity1.tags = ["protagonist"]
        db_service.insert_entity(entity1)
        
        entity2 = Entity(name="Entity 2", type="character")
        entity2.tags = ["protagonist", "warrior"]
        db_service.insert_entity(entity2)
        
        entity3 = Entity(name="Entity 3", type="location")
        entity3.tags = ["city"]
        db_service.insert_entity(entity3)
        
        # Run migration
        migration = TagMigration(db_service)
        migration.run(dry_run=False)
        
        # Query entities by tag
        protagonist_entities = db_service.get_entities_by_tag("protagonist")
        assert len(protagonist_entities) == 2
        entity_names = sorted([e.name for e in protagonist_entities])
        assert entity_names == ["Entity 1", "Entity 2"]

    def test_delete_event_removes_tag_associations_after_migration(self, db_service):
        """Test that deleting an event removes tag associations."""
        # Create event with tags
        event = Event(name="Event", lore_date=100.0)
        event.tags = ["tag1", "tag2"]
        db_service.insert_event(event)
        
        # Run migration
        migration = TagMigration(db_service)
        migration.run(dry_run=False)
        
        # Verify tags exist
        tags_before = db_service.get_tags_for_event(event.id)
        assert len(tags_before) == 2
        
        # Delete event
        db_service.delete_event(event.id)
        
        # Verify tag associations are gone (CASCADE delete)
        tags_after = db_service.get_tags_for_event(event.id)
        assert len(tags_after) == 0
        
        # Verify tags themselves still exist (only association deleted)
        all_tags = db_service.get_all_tags()
        tag_names = [t["name"] for t in all_tags]
        assert "tag1" in tag_names

    def test_timeline_grouping_after_migration(self, db_service):
        """Test that timeline grouping works correctly after tag migration."""
        # Create events with tags in JSON attributes
        event1 = Event(name="Battle Event", lore_date=100.0)
        event1.tags = ["battle", "important"]
        db_service.insert_event(event1)

        event2 = Event(name="Political Event", lore_date=200.0)
        event2.tags = ["political", "important"]
        db_service.insert_event(event2)

        event3 = Event(name="Minor Event", lore_date=300.0)
        event3.tags = ["other"]
        db_service.insert_event(event3)

        # Run migration
        migration = TagMigration(db_service)
        success = migration.run(dry_run=False)
        assert success

        # Test DUPLICATE mode grouping
        tag_order = ["battle", "political", "important"]
        result = db_service.get_events_grouped_by_tags(
            tag_order=tag_order, mode="DUPLICATE"
        )

        groups = result["groups"]
        assert len(groups) == 3

        # Battle group should have event1
        battle_group = next(g for g in groups if g["tag_name"] == "battle")
        battle_event_ids = [e.id for e in battle_group["events"]]
        assert event1.id in battle_event_ids

        # Political group should have event2
        political_group = next(g for g in groups if g["tag_name"] == "political")
        political_event_ids = [e.id for e in political_group["events"]]
        assert event2.id in political_event_ids

        # Important group should have event1 and event2 (DUPLICATE mode)
        important_group = next(g for g in groups if g["tag_name"] == "important")
        important_event_ids = [e.id for e in important_group["events"]]
        assert event1.id in important_event_ids
        assert event2.id in important_event_ids
        assert len(important_event_ids) == 2

        # Remaining should have event3
        remaining_ids = [e.id for e in result["remaining"]]
        assert event3.id in remaining_ids

        # Test group counts
        counts = db_service.get_group_counts(tag_order=tag_order)
        battle_count = next(c for c in counts if c["tag_name"] == "battle")
        assert battle_count["count"] == 1

        important_count = next(c for c in counts if c["tag_name"] == "important")
        assert important_count["count"] == 2
