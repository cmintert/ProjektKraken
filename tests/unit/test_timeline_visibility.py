"""
Tests for Timeline visibility logic (Events, Bands, Labels).
"""

from unittest.mock import MagicMock

import pytest

from src.core.events import Event
from src.gui.widgets.timeline import (
    EventItem,
    TimelineView,
)
from src.gui.widgets.timeline.group_band_item import GroupBandItem
from src.gui.widgets.timeline.group_band_manager import GroupBandManager


@pytest.fixture
def timeline_view(qtbot):
    """Create TimelineView for testing."""
    view = TimelineView()
    qtbot.addWidget(view)

    # Mock band manager
    view._band_manager = MagicMock(spec=GroupBandManager)

    return view


class TestTimelineVisibility:
    """Tests for visibility of timeline elements."""

    def test_events_visible_in_default_view(self, timeline_view):
        """Test that events are visible in default (ungrouped) view."""
        event = Event(name="Visible Event", lore_date=100.0)
        timeline_view.set_events([event])

        items = [i for i in timeline_view.scene.items() if isinstance(i, EventItem)]
        # Default view also triggers 'All events' logic if we don't control it,
        # but without grouping_active it uses standard packing.
        # repack_events check: if grouping_active ... else: pack_events.
        # So default view is clean.
        assert len(items) == 1
        assert items[0].isVisible()

    def test_band_visibility_when_grouping_active(self, timeline_view):
        """Test that group bands are visible when grouping is active."""
        view = timeline_view
        view._grouping_tag_order = ["tag1"]
        view._grouping_mode = "DUPLICATE"

        # Mock bands
        mock_band = GroupBandItem("tag1", "#FF0000", 1, 100, 100)
        # We must add it to scene manually as the manager usually does this
        view.scene.addItem(mock_band)

        all_events_band = GroupBandItem(
            "All events", "#808080", 1, 100, 100, is_collapsed=True
        )
        view.scene.addItem(all_events_band)

        def get_band(tag):
            if tag == "tag1":
                return mock_band
            if tag == "All events":
                return all_events_band
            return None

        view._band_manager.get_band.side_effect = get_band

        # Add event with tag
        event = Event(name="Tagged Event", lore_date=100.0)
        event.tags = ["tag1"]

        view.set_events([event])

        # Verify band is in scene and visible
        assert mock_band in view.scene.items()
        assert mock_band.isVisible()

    def test_events_hidden_when_band_collapsed(self, timeline_view):
        """Test that events are hidden when their group band is collapsed."""
        view = timeline_view
        view._grouping_tag_order = ["tag1"]
        view._grouping_mode = "DUPLICATE"

        # Mock collapsed band for tag1
        mock_band = GroupBandItem("tag1", "#FF0000", 1, 100, 100, is_collapsed=True)
        view.scene.addItem(mock_band)

        # Mock collapsed "All events" to avoid duplicates polluting check
        all_events_band = GroupBandItem(
            "All events", "#808080", 1, 100, 100, is_collapsed=True
        )
        view.scene.addItem(all_events_band)

        def get_band(tag):
            if tag == "tag1":
                return mock_band
            if tag == "All events":
                return all_events_band
            return None

        view._band_manager.get_band.side_effect = get_band

        event = Event(name="Collapsed Event", lore_date=100.0)
        event.tags = ["tag1"]

        view.set_events([event])

        # Event item should be hidden
        # The original item is hidden by tag1 band.
        # "All events" is collapsed, so it generates no duplicates for grouped events?
        # Check logic: if all_events_band.is_collapsed -> hide ungrouped.
        # It does NOT generate duplicates.
        # So we expect 1 item (Original) and it should be hidden.
        items = [i for i in view.scene.items() if isinstance(i, EventItem)]
        assert len(items) == 1
        assert not items[0].isVisible()

    def test_events_visible_when_band_expanded(self, timeline_view):
        """Test that events are visible when their group band is expanded."""
        view = timeline_view
        view._grouping_tag_order = ["tag1"]
        view._grouping_mode = "DUPLICATE"

        # Mock expanded band
        mock_band = GroupBandItem("tag1", "#FF0000", 1, 100, 100, is_collapsed=False)
        view.scene.addItem(mock_band)

        # Collapse "All events" to simplify
        all_events_band = GroupBandItem(
            "All events", "#808080", 1, 100, 100, is_collapsed=True
        )
        view.scene.addItem(all_events_band)

        def get_band(tag):
            if tag == "tag1":
                return mock_band
            if tag == "All events":
                return all_events_band
            return None

        view._band_manager.get_band.side_effect = get_band

        event = Event(name="Expanded Event", lore_date=100.0)
        event.tags = ["tag1"]

        view.set_events([event])

        # Event item should be visible
        items = [i for i in view.scene.items() if isinstance(i, EventItem)]
        assert len(items) == 1
        assert items[0].isVisible()

    def test_duplicate_events_visibility(self, timeline_view):
        """
        Test visibility of duplicate events (one in collapsed group, one in expanded).
        """
        view = timeline_view
        view._grouping_tag_order = ["tag1", "tag2"]
        view._grouping_mode = "DUPLICATE"

        # Create two bands: tag1 collapsed, tag2 expanded
        band1 = GroupBandItem("tag1", "#FF0000", 1, 100, 100, is_collapsed=True)
        band2 = GroupBandItem("tag2", "#00FF00", 1, 100, 100, is_collapsed=False)
        all_evt = GroupBandItem("All events", "#8080", 1, 100, 100, is_collapsed=True)

        view.scene.addItem(band1)
        view.scene.addItem(band2)
        view.scene.addItem(all_evt)

        def get_band(tag):
            if tag == "tag1":
                return band1
            if tag == "tag2":
                return band2
            if tag == "All events":
                return all_evt
            return None

        view._band_manager.get_band.side_effect = get_band

        event = Event(name="Multi-tag Event", lore_date=100.0)
        event.tags = ["tag1", "tag2"]

        view.set_events([event])

        # When tag1 is collapsed, the event is skipped in that group loop (not placed).
        # So when it reaches tag2, it uses the ORIGINAL item (not a duplicate).
        # So we have 1 item total, and it is visible (in tag2).
        items = [i for i in view.scene.items() if isinstance(i, EventItem)]
        assert len(items) == 1
        assert items[0].isVisible()

    def test_label_overlay_visibility(self, timeline_view):
        """Test that group label overlay is visible when grouping is active."""
        view = timeline_view
        view.show()  # Ensure view is visible
        assert view.isVisible()

        view._grouping_tag_order = ["tag1"]
        view.resize(800, 600)  # Ensure non-zero size

        # We need to trigger label update manually since we bypassed set_grouping_config
        # Setting _grouping_tag_order is not enough.
        # But we also need bands to exist in manager
        mock_band = GroupBandItem("tag1", "#FF", 1, 100, 100)
        view.scene.addItem(mock_band)
        mock_band.setVisible(True)  # Explicitly ensure visible
        mock_band.setY(100)  # Ensure it has a position

        view._band_manager.get_band.return_value = mock_band

        # Trigger update
        view._update_label_overlay()

        # Check internal state of overlay
        assert len(view._label_overlay._labels) > 0, "Labels list should not be empty"
        assert view._label_overlay.isVisible()
