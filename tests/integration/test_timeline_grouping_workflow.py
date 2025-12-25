"""
Integration tests for Timeline Grouping - Milestone 2.

Tests the complete workflow of timeline grouping including service methods,
commands, and data propagation.
"""

import pytest

from src.commands.timeline_grouping_commands import (
    SetTimelineGroupingCommand,
    UpdateTagColorCommand,
)
from src.core.events import Event


@pytest.mark.integration
class TestTimelineGroupingIntegration:
    """Integration tests for timeline grouping workflow."""

    def test_complete_grouping_workflow(self, db_service):
        """
        Test complete workflow: create events, set grouping, get groups, update tags.
        """
        # Step 1: Create events with tags
        event1 = Event(name="Battle of Hastings", lore_date=1066.0)
        event2 = Event(name="Signing of Magna Carta", lore_date=1215.0)
        event3 = Event(name="War of Roses", lore_date=1455.0)

        db_service.insert_event(event1)
        db_service.insert_event(event2)
        db_service.insert_event(event3)

        db_service.assign_tag_to_event(event1.id, "battle")
        db_service.assign_tag_to_event(event1.id, "important")
        db_service.assign_tag_to_event(event2.id, "important")
        db_service.assign_tag_to_event(event2.id, "political")
        db_service.assign_tag_to_event(event3.id, "battle")

        # Step 2: Set timeline grouping configuration
        tag_order = ["battle", "important", "political"]
        cmd = SetTimelineGroupingCommand(tag_order=tag_order)
        result = cmd.execute(db_service)
        assert result.success

        # Step 3: Get group metadata
        metadata = db_service.get_group_metadata(tag_order=tag_order)
        assert len(metadata) == 3

        battle_meta = next(m for m in metadata if m["tag_name"] == "battle")
        assert battle_meta["count"] == 2

        # Step 4: Get events for a specific group
        battle_events = db_service.get_events_for_group(tag_name="battle")
        assert len(battle_events) == 2
        assert battle_events[0].name == "Battle of Hastings"

        # Step 5: Update tag color
        color_cmd = UpdateTagColorCommand(tag_name="battle", color="#FF0000")
        color_cmd.execute(db_service)

        # Step 6: Verify color in metadata
        metadata = db_service.get_group_metadata(tag_order=tag_order)
        battle_meta = next(m for m in metadata if m["tag_name"] == "battle")
        assert battle_meta["color"] == "#FF0000"

    def test_tag_edit_propagates_to_all_groups(self, db_service):
        """
        Test that editing a tag (adding/removing from event) updates all groups.
        """
        # Create event with one tag
        event1 = Event(name="Event 1", lore_date=100.0)
        db_service.insert_event(event1)
        db_service.assign_tag_to_event(event1.id, "tag-a")

        # Get initial groups
        result = db_service.get_events_grouped_by_tags(
            tag_order=["tag-a", "tag-b"], mode="DUPLICATE"
        )

        assert len(result["groups"][0]["events"]) == 1  # tag-a has event1
        assert len(result["groups"][1]["events"]) == 0  # tag-b has no events

        # Add second tag to event
        db_service.assign_tag_to_event(event1.id, "tag-b")

        # Get updated groups
        result = db_service.get_events_grouped_by_tags(
            tag_order=["tag-a", "tag-b"], mode="DUPLICATE"
        )

        # Event should now appear in both groups (DUPLICATE mode)
        assert len(result["groups"][0]["events"]) == 1  # tag-a still has event1
        assert len(result["groups"][1]["events"]) == 1  # tag-b now has event1
        assert result["groups"][0]["events"][0].id == event1.id
        assert result["groups"][1]["events"][0].id == event1.id

    def test_removing_tag_updates_groups(self, db_service):
        """
        Test that removing a tag from an event updates groups correctly.
        """
        # Create event with multiple tags
        event1 = Event(name="Event 1", lore_date=100.0)
        db_service.insert_event(event1)
        db_service.assign_tag_to_event(event1.id, "tag-a")
        db_service.assign_tag_to_event(event1.id, "tag-b")

        # Initial state: event in both groups
        result = db_service.get_events_grouped_by_tags(
            tag_order=["tag-a", "tag-b"], mode="DUPLICATE"
        )
        assert len(result["groups"][0]["events"]) == 1
        assert len(result["groups"][1]["events"]) == 1

        # Remove tag-b
        db_service.remove_tag_from_event(event1.id, "tag-b")

        # Updated state: event only in tag-a group
        result = db_service.get_events_grouped_by_tags(
            tag_order=["tag-a", "tag-b"], mode="DUPLICATE"
        )
        assert len(result["groups"][0]["events"]) == 1
        assert len(result["groups"][1]["events"]) == 0

    def test_deleting_event_removes_from_all_groups(self, db_service):
        """
        Test that deleting an event removes it from all groups.
        """
        # Create event with multiple tags
        event1 = Event(name="Event 1", lore_date=100.0)
        event2 = Event(name="Event 2", lore_date=200.0)
        db_service.insert_event(event1)
        db_service.insert_event(event2)

        db_service.assign_tag_to_event(event1.id, "tag-a")
        db_service.assign_tag_to_event(event1.id, "tag-b")
        db_service.assign_tag_to_event(event2.id, "tag-a")

        # Initial state
        result = db_service.get_events_grouped_by_tags(
            tag_order=["tag-a", "tag-b"], mode="DUPLICATE"
        )
        assert len(result["groups"][0]["events"]) == 2
        assert len(result["groups"][1]["events"]) == 1

        # Delete event1
        db_service.delete_event(event1.id)

        # Updated state: event1 removed from all groups
        result = db_service.get_events_grouped_by_tags(
            tag_order=["tag-a", "tag-b"], mode="DUPLICATE"
        )
        assert len(result["groups"][0]["events"]) == 1  # Only event2
        assert len(result["groups"][1]["events"]) == 0  # No events

    def test_undo_redo_grouping_configuration(self, db_service):
        """
        Test undo/redo cycle for grouping configuration changes.
        """
        # Set initial configuration
        initial_order = ["tag1", "tag2"]
        cmd1 = SetTimelineGroupingCommand(tag_order=initial_order)
        cmd1.execute(db_service)

        config = db_service.get_timeline_grouping_config()
        assert config["tag_order"] == initial_order

        # Change configuration
        new_order = ["tag3", "tag4", "tag5"]
        cmd2 = SetTimelineGroupingCommand(tag_order=new_order)
        cmd2.execute(db_service)

        config = db_service.get_timeline_grouping_config()
        assert config["tag_order"] == new_order

        # Undo second command
        cmd2.undo(db_service)
        config = db_service.get_timeline_grouping_config()
        assert config["tag_order"] == initial_order

        # Redo second command
        cmd2.execute(db_service)
        config = db_service.get_timeline_grouping_config()
        assert config["tag_order"] == new_order

    def test_undo_redo_tag_color_updates(self, db_service):
        """
        Test undo/redo cycle for tag color updates.
        """
        # Create tag
        db_service.create_tag("test-tag")

        # Set initial color
        cmd1 = UpdateTagColorCommand(tag_name="test-tag", color="#FF0000")
        cmd1.execute(db_service)
        assert db_service.get_tag_color("test-tag") == "#FF0000"

        # Change color
        cmd2 = UpdateTagColorCommand(tag_name="test-tag", color="#00FF00")
        cmd2.execute(db_service)
        assert db_service.get_tag_color("test-tag") == "#00FF00"

        # Undo second change
        cmd2.undo(db_service)
        assert db_service.get_tag_color("test-tag") == "#FF0000"

        # Redo second change
        cmd2.execute(db_service)
        assert db_service.get_tag_color("test-tag") == "#00FF00"

    def test_date_range_filtering_across_workflow(self, db_service):
        """
        Test that date range filtering works consistently across all operations.
        """
        # Create events across time range
        events = [
            Event(name=f"Event {i}", lore_date=float(i * 100)) for i in range(1, 11)
        ]
        for event in events:
            db_service.insert_event(event)
            db_service.assign_tag_to_event(event.id, "test-tag")

        # Get metadata with date range
        metadata = db_service.get_group_metadata(
            tag_order=["test-tag"], date_range=(200.0, 800.0)
        )
        assert metadata[0]["count"] == 7  # Events 2-8

        # Get events with same date range
        filtered_events = db_service.get_events_for_group(
            tag_name="test-tag", date_range=(200.0, 800.0)
        )
        assert len(filtered_events) == 7

        # Get grouped events with date range
        result = db_service.get_events_grouped_by_tags(
            tag_order=["test-tag"], date_range=(200.0, 800.0)
        )
        assert len(result["groups"][0]["events"]) == 7

    def test_duplicate_mode_with_multiple_tags_on_same_event(self, db_service):
        """
        Test DUPLICATE mode behavior when an event has multiple tags.
        """
        # Create single event with three tags
        event1 = Event(name="Multi-tag Event", lore_date=100.0)
        db_service.insert_event(event1)
        db_service.assign_tag_to_event(event1.id, "tag-a")
        db_service.assign_tag_to_event(event1.id, "tag-b")
        db_service.assign_tag_to_event(event1.id, "tag-c")

        # Get groups in DUPLICATE mode
        result = db_service.get_events_grouped_by_tags(
            tag_order=["tag-a", "tag-b", "tag-c"], mode="DUPLICATE"
        )

        # Event should appear in all three groups
        for group in result["groups"]:
            assert len(group["events"]) == 1
            assert group["events"][0].id == event1.id

        # Metadata should show count of 1 for each group
        metadata = db_service.get_group_metadata(tag_order=["tag-a", "tag-b", "tag-c"])
        for meta in metadata:
            assert meta["count"] == 1

    def test_first_match_mode_with_multiple_tags_on_same_event(self, db_service):
        """
        Test FIRST_MATCH mode behavior when an event has multiple tags.
        """
        # Create single event with three tags
        event1 = Event(name="Multi-tag Event", lore_date=100.0)
        db_service.insert_event(event1)
        db_service.assign_tag_to_event(event1.id, "tag-a")
        db_service.assign_tag_to_event(event1.id, "tag-b")
        db_service.assign_tag_to_event(event1.id, "tag-c")

        # Set grouping to FIRST_MATCH mode
        cmd = SetTimelineGroupingCommand(
            tag_order=["tag-a", "tag-b", "tag-c"], mode="FIRST_MATCH"
        )
        cmd.execute(db_service)

        # Get groups in FIRST_MATCH mode
        result = db_service.get_events_grouped_by_tags(
            tag_order=["tag-a", "tag-b", "tag-c"], mode="FIRST_MATCH"
        )

        # Event should only appear in first matching group (tag-a)
        assert len(result["groups"][0]["events"]) == 1
        assert result["groups"][0]["events"][0].id == event1.id
        assert len(result["groups"][1]["events"]) == 0
        assert len(result["groups"][2]["events"]) == 0

    def test_remaining_events_handling(self, db_service):
        """
        Test that remaining (ungrouped) events are handled correctly.
        """
        # Create mixed events
        event1 = Event(name="Grouped Event", lore_date=100.0)
        event2 = Event(name="Ungrouped Event", lore_date=200.0)
        event3 = Event(name="Other Tag Event", lore_date=300.0)

        db_service.insert_event(event1)
        db_service.insert_event(event2)
        db_service.insert_event(event3)

        db_service.assign_tag_to_event(event1.id, "grouped-tag")
        # event2 has no tags
        db_service.assign_tag_to_event(event3.id, "other-tag")

        # Get groups (only grouped-tag)
        result = db_service.get_events_grouped_by_tags(
            tag_order=["grouped-tag"], mode="DUPLICATE"
        )

        # Check remaining events
        remaining_ids = [e.id for e in result["remaining"]]
        assert event1.id not in remaining_ids  # In grouped
        assert event2.id in remaining_ids  # No tags
        assert event3.id in remaining_ids  # Different tag

    def test_empty_tag_list_returns_all_events_as_remaining(self, db_service):
        """
        Test that empty tag list puts all events in remaining.
        """
        # Create events with tags
        event1 = Event(name="Event 1", lore_date=100.0)
        event2 = Event(name="Event 2", lore_date=200.0)
        db_service.insert_event(event1)
        db_service.insert_event(event2)
        db_service.assign_tag_to_event(event1.id, "tag-a")
        db_service.assign_tag_to_event(event2.id, "tag-b")

        # Get groups with empty tag order
        result = db_service.get_events_grouped_by_tags(tag_order=[], mode="DUPLICATE")

        # All events should be in remaining
        assert len(result["groups"]) == 0
        assert len(result["remaining"]) == 2
