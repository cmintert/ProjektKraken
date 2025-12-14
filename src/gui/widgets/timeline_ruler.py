"""
Timeline Ruler Module.

Provides semantic zoom ruler with Aeon Timeline-style behavior:
- Level-of-detail (LOD) transitions between temporal granularities
- Opacity interpolation for smooth fade-in of minor ticks
- Label collision avoidance with priority-based culling
- Sticky parent context labels
- Calendar-aware date divisions
"""

from dataclasses import dataclass
from enum import IntEnum
from typing import List, Tuple, Optional, TYPE_CHECKING
import math

if TYPE_CHECKING:
    from src.core.calendar import CalendarConverter


class TickLevel(IntEnum):
    """
    Temporal granularity levels for ruler ticks.

    Ordered from coarsest (ERA) to finest (MINUTE).
    Used to determine which ticks to display at each zoom level.
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
    """
    Information about a single ruler tick.

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
    """
    Semantic zoom ruler engine.

    Calculates tick positions and labels based on visible date range
    and viewport size. Implements smooth LOD transitions, label
    collision avoidance, and calendar-aware date divisions.
    """

    # Spacing thresholds for LOD transitions (in pixels)
    THRESHOLD_SHOW = 60  # Minor ticks start appearing
    THRESHOLD_FULL = 140  # Minor ticks fully opaque

    # Target spacing between major ticks (pixels)
    TARGET_MAJOR_SPACING = 120

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
        """
        Sets the calendar converter for date-based divisions.

        Args:
            converter: CalendarConverter instance or None for numeric mode.
        """
        self._calendar = converter

    def get_finer_level(self, level: TickLevel) -> TickLevel:
        """
        Gets the next finer granularity level.

        Args:
            level: Current tick level.

        Returns:
            TickLevel: Next finer level, or same if already finest.
        """
        if level.value < TickLevel.MINUTE.value:
            return TickLevel(level.value + 1)
        return level

    def get_coarser_level(self, level: TickLevel) -> TickLevel:
        """
        Gets the next coarser granularity level.

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
        """
        Calculates the active major and minor tick levels based on zoom.

        Args:
            date_range: Number of days visible in the viewport.
            viewport_width: Width of viewport in pixels.

        Returns:
            Tuple of (major_level, minor_level, minor_opacity).
        """
        if date_range <= 0 or viewport_width <= 0:
            return TickLevel.YEAR, TickLevel.MONTH, 0.0

        # Find the best major level based on spacing
        best_level = TickLevel.ERA
        best_spacing = 0.0

        for level in TickLevel:
            step = self.NUMERIC_LEVEL_STEPS[level]
            num_ticks = date_range / step
            if num_ticks > 0:
                spacing = viewport_width / num_ticks
                if spacing >= self.TARGET_MAJOR_SPACING / 2:
                    if spacing > best_spacing or level.value > best_level.value:
                        best_level = level
                        best_spacing = spacing

        # If spacing is too tight, go coarser
        while best_spacing < self.TARGET_MAJOR_SPACING / 2:
            best_level = self.get_coarser_level(best_level)
            if best_level == TickLevel.ERA:
                break
            step = self.NUMERIC_LEVEL_STEPS[best_level]
            num_ticks = max(1, date_range / step)
            best_spacing = viewport_width / num_ticks

        # Minor level is one step finer
        minor_level = self.get_finer_level(best_level)

        # Calculate minor tick spacing and opacity
        minor_step = self.NUMERIC_LEVEL_STEPS[minor_level]
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

        return best_level, minor_level, minor_opacity

    def calculate_ticks(
        self,
        start_date: float,
        end_date: float,
        viewport_width: float,
        scale_factor: float,
    ) -> List[TickInfo]:
        """
        Calculates all ticks for the visible date range.

        Args:
            start_date: Left edge date value.
            end_date: Right edge date value.
            viewport_width: Width of viewport in pixels.
            scale_factor: Pixels per day factor.

        Returns:
            List of TickInfo objects for rendering.
        """
        date_range = end_date - start_date
        if date_range <= 0:
            return []

        major_level, minor_level, minor_opacity = self.calculate_active_levels(
            date_range, viewport_width
        )

        ticks: List[TickInfo] = []

        # Generate major ticks
        major_step = self.NUMERIC_LEVEL_STEPS[major_level]
        ticks.extend(
            self._generate_ticks_for_level(
                start_date, end_date, major_step, major_level, 1.0, True, scale_factor
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
                    scale_factor,
                )
            )

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
        scale_factor: float,
    ) -> List[TickInfo]:
        """
        Generates ticks for a specific level.

        Args:
            start_date: Start of visible range.
            end_date: End of visible range.
            step: Interval between ticks.
            level: TickLevel for these ticks.
            opacity: Opacity value for these ticks.
            is_major: Whether these are major ticks.
            scale_factor: Pixels per day.

        Returns:
            List of TickInfo objects.
        """
        ticks: List[TickInfo] = []
        if step <= 0:
            return ticks

        # Align start to step boundary
        first_tick = math.floor(start_date / step) * step

        current = first_tick
        max_ticks = 500  # Safety limit
        count = 0

        while current <= end_date and count < max_ticks:
            # Skip ticks outside the visible range (with buffer)
            if current >= start_date - step:
                screen_x = (current - start_date) * scale_factor
                label = self._format_label(current, level)

                ticks.append(
                    TickInfo(
                        position=current,
                        screen_x=screen_x,
                        level=level,
                        label=label,
                        opacity=opacity,
                        is_major=is_major,
                    )
                )

            current += step
            count += 1

        return ticks

    def _format_label(self, position: float, level: TickLevel) -> str:
        """
        Formats a label for a tick position.

        Args:
            position: Date position in lore_date units.
            level: Tick level for formatting context.

        Returns:
            Formatted label string.
        """
        if self._calendar:
            return self._format_calendar_label(position, level)
        return self._format_numeric_label(position, level)

    def _format_calendar_label(self, position: float, level: TickLevel) -> str:
        """
        Formats a label using the calendar converter.

        Args:
            position: Date position.
            level: Tick level.

        Returns:
            Calendar-formatted label.
        """
        try:
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
                # Show month abbreviation
                if date.month_name:
                    return date.month_name[:3]
                return f"M{date.month}"
            elif level == TickLevel.WEEK:
                return f"D{date.day}"
            elif level == TickLevel.DAY:
                return str(date.day)
            elif level == TickLevel.HOUR:
                hours = int(date.time_fraction * 24)
                return f"{hours:02d}:00"
            elif level == TickLevel.MINUTE:
                hours = int(date.time_fraction * 24)
                minutes = int((date.time_fraction * 24 - hours) * 60)
                return f"{hours:02d}:{minutes:02d}"
            else:
                return str(date.year)
        except Exception:
            return self._format_numeric_label(position, level)

    def _format_numeric_label(self, position: float, level: TickLevel) -> str:
        """
        Formats a numeric (non-calendar) label.

        Args:
            position: Date position.
            level: Tick level.

        Returns:
            Numeric label string.
        """
        # Handle sub-day levels with time formatting
        if level == TickLevel.HOUR:
            # Extract the fractional part of the day and convert to hours
            day_fraction = position - int(position)
            hours = int(day_fraction * 24) % 24
            return f"{hours:02d}:00"
        elif level == TickLevel.MINUTE:
            # Extract fractional part and convert to hours:minutes
            day_fraction = position - int(position)
            total_minutes = int(day_fraction * 24 * 60)
            hours = (total_minutes // 60) % 24
            minutes = total_minutes % 60
            return f"{hours:02d}:{minutes:02d}"

        # Handle standard numeric formatting for day+ levels
        abs_pos = abs(position)
        if abs_pos >= 1e9:
            return f"{position/1e9:.1f}B"
        elif abs_pos >= 1e6:
            return f"{position/1e6:.1f}M"
        elif abs_pos >= 1e4:
            return f"{position/1e3:.0f}k"
        elif abs_pos >= 1:
            return f"{position:.0f}"
        elif abs_pos >= 0.01:
            return f"{position:.2f}"
        else:
            return f"{position:.4f}"

    def avoid_collisions(
        self, ticks: List[TickInfo], label_width: float = 50
    ) -> List[TickInfo]:
        """
        Removes labels that would overlap with higher-priority labels.

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

        # Track occupied regions
        result: List[TickInfo] = []
        last_label_end = float("-inf")

        # Process major ticks first
        for tick in sorted_ticks:
            if tick.is_major:
                if tick.screen_x >= last_label_end + 5:  # 5px padding
                    result.append(tick)
                    if tick.label:
                        last_label_end = tick.screen_x + label_width
                else:
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

        # Then process minor ticks
        for tick in sorted_ticks:
            if not tick.is_major:
                if tick.screen_x >= last_label_end + 5:
                    result.append(tick)
                    if tick.label:
                        last_label_end = tick.screen_x + label_width * 0.7
                else:
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

        return result

    def get_parent_context(self, start_date: float) -> str:
        """
        Gets the parent context label for sticky display.

        Args:
            start_date: Left edge date value.

        Returns:
            Context string (e.g., "Year 2025").
        """
        if self._calendar:
            try:
                date = self._calendar.from_float(start_date)
                return f"Year {date.year}"
            except Exception:
                pass

        # Numeric fallback
        if abs(start_date) >= 1e6:
            return f"~{start_date/1e6:.0f}M"
        elif abs(start_date) >= 1e3:
            return f"~{start_date/1e3:.0f}k"
        else:
            return f"~{start_date:.0f}"
