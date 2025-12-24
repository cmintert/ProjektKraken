"""
Unit tests for timeline lane grouping with normalized tags.

This module tests the backend grouping logic for organizing events
into tag-based groups with DUPLICATE mode as default.
"""

import pytest

from src.core.events import Event


@pytest.mark.unit
class TestTimelineGrouping:
    """Tests for timeline event grouping by tags."""

    def test_get_events_grouped_by_tags_duplicate_mode_assigns_event_to_all_matching_groups(
        self, db_service
    ):
        """
        Test that DUPLICATE mode assigns events to all matching tag groups.

        An event with multiple tags from the group_by_tags list should
        appear in every relevant group.
        """
        # Create events with various tag combinations
        event1 = Event(name="Battle of Hastings", lore_date=1066.0)
        event2 = Event(name="Signing of Magna Carta", lore_date=1215.0)
        event3 = Event(name="War of Roses", lore_date=1455.0)

        db_service.insert_event(event1)
        db_service.insert_event(event2)
        db_service.insert_event(event3)

        # Assign tags
        # event1: battle, important
        db_service.assign_tag_to_event(event1.id, "battle")
        db_service.assign_tag_to_event(event1.id, "important")

        # event2: important, political
        db_service.assign_tag_to_event(event2.id, "important")
        db_service.assign_tag_to_event(event2.id, "political")

        # event3: battle
        db_service.assign_tag_to_event(event3.id, "battle")

        # Group by tags in specific order
        tag_order = ["battle", "important", "political"]
        result = db_service.get_events_grouped_by_tags(
            tag_order=tag_order, mode="DUPLICATE"
        )

        # Verify structure
        assert "groups" in result
        assert "remaining" in result

        groups = result["groups"]
        assert len(groups) == 3

        # Battle group should have event1 and event3
        battle_group = next(g for g in groups if g["tag_name"] == "battle")
        battle_event_ids = [e.id for e in battle_group["events"]]
        assert event1.id in battle_event_ids
        assert event3.id in battle_event_ids
        assert len(battle_event_ids) == 2

        # Important group should have event1 and event2
        important_group = next(g for g in groups if g["tag_name"] == "important")
        important_event_ids = [e.id for e in important_group["events"]]
        assert event1.id in important_event_ids
        assert event2.id in important_event_ids
        assert len(important_event_ids) == 2

        # Political group should have only event2
        political_group = next(g for g in groups if g["tag_name"] == "political")
        political_event_ids = [e.id for e in political_group["events"]]
        assert event2.id in political_event_ids
        assert len(political_event_ids) == 1

        # Remaining should be empty (all events have at least one group tag)
        assert len(result["remaining"]) == 0

    def test_get_group_counts_returns_distinct_event_counts_per_tag(self, db_service):
        """
        Test that get_group_counts returns accurate counts for each tag group.

        Counts should reflect the number of events in each group, including
        duplicates across groups.
        """
        # Create events
        event1 = Event(name="Event 1", lore_date=100.0)
        event2 = Event(name="Event 2", lore_date=200.0)
        event3 = Event(name="Event 3", lore_date=300.0)

        db_service.insert_event(event1)
        db_service.insert_event(event2)
        db_service.insert_event(event3)

        # Assign tags
        db_service.assign_tag_to_event(event1.id, "tag-a")
        db_service.assign_tag_to_event(event1.id, "tag-b")
        db_service.assign_tag_to_event(event2.id, "tag-b")
        db_service.assign_tag_to_event(event3.id, "tag-c")

        # Get counts
        tag_order = ["tag-a", "tag-b", "tag-c"]
        counts = db_service.get_group_counts(tag_order=tag_order)

        # Verify counts
        assert len(counts) == 3

        tag_a_count = next(c for c in counts if c["tag_name"] == "tag-a")
        assert tag_a_count["count"] == 1

        tag_b_count = next(c for c in counts if c["tag_name"] == "tag-b")
        assert tag_b_count["count"] == 2

        tag_c_count = next(c for c in counts if c["tag_name"] == "tag-c")
        assert tag_c_count["count"] == 1

    def test_remaining_contains_only_events_with_no_group_tags(self, db_service):
        """
        Test that the remaining set contains only events with no group tags.

        Events that have tags but none matching the group_by_tags list
        should appear in the remaining set.
        """
        # Create events
        event1 = Event(name="Grouped Event", lore_date=100.0)
        event2 = Event(name="Untagged Event", lore_date=200.0)
        event3 = Event(name="Other Tag Event", lore_date=300.0)

        db_service.insert_event(event1)
        db_service.insert_event(event2)
        db_service.insert_event(event3)

        # Assign tags
        db_service.assign_tag_to_event(event1.id, "grouped-tag")
        # event2 has no tags
        db_service.assign_tag_to_event(event3.id, "other-tag")

        # Group by specific tags
        tag_order = ["grouped-tag"]
        result = db_service.get_events_grouped_by_tags(
            tag_order=tag_order, mode="DUPLICATE"
        )

        # Verify grouped events
        groups = result["groups"]
        assert len(groups) == 1
        grouped_event_ids = [e.id for e in groups[0]["events"]]
        assert event1.id in grouped_event_ids

        # Verify remaining contains event2 and event3
        remaining_ids = [e.id for e in result["remaining"]]
        assert event2.id in remaining_ids
        assert event3.id in remaining_ids
        assert len(remaining_ids) == 2

    def test_get_events_grouped_by_tags_first_match_mode_explicit(self, db_service):
        """
        Test that FIRST_MATCH mode assigns events only to their first matching group.

        In FIRST_MATCH mode, an event with multiple tags should only appear
        in the first group (by tag_order) that matches.
        """
        # Create event with multiple tags
        event1 = Event(name="Multi-tag Event", lore_date=100.0)
        db_service.insert_event(event1)

        db_service.assign_tag_to_event(event1.id, "tag-b")
        db_service.assign_tag_to_event(event1.id, "tag-a")
        db_service.assign_tag_to_event(event1.id, "tag-c")

        # Group with FIRST_MATCH mode
        tag_order = ["tag-a", "tag-b", "tag-c"]
        result = db_service.get_events_grouped_by_tags(
            tag_order=tag_order, mode="FIRST_MATCH"
        )

        groups = result["groups"]

        # Event should only be in tag-a group (first match)
        tag_a_group = next(g for g in groups if g["tag_name"] == "tag-a")
        assert event1.id in [e.id for e in tag_a_group["events"]]

        # Event should NOT be in tag-b or tag-c groups
        tag_b_group = next(g for g in groups if g["tag_name"] == "tag-b")
        assert event1.id not in [e.id for e in tag_b_group["events"]]

        tag_c_group = next(g for g in groups if g["tag_name"] == "tag-c")
        assert event1.id not in [e.id for e in tag_c_group["events"]]

    def test_get_events_grouped_by_tags_respects_tag_order(self, db_service):
        """
        Test that groups are returned in the same order as tag_order parameter.
        """
        # Create events with tags
        event1 = Event(name="Event 1", lore_date=100.0)
        db_service.insert_event(event1)
        db_service.assign_tag_to_event(event1.id, "zebra")
        db_service.assign_tag_to_event(event1.id, "alpha")

        event2 = Event(name="Event 2", lore_date=200.0)
        db_service.insert_event(event2)
        db_service.assign_tag_to_event(event2.id, "beta")

        # Group with specific order
        tag_order = ["zebra", "beta", "alpha"]
        result = db_service.get_events_grouped_by_tags(
            tag_order=tag_order, mode="DUPLICATE"
        )

        groups = result["groups"]
        assert len(groups) == 3

        # Verify order matches tag_order
        assert groups[0]["tag_name"] == "zebra"
        assert groups[1]["tag_name"] == "beta"
        assert groups[2]["tag_name"] == "alpha"

    def test_get_events_grouped_by_tags_filters_by_date_range(self, db_service):
        """
        Test that date_range parameter filters events correctly.

        Only events within the specified date range should be included
        in the groups and counts.
        """
        # Create events at different dates
        event1 = Event(name="Early Event", lore_date=100.0)
        event2 = Event(name="Middle Event", lore_date=500.0)
        event3 = Event(name="Late Event", lore_date=900.0)

        db_service.insert_event(event1)
        db_service.insert_event(event2)
        db_service.insert_event(event3)

        # Assign same tag to all
        db_service.assign_tag_to_event(event1.id, "test-tag")
        db_service.assign_tag_to_event(event2.id, "test-tag")
        db_service.assign_tag_to_event(event3.id, "test-tag")

        # Query with date range (200.0 to 800.0)
        tag_order = ["test-tag"]
        result = db_service.get_events_grouped_by_tags(
            tag_order=tag_order, mode="DUPLICATE", date_range=(200.0, 800.0)
        )

        groups = result["groups"]
        assert len(groups) == 1

        # Only event2 should be in the group
        event_ids = [e.id for e in groups[0]["events"]]
        assert event2.id in event_ids
        assert event1.id not in event_ids
        assert event3.id not in event_ids
        assert len(event_ids) == 1

    def test_get_group_counts_respects_date_range(self, db_service):
        """
        Test that get_group_counts filters by date range correctly.
        """
        # Create events
        event1 = Event(name="Event 1", lore_date=100.0)
        event2 = Event(name="Event 2", lore_date=500.0)
        event3 = Event(name="Event 3", lore_date=900.0)

        db_service.insert_event(event1)
        db_service.insert_event(event2)
        db_service.insert_event(event3)

        # All have the same tag
        db_service.assign_tag_to_event(event1.id, "counted")
        db_service.assign_tag_to_event(event2.id, "counted")
        db_service.assign_tag_to_event(event3.id, "counted")

        # Get counts with date range
        tag_order = ["counted"]
        counts = db_service.get_group_counts(
            tag_order=tag_order, date_range=(200.0, 800.0)
        )

        # Should count only event2
        assert len(counts) == 1
        assert counts[0]["tag_name"] == "counted"
        assert counts[0]["count"] == 1

    def test_get_events_grouped_by_tags_sorts_by_lore_date_within_groups(
        self, db_service
    ):
        """
        Test that events within each group are sorted by lore_date.
        """
        # Create events out of order
        event1 = Event(name="Event C", lore_date=300.0)
        event2 = Event(name="Event A", lore_date=100.0)
        event3 = Event(name="Event B", lore_date=200.0)

        db_service.insert_event(event1)
        db_service.insert_event(event2)
        db_service.insert_event(event3)

        # Assign same tag to all
        db_service.assign_tag_to_event(event1.id, "sorted-tag")
        db_service.assign_tag_to_event(event2.id, "sorted-tag")
        db_service.assign_tag_to_event(event3.id, "sorted-tag")

        # Get grouped events
        tag_order = ["sorted-tag"]
        result = db_service.get_events_grouped_by_tags(
            tag_order=tag_order, mode="DUPLICATE"
        )

        events = result["groups"][0]["events"]
        assert len(events) == 3

        # Verify sorting by lore_date
        assert events[0].lore_date == 100.0
        assert events[1].lore_date == 200.0
        assert events[2].lore_date == 300.0

    def test_remaining_events_excludes_events_with_any_group_tag(self, db_service):
        """
        Test that remaining events exclude any event with at least one group tag.

        Even if an event has multiple tags and only one matches a group,
        it should not appear in remaining.
        """
        # Create events
        event1 = Event(name="Event 1", lore_date=100.0)
        event2 = Event(name="Event 2", lore_date=200.0)

        db_service.insert_event(event1)
        db_service.insert_event(event2)

        # event1 has both grouped and non-grouped tags
        db_service.assign_tag_to_event(event1.id, "grouped")
        db_service.assign_tag_to_event(event1.id, "other")

        # event2 has only non-grouped tag
        db_service.assign_tag_to_event(event2.id, "other")

        # Group by one tag
        tag_order = ["grouped"]
        result = db_service.get_events_grouped_by_tags(
            tag_order=tag_order, mode="DUPLICATE"
        )

        # event1 should be in grouped
        grouped_ids = [e.id for e in result["groups"][0]["events"]]
        assert event1.id in grouped_ids

        # Only event2 should be in remaining
        remaining_ids = [e.id for e in result["remaining"]]
        assert event2.id in remaining_ids
        assert event1.id not in remaining_ids

    def test_empty_tag_order_returns_empty_groups(self, db_service):
        """
        Test that providing an empty tag_order returns empty groups.

        All events should be in the remaining set.
        """
        # Create events with tags
        event1 = Event(name="Event 1", lore_date=100.0)
        db_service.insert_event(event1)
        db_service.assign_tag_to_event(event1.id, "any-tag")

        # Query with empty tag_order
        result = db_service.get_events_grouped_by_tags(tag_order=[], mode="DUPLICATE")

        # No groups
        assert len(result["groups"]) == 0

        # All events in remaining
        remaining_ids = [e.id for e in result["remaining"]]
        assert event1.id in remaining_ids

    def test_get_group_counts_includes_metadata(self, db_service):
        """
        Test that get_group_counts includes metadata like earliest and latest dates.
        """
        # Create events
        event1 = Event(name="Event 1", lore_date=100.0)
        event2 = Event(name="Event 2", lore_date=500.0)
        event3 = Event(name="Event 3", lore_date=900.0)

        db_service.insert_event(event1)
        db_service.insert_event(event2)
        db_service.insert_event(event3)

        # Assign tags
        db_service.assign_tag_to_event(event1.id, "span-tag")
        db_service.assign_tag_to_event(event2.id, "span-tag")
        db_service.assign_tag_to_event(event3.id, "span-tag")

        # Get counts
        tag_order = ["span-tag"]
        counts = db_service.get_group_counts(tag_order=tag_order)

        assert len(counts) == 1
        count_info = counts[0]

        # Verify metadata
        assert count_info["tag_name"] == "span-tag"
        assert count_info["count"] == 3
        assert "earliest_date" in count_info
        assert "latest_date" in count_info
        assert count_info["earliest_date"] == 100.0
        assert count_info["latest_date"] == 900.0

    def test_get_events_grouped_by_tags_handles_nonexistent_tags(self, db_service):
        """
        Test that nonexistent tags in tag_order return empty groups.
        """
        # Create event with one tag
        event1 = Event(name="Event 1", lore_date=100.0)
        db_service.insert_event(event1)
        db_service.assign_tag_to_event(event1.id, "existing-tag")

        # Query with mix of existing and nonexistent tags
        tag_order = ["nonexistent", "existing-tag", "also-nonexistent"]
        result = db_service.get_events_grouped_by_tags(
            tag_order=tag_order, mode="DUPLICATE"
        )

        groups = result["groups"]
        assert len(groups) == 3

        # Nonexistent groups should be empty
        nonexistent_group = next(g for g in groups if g["tag_name"] == "nonexistent")
        assert len(nonexistent_group["events"]) == 0

        # Existing group should have the event
        existing_group = next(g for g in groups if g["tag_name"] == "existing-tag")
        assert len(existing_group["events"]) == 1
        assert existing_group["events"][0].id == event1.id

    def test_get_events_grouped_by_tags_default_mode_is_duplicate(self, db_service):
        """
        Test that the default mode is DUPLICATE when not specified.
        """
        # Create event with multiple tags
        event1 = Event(name="Event 1", lore_date=100.0)
        db_service.insert_event(event1)
        db_service.assign_tag_to_event(event1.id, "tag-a")
        db_service.assign_tag_to_event(event1.id, "tag-b")

        # Call without specifying mode
        tag_order = ["tag-a", "tag-b"]
        result = db_service.get_events_grouped_by_tags(tag_order=tag_order)

        # Event should appear in both groups (DUPLICATE behavior)
        tag_a_group = next(g for g in result["groups"] if g["tag_name"] == "tag-a")
        tag_b_group = next(g for g in result["groups"] if g["tag_name"] == "tag-b")

        assert event1.id in [e.id for e in tag_a_group["events"]]
        assert event1.id in [e.id for e in tag_b_group["events"]]

    def test_remaining_events_sorted_by_lore_date(self, db_service):
        """
        Test that remaining events are sorted by lore_date.
        """
        # Create events without group tags
        event1 = Event(name="Event C", lore_date=300.0)
        event2 = Event(name="Event A", lore_date=100.0)
        event3 = Event(name="Event B", lore_date=200.0)

        db_service.insert_event(event1)
        db_service.insert_event(event2)
        db_service.insert_event(event3)

        # No tags assigned, all should be in remaining
        tag_order = ["some-tag"]
        result = db_service.get_events_grouped_by_tags(
            tag_order=tag_order, mode="DUPLICATE"
        )

        remaining = result["remaining"]
        assert len(remaining) == 3

        # Verify sorting
        assert remaining[0].lore_date == 100.0
        assert remaining[1].lore_date == 200.0
        assert remaining[2].lore_date == 300.0
