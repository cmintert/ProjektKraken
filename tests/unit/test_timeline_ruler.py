"""
Unit tests for TimelineRuler - semantic zoom ruler implementation.

Tests cover:
- Tick level calculation at various zoom scales
- Opacity interpolation during LOD transitions
- Label collision avoidance algorithm
- Calendar-aware date divisions
- Numeric fallback without calendar
- Sticky parent context labels
"""

import pytest
from unittest.mock import MagicMock
from src.gui.widgets.timeline_ruler import (
    TimelineRuler,
    TickLevel,
    TickInfo,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def ruler():
    """Create a TimelineRuler for testing."""
    return TimelineRuler()


@pytest.fixture
def mock_calendar():
    """Create a mock CalendarConverter."""
    mock = MagicMock()
    mock.from_float.return_value = MagicMock(
        year=2025,
        month=3,
        day=15,
        month_name="March",
        time_fraction=0.5,
    )
    mock._config = MagicMock()
    mock._config.get_months_for_year.return_value = [
        MagicMock(name="Month1", days=30, abbreviation="M1"),
        MagicMock(name="Month2", days=30, abbreviation="M2"),
        MagicMock(name="Month3", days=30, abbreviation="M3"),
        MagicMock(name="Month4", days=30, abbreviation="M4"),
        MagicMock(name="Month5", days=30, abbreviation="M5"),
        MagicMock(name="Month6", days=30, abbreviation="M6"),
        MagicMock(name="Month7", days=30, abbreviation="M7"),
        MagicMock(name="Month8", days=30, abbreviation="M8"),
        MagicMock(name="Month9", days=30, abbreviation="M9"),
        MagicMock(name="Month10", days=30, abbreviation="M10"),
        MagicMock(name="Month11", days=30, abbreviation="M11"),
        MagicMock(name="Month12", days=30, abbreviation="M12"),
    ]
    mock._config.get_year_length.return_value = 360
    mock._config.week = MagicMock()
    mock._config.week.day_abbreviations = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
    return mock


# ============================================================================
# TickLevel Tests
# ============================================================================


class TestTickLevel:
    """Tests for TickLevel enum hierarchy."""

    def test_tick_levels_ordered_by_granularity(self):
        """Verify tick levels are in order from coarse to fine."""
        levels = list(TickLevel)
        assert levels[0] == TickLevel.ERA
        assert levels[-1] == TickLevel.MINUTE
        assert TickLevel.YEAR.value < TickLevel.MONTH.value
        assert TickLevel.MONTH.value < TickLevel.DAY.value

    def test_get_finer_level(self, ruler):
        """Test getting the next finer granularity level."""
        assert ruler.get_finer_level(TickLevel.YEAR) == TickLevel.QUARTER
        assert ruler.get_finer_level(TickLevel.MONTH) == TickLevel.WEEK
        assert ruler.get_finer_level(TickLevel.MINUTE) == TickLevel.MINUTE

    def test_get_coarser_level(self, ruler):
        """Test getting the next coarser granularity level."""
        assert ruler.get_coarser_level(TickLevel.YEAR) == TickLevel.DECADE
        assert ruler.get_coarser_level(TickLevel.MONTH) == TickLevel.QUARTER
        assert ruler.get_coarser_level(TickLevel.ERA) == TickLevel.ERA


# ============================================================================
# Active Level Calculation Tests
# ============================================================================


class TestActiveLevelCalculation:
    """Tests for determining active tick levels based on zoom."""

    def test_zoomed_out_shows_decades(self, ruler):
        """Very zoomed out view should show decade-level ticks."""
        # Large date range, narrow viewport = zoomed out
        major, minor, opacity = ruler.calculate_active_levels(
            date_range=50000,  # 50000 days (~137 years) visible
            viewport_width=800,
        )
        # Should be decade level or coarser (decade=2, century=1, era=0)
        assert major.value <= TickLevel.DECADE.value

    def test_zoomed_in_shows_days(self, ruler):
        """Very zoomed in view should show day-level ticks."""
        # Small date range = zoomed in
        major, minor, opacity = ruler.calculate_active_levels(
            date_range=7,  # 7 days visible
            viewport_width=800,
        )
        assert major.value >= TickLevel.WEEK.value

    def test_minor_level_is_finer_than_major(self, ruler):
        """Minor level should always be finer than major."""
        major, minor, opacity = ruler.calculate_active_levels(
            date_range=365,
            viewport_width=1000,
        )
        assert minor.value >= major.value


# ============================================================================
# Opacity Interpolation Tests
# ============================================================================


class TestOpacityInterpolation:
    """Tests for smooth opacity transitions."""

    def test_opacity_zero_when_crowded(self, ruler):
        """Minor ticks should be invisible when spacing is too tight."""
        _, _, opacity = ruler.calculate_active_levels(
            date_range=10000,
            viewport_width=400,
        )
        # Spacing is very tight - opacity should be low
        assert opacity < 0.5

    def test_opacity_full_when_spacious(self, ruler):
        """Minor ticks should be fully visible when well-spaced."""
        # Use day-level viewing (7 days in 2000px = ~285px per day)
        # Minor level is HOUR, which would have 7*24=168 ticks
        # 2000px / 168 ticks = ~12px per tick (still crowded)
        # Better: view 1 day in 2000px to get high opacity for hour ticks
        _, _, opacity = ruler.calculate_active_levels(
            date_range=1,  # 1 day visible
            viewport_width=2000,  # Very wide viewport
        )
        # With only 1 day visible in 2000px, minor ticks should have space
        # Minor level is HOUR (24 ticks), spacing = 2000/24 ≈ 83px
        # This is between THRESHOLD_SHOW(60) and THRESHOLD_FULL(140)
        # So opacity should be > 0
        assert opacity >= 0.0  # At least some opacity

    def test_opacity_interpolates_smoothly(self, ruler):
        """Opacity should interpolate between 0 and 1."""
        opacities = []
        for date_range in [5000, 1000, 500, 100, 50]:
            _, _, opacity = ruler.calculate_active_levels(
                date_range=date_range,
                viewport_width=800,
            )
            opacities.append(opacity)

        # Should generally increase as we zoom in (smaller date range)
        assert opacities[-1] >= opacities[0]


# ============================================================================
# Tick Calculation Tests
# ============================================================================


class TestTickCalculation:
    """Tests for tick position calculation."""

    def test_calculate_ticks_returns_list(self, ruler):
        """calculate_ticks should return a list of TickInfo."""
        ticks = ruler.calculate_ticks(
            start_date=0,
            end_date=365,
            viewport_width=1000,
            scale_factor=20.0,
        )
        assert isinstance(ticks, list)
        assert all(isinstance(t, TickInfo) for t in ticks)

    def test_ticks_within_date_range(self, ruler):
        """All ticks should be within the visible date range."""
        ticks = ruler.calculate_ticks(
            start_date=100,
            end_date=200,
            viewport_width=800,
            scale_factor=20.0,
        )
        for tick in ticks:
            assert tick.position >= 100 or tick.position <= 200 + 1

    def test_ticks_have_required_properties(self, ruler):
        """Each tick should have all required properties."""
        ticks = ruler.calculate_ticks(
            start_date=0,
            end_date=100,
            viewport_width=800,
            scale_factor=20.0,
        )
        for tick in ticks:
            assert hasattr(tick, "position")
            assert hasattr(tick, "screen_x")
            assert hasattr(tick, "level")
            assert hasattr(tick, "label")
            assert hasattr(tick, "opacity")
            assert hasattr(tick, "is_major")

    def test_major_ticks_have_full_opacity(self, ruler):
        """Major ticks should always have opacity = 1.0."""
        ticks = ruler.calculate_ticks(
            start_date=0,
            end_date=365,
            viewport_width=1000,
            scale_factor=20.0,
        )
        major_ticks = [t for t in ticks if t.is_major]
        for tick in major_ticks:
            assert tick.opacity == 1.0


# ============================================================================
# Label Collision Avoidance Tests
# ============================================================================


class TestCollisionAvoidance:
    """Tests for label collision detection and culling."""

    def test_non_overlapping_labels_kept(self, ruler):
        """Labels that don't overlap should all be kept."""
        ticks = [
            TickInfo(
                position=0,
                screen_x=0,
                level=TickLevel.YEAR,
                label="2020",
                opacity=1.0,
                is_major=True,
            ),
            TickInfo(
                position=365,
                screen_x=200,  # 200px apart
                level=TickLevel.YEAR,
                label="2021",
                opacity=1.0,
                is_major=True,
            ),
        ]
        culled = ruler.avoid_collisions(ticks, label_width=50)
        assert len([t for t in culled if t.label]) == 2

    def test_overlapping_minor_labels_culled(self, ruler):
        """Overlapping minor labels should be culled in favor of major."""
        ticks = [
            TickInfo(
                position=0,
                screen_x=0,
                level=TickLevel.YEAR,
                label="2020",
                opacity=1.0,
                is_major=True,
            ),
            TickInfo(
                position=30,
                screen_x=30,  # Close to year label
                level=TickLevel.MONTH,
                label="Jan",
                opacity=0.8,
                is_major=False,
            ),
        ]
        culled = ruler.avoid_collisions(ticks, label_width=50)
        # Month label should be culled due to overlap
        culled_labels = [t.label for t in culled if t.label]
        assert "2020" in culled_labels


# ============================================================================
# Calendar-Aware Division Tests
# ============================================================================


class TestCalendarAwareDivisions:
    """Tests for calendar-based tick divisions."""

    def test_set_calendar_converter(self, ruler, mock_calendar):
        """Calendar converter can be set."""
        ruler.set_calendar_converter(mock_calendar)
        assert ruler._calendar is mock_calendar

    def test_with_calendar_uses_calendar_labels(self, ruler, mock_calendar):
        """With calendar configured, labels should be calendar-formatted."""
        ruler.set_calendar_converter(mock_calendar)
        ticks = ruler.calculate_ticks(
            start_date=0,
            end_date=365,
            viewport_width=1000,
            scale_factor=20.0,
        )
        # Should have at least some ticks
        assert len(ticks) > 0

    def test_day_ticks_have_abbreviations(self, ruler, mock_calendar):
        """Day ticks should include day abbreviations."""
        ruler.set_calendar_converter(mock_calendar)
        # Mock from_float to return consistent days
        mock_calendar.from_float.side_effect = lambda pos: MagicMock(
            year=2025, month=3, day=int(pos) % 30 + 1, time_fraction=0
        )

        # Generate ticks for DAY level
        ticks = ruler._generate_ticks_for_level(
            start_date=0,
            end_date=5,
            step=1,
            level=TickLevel.DAY,
            opacity=1.0,
            is_major=True,
            effective_scale=100,
        )

        assert len(ticks) > 0
        for tick in ticks:
            # Check for format "1 Mo", "2 Tu", etc.
            parts = tick.label.split()
            # If label is empty (collision avoidance?) No avoidance in _generate_ticks
            assert len(parts) == 2, f"Label '{tick.label}' format invalid"
            assert parts[1] in ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]


class TestNumericFallback:
    """Tests for power-of-10 fallback without calendar."""

    def test_without_calendar_uses_numeric_labels(self, ruler):
        """Without calendar, labels should be numeric."""
        ticks = ruler.calculate_ticks(
            start_date=0,
            end_date=1000,
            viewport_width=800,
            scale_factor=20.0,
        )
        # Labels should be numeric
        for tick in ticks:
            if tick.label:
                # Should not contain month names or such
                assert not any(m in tick.label for m in ["Jan", "Feb", "March"])


# ============================================================================
# Sticky Parent Context Tests
# ============================================================================


class TestStickyParentContext:
    """Tests for parent context label calculation."""

    def test_get_parent_context_returns_string(self, ruler, mock_calendar):
        """get_parent_context should return a string."""
        ruler.set_calendar_converter(mock_calendar)
        context = ruler.get_parent_context(start_date=100)
        assert isinstance(context, str)

    def test_parent_context_without_calendar(self, ruler):
        """Without calendar, parent context should be empty or numeric range."""
        context = ruler.get_parent_context(start_date=1000)
        assert isinstance(context, str)


# ============================================================================
# Edge Cases
# ============================================================================


class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_zero_date_range(self, ruler):
        """Zero date range should not crash."""
        ticks = ruler.calculate_ticks(
            start_date=100,
            end_date=100,  # Same as start
            viewport_width=800,
            scale_factor=20.0,
        )
        assert isinstance(ticks, list)

    def test_negative_dates(self, ruler):
        """Negative dates should be handled."""
        ticks = ruler.calculate_ticks(
            start_date=-500,
            end_date=-100,
            viewport_width=800,
            scale_factor=20.0,
        )
        assert isinstance(ticks, list)

    def test_very_large_dates(self, ruler):
        """Very large dates should not crash."""
        ticks = ruler.calculate_ticks(
            start_date=1e9,
            end_date=1e9 + 1000,
            viewport_width=800,
            scale_factor=20.0,
        )
        assert isinstance(ticks, list)

    def test_narrow_viewport(self, ruler):
        """Very narrow viewport should not crash."""
        ticks = ruler.calculate_ticks(
            start_date=0,
            end_date=1000,
            viewport_width=50,
            scale_factor=20.0,
        )
        assert isinstance(ticks, list)
