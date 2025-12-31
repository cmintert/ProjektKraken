"""
Unit tests for tag_filter module.

Tests the FilterClause framework and TagClause implementation with
comprehensive coverage of include/exclude logic, 'any'/'all' semantics,
case sensitivity, and object type scoping.
"""

import pytest

from src.core.entities import Entity
from src.core.events import Event
from src.services import tag_filter


@pytest.mark.unit
class TestTagFilter:
    """Tests for tag-based filtering functionality."""

    def test_filter_object_ids_empty_database(self, db_service):
        """Test filtering with empty database returns empty list."""
        results = tag_filter.filter_object_ids(db_service)
        assert results == []

    def test_filter_object_ids_no_filters_returns_all(self, db_service):
        """Test that no filters returns all objects."""
        # Create test data
        e1 = Entity(name="Entity1", type="character")
        e2 = Entity(name="Entity2", type="location")
        ev1 = Event(name="Event1", lore_date=100.0)
        ev2 = Event(name="Event2", lore_date=200.0)

        db_service.insert_entity(e1)
        db_service.insert_entity(e2)
        db_service.insert_event(ev1)
        db_service.insert_event(ev2)

        # No filters = all objects
        results = tag_filter.filter_object_ids(db_service)
        assert len(results) == 4
        result_set = set(results)
        assert ("entity", e1.id) in result_set
        assert ("entity", e2.id) in result_set
        assert ("event", ev1.id) in result_set
        assert ("event", ev2.id) in result_set

    def test_filter_object_ids_include_any(self, db_service):
        """Test include with 'any' mode."""
        # Create test data
        e1 = Entity(name="Entity1", type="character")
        e2 = Entity(name="Entity2", type="location")
        ev1 = Event(name="Event1", lore_date=100.0)
        ev2 = Event(name="Event2", lore_date=200.0)

        db_service.insert_entity(e1)
        db_service.insert_entity(e2)
        db_service.insert_event(ev1)
        db_service.insert_event(ev2)

        # Assign tags
        db_service.assign_tag_to_entity(e1.id, "important")
        db_service.assign_tag_to_entity(e1.id, "protagonist")
        db_service.assign_tag_to_event(ev1.id, "important")
        db_service.assign_tag_to_event(ev2.id, "minor")

        # Filter for objects with "important" OR "minor"
        results = tag_filter.filter_object_ids(
            db_service, include=["important", "minor"], include_mode="any"
        )

        result_set = set(results)
        assert len(results) == 3
        assert ("entity", e1.id) in result_set  # has "important"
        assert ("event", ev1.id) in result_set  # has "important"
        assert ("event", ev2.id) in result_set  # has "minor"
        assert ("entity", e2.id) not in result_set  # has no tags

    def test_filter_object_ids_include_all(self, db_service):
        """Test include with 'all' mode."""
        # Create test data
        e1 = Entity(name="Entity1", type="character")
        e2 = Entity(name="Entity2", type="location")
        ev1 = Event(name="Event1", lore_date=100.0)

        db_service.insert_entity(e1)
        db_service.insert_entity(e2)
        db_service.insert_event(ev1)

        # Assign tags
        db_service.assign_tag_to_entity(e1.id, "important")
        db_service.assign_tag_to_entity(e1.id, "protagonist")
        db_service.assign_tag_to_entity(e2.id, "important")
        # e2 only has "important", not "protagonist"

        db_service.assign_tag_to_event(ev1.id, "important")
        db_service.assign_tag_to_event(ev1.id, "protagonist")

        # Filter for objects with BOTH "important" AND "protagonist"
        results = tag_filter.filter_object_ids(
            db_service, include=["important", "protagonist"], include_mode="all"
        )

        result_set = set(results)
        assert len(results) == 2
        assert ("entity", e1.id) in result_set  # has both tags
        assert ("event", ev1.id) in result_set  # has both tags
        assert ("entity", e2.id) not in result_set  # only has "important"

    def test_filter_object_ids_exclude_any(self, db_service):
        """Test exclude with 'any' mode."""
        # Create test data
        e1 = Entity(name="Entity1", type="character")
        e2 = Entity(name="Entity2", type="location")
        ev1 = Event(name="Event1", lore_date=100.0)
        ev2 = Event(name="Event2", lore_date=200.0)

        db_service.insert_entity(e1)
        db_service.insert_entity(e2)
        db_service.insert_event(ev1)
        db_service.insert_event(ev2)

        # Assign tags
        db_service.assign_tag_to_entity(e1.id, "archived")
        db_service.assign_tag_to_event(ev1.id, "draft")

        # Exclude objects with "archived" OR "draft"
        results = tag_filter.filter_object_ids(
            db_service, exclude=["archived", "draft"], exclude_mode="any"
        )

        result_set = set(results)
        assert len(results) == 2
        assert ("entity", e2.id) in result_set  # no exclusion tags
        assert ("event", ev2.id) in result_set  # no exclusion tags
        assert ("entity", e1.id) not in result_set  # has "archived"
        assert ("event", ev1.id) not in result_set  # has "draft"

    def test_filter_object_ids_exclude_all(self, db_service):
        """Test exclude with 'all' mode."""
        # Create test data
        e1 = Entity(name="Entity1", type="character")
        e2 = Entity(name="Entity2", type="location")
        ev1 = Event(name="Event1", lore_date=100.0)

        db_service.insert_entity(e1)
        db_service.insert_entity(e2)
        db_service.insert_event(ev1)

        # Assign tags
        db_service.assign_tag_to_entity(e1.id, "archived")
        db_service.assign_tag_to_entity(e1.id, "deprecated")
        db_service.assign_tag_to_entity(e2.id, "archived")
        # e2 only has "archived", not "deprecated"

        # Exclude only if object has BOTH "archived" AND "deprecated"
        results = tag_filter.filter_object_ids(
            db_service, exclude=["archived", "deprecated"], exclude_mode="all"
        )

        result_set = set(results)
        assert len(results) == 2
        assert ("entity", e2.id) in result_set  # only has "archived"
        assert ("event", ev1.id) in result_set  # has no tags
        assert ("entity", e1.id) not in result_set  # has both exclusion tags

    def test_filter_object_ids_include_and_exclude(self, db_service):
        """Test combining include and exclude filters."""
        # Create test data
        e1 = Entity(name="Entity1", type="character")
        e2 = Entity(name="Entity2", type="location")
        e3 = Entity(name="Entity3", type="item")
        ev1 = Event(name="Event1", lore_date=100.0)

        db_service.insert_entity(e1)
        db_service.insert_entity(e2)
        db_service.insert_entity(e3)
        db_service.insert_event(ev1)

        # Assign tags
        db_service.assign_tag_to_entity(e1.id, "important")
        db_service.assign_tag_to_entity(e1.id, "archived")
        db_service.assign_tag_to_entity(e2.id, "important")
        db_service.assign_tag_to_entity(e3.id, "minor")
        db_service.assign_tag_to_event(ev1.id, "important")

        # Include "important", exclude "archived"
        results = tag_filter.filter_object_ids(
            db_service, include=["important"], exclude=["archived"]
        )

        result_set = set(results)
        assert len(results) == 2
        assert ("entity", e2.id) in result_set  # has "important", not "archived"
        assert ("event", ev1.id) in result_set  # has "important", not "archived"
        assert ("entity", e1.id) not in result_set  # excluded by "archived"
        assert ("entity", e3.id) not in result_set  # doesn't have "important"

    def test_filter_object_ids_case_insensitive(self, db_service):
        """Test case-insensitive matching (default behavior)."""
        # Create test data
        e1 = Entity(name="Entity1", type="character")
        e2 = Entity(name="Entity2", type="location")

        db_service.insert_entity(e1)
        db_service.insert_entity(e2)

        # Assign tags with different cases
        db_service.assign_tag_to_entity(e1.id, "Important")
        db_service.assign_tag_to_entity(e2.id, "IMPORTANT")

        # Filter with lowercase, should match both
        results = tag_filter.filter_object_ids(
            db_service, include=["important"], case_sensitive=False
        )

        result_set = set(results)
        assert len(results) == 2
        assert ("entity", e1.id) in result_set
        assert ("entity", e2.id) in result_set

    def test_filter_object_ids_case_sensitive(self, db_service):
        """Test case-sensitive matching."""
        # Create test data
        e1 = Entity(name="Entity1", type="character")
        e2 = Entity(name="Entity2", type="location")
        e3 = Entity(name="Entity3", type="item")

        db_service.insert_entity(e1)
        db_service.insert_entity(e2)
        db_service.insert_entity(e3)

        # Assign tags with different cases
        db_service.assign_tag_to_entity(e1.id, "Important")
        db_service.assign_tag_to_entity(e2.id, "important")
        db_service.assign_tag_to_entity(e3.id, "IMPORTANT")

        # Filter with exact case, should match only e2
        results = tag_filter.filter_object_ids(
            db_service, include=["important"], case_sensitive=True
        )

        result_set = set(results)
        assert len(results) == 1
        assert ("entity", e2.id) in result_set
        assert ("entity", e1.id) not in result_set
        assert ("entity", e3.id) not in result_set

    def test_filter_object_ids_object_type_entity_only(self, db_service):
        """Test filtering only entities."""
        # Create test data
        e1 = Entity(name="Entity1", type="character")
        ev1 = Event(name="Event1", lore_date=100.0)

        db_service.insert_entity(e1)
        db_service.insert_event(ev1)

        # Assign same tag to both
        db_service.assign_tag_to_entity(e1.id, "important")
        db_service.assign_tag_to_event(ev1.id, "important")

        # Filter for entities only
        results = tag_filter.filter_object_ids(
            db_service, object_type="entity", include=["important"]
        )

        result_set = set(results)
        assert len(results) == 1
        assert ("entity", e1.id) in result_set
        assert ("event", ev1.id) not in result_set

    def test_filter_object_ids_object_type_event_only(self, db_service):
        """Test filtering only events."""
        # Create test data
        e1 = Entity(name="Entity1", type="character")
        ev1 = Event(name="Event1", lore_date=100.0)

        db_service.insert_entity(e1)
        db_service.insert_event(ev1)

        # Assign same tag to both
        db_service.assign_tag_to_entity(e1.id, "important")
        db_service.assign_tag_to_event(ev1.id, "important")

        # Filter for events only
        results = tag_filter.filter_object_ids(
            db_service, object_type="event", include=["important"]
        )

        result_set = set(results)
        assert len(results) == 1
        assert ("event", ev1.id) in result_set
        assert ("entity", e1.id) not in result_set

    def test_filter_object_ids_object_type_both(self, db_service):
        """Test filtering both entities and events (default)."""
        # Create test data
        e1 = Entity(name="Entity1", type="character")
        ev1 = Event(name="Event1", lore_date=100.0)

        db_service.insert_entity(e1)
        db_service.insert_event(ev1)

        # Assign same tag to both
        db_service.assign_tag_to_entity(e1.id, "important")
        db_service.assign_tag_to_event(ev1.id, "important")

        # Filter for both (object_type=None)
        results = tag_filter.filter_object_ids(db_service, include=["important"])

        result_set = set(results)
        assert len(results) == 2
        assert ("entity", e1.id) in result_set
        assert ("event", ev1.id) in result_set

    def test_filter_object_ids_empty_include_list(self, db_service):
        """Test that empty include list returns all objects."""
        # Create test data
        e1 = Entity(name="Entity1", type="character")
        ev1 = Event(name="Event1", lore_date=100.0)

        db_service.insert_entity(e1)
        db_service.insert_event(ev1)

        db_service.assign_tag_to_entity(e1.id, "important")

        # Empty include list = all objects
        results = tag_filter.filter_object_ids(db_service, include=[])

        result_set = set(results)
        assert len(results) == 2
        assert ("entity", e1.id) in result_set
        assert ("event", ev1.id) in result_set

    def test_filter_object_ids_empty_exclude_list(self, db_service):
        """Test that empty exclude list excludes nothing."""
        # Create test data
        e1 = Entity(name="Entity1", type="character")
        ev1 = Event(name="Event1", lore_date=100.0)

        db_service.insert_entity(e1)
        db_service.insert_event(ev1)

        db_service.assign_tag_to_entity(e1.id, "archived")

        # Empty exclude list = no exclusions
        results = tag_filter.filter_object_ids(db_service, exclude=[])

        result_set = set(results)
        assert len(results) == 2
        assert ("entity", e1.id) in result_set
        assert ("event", ev1.id) in result_set

    def test_filter_object_ids_no_matches(self, db_service):
        """Test filtering with no matches returns empty list."""
        # Create test data
        e1 = Entity(name="Entity1", type="character")
        db_service.insert_entity(e1)
        db_service.assign_tag_to_entity(e1.id, "other")

        # Filter for non-existent tag
        results = tag_filter.filter_object_ids(db_service, include=["nonexistent"])

        assert results == []

    def test_filter_object_ids_multiple_tags_on_object(self, db_service):
        """Test that objects with multiple tags are handled correctly."""
        # Create test data
        e1 = Entity(name="Entity1", type="character")
        db_service.insert_entity(e1)

        # Assign multiple tags
        db_service.assign_tag_to_entity(e1.id, "important")
        db_service.assign_tag_to_entity(e1.id, "protagonist")
        db_service.assign_tag_to_entity(e1.id, "hero")

        # Test include any - should match
        results = tag_filter.filter_object_ids(
            db_service, include=["important"], include_mode="any"
        )
        assert len(results) == 1

        # Test include all with subset - should match
        results = tag_filter.filter_object_ids(
            db_service, include=["important", "hero"], include_mode="all"
        )
        assert len(results) == 1

        # Test include all with superset - should not match
        results = tag_filter.filter_object_ids(
            db_service,
            include=["important", "hero", "villain"],
            include_mode="all",
        )
        assert len(results) == 0

    def test_filter_object_ids_invalid_object_type(self, db_service):
        """Test that invalid object_type raises ValueError."""
        with pytest.raises(ValueError, match="Invalid object_type"):
            tag_filter.filter_object_ids(db_service, object_type="invalid")

    def test_filter_object_ids_invalid_include_mode(self, db_service):
        """Test that invalid include_mode raises ValueError."""
        with pytest.raises(ValueError, match="Invalid include_mode"):
            tag_filter.filter_object_ids(
                db_service, include=["tag"], include_mode="invalid"
            )

    def test_filter_object_ids_invalid_exclude_mode(self, db_service):
        """Test that invalid exclude_mode raises ValueError."""
        with pytest.raises(ValueError, match="Invalid exclude_mode"):
            tag_filter.filter_object_ids(
                db_service, exclude=["tag"], exclude_mode="invalid"
            )

    def test_filter_object_ids_with_connection(self, db_service):
        """Test that filter_object_ids works with raw connection."""
        # Create test data
        e1 = Entity(name="Entity1", type="character")
        db_service.insert_entity(e1)
        db_service.assign_tag_to_entity(e1.id, "important")

        # Use raw connection instead of db_service
        results = tag_filter.filter_object_ids(
            db_service._connection, include=["important"]
        )

        assert len(results) == 1
        assert ("entity", e1.id) in results

    def test_filter_clause_abstract(self):
        """Test that FilterClause is abstract and cannot be instantiated directly."""
        # FilterClause is abstract, but we can test that TagClause inherits from it
        clause = tag_filter.TagClause(include=["test"])
        assert isinstance(clause, tag_filter.FilterClause)

    def test_complex_scenario(self, db_service):
        """Test a complex real-world scenario with multiple filters."""
        # Create a complex dataset
        entities = []
        for i in range(5):
            e = Entity(name=f"Entity{i}", type="character")
            db_service.insert_entity(e)
            entities.append(e)

        events = []
        for i in range(5):
            ev = Event(name=f"Event{i}", lore_date=float(i * 100))
            db_service.insert_event(ev)
            events.append(ev)

        # entities[0]: important, protagonist
        # entities[1]: important, archived
        # entities[2]: minor
        # entities[3]: important, protagonist, archived
        # entities[4]: no tags

        db_service.assign_tag_to_entity(entities[0].id, "important")
        db_service.assign_tag_to_entity(entities[0].id, "protagonist")

        db_service.assign_tag_to_entity(entities[1].id, "important")
        db_service.assign_tag_to_entity(entities[1].id, "archived")

        db_service.assign_tag_to_entity(entities[2].id, "minor")

        db_service.assign_tag_to_entity(entities[3].id, "important")
        db_service.assign_tag_to_entity(entities[3].id, "protagonist")
        db_service.assign_tag_to_entity(entities[3].id, "archived")

        # events[0]: important
        # events[1]: important, protagonist
        # events[2]: archived
        # events[3]: no tags
        # events[4]: minor

        db_service.assign_tag_to_event(events[0].id, "important")

        db_service.assign_tag_to_event(events[1].id, "important")
        db_service.assign_tag_to_event(events[1].id, "protagonist")

        db_service.assign_tag_to_event(events[2].id, "archived")

        db_service.assign_tag_to_event(events[4].id, "minor")

        # Test: Include (important OR protagonist) AND exclude archived
        results = tag_filter.filter_object_ids(
            db_service,
            include=["important", "protagonist"],
            include_mode="any",
            exclude=["archived"],
            exclude_mode="any",
        )

        result_set = set(results)
        # Should include:
        # entities[0]: has important/protagonist, not archived ✓
        # events[0]: has important, not archived ✓
        # events[1]: has important/protagonist, not archived ✓
        #
        # Should exclude:
        # entities[1]: has archived ✗
        # entities[3]: has archived ✗
        # events[2]: has archived (but doesn't have important/protagonist anyway) ✗
        assert len(result_set) == 3
        assert ("entity", entities[0].id) in result_set
        assert ("event", events[0].id) in result_set
        assert ("event", events[1].id) in result_set

    def test_tag_names_with_spaces(self, db_service):
        """Test that tag names with spaces are handled correctly."""
        # Create test data
        e1 = Entity(name="Entity1", type="character")
        db_service.insert_entity(e1)

        # Assign tag with spaces
        db_service.assign_tag_to_entity(e1.id, "very important")

        # Filter with matching tag
        results = tag_filter.filter_object_ids(db_service, include=["very important"])

        assert len(results) == 1
        assert ("entity", e1.id) in results

    def test_special_characters_in_tags(self, db_service):
        """Test that special characters in tag names are handled correctly."""
        # Create test data
        e1 = Entity(name="Entity1", type="character")
        db_service.insert_entity(e1)

        # Assign tag with special characters
        db_service.assign_tag_to_entity(e1.id, "test-tag_123")

        # Filter with matching tag
        results = tag_filter.filter_object_ids(db_service, include=["test-tag_123"])

        assert len(results) == 1
        assert ("entity", e1.id) in results
