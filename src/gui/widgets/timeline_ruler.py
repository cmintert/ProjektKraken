"""Timeline Ruler Module.

Provides semantic zoom ruler with Aeon Timeline-style behavior:
- Level-of-detail (LOD) transitions between temporal granularities
- Opacity interpolation for smooth fade-in of minor ticks
- Label collision avoidance with priority-based culling
- Sticky parent context labels
- Calendar-aware date divisions
"""

import logging
import math
from collections.abc import Iterator
from dataclasses import dataclass
from enum import IntEnum
from typing import TYPE_CHECKING, List, Optional, Tuple

from src.core.calendar import CalendarDate

logger = logging.getLogger(__name__)

_BILLION = 1e9
_MILLION = 1e6
_TEN_THOUSAND = 1e4
_THOUSAND = 1e3
_HUNDREDTH = 0.01

if TYPE_CHECKING:
    from src.core.calendar import CalendarConverter


class TickLevel(IntEnum):
    """Temporal granularity levels for ruler ticks.

    Ordered from coarsest (ERA) to finest (MINUTE). Used to determine which ticks to
    display at each zoom level.
    """

    ERA = 0
    CENTURY = 1
    DECADE = 2
    YEAR = 3
    QUARTER = 4
    MONTH = 5
    WEEK = 6
    DAY = 7
    HOUR = 8
    MINUTE = 9


@dataclass
class TickInfo:
    """Information about a single ruler tick.

    Attributes:
        position: Float position in lore_date units.
        screen_x: Pixel position on screen.
        level: TickLevel indicating the granularity.
        label: Display text for this tick.
        opacity: Float 0.0-1.0 for fade-in effect.
        is_major: Whether this is a major (always visible) tick.

    """

    position: float
    screen_x: float
    level: TickLevel
    label: str
    opacity: float
    is_major: bool


class TimelineRuler:
    """Semantic zoom ruler engine.

    Calculates tick positions and labels based on visible date range and viewport size.
    Implements smooth LOD transitions, label collision avoidance, and calendar-aware
    date divisions.
    """

    # Spacing thresholds for LOD transitions (in pixels)
    THRESHOLD_SHOW = 40  # Minor ticks start appearing
    THRESHOLD_FULL = 100  # Minor ticks fully opaque

    # Target spacing between major ticks (pixels)
    TARGET_MAJOR_SPACING = 100
    MAX_TICKS = 500
    MONTHS_PER_YEAR = 12
    MONTHS_PER_QUARTER = 3
    YEAR_SPANS = {
        TickLevel.ERA: 1000,
        TickLevel.CENTURY: 100,
        TickLevel.DECADE: 10,
        TickLevel.YEAR: 1,
    }
    TIME_UNITS = {TickLevel.HOUR: 24, TickLevel.MINUTE: 1440}

    # Level step sizes (in days) for numeric mode
    NUMERIC_LEVEL_STEPS = {
        TickLevel.ERA: 365000,  # ~1000 years
        TickLevel.CENTURY: 36500,  # 100 years
        TickLevel.DECADE: 3650,  # 10 years
        TickLevel.YEAR: 365,  # 1 year
        TickLevel.QUARTER: 91,  # ~3 months
        TickLevel.MONTH: 30,  # 1 month
        TickLevel.WEEK: 7,  # 1 week
        TickLevel.DAY: 1,  # 1 day
        TickLevel.HOUR: 1 / 24,  # 1 hour
        TickLevel.MINUTE: 1 / 1440,  # 1 minute
    }

    def __init__(self) -> None:
        """Initializes the TimelineRuler."""
        self._calendar: Optional["CalendarConverter"] = None

    def set_calendar_converter(self, converter: Optional["CalendarConverter"]) -> None:
        """Sets the calendar converter for date-based divisions.

        Args:
            converter: CalendarConverter instance or None for numeric mode.

        """
        self._calendar = converter

    def get_finer_level(self, level: TickLevel) -> TickLevel:
        """Gets the next finer granularity level.

        Args:
            level: Current tick level.

        Returns:
            TickLevel: Next finer level, or same if already finest.

        """
        if level.value < TickLevel.MINUTE.value:
            return TickLevel(level.value + 1)
        return level

    def get_coarser_level(self, level: TickLevel) -> TickLevel:
        """Gets the next coarser granularity level.

        Args:
            level: Current tick level.

        Returns:
            TickLevel: Next coarser level, or same if already coarsest.

        """
        if level.value > TickLevel.ERA.value:
            return TickLevel(level.value - 1)
        return level

    def calculate_active_levels(
        self, date_range: float, viewport_width: float
    ) -> Tuple[TickLevel, TickLevel, float]:
        """Calculates the active major and minor tick levels based on zoom.

        Args:
            date_range: Number of days visible in the viewport.
            viewport_width: Width of viewport in pixels.

        Returns:
            Tuple of (major_level, minor_level, minor_opacity).

        """
        if date_range <= 0 or viewport_width <= 0:
            return TickLevel.YEAR, TickLevel.MONTH, 0.0

        # Find the finest level that has acceptable spacing
        # Start from finest (MINUTE) and work backwards to find acceptable level
        best_level = TickLevel.ERA

        for level in reversed(list(TickLevel)):
            step = self.NUMERIC_LEVEL_STEPS[level]
            num_ticks = date_range / step
            if num_ticks > 0:
                spacing = viewport_width / num_ticks
                # Accept this level if spacing is at least half the target
                if spacing >= self.TARGET_MAJOR_SPACING / 2:
                    best_level = level
                    break  # Found finest acceptable level

        # Minor level is one step finer
        minor_level = self.get_finer_level(best_level)

        return (
            best_level,
            minor_level,
            self._minor_opacity(date_range, viewport_width, minor_level),
        )

    def _minor_opacity(
        self, date_range: float, viewport_width: float, level: TickLevel
    ) -> float:
        """Calculate the fade using the existing spacing thresholds."""
        minor_step = self.NUMERIC_LEVEL_STEPS[level]
        minor_num_ticks = max(1, date_range / minor_step)
        minor_spacing = viewport_width / minor_num_ticks

        if minor_spacing < self.THRESHOLD_SHOW:
            minor_opacity = 0.0
        elif minor_spacing > self.THRESHOLD_FULL:
            minor_opacity = 1.0
        else:
            minor_opacity = (minor_spacing - self.THRESHOLD_SHOW) / (
                self.THRESHOLD_FULL - self.THRESHOLD_SHOW
            )

        return minor_opacity

    def _supports_quarters(self, start_date: float, end_date: float) -> bool:
        """Return whether every visible year has exactly twelve months."""
        if self._calendar is None:
            return True
        config = self._calendar._config
        if len(config.months) == self.MONTHS_PER_YEAR and all(
            len(variant.months) == self.MONTHS_PER_YEAR
            for variant in config.year_variants
        ):
            return True
        if len(config.months) != self.MONTHS_PER_YEAR and not config.year_variants:
            return False
        first_year = self._calendar.from_float(start_date).year
        last_year = self._calendar.from_float(end_date).year
        variant_years = {
            variant.year
            for variant in config.year_variants
            if first_year <= variant.year <= last_year
        }
        if len(config.months) != self.MONTHS_PER_YEAR and len(variant_years) != (
            last_year - first_year + 1
        ):
            return False
        return all(
            len(config.get_months_for_year(year)) == self.MONTHS_PER_YEAR
            for year in variant_years
        )

    def calculate_ticks(
        self,
        start_date: float,
        end_date: float,
        viewport_width: float,
        scale_factor: float,
    ) -> List[TickInfo]:
        """Calculates all ticks for the visible date range.

        Args:
            start_date: Left edge date value.
            end_date: Right edge date value.
            viewport_width: Width of viewport in pixels.
            scale_factor: Pixels per day factor.

        Returns:
            List of TickInfo objects for rendering.

        """
        date_range = end_date - start_date
        if (
            not all(math.isfinite(v) for v in (start_date, end_date, viewport_width))
            or not math.isfinite(date_range)
            or date_range <= 0
            or viewport_width <= 0
        ):
            return []

        major_level, minor_level, minor_opacity = self.calculate_active_levels(
            date_range, viewport_width
        )
        if TickLevel.QUARTER in (
            major_level,
            minor_level,
        ) and not self._supports_quarters(start_date, end_date):
            major_level, minor_level = TickLevel.YEAR, TickLevel.MONTH
            minor_opacity = self._minor_opacity(date_range, viewport_width, minor_level)
        if (
            self._calendar is not None
            and TickLevel.WEEK in (major_level, minor_level)
            and not self._calendar._config.week.day_names
        ):
            major_level, minor_level = TickLevel.MONTH, TickLevel.DAY
            minor_opacity = self._minor_opacity(date_range, viewport_width, minor_level)

        # Calculate effective scale for screen_x (pixels per day in viewport)
        effective_scale = viewport_width / date_range

        ticks: List[TickInfo] = []

        # Generate major ticks
        major_step = self.NUMERIC_LEVEL_STEPS[major_level]
        ticks.extend(
            self._generate_ticks_for_level(
                start_date,
                end_date,
                major_step,
                major_level,
                1.0,
                True,
                effective_scale,
            )
        )

        # Generate minor ticks if visible
        if minor_opacity > 0 and minor_level != major_level:
            minor_step = self.NUMERIC_LEVEL_STEPS[minor_level]
            ticks.extend(
                self._generate_ticks_for_level(
                    start_date,
                    end_date,
                    minor_step,
                    minor_level,
                    minor_opacity,
                    False,
                    effective_scale,
                )
            )

        # Calendar levels share exact boundaries. Keep the major tick at each one.
        if self._calendar is not None:
            ticks = list({tick.position: tick for tick in reversed(ticks)}.values())

        # Sort by position
        ticks.sort(key=lambda t: t.position)

        return ticks

    def _generate_ticks_for_level(
        self,
        start_date: float,
        end_date: float,
        step: float,
        level: TickLevel,
        opacity: float,
        is_major: bool,
        effective_scale: float,
    ) -> List[TickInfo]:
        """Generates ticks for a specific level.

        Args:
            start_date: Start of visible range.
            end_date: End of visible range.
            step: Interval between ticks.
            level: TickLevel for these ticks.
            opacity: Opacity value for these ticks.
            is_major: Whether these are major ticks.
            effective_scale: Effective pixels per day (viewport_width / date_range).

        Returns:
            List of TickInfo objects.

        """
        if self._calendar is not None and level <= TickLevel.MONTH:
            boundaries = self._calendar_boundaries(start_date, end_date, level)
            return [
                TickInfo(
                    position=position,
                    screen_x=(position - start_date) * effective_scale,
                    level=level,
                    label=self._format_calendar_label(position, level, date),
                    opacity=opacity,
                    is_major=is_major,
                )
                for position, date in boundaries
            ]

        if self._calendar is not None and level == TickLevel.WEEK:
            step = len(self._calendar._config.week.day_names)
        if step <= 0:
            return []

        # Include one boundary preceding the viewport. Derive every position from
        # its integer index so fractional-day rounding cannot accumulate.
        units = self.TIME_UNITS.get(level)
        first_index = math.floor(start_date * units if units else start_date / step)
        ticks: List[TickInfo] = []
        for index in range(first_index, first_index + self.MAX_TICKS):
            position = index / units if units else index * step
            if position > end_date:
                break
            ticks.append(
                TickInfo(
                    position=position,
                    screen_x=(position - start_date) * effective_scale,
                    level=level,
                    label=self._format_label(position, level),
                    opacity=opacity,
                    is_major=is_major,
                )
            )
        return ticks

    def _calendar_boundaries(
        self, start_date: float, end_date: float, level: TickLevel
    ) -> Iterator[tuple[float, CalendarDate]]:
        """Yield at most 500 real boundaries, including the preceding boundary.

        Year spans are anchored to year one. Month traversal uses each year's
        actual month list, including variants and the transition through year zero.
        """
        calendar = self._calendar
        if calendar is None:
            return
        if level == TickLevel.QUARTER and not self._supports_quarters(
            start_date, end_date
        ):
            return
        start = calendar.from_float(start_date)
        year_span = self.YEAR_SPANS.get(level)
        month_span = self.MONTHS_PER_QUARTER if level == TickLevel.QUARTER else 1
        year = start.year
        month = 1
        if year_span is not None:
            year = 1 + ((year - 1) // year_span) * year_span
        else:
            month = 1 + ((start.month - 1) // month_span) * month_span

        for _ in range(self.MAX_TICKS):
            date = CalendarDate(year, month, 1)
            position = calendar.to_float(date)
            if position > end_date:
                return
            yield position, date
            if year_span is not None:
                year += year_span
            else:
                month += month_span
                if month > len(calendar._config.get_months_for_year(year)):
                    year += 1
                    month = 1

    def _format_label(self, position: float, level: TickLevel) -> str:
        """Formats a label for a tick position.

        Args:
            position: Date position in lore_date units.
            level: Tick level for formatting context.

        Returns:
            Formatted label string.

        """
        if self._calendar:
            return self._format_calendar_label(position, level)
        return self._format_numeric_label(position, level)

    def _format_calendar_label(
        self, position: float, level: TickLevel, date: CalendarDate | None = None
    ) -> str:
        """Formats a label using the calendar converter.

        Args:
            position: Date position.
            level: Tick level.
            date: Exact boundary date when generated by calendar traversal.

        Returns:
            Calendar-formatted label.

        """
        try:
            if not self._calendar:
                return self._format_numeric_label(position, level)

            if level in self.TIME_UNITS:
                # Tick positions can land a fraction of an ULP before a minute.
                # Round to the known tick unit instead of truncating clock fields.
                return self._format_clock_label(position, level)

            if date is None:
                date = self._calendar.from_float(position)

            if level <= TickLevel.DECADE:
                # Show year (possibly with era)
                return str(date.year)
            elif level <= TickLevel.YEAR:
                return str(date.year)
            elif level == TickLevel.QUARTER:
                # Show year and quarter
                q = (date.month - 1) // 3 + 1
                return f"Q{q}"
            elif level == TickLevel.MONTH:
                # Show month abbreviation from calendar config
                months = self._calendar._config.get_months_for_year(date.year)
                if date.month <= len(months):
                    abbrev = months[date.month - 1].abbreviation
                    return abbrev
                return f"M{date.month}"
            elif level == TickLevel.WEEK or level == TickLevel.DAY:
                day_str = str(date.day)
                try:
                    week_config = self._calendar._config.week
                    if week_config.day_names:
                        # Use floor to handle negative positions correctly
                        day_idx = math.floor(position) % len(week_config.day_names)
                        if day_idx < len(week_config.day_abbreviations):
                            abbrev = week_config.day_abbreviations[day_idx]
                            return f"{day_str} {abbrev}"
                except (AttributeError, ValueError, IndexError):
                    # Week config may be unavailable or misconfigured
                    pass

                return day_str
            else:
                return str(date.year)
        except Exception as e:
            logger.warning(
                f"Calendar label formatting failed at position {position}: {e}"
            )
            return self._format_numeric_label(position, level)

    def _format_clock_label(self, position: float, level: TickLevel) -> str:
        """Format an hour/minute tick without truncation or negative-day drift."""
        units = self.TIME_UNITS[level]
        clock_unit = round(position * units) % units
        minutes = clock_unit * (60 if level == TickLevel.HOUR else 1)
        return f"{minutes // 60:02d}:{minutes % 60:02d}"

    def _format_numeric_label(self, position: float, level: TickLevel) -> str:
        """Formats a numeric (non-calendar) label.

        Args:
            position: Date position (in days, where 1.0 = 1 day).
            level: Tick level.

        Returns:
            Numeric label string.

        """
        # Handle sub-day levels with time formatting
        if level in self.TIME_UNITS:
            return self._format_clock_label(position, level)
        elif level == TickLevel.DAY:
            # Show day number
            day_num = int(position) % 30 + 1
            return f"D{day_num}"
        elif level == TickLevel.WEEK:
            # Show week number
            week_num = int(position / 7) % 52 + 1
            return f"W{week_num}"
        elif level == TickLevel.MONTH:
            # Show month number
            month_num = int(position / 30) % 12 + 1
            return f"M{month_num}"
        elif level == TickLevel.QUARTER:
            # Show quarter
            quarter = int(position / 91) % 4 + 1
            return f"Q{quarter}"
        elif level == TickLevel.YEAR:
            # Show year
            year = int(position / 365) + 1
            return f"Y{year}"

        # Handle standard numeric formatting for decade+ levels
        abs_pos = abs(position)
        if abs_pos >= _BILLION:
            return f"{position / _BILLION:.1f}B"
        elif abs_pos >= _MILLION:
            return f"{position / _MILLION:.1f}M"
        elif abs_pos >= _TEN_THOUSAND:
            return f"{position / _THOUSAND:.0f}k"
        elif abs_pos >= 1:
            return f"{position:.0f}"
        elif abs_pos >= _HUNDREDTH:
            return f"{position:.2f}"
        else:
            return f"{position:.4f}"

    def avoid_collisions(
        self, ticks: List[TickInfo], label_width: float = 50
    ) -> List[TickInfo]:
        """Removes labels that would overlap with higher-priority labels.

        Args:
            ticks: List of tick info objects.
            label_width: Estimated width of labels in pixels.

        Returns:
            List of ticks with some labels cleared to avoid overlap.

        """
        if not ticks:
            return ticks

        # Sort by screen position
        sorted_ticks = sorted(ticks, key=lambda t: t.screen_x)

        # Track occupied label regions
        occupied_regions: List[Tuple[float, float]] = []  # (start_x, end_x)

        def is_overlapping(x: float, width: float) -> bool:
            """Check if a label would overlap with existing labels."""
            for start, end in occupied_regions:
                if x < end and x + width > start:
                    return True
            return False

        result: List[TickInfo] = []

        # Process all ticks in position order
        for tick in sorted_ticks:
            # Calculate label width based on tick type
            effective_width = label_width if tick.is_major else label_width * 0.8

            if tick.label and is_overlapping(tick.screen_x, effective_width):
                # Keep tick but clear label
                result.append(
                    TickInfo(
                        position=tick.position,
                        screen_x=tick.screen_x,
                        level=tick.level,
                        label="",
                        opacity=tick.opacity,
                        is_major=tick.is_major,
                    )
                )
            else:
                result.append(tick)
                if tick.label:
                    occupied_regions.append(
                        (tick.screen_x, tick.screen_x + effective_width)
                    )

        return result

    def get_parent_context(
        self, start_date: float, level: TickLevel = TickLevel.YEAR
    ) -> str:
        """Gets the parent context label for sticky display.

        Args:
            start_date: Left edge date value.
            level: Active major ruler level.

        Returns:
            Context string (e.g., "Year 2025").

        """
        if self._calendar:
            try:
                date = self._calendar.from_float(start_date)
                if level >= TickLevel.HOUR:
                    return self._calendar.format_date(float(math.floor(start_date)))
                if level in (TickLevel.WEEK, TickLevel.DAY):
                    month_name = date.month_name or f"Month {date.month}"
                    return f"Year {date.year}, {month_name}"
                return f"Year {date.year}"
            except (AttributeError, ValueError):
                # Calendar conversion may fail for extreme dates
                pass
        # Numeric fallback
        if level >= TickLevel.WEEK:
            return f"Day {math.floor(start_date) + 1}"
        if abs(start_date) >= _MILLION:
            return f"~{start_date / _MILLION:.0f}M"
        elif abs(start_date) >= _THOUSAND:
            return f"~{start_date / _THOUSAND:.0f}k"
        else:
            return f"~{start_date:.0f}"
