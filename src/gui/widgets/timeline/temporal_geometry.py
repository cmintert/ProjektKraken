"""Screen-space geometry for the timeline's temporal visual grammar."""

from dataclasses import dataclass
from typing import Literal

from src.core.temporal_display import TemporalDisplay
from src.core.temporal_expression import TemporalPrecision, TemporalQualifier

WINDOW_DETAIL_PX = 24.0
COMPACT_WINDOW_PX = 16.0
SOFT_HALO_PX = 32.0
MIN_DURATION_PX = 6.0
POINT_MARKER_PX = 16.0


@dataclass(frozen=True)
class TemporalGeometry:
    """Paint and hit geometry relative to an event's layout coordinate."""

    mode: Literal["exact", "window", "one_sided", "soft", "duration", "unresolved"]
    left: float
    right: float
    marker_x: float = 0.0
    compact: bool = False
    cap_left: bool = False
    cap_right: bool = False
    certain_left: float | None = None
    certain_right: float | None = None

    @property
    def label_left(self) -> float:
        """Place exact labels beside markers and other labels below spans."""
        return self.right + 5 if self.mode == "exact" else self.left


def project_temporal_geometry(
    display: TemporalDisplay, pixels_per_day: float
) -> TemporalGeometry:
    """Use true time coordinates only when their width is readable."""
    scale = pixels_per_day
    if display.error:
        return TemporalGeometry("unresolved", -8, 8)

    start = display.possible_start
    end = display.possible_end
    if display.kind == "duration":
        if start is None or end is None:
            return TemporalGeometry("unresolved", -8, 8)
        left = (start - display.anchor) * scale
        right = (end - display.anchor) * scale
        compact = right - left < MIN_DURATION_PX
        if compact:
            center = (left + right) / 2
            left, right = center - MIN_DURATION_PX / 2, center + MIN_DURATION_PX / 2
        certain_left = (
            (display.certain_start - display.anchor) * scale
            if display.certain_start is not None
            else None
        )
        certain_right = (
            (display.certain_end - display.anchor) * scale
            if display.certain_end is not None
            else None
        )
        if compact and certain_left is not None and certain_right is not None:
            if (
                display.certain_start == display.possible_start
                and display.certain_end == display.possible_end
            ):
                certain_left, certain_right = left, right
            else:
                center = (certain_left + certain_right) / 2
                certain_left = max(left, center - 1)
                certain_right = min(right, center + 1)
        return TemporalGeometry(
            "duration",
            left,
            right,
            compact=compact,
            certain_left=certain_left,
            certain_right=certain_right,
        )

    if display.explicit_window and (start is None or end is None):
        bound = start if start is not None else end
        assert bound is not None
        cap = (bound - display.anchor) * scale
        if start is not None:
            return TemporalGeometry(
                "one_sided",
                cap,
                cap + SOFT_HALO_PX,
                marker_x=cap + SOFT_HALO_PX / 2,
                cap_left=True,
            )
        return TemporalGeometry(
            "one_sided",
            cap - SOFT_HALO_PX,
            cap,
            marker_x=cap - SOFT_HALO_PX / 2,
            cap_right=True,
        )

    if start is None or end is None:
        return TemporalGeometry("soft", -SOFT_HALO_PX / 2, SOFT_HALO_PX / 2)

    exact = (
        not display.explicit_window
        and display.qualifier
        in {TemporalQualifier.ASSERTED, TemporalQualifier.CALCULATED}
        and display.precision
        in {None, TemporalPrecision.MINUTE, TemporalPrecision.SECOND}
    )
    if exact:
        return TemporalGeometry("exact", -POINT_MARKER_PX / 2, POINT_MARKER_PX / 2)

    left = (start - display.anchor) * scale
    right = (end - display.anchor) * scale
    compact = right - left < WINDOW_DETAIL_PX
    if compact:
        left, right = -COMPACT_WINDOW_PX / 2, COMPACT_WINDOW_PX / 2
    return TemporalGeometry(
        "window",
        left,
        right,
        compact=compact,
        cap_left=True,
        cap_right=True,
    )
