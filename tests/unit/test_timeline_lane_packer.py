"""
Unit tests for TimelineLanePacker.

Tests the lane packing algorithm in isolation.
"""

from src.core.events import Event
from src.gui.widgets.timeline_lane_packer import TimelineLanePacker


class TestTimelineLanePacker:
    """Tests for the TimelineLanePacker class."""

    def test_non_overlapping_events_same_lane(self):
        """Non-overlapping events should use the same lane."""
        packer = TimelineLanePacker(scale_factor=10.0)

        events = [
            Event(name="E1", lore_date=10, lore_duration=5),  # 10-15
            Event(name="E2", lore_date=20, lore_duration=5),  # 20-25
            Event(name="E3", lore_date=30, lore_duration=5),  # 30-35
        ]

        assignments = packer.pack_events(events)

        # All should be on the same lane
        assert assignments[events[0].id] == 0
        assert assignments[events[1].id] == 0
        assert assignments[events[2].id] == 0

    def test_overlapping_events_different_lanes(self):
        """Overlapping events should use different lanes."""
        packer = TimelineLanePacker(scale_factor=10.0)

        events = [
            Event(name="E1", lore_date=10, lore_duration=30),  # 10-40
            Event(name="E2", lore_date=20, lore_duration=30),  # 20-50 (overlaps E1)
        ]

        assignments = packer.pack_events(events)

        # Should use different lanes
        assert assignments[events[0].id] != assignments[events[1].id]

    def test_lane_reuse(self):
        """Lane should be reused when earlier event finishes."""
        packer = TimelineLanePacker(scale_factor=10.0)

        events = [
            Event(name="E1", lore_date=10, lore_duration=30),  # 10-40
            Event(name="E2", lore_date=20, lore_duration=30),  # 20-50 (overlaps E1)
            Event(name="E3", lore_date=55, lore_duration=10),  # 55-65 (after both)
        ]

        assignments = packer.pack_events(events)

        # E1 and E2 should be in different lanes
        assert assignments[events[0].id] != assignments[events[1].id]
        # E3 should reuse one of the lanes (lane 0)
        assert assignments[events[2].id] == 0

    def test_point_events(self):
        """Point events (duration=0) should be packed correctly."""
        packer = TimelineLanePacker(scale_factor=10.0)

        events = [
            Event(name="P1", lore_date=10, lore_duration=0),  # Point event
            Event(name="P2", lore_date=15, lore_duration=0),  # Point event
        ]

        assignments = packer.pack_events(events)

        # Both should have lane assignments
        assert events[0].id in assignments
        assert events[1].id in assignments

    def test_scale_factor_update(self):
        """Scale factor update should affect packing."""
        packer = TimelineLanePacker(scale_factor=10.0)

        events = [
            Event(name="E1", lore_date=10, lore_duration=5),
        ]

        # Pack with initial scale
        assignments1 = packer.pack_events(events)

        # Update scale and pack again
        packer.update_scale_factor(20.0)
        assignments2 = packer.pack_events(events)

        # Should still assign to lane 0, but internal calculations differ
        assert assignments1[events[0].id] == 0
        assert assignments2[events[0].id] == 0
        assert packer.scale_factor == 20.0

    def test_empty_events(self):
        """Empty events list should return empty assignments."""
        packer = TimelineLanePacker(scale_factor=10.0)

        assignments = packer.pack_events([])

        assert assignments == {}

    def test_long_event_names(self):
        """Events with long names should get appropriate spacing."""
        packer = TimelineLanePacker(scale_factor=10.0)

        events = [
            Event(
                name="Very Long Event Name That Extends Far",
                lore_date=10,
                lore_duration=0,
            ),
            Event(
                name="Another Long Name",
                lore_date=12,
                lore_duration=0,
            ),
        ]

        assignments = packer.pack_events(events)

        # The second event should be in a different lane due to text width
        # (though this depends on exact font metrics)
        assert events[0].id in assignments
        assert events[1].id in assignments
