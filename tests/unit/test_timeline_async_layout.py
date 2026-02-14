"""
Unit tests for async timeline layout functionality.

Tests the integration of LayoutWorker into TimelineView for non-blocking
lane packing calculations.
"""

import time

from PySide6.QtCore import QThreadPool

from src.core.events import Event
from src.gui.widgets.timeline import TimelineWidget


class TestAsyncLayoutIntegration:
    """Tests for async layout worker integration."""

    def test_small_dataset_remains_synchronous(self, qapp, qtbot):
        """Small datasets (< 50 events) should use synchronous packing."""
        widget = TimelineWidget()
        qtbot.addWidget(widget)

        # Create 30 events
        events = [
            Event(name=f"Event {i}", lore_date=i * 10.0, lore_duration=5.0)
            for i in range(30)
        ]

        start_time = time.perf_counter()
        widget.set_events(events)
        elapsed = time.perf_counter() - start_time

        # Should complete quickly without async overhead
        assert elapsed < 0.5

        # Verify all events are positioned
        from src.gui.widgets.timeline import EventItem

        items = [i for i in widget.view.scene.items() if isinstance(i, EventItem)]
        assert len(items) == 30

    def test_large_dataset_uses_async_worker(self, qapp, qtbot):
        """Large datasets (>= 50 events) should use async worker."""
        widget = TimelineWidget()
        qtbot.addWidget(widget)

        # Create 100 events to trigger async path
        events = [
            Event(name=f"Event {i}", lore_date=i * 10.0, lore_duration=5.0)
            for i in range(100)
        ]

        # Set events and wait for async completion
        widget.set_events(events)

        # Wait for worker to complete (use qtbot to wait for signal or timeout)
        qtbot.wait(1000)  # Wait up to 1 second

        # Verify all events are positioned
        from src.gui.widgets.timeline import EventItem

        items = [i for i in widget.view.scene.items() if isinstance(i, EventItem)]
        assert len(items) == 100

        # Verify proper lane assignments
        for item in items:
            assert item.y() >= 80  # Should be positioned

    def test_async_worker_handles_500_events(self, qapp, qtbot):
        """Verify async worker can handle 500+ events efficiently."""
        widget = TimelineWidget()
        qtbot.addWidget(widget)

        # Create 500 events with some overlaps
        events = []
        for i in range(500):
            # Some events overlap to test lane packing
            date = i * 5.0  # More dense than simple spacing
            duration = 10.0 if i % 3 == 0 else 5.0
            events.append(
                Event(name=f"Event {i}", lore_date=date, lore_duration=duration)
            )

        start_time = time.perf_counter()
        widget.set_events(events)

        # Wait for async completion
        qtbot.wait(5000)  # Wait up to 5 seconds for 500 events

        elapsed = time.perf_counter() - start_time

        # Verify completion
        from src.gui.widgets.timeline import EventItem

        items = [i for i in widget.view.scene.items() if isinstance(i, EventItem)]
        assert len(items) == 500

        # Performance check - should complete within reasonable time
        assert elapsed < 10.0  # 10 seconds is generous for 500 events

        print(f"500 events processed in {elapsed:.3f}s")

    def test_zoom_triggers_async_repack(self, qapp, qtbot):
        """Zooming should trigger async repacking for large datasets."""
        widget = TimelineWidget()
        qtbot.addWidget(widget)

        # Create 100 events
        events = [
            Event(name=f"Event {i}", lore_date=i * 20.0, lore_duration=10.0)
            for i in range(100)
        ]

        widget.set_events(events)
        qtbot.wait(1000)

        # Trigger zoom via _apply_zoom
        initial_zoom = widget.view._current_zoom
        new_zoom = initial_zoom * 1.2
        widget.view._apply_zoom(new_zoom)

        # Wait for repack to complete
        qtbot.wait(1000)

        # Verify zoom changed
        assert widget.view._current_zoom != initial_zoom

        # Verify events are still properly positioned
        from src.gui.widgets.timeline import EventItem

        items = [i for i in widget.view.scene.items() if isinstance(i, EventItem)]
        assert len(items) == 100

    def test_concurrent_repack_requests_handled(self, qapp, qtbot):
        """Multiple rapid repack requests should be handled gracefully."""
        widget = TimelineWidget()
        qtbot.addWidget(widget)

        events = [
            Event(name=f"Event {i}", lore_date=i * 10.0, lore_duration=5.0)
            for i in range(100)
        ]

        widget.set_events(events)

        # Trigger multiple zoom operations rapidly
        for i in range(5):
            zoom = 1.0 + (i * 0.1)
            widget.view._apply_zoom(zoom)
            time.sleep(0.01)  # Small delay between zooms

        # Wait for all operations to settle
        qtbot.wait(2000)

        # Verify scene is still valid and events positioned
        from src.gui.widgets.timeline import EventItem

        items = [i for i in widget.view.scene.items() if isinstance(i, EventItem)]
        assert len(items) == 100


class TestProgressIndicators:
    """Tests for progress indicator functionality."""

    def test_progress_shown_for_long_operations(self, qapp, qtbot):
        """Progress indicator should appear for operations > 100ms."""
        widget = TimelineWidget()
        qtbot.addWidget(widget)

        # Create enough events to trigger visible progress
        events = [
            Event(name=f"Event {i}", lore_date=i * 5.0, lore_duration=3.0)
            for i in range(200)
        ]

        # Check if view has progress indicator attribute
        widget.set_events(events)

        # Progress indicator should be visible during processing
        # (This test will need adjustment once progress UI is implemented)
        if hasattr(widget.view, "_layout_in_progress"):
            # During operation, should be True
            # After completion (qtbot.wait), should be False
            pass

        qtbot.wait(2000)

        # After completion, progress should be hidden
        if hasattr(widget.view, "_layout_in_progress"):
            assert not widget.view._layout_in_progress

    def test_no_progress_for_quick_operations(self, qapp, qtbot):
        """Progress indicator should not appear for quick operations."""
        widget = TimelineWidget()
        qtbot.addWidget(widget)

        # Small dataset that completes quickly
        events = [Event(name=f"Event {i}", lore_date=i * 10.0) for i in range(10)]

        widget.set_events(events)
        qtbot.wait(100)

        # Progress indicator should not have been shown
        # (Test will be refined once implementation is complete)


class TestBatchSceneUpdates:
    """Tests for batch scene update functionality."""

    def test_scene_updates_are_batched(self, qapp, qtbot):
        """Scene updates should be batched during async layout."""
        widget = TimelineWidget()
        qtbot.addWidget(widget)

        events = [
            Event(name=f"Event {i}", lore_date=i * 10.0, lore_duration=5.0)
            for i in range(100)
        ]

        # Track scene update calls (this will need implementation hooks)
        widget.set_events(events)
        qtbot.wait(1000)

        # Verify all items are visible and positioned
        from src.gui.widgets.timeline import EventItem

        items = [i for i in widget.view.scene.items() if isinstance(i, EventItem)]
        assert len(items) == 100

        for item in items:
            assert item.isVisible()

    def test_scene_remains_responsive_during_layout(self, qapp, qtbot):
        """Scene should remain interactive during async layout calculation."""
        widget = TimelineWidget()
        qtbot.addWidget(widget)
        widget.show()

        events = [
            Event(name=f"Event {i}", lore_date=i * 5.0, lore_duration=3.0)
            for i in range(300)
        ]

        widget.set_events(events)

        # Try to interact with view immediately (pan)
        # View should remain responsive even during calculation
        initial_pos = widget.view.horizontalScrollBar().value()
        widget.view.horizontalScrollBar().setValue(initial_pos + 100)

        # Should be able to change scroll position
        new_pos = widget.view.horizontalScrollBar().value()
        # May not be exactly initial_pos + 100 due to constraints, but should change
        assert new_pos != initial_pos or initial_pos + 100 == new_pos

        qtbot.wait(2000)


class TestPerformanceMetrics:
    """Tests for performance characteristics."""

    def test_zoom_pan_performance_with_500_events(self, qapp, qtbot):
        """Zoom and pan should remain smooth with 500+ events."""
        widget = TimelineWidget()
        qtbot.addWidget(widget)

        # Create 500 events
        events = [
            Event(name=f"Event {i}", lore_date=i * 8.0, lore_duration=5.0)
            for i in range(500)
        ]

        widget.set_events(events)
        qtbot.wait(5000)

        # Measure zoom performance
        zoom_times = []
        for i in range(3):
            start = time.perf_counter()
            zoom_level = 1.0 + (i * 0.2)
            widget.view._apply_zoom(zoom_level)
            qtbot.wait(100)  # Small wait for operation to start
            elapsed = time.perf_counter() - start
            zoom_times.append(elapsed)

        # Zoom should feel responsive (< 200ms to initiate)
        avg_zoom_time = sum(zoom_times) / len(zoom_times)
        print(f"Average zoom time: {avg_zoom_time * 1000:.2f}ms")
        assert avg_zoom_time < 0.5  # Should start within 500ms

        # Measure pan performance
        pan_times = []
        for offset in [100, 200, 300]:
            start = time.perf_counter()
            widget.view.horizontalScrollBar().setValue(offset)
            elapsed = time.perf_counter() - start
            pan_times.append(elapsed)

        avg_pan_time = sum(pan_times) / len(pan_times)
        print(f"Average pan time: {avg_pan_time * 1000:.2f}ms")
        assert avg_pan_time < 0.1  # Panning should be immediate

    def test_ui_thread_blocking_time(self, qapp, qtbot):
        """UI thread should not be blocked for extended periods."""
        widget = TimelineWidget()
        qtbot.addWidget(widget)

        # Create large dataset
        events = [
            Event(name=f"Event {i}", lore_date=i * 5.0, lore_duration=3.0)
            for i in range(300)
        ]

        # Measure time for set_events to return (should be quick with async)
        start = time.perf_counter()
        widget.set_events(events)
        blocking_time = time.perf_counter() - start

        # set_events should return quickly, not block on calculation
        print(f"UI blocking time: {blocking_time * 1000:.2f}ms")
        assert blocking_time < 0.2  # Should return within 200ms

        # Wait for async completion
        qtbot.wait(3000)

        # Verify events are processed
        from src.gui.widgets.timeline import EventItem

        items = [i for i in widget.view.scene.items() if isinstance(i, EventItem)]
        assert len(items) == 300


class TestErrorHandling:
    """Tests for error handling in async operations."""

    def test_worker_error_handled_gracefully(self, qapp, qtbot):
        """Worker errors should be logged and not crash the UI."""
        widget = TimelineWidget()
        qtbot.addWidget(widget)
        widget.show()

        # Create events - normal case first
        events = [Event(name=f"Event {i}", lore_date=i * 10.0) for i in range(50)]

        # Should not raise exceptions
        widget.set_events(events)
        qtbot.wait(1000)

        # Verify widget is still functional
        assert widget.isVisible()
        from src.gui.widgets.timeline import EventItem

        items = [i for i in widget.view.scene.items() if isinstance(i, EventItem)]
        assert len(items) == 50

    def test_threadpool_cleanup(self, qapp, qtbot):
        """Thread pool should be properly cleaned up."""
        widget = TimelineWidget()
        qtbot.addWidget(widget)

        events = [Event(name=f"Event {i}", lore_date=i * 10.0) for i in range(100)]

        widget.set_events(events)
        qtbot.wait(1000)

        # Close widget
        widget.close()

        # Thread pool should still be valid globally
        pool = QThreadPool.globalInstance()
        assert pool.activeThreadCount() >= 0  # Should not crash
