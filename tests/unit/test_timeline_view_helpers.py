"""
Tests for TimelineView helper methods and refactored code.
"""

import pytest
from PySide6.QtGui import QImage, QPainter

from src.core.events import Event
from src.gui.widgets.timeline import (
    EventItem,
    TimelineView,
)


@pytest.fixture
def timeline_view(qtbot):
    """Create TimelineView for testing."""
    view = TimelineView()
    qtbot.addWidget(view)
    return view


@pytest.fixture
def sample_events():
    """Sample events for testing."""
    return [
        Event(id="e1", name="Event 1", lore_date=100.0, type="cosmic"),
        Event(id="e2", name="Event 2", lore_date=200.0, type="combat"),
        Event(id="e3", name="Event 3", lore_date=300.0, type="session"),
    ]


class TestApplyZoom:
    """Tests for the _apply_zoom helper method."""

    def test_apply_zoom_updates_transform(self, timeline_view):
        """Test that _apply_zoom correctly sets the transform."""
        timeline_view._apply_zoom(2.0)

        transform = timeline_view.transform()
        assert abs(transform.m11() - 2.0) < 0.01

    def test_apply_zoom_updates_current_zoom(self, timeline_view):
        """Test that _apply_zoom updates _current_zoom."""
        timeline_view._apply_zoom(1.5)

        assert timeline_view._current_zoom == 1.5

    def test_apply_zoom_updates_playhead_zoom(self, timeline_view):
        """Test that _apply_zoom updates the playhead's zoom level."""
        timeline_view._apply_zoom(3.0)

        expected_zoom = 3.0 * timeline_view.scale_factor
        assert timeline_view._playhead._zoom_level == expected_zoom


class TestSetupRulerFonts:
    """Tests for the _setup_ruler_fonts helper method."""

    def test_setup_ruler_fonts_returns_tuple(self, timeline_view):
        """Test that _setup_ruler_fonts returns a tuple of fonts."""
        image = QImage(100, 100, QImage.Format_ARGB32)
        painter = QPainter(image)

        result = timeline_view._setup_ruler_fonts(painter)

        painter.end()

        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_setup_ruler_fonts_major_is_bold(self, timeline_view):
        """Test that the major font is bold."""
        image = QImage(100, 100, QImage.Format_ARGB32)
        painter = QPainter(image)

        major_font, minor_font = timeline_view._setup_ruler_fonts(painter)

        painter.end()

        assert major_font.bold() is True
        assert minor_font.bold() is False

    def test_setup_ruler_fonts_sizes(self, timeline_view):
        """Test that fonts have correct point sizes."""
        image = QImage(100, 100, QImage.Format_ARGB32)
        painter = QPainter(image)

        major_font, minor_font = timeline_view._setup_ruler_fonts(painter)

        painter.end()

        assert major_font.pointSize() == 9
        assert minor_font.pointSize() == 8


class TestPositionEventItem:
    """Tests for the _position_event_item helper method."""

    def test_position_event_item_sets_y(self, timeline_view):
        """Test that _position_event_item sets the item's Y position."""
        event = Event(id="test", name="Test", lore_date=100.0, type="generic")
        item = EventItem(event, timeline_view.scale_factor)
        timeline_view.scene.addItem(item)

        timeline_view._position_event_item(item, 150.0)

        assert item.y() == 150.0

    def test_position_event_item_sets_visible(self, timeline_view):
        """Test that _position_event_item makes the item visible."""
        event = Event(id="test", name="Test", lore_date=100.0, type="generic")
        item = EventItem(event, timeline_view.scale_factor)
        item.setVisible(False)
        timeline_view.scene.addItem(item)

        timeline_view._position_event_item(item, 100.0)

        assert item.isVisible() is True

    def test_position_event_item_updates_initial_y(self, timeline_view):
        """Test that _position_event_item updates _initial_y."""
        event = Event(id="test", name="Test", lore_date=100.0, type="generic")
        item = EventItem(event, timeline_view.scale_factor)
        timeline_view.scene.addItem(item)

        timeline_view._position_event_item(item, 200.0)

        assert item._initial_y == 200.0


class TestUpdateSceneRectFromEvents:
    """Tests for the _update_scene_rect_from_events helper method."""

    def test_update_scene_rect_sets_valid_rect(self, timeline_view, sample_events):
        """Test that _update_scene_rect_from_events sets a valid scene rect."""
        timeline_view.set_events(sample_events)

        # Call directly to test the method
        timeline_view._update_scene_rect_from_events(sample_events)

        rect = timeline_view.scene.sceneRect()
        assert rect.width() > 0
        assert rect.height() > 0

    def test_update_scene_rect_handles_single_event(self, timeline_view):
        """Test that _update_scene_rect_from_events handles a single event."""
        events = [Event(id="solo", name="Solo Event", lore_date=500.0, type="generic")]
        timeline_view.set_events(events)

        timeline_view._update_scene_rect_from_events(events)

        rect = timeline_view.scene.sceneRect()
        assert rect.width() > 0  # Should have some width even with single event

    def test_update_scene_rect_includes_margin(self, timeline_view, sample_events):
        """Test that scene rect includes margin around events."""
        timeline_view.set_events(sample_events)
        timeline_view._update_scene_rect_from_events(sample_events)

        rect = timeline_view.scene.sceneRect()
        scale = timeline_view.scale_factor

        # Min event is at 100, max at 300
        # Rect should start before 100 * scale and end after 300 * scale
        assert rect.left() < 100 * scale
        assert rect.right() > 300 * scale


class TestEventUpdatePreview:
    """Tests for the update_event_preview method."""

    def test_update_event_preview_changes_name(self, timeline_view):
        """Test that update_event_preview updates the event name."""
        events = [Event(id="upd", name="Original", lore_date=100.0, type="generic")]
        timeline_view.set_events(events)

        timeline_view.update_event_preview({"id": "upd", "name": "Updated"})

        items = [i for i in timeline_view.scene.items() if isinstance(i, EventItem)]
        assert items[0].event.name == "Updated"

    def test_update_event_preview_changes_lore_date(self, timeline_view):
        """Test that update_event_preview updates the lore_date."""
        events = [Event(id="upd", name="Test", lore_date=100.0, type="generic")]
        timeline_view.set_events(events)

        timeline_view.update_event_preview({"id": "upd", "lore_date": 250.0})

        items = [i for i in timeline_view.scene.items() if isinstance(i, EventItem)]
        assert items[0].event.lore_date == 250.0

    def test_update_event_preview_nonexistent_id(self, timeline_view, sample_events):
        """Test that update_event_preview handles nonexistent IDs gracefully."""
        timeline_view.set_events(sample_events)

        # Should not crash
        timeline_view.update_event_preview({"id": "nonexistent", "name": "New"})

        # Original events unchanged
        items = [i for i in timeline_view.scene.items() if isinstance(i, EventItem)]
        assert len(items) == 3


class TestPlayheadHelpers:
    """Tests for playhead-related methods."""

    def test_get_playhead_time(self, timeline_view):
        """Test get_playhead_time returns correct value."""
        timeline_view.set_playhead_time(123.0)

        result = timeline_view.get_playhead_time()

        assert abs(result - 123.0) < 0.01

    def test_is_playing_initially_false(self, timeline_view):
        """Test that is_playing returns False initially."""
        assert timeline_view.is_playing() is False

    def test_is_playing_after_start(self, timeline_view):
        """Test that is_playing returns True after start_playback."""
        timeline_view.start_playback()

        assert timeline_view.is_playing() is True

        timeline_view.stop_playback()
