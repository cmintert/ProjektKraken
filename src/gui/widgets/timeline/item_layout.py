"""Shared paint, hit and packing extents for timeline presentation channels."""

from dataclasses import dataclass, replace
from math import ceil

from PySide6.QtCore import QRectF
from PySide6.QtGui import QFont, QFontMetricsF

from src.core.temporal_display import TemporalDisplay
from src.core.temporal_presentation import TemporalPresentation
from src.gui.widgets.timeline.temporal_geometry import (
    MIN_DURATION_PX,
    TemporalGeometry,
    project_temporal_geometry,
)

ROW_SPACING = 26.0
LABEL_GUTTER = 92.0


@dataclass(frozen=True)
class TemporalRow:
    """One labeled visual channel in device coordinates."""

    label: str
    geometry: TemporalGeometry
    y: float
    measure: bool = False
    value: str = ""

    @property
    def rect(self) -> QRectF:
        """Return actual glyph extent, including the measure surface."""
        height = 18 if self.measure else 16
        padding = 4 if self.measure else 0
        return QRectF(
            self.geometry.left - padding,
            self.y - height / 2,
            self.geometry.right - self.geometry.left + padding * 2,
            height,
        )


@dataclass(frozen=True)
class TimelineItemLayout:
    """Single source of geometry for rendering and lane packing."""

    rows: tuple[TemporalRow, ...]
    bounds: QRectF
    label_x: float
    name_y: float
    caption_y: float

    @property
    def height(self) -> int:
        """Include space above and below all channels."""
        return ceil(self.bounds.height())


def occurrence_geometry(
    display: TemporalDisplay, anchor: float, scale: float
) -> TemporalGeometry:
    """Position a separately asserted occurrence relative to the item anchor."""
    geometry = project_temporal_geometry(display, scale)
    offset = (display.anchor - anchor) * scale
    return replace(
        geometry,
        left=geometry.left + offset,
        right=geometry.right + offset,
        marker_x=geometry.marker_x + offset,
    )


def _layered_rows(
    presentation: TemporalPresentation, scale: float
) -> tuple[TemporalRow, ...]:
    start = occurrence_geometry(presentation.start, presentation.presence.anchor, scale)
    rows = [TemporalRow("Starts", start, 0)]
    if presentation.end is not None:
        end = occurrence_geometry(presentation.end, presentation.presence.anchor, scale)
        rows.append(TemporalRow("Ends", end, ROW_SPACING))
    elif presentation.authored_duration is not None:
        width = presentation.authored_duration * scale
        value = f"{presentation.authored_duration:g} days"
        # The measure has a neutral surface and is deliberately detached in X.
        left = start.left
        geometry = TemporalGeometry(
            "duration",
            left,
            left + max(width, MIN_DURATION_PX),
            compact=width < MIN_DURATION_PX,
        )
        rows.append(TemporalRow("Duration", geometry, ROW_SPACING, True, value))
    presence = project_temporal_geometry(presentation.presence, scale)
    value = ""
    if presence.mode == "unresolved":
        presence = occurrence_geometry(
            presentation.start, presentation.presence.anchor, scale
        )
        value = "Span not bounded"
    rows.append(TemporalRow("Possible span", presence, ROW_SPACING * 2, value=value))
    return tuple(rows)


def timeline_item_layout(
    presentation: TemporalPresentation,
    name: str,
    scale: float,
    font: QFont | None = None,
) -> TimelineItemLayout:
    """Measure text and glyphs once for paint, hit regions and packing."""
    rows = (
        _layered_rows(presentation, scale)
        if presentation.layered
        else (
            TemporalRow("", project_temporal_geometry(presentation.presence, scale), 0),
        )
    )
    geometry = rows[0].geometry
    exact = not presentation.layered and geometry.mode == "exact"
    left = min(row.rect.left() for row in rows)
    x = geometry.label_left if exact else left
    name_y = -2 if exact else (20 if not presentation.layered else -18)
    caption_y = 10 if exact else (32 if not presentation.layered else 78)
    main_font = QFont(font) if font is not None else QFont()
    main_font.setPointSize(10)
    main_font.setBold(True)
    caption_font = QFont(main_font)
    caption_font.setBold(False)
    caption_font.setPointSize(8)
    main_metrics = QFontMetricsF(main_font)
    caption_metrics = QFontMetricsF(caption_font)
    width = max(
        400.0,
        main_metrics.horizontalAdvance(name + " · Not yet"),
        caption_metrics.horizontalAdvance(presentation.presence.caption),
    )
    bounds = QRectF(
        x,
        name_y - main_metrics.ascent(),
        width,
        caption_y - name_y + main_metrics.height() + 4,
    )
    for row in rows:
        bounds = bounds.united(row.rect)
        if row.label:
            bounds = bounds.united(
                QRectF(left - LABEL_GUTTER, row.y - 10, LABEL_GUTTER, 20)
            )
        if row.value:
            value_x = row.geometry.right + 12
            bounds = bounds.united(
                QRectF(
                    value_x,
                    row.y - 10,
                    caption_metrics.horizontalAdvance(row.value),
                    20,
                )
            )
    return TimelineItemLayout(rows, bounds.adjusted(-5, -4, 5, 4), x, name_y, caption_y)
