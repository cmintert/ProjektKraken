"""
Unit tests for Timeline Grouping Service - Milestone 2.

This module tests the service layer methods for timeline grouping,
including metadata retrieval, group configuration, and tag colors.
"""

import pytest

from src.core.events import Event


@pytest.mark.unit
class TestTimelineGroupingService:
    """Tests for timeline grouping service layer methods."""

    def test_get_group_metadata_returns_tag_info_with_colors(self, db_service):
        """
        Test that get_group_metadata returns tag name, color, count, and date span.
        """
        # Create events with tags
        event1 = Event(name="Event 1", lore_date=100.0)
        event2 = Event(name="Event 2", lore_date=200.0)
        event3 = Event(name="Event 3", lore_date=300.0)

        db_service.insert_event(event1)
        db_service.insert_event(event2)
        db_service.insert_event(event3)

        # Assign tags
        db_service.assign_tag_to_event(event1.id, "battle")
        db_service.assign_tag_to_event(event1.id, "important")
        db_service.assign_tag_to_event(event2.id, "important")
        db_service.assign_tag_to_event(event3.id, "political")

        # Set color for "important" tag
        db_service.set_tag_color("important", "#FF0000")

        # Get group metadata
        tag_order = ["battle", "important", "political"]
        metadata = db_service.get_group_metadata(
            tag_order=tag_order, date_range=(50.0, 350.0)
        )

        assert len(metadata) == 3

        # Check battle group
        battle_meta = next(m for m in metadata if m["tag_name"] == "battle")
        assert battle_meta["count"] == 1
        assert battle_meta["earliest_date"] == 100.0
        assert battle_meta["latest_date"] == 100.0
        assert "color" in battle_meta  # Generated color

        # Check important group with explicit color
        important_meta = next(m for m in metadata if m["tag_name"] == "important")
        assert important_meta["count"] == 2
        assert important_meta["color"] == "#FF0000"
        assert important_meta["earliest_date"] == 100.0
        assert important_meta["latest_date"] == 200.0

    def test_get_events_for_group_returns_only_matching_events(self, db_service):
        """
        Test that get_events_for_group returns only events with the specified tag.
        """
        # Create events
        event1 = Event(name="Battle Event", lore_date=100.0)
        event2 = Event(name="Political Event", lore_date=200.0)
        event3 = Event(name="Mixed Event", lore_date=150.0)

        db_service.insert_event(event1)
        db_service.insert_event(event2)
        db_service.insert_event(event3)

        # Assign tags
        db_service.assign_tag_to_event(event1.id, "battle")
        db_service.assign_tag_to_event(event2.id, "political")
        db_service.assign_tag_to_event(event3.id, "battle")
        db_service.assign_tag_to_event(event3.id, "political")

        # Get events for "battle" group
        battle_events = db_service.get_events_for_group(
            tag_name="battle", date_range=None
        )

        assert len(battle_events) == 2
        event_ids = [e.id for e in battle_events]
        assert event1.id in event_ids
        assert event3.id in event_ids
        assert event2.id not in event_ids

        # Events should be sorted by lore_date
        assert battle_events[0].lore_date == 100.0
        assert battle_events[1].lore_date == 150.0

    def test_get_events_for_group_respects_date_range(self, db_service):
        """
        Test that get_events_for_group filters by date range.
        """
        # Create events
        event1 = Event(name="Early", lore_date=100.0)
        event2 = Event(name="Middle", lore_date=500.0)
        event3 = Event(name="Late", lore_date=900.0)

        db_service.insert_event(event1)
        db_service.insert_event(event2)
        db_service.insert_event(event3)

        # All have same tag
        db_service.assign_tag_to_event(event1.id, "test")
        db_service.assign_tag_to_event(event2.id, "test")
        db_service.assign_tag_to_event(event3.id, "test")

        # Get events in range
        events = db_service.get_events_for_group(
            tag_name="test", date_range=(200.0, 800.0)
        )

        assert len(events) == 1
        assert events[0].id == event2.id

    def test_set_tag_color_stores_and_retrieves_color(self, db_service):
        """
        Test that set_tag_color stores a color for a tag.
        """
        # Create tag
        db_service.create_tag("colored-tag")

        # Set color
        db_service.set_tag_color("colored-tag", "#00FF00")

        # Retrieve tag
        tag = db_service.get_tag_by_name("colored-tag")
        assert tag is not None
        assert tag["color"] == "#00FF00"

    def test_get_tag_color_generates_deterministic_color_when_not_set(self, db_service):
        """
        Test that get_tag_color generates a deterministic color when none is set.
        """
        # Create tag without color
        db_service.create_tag("auto-color-tag")

        # Get color (should be generated)
        color1 = db_service.get_tag_color("auto-color-tag")
        assert color1.startswith("#")
        assert len(color1) == 7  # #RRGGBB format

        # Should be deterministic (same color each time)
        color2 = db_service.get_tag_color("auto-color-tag")
        assert color1 == color2

    def test_get_tag_color_returns_stored_color_when_set(self, db_service):
        """
        Test that get_tag_color returns the stored color when available.
        """
        # Create tag with color
        db_service.create_tag("red-tag")
        db_service.set_tag_color("red-tag", "#FF0000")

        # Get color
        color = db_service.get_tag_color("red-tag")
        assert color == "#FF0000"

    def test_update_tag_color_changes_existing_color(self, db_service):
        """
        Test that updating a tag color changes it correctly.
        """
        # Create tag with initial color
        db_service.create_tag("changing-tag")
        db_service.set_tag_color("changing-tag", "#FF0000")

        # Update color
        db_service.set_tag_color("changing-tag", "#00FF00")

        # Verify change
        color = db_service.get_tag_color("changing-tag")
        assert color == "#00FF00"

    def test_get_group_metadata_with_no_events_returns_zero_counts(self, db_service):
        """
        Test that get_group_metadata returns zero counts for tags with no events.
        """
        # Create tags but no events
        db_service.create_tag("empty-tag-1")
        db_service.create_tag("empty-tag-2")

        # Get metadata
        metadata = db_service.get_group_metadata(
            tag_order=["empty-tag-1", "empty-tag-2"]
        )

        assert len(metadata) == 2
        for meta in metadata:
            assert meta["count"] == 0
            assert meta["earliest_date"] is None
            assert meta["latest_date"] is None
            assert "color" in meta

    def test_get_events_for_group_with_nonexistent_tag_returns_empty(self, db_service):
        """
        Test that get_events_for_group returns empty list for nonexistent tag.
        """
        events = db_service.get_events_for_group(tag_name="nonexistent")
        assert events == []

    def test_get_group_metadata_includes_all_tags_in_order(self, db_service):
        """
        Test that get_group_metadata returns metadata for all tags in the specified order.
        """
        # Create events with tags
        event1 = Event(name="Event 1", lore_date=100.0)
        db_service.insert_event(event1)
        db_service.assign_tag_to_event(event1.id, "zebra")
        db_service.assign_tag_to_event(event1.id, "alpha")

        # Get metadata in specific order
        tag_order = ["zebra", "beta", "alpha"]
        metadata = db_service.get_group_metadata(tag_order=tag_order)

        assert len(metadata) == 3
        assert metadata[0]["tag_name"] == "zebra"
        assert metadata[1]["tag_name"] == "beta"
        assert metadata[2]["tag_name"] == "alpha"

    def test_color_generation_is_consistent_across_calls(self, db_service):
        """
        Test that auto-generated colors are consistent for the same tag name.
        """
        # Create two tags with same name pattern
        db_service.create_tag("test-tag")

        # Get color multiple times
        colors = [db_service.get_tag_color("test-tag") for _ in range(5)]

        # All should be the same
        assert len(set(colors)) == 1
        assert colors[0].startswith("#")

    def test_set_tag_color_validates_hex_format(self, db_service):
        """
        Test that set_tag_color validates hex color format.
        """
        db_service.create_tag("test-tag")

        # Valid formats should work
        db_service.set_tag_color("test-tag", "#FF0000")
        db_service.set_tag_color("test-tag", "#abc")  # Short form

        # Invalid formats should raise ValueError
        with pytest.raises(ValueError):
            db_service.set_tag_color("test-tag", "red")

        with pytest.raises(ValueError):
            db_service.set_tag_color("test-tag", "#GGGGGG")
