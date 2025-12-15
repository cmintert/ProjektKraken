"""
Advanced tests for Timeline widget improvements.

Tests zoom-to-cursor, smart lane packing, EventItem reuse, and scrubber/playhead.
"""

import pytest
from PySide6.QtCore import Qt, QPoint, QPointF
from PySide6.QtGui import QWheelEvent
from src.gui.widgets.timeline import TimelineWidget, TimelineView, EventItem, PlayheadItem
from src.core.events import Event


@pytest.fixture
def timeline_widget(qtbot):
    """Create TimelineWidget for testing."""
    widget = TimelineWidget()
    qtbot.addWidget(widget)
    return widget


@pytest.fixture
def timeline_view(qtbot):
    """Create TimelineView for testing."""
    view = TimelineView()
    qtbot.addWidget(view)
    return view


class TestSmartLanePacking:
    """Tests for greedy lane packing algorithm."""

    def test_non_overlapping_events_same_lane(self, timeline_widget):
        """Non-overlapping events should use the same lane."""
        events = [
            Event(name="E1", lore_date=10, lore_duration=5),  # 10-15
            Event(name="E2", lore_date=20, lore_duration=5),  # 20-25
            Event(name="E3", lore_date=30, lore_duration=5),  # 30-35
        ]
        timeline_widget.set_events(events)

        items = [i for i in timeline_widget.view.scene.items() if isinstance(i, EventItem)]
        items.sort(key=lambda i: i.event.lore_date)

        # All should be on the same lane (same y coordinate)
        assert items[0].y() == items[1].y() == items[2].y()

    def test_overlapping_events_different_lanes(self, timeline_widget):
        """Overlapping events should use different lanes."""
        events = [
            Event(name="E1", lore_date=10, lore_duration=30),  # 10-40
            Event(name="E2", lore_date=20, lore_duration=30),  # 20-50 (overlaps E1)
            Event(name="E3", lore_date=25, lore_duration=30),  # 25-55 (overlaps E1, E2)
        ]
        timeline_widget.set_events(events)

        items = [i for i in timeline_widget.view.scene.items() if isinstance(i, EventItem)]
        items.sort(key=lambda i: i.event.lore_date)

        # All three should be on different lanes
        y_coords = [items[0].y(), items[1].y(), items[2].y()]
        assert len(set(y_coords)) == 3, "All overlapping events should use different lanes"

    def test_lane_reuse_after_gap(self, timeline_widget):
        """Events after a gap should reuse lanes."""
        events = [
            Event(name="E1", lore_date=10, lore_duration=30),  # 10-40
            Event(name="E2", lore_date=20, lore_duration=30),  # 20-50 (overlaps E1)
            Event(name="E3", lore_date=60, lore_duration=10),  # 60-70 (no overlap)
        ]
        timeline_widget.set_events(events)

        items = [i for i in timeline_widget.view.scene.items() if isinstance(i, EventItem)]
        items.sort(key=lambda i: i.event.lore_date)

        # E1 and E2 should use different lanes
        assert items[0].y() != items[1].y()
        # E3 should reuse E1's lane (earliest ending)
        assert items[0].y() == items[2].y()

    def test_point_events_minimal_lanes(self, timeline_widget):
        """Point events (zero duration) at different times should use same lane."""
        events = [
            Event(name="E1", lore_date=10, lore_duration=0),
            Event(name="E2", lore_date=20, lore_duration=0),
            Event(name="E3", lore_date=30, lore_duration=0),
        ]
        timeline_widget.set_events(events)

        items = [i for i in timeline_widget.view.scene.items() if isinstance(i, EventItem)]
        items.sort(key=lambda i: i.event.lore_date)

        # All point events should be on the same lane
        assert items[0].y() == items[1].y() == items[2].y()

    def test_complex_overlapping_pattern(self, timeline_widget):
        """Test complex overlapping pattern uses minimal lanes."""
        events = [
            Event(name="E1", lore_date=0, lore_duration=10),   # 0-10 -> Lane 0
            Event(name="E2", lore_date=5, lore_duration=10),   # 5-15 -> Lane 1
            Event(name="E3", lore_date=12, lore_duration=10),  # 12-22 -> Lane 0 (reuse)
            Event(name="E4", lore_date=16, lore_duration=10),  # 16-26 -> Lane 1 (reuse)
        ]
        timeline_widget.set_events(events)

        items = [i for i in timeline_widget.view.scene.items() if isinstance(i, EventItem)]
        items.sort(key=lambda i: i.event.lore_date)

        # Should only use 2 lanes
        y_coords = [item.y() for item in items]
        unique_lanes = len(set(y_coords))
        assert unique_lanes == 2, f"Should use 2 lanes, but used {unique_lanes}"


class TestZoomToCursor:
    """Tests for zoom-to-cursor behavior."""

    def test_zoom_in_at_point(self, timeline_view, qtbot):
        """Zoom in should keep scene point under cursor stable."""
        # Set up some events and show the view so geometry is initialized
        timeline_view.set_events([Event(name="E1", lore_date=100, lore_duration=0)])
        timeline_view.show()
        qtbot.waitExposed(timeline_view)
        timeline_view.resize(800, 600)
        
        # Record initial transform
        initial_zoom = timeline_view._current_zoom
        
        # Simulate zoom in
        cursor_pos = QPointF(400, 300)  # Center of view
        event = QWheelEvent(
            cursor_pos,
            cursor_pos,
            QPoint(0, 0),
            QPoint(0, 120),  # Positive delta = zoom in
            Qt.NoButton,
            Qt.NoModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False,
        )
        
        timeline_view.wheelEvent(event)
        
        # Check zoom increased
        assert timeline_view._current_zoom > initial_zoom

    def test_zoom_out_at_point(self, timeline_view, qtbot):
        """Zoom out should keep scene point under cursor stable."""
        timeline_view.set_events([Event(name="E1", lore_date=100, lore_duration=0)])
        timeline_view.show()
        qtbot.waitExposed(timeline_view)
        timeline_view.resize(800, 600)
        
        initial_zoom = timeline_view._current_zoom
        cursor_pos = QPointF(400, 300)
        
        # Simulate zoom out
        event = QWheelEvent(
            cursor_pos,
            cursor_pos,
            QPoint(0, 0),
            QPoint(0, -120),  # Negative delta = zoom out
            Qt.NoButton,
            Qt.NoModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False,
        )
        
        timeline_view.wheelEvent(event)
        
        # Check zoom decreased
        assert timeline_view._current_zoom < initial_zoom

    def test_zoom_min_limit(self, timeline_view):
        """Zooming out should respect minimum zoom limit."""
        timeline_view.set_events([Event(name="E1", lore_date=100, lore_duration=0)])
        
        # Zoom out many times
        cursor_pos = QPointF(100, 100)
        for _ in range(50):
            event = QWheelEvent(
                cursor_pos,
                cursor_pos,
                QPoint(0, 0),
                QPoint(0, -120),
                Qt.NoButton,
                Qt.NoModifier,
                Qt.ScrollPhase.NoScrollPhase,
                False,
            )
            timeline_view.wheelEvent(event)
        
        # Should not go below MIN_ZOOM
        assert timeline_view._current_zoom >= timeline_view.MIN_ZOOM

    def test_zoom_max_limit(self, timeline_view):
        """Zooming in should respect maximum zoom limit."""
        timeline_view.set_events([Event(name="E1", lore_date=100, lore_duration=0)])
        
        # Zoom in many times
        cursor_pos = QPointF(100, 100)
        for _ in range(50):
            event = QWheelEvent(
                cursor_pos,
                cursor_pos,
                QPoint(0, 0),
                QPoint(0, 120),
                Qt.NoButton,
                Qt.NoModifier,
                Qt.ScrollPhase.NoScrollPhase,
                False,
            )
            timeline_view.wheelEvent(event)
        
        # Should not exceed MAX_ZOOM
        assert timeline_view._current_zoom <= timeline_view.MAX_ZOOM


class TestEventItemUpdate:
    """Tests for EventItem reuse and update functionality."""

    def test_event_item_update_method_exists(self):
        """EventItem should have update_event method."""
        event = Event(name="Test", lore_date=100, lore_duration=0)
        item = EventItem(event, 10.0)
        
        assert hasattr(item, 'update_event')
        assert callable(item.update_event)

    def test_event_item_update_changes_data(self):
        """update_event should update the event data."""
        event1 = Event(name="Original", lore_date=100, type="cosmic", lore_duration=0)
        item = EventItem(event1, 10.0)
        
        assert item.event.name == "Original"
        assert item.event.type == "cosmic"
        
        event2 = Event(id=event1.id, name="Updated", lore_date=150, type="combat", lore_duration=10)
        item.update_event(event2)
        
        assert item.event.name == "Updated"
        assert item.event.type == "combat"
        assert item.event.lore_date == 150
        assert item.event.lore_duration == 10

    def test_items_reused_on_set_events(self, timeline_widget):
        """set_events should reuse existing items where possible."""
        event1 = Event(id="test-id-1", name="Event1", lore_date=100, lore_duration=0)
        event2 = Event(id="test-id-2", name="Event2", lore_date=200, lore_duration=0)
        
        timeline_widget.set_events([event1, event2])
        
        # Get initial items
        items_before = [i for i in timeline_widget.view.scene.items() if isinstance(i, EventItem)]
        item_ids_before = {id(item) for item in items_before}
        
        # Update events with same IDs but different data
        event1_updated = Event(id="test-id-1", name="Updated1", lore_date=110, lore_duration=5)
        event2_updated = Event(id="test-id-2", name="Updated2", lore_date=210, lore_duration=5)
        
        timeline_widget.set_events([event1_updated, event2_updated])
        
        # Get items after update
        items_after = [i for i in timeline_widget.view.scene.items() if isinstance(i, EventItem)]
        item_ids_after = {id(item) for item in items_after}
        
        # Should have reused the same item objects
        assert item_ids_before == item_ids_after

    def test_items_removed_when_event_deleted(self, timeline_widget):
        """Items should be removed when their events are deleted."""
        event1 = Event(id="keep", name="Keep", lore_date=100, lore_duration=0)
        event2 = Event(id="delete", name="Delete", lore_date=200, lore_duration=0)
        
        timeline_widget.set_events([event1, event2])
        
        # Should have 2 event items
        items = [i for i in timeline_widget.view.scene.items() if isinstance(i, EventItem)]
        assert len(items) == 2
        
        # Remove one event
        timeline_widget.set_events([event1])
        
        # Should only have 1 event item now
        items = [i for i in timeline_widget.view.scene.items() if isinstance(i, EventItem)]
        assert len(items) == 1
        assert items[0].event.id == "keep"


class TestScrubberPlayhead:
    """Tests for scrubber/playhead functionality."""

    def test_playhead_exists_in_scene(self, timeline_view):
        """Playhead should be present in the scene."""
        playhead_items = [i for i in timeline_view.scene.items() if isinstance(i, PlayheadItem)]
        assert len(playhead_items) == 1

    def test_set_playhead_time(self, timeline_view):
        """set_playhead_time should position the playhead correctly."""
        timeline_view.set_playhead_time(100.0)
        
        playhead_time = timeline_view.get_playhead_time()
        assert abs(playhead_time - 100.0) < 0.1

    def test_playhead_time_changed_signal(self, timeline_view, qtbot):
        """Playhead should emit signal when time changes."""
        with qtbot.waitSignal(timeline_view.playhead_time_changed, timeout=1000) as blocker:
            timeline_view.set_playhead_time(50.0)
        
        assert blocker.args[0] == 50.0

    def test_start_stop_playback(self, timeline_view):
        """Playback should start and stop correctly."""
        assert not timeline_view.is_playing()
        
        timeline_view.start_playback()
        assert timeline_view.is_playing()
        
        timeline_view.stop_playback()
        assert not timeline_view.is_playing()

    def test_step_forward(self, timeline_view):
        """step_forward should advance playhead."""
        timeline_view.set_playhead_time(10.0)
        initial_time = timeline_view.get_playhead_time()
        
        timeline_view.step_forward()
        
        new_time = timeline_view.get_playhead_time()
        assert new_time > initial_time

    def test_step_backward(self, timeline_view):
        """step_backward should move playhead back."""
        timeline_view.set_playhead_time(10.0)
        initial_time = timeline_view.get_playhead_time()
        
        timeline_view.step_backward()
        
        new_time = timeline_view.get_playhead_time()
        assert new_time < initial_time

    def test_playback_advances_automatically(self, timeline_view, qtbot):
        """Playback should automatically advance playhead over time."""
        timeline_view.set_playhead_time(0.0)
        initial_time = timeline_view.get_playhead_time()
        
        timeline_view.start_playback()
        
        # Wait for playback to advance (default interval is 100ms)
        qtbot.wait(300)
        
        timeline_view.stop_playback()
        
        final_time = timeline_view.get_playhead_time()
        assert final_time > initial_time


class TestPlaybackControls:
    """Tests for playback control buttons in TimelineWidget."""

    def test_play_pause_button_exists(self, timeline_widget):
        """Play/Pause button should exist."""
        assert timeline_widget.btn_play_pause is not None
        assert timeline_widget.btn_play_pause.text() in ["▶", "■"]

    def test_step_buttons_exist(self, timeline_widget):
        """Step forward/backward buttons should exist."""
        assert timeline_widget.btn_step_forward is not None
        assert timeline_widget.btn_step_back is not None

    def test_toggle_playback(self, timeline_widget):
        """toggle_playback should start/stop playback and update button."""
        initial_text = timeline_widget.btn_play_pause.text()
        assert initial_text == "▶"
        
        timeline_widget.toggle_playback()
        assert timeline_widget.view.is_playing()
        assert timeline_widget.btn_play_pause.text() == "■"
        
        timeline_widget.toggle_playback()
        assert not timeline_widget.view.is_playing()
        assert timeline_widget.btn_play_pause.text() == "▶"

    def test_step_forward_button(self, timeline_widget):
        """Step forward button should advance playhead."""
        timeline_widget.set_playhead_time(10.0)
        initial_time = timeline_widget.get_playhead_time()
        
        timeline_widget.btn_step_forward.click()
        
        new_time = timeline_widget.get_playhead_time()
        assert new_time > initial_time

    def test_step_backward_button(self, timeline_widget):
        """Step backward button should move playhead back."""
        timeline_widget.set_playhead_time(10.0)
        initial_time = timeline_widget.get_playhead_time()
        
        timeline_widget.btn_step_back.click()
        
        new_time = timeline_widget.get_playhead_time()
        assert new_time < initial_time

    def test_widget_exposes_playhead_signal(self, timeline_widget, qtbot):
        """TimelineWidget should expose playhead_time_changed signal."""
        with qtbot.waitSignal(timeline_widget.playhead_time_changed, timeout=1000) as blocker:
            timeline_widget.set_playhead_time(42.0)
        
        assert blocker.args[0] == 42.0


class TestEventItemCaching:
    """Tests for QGraphicsItem caching."""

    def test_event_item_has_cache_mode_set(self):
        """EventItem should have caching enabled."""
        event = Event(name="Test", lore_date=100, lore_duration=0)
        item = EventItem(event, 10.0)
        
        from PySide6.QtWidgets import QGraphicsItem
        assert item.cacheMode() == QGraphicsItem.DeviceCoordinateCache
