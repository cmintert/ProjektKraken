"""
Tests for TimelineView fit_all functionality.
"""

import pytest

from src.core.events import Event
from src.gui.widgets.timeline import TimelineView


@pytest.fixture
def timeline_view(qtbot):
    """Create TimelineView for testing."""
    view = TimelineView()
    qtbot.addWidget(view)
    view.resize(800, 600)  # Ensure non-zero size
    return view


@pytest.fixture
def sample_events():
    """Sample events for testing."""
    return [
        Event(id="e1", name="Event 1", lore_date=100.0, type="cosmic"),
        Event(id="e2", name="Event 2", lore_date=200.0, type="combat"),
    ]


class TestFitAll:
    """Tests for fit_all method."""

    def test_fit_all_events_only(self, timeline_view, sample_events):
        """Test fit_all with only events (existing behavior compatibility)."""
        timeline_view.set_events(sample_events)

        # Initial range is 100 to 200.
        # Margin is 10% of 100 = 10.
        # Expected range approx 90 to 210.

        timeline_view.fit_all()

        # Check that we can see the range
        # mapping 0,0 and width,0 to scene coords
        viewport_rect = timeline_view.viewport().rect()
        left_scene = timeline_view.mapToScene(viewport_rect.topLeft()).x()
        right_scene = timeline_view.mapToScene(viewport_rect.topRight()).x()

        start_date = left_scene / timeline_view.scale_factor
        end_date = right_scene / timeline_view.scale_factor

        assert start_date <= 100.0
        assert end_date >= 200.0

    def test_fit_all_includes_playhead(self, timeline_view, sample_events):
        """Test that fit_all extends range to include playhead."""
        timeline_view.set_events(sample_events)

        # Set playhead far out
        timeline_view.set_playhead_time(500.0)

        timeline_view.fit_all()

        viewport_rect = timeline_view.viewport().rect()
        right_scene = timeline_view.mapToScene(viewport_rect.topRight()).x()
        end_date = right_scene / timeline_view.scale_factor

        # Should now find 500 inside the view
        assert end_date >= 500.0

    def test_fit_all_includes_current_time(self, timeline_view, sample_events):
        """Test that fit_all extends range to include current time line."""
        timeline_view.set_events(sample_events)

        # Set current time far out in negative
        timeline_view.set_current_time(-100.0)

        # Ensure it is visible implies we should fit it
        # (It is shown by default when set, usually)

        timeline_view.fit_all()

        viewport_rect = timeline_view.viewport().rect()
        left_scene = timeline_view.mapToScene(viewport_rect.topLeft()).x()
        start_date = left_scene / timeline_view.scale_factor

        # Should now find -100 inside the view
        assert start_date <= -100.0

    def test_fit_all_no_events_only_playhead(self, timeline_view):
        """Test fit_all with no events, only playhead."""
        timeline_view.set_playhead_time(1000.0)

        timeline_view.fit_all()

        # visual check: playhead should be centered roughly
        viewport_rect = timeline_view.viewport().rect()

        # Margin around single point is default 10 units in existing logic
        # (for single event). We expect something similar.

        left_scene = timeline_view.mapToScene(viewport_rect.topLeft()).x()
        right_scene = timeline_view.mapToScene(viewport_rect.topRight()).x()
        start_date = left_scene / timeline_view.scale_factor
        end_date = right_scene / timeline_view.scale_factor

        assert start_date <= 1000.0 <= end_date

    def test_fit_all_playhead_and_current_time_extreme(self, timeline_view):
        """Test fitting playhead and current time when they are far apart."""
        timeline_view.set_playhead_time(-1000.0)
        timeline_view.set_current_time(1000.0)

        timeline_view.fit_all()

        viewport_rect = timeline_view.viewport().rect()
        left_scene = timeline_view.mapToScene(viewport_rect.topLeft()).x()
        right_scene = timeline_view.mapToScene(viewport_rect.topRight()).x()

        start_date = left_scene / timeline_view.scale_factor
        end_date = right_scene / timeline_view.scale_factor

        assert start_date <= -1000.0
        assert end_date >= 1000.0
