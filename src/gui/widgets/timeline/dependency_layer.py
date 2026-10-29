"""Cached timing snapshots and noninteractive device-space strand rendering."""

from collections import defaultdict
from dataclasses import dataclass, field

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetricsF,
    QPainter,
    QPainterPath,
    QPen,
    QTransform,
)

from src.core.calendar import CalendarConverter
from src.core.command import LoreMutationEffect
from src.core.events import Event
from src.core.temporal_presentation import (
    TemporalPresentation,
    event_temporal_presentation,
)
from src.core.timeline_dependencies import (
    Endpoint,
    TimelineDependency,
    timeline_dependencies,
)
from src.gui.widgets.timeline.event_item import EventItem
from src.gui.widgets.timeline.group_band_item import GroupBandItem
from src.gui.widgets.timeline.item_layout import (
    LABEL_GUTTER,
    TimelineItemLayout,
    timeline_item_layout,
)
from src.gui.widgets.timeline.wire_router import Wire, route_wires


@dataclass
class DependencyCurve:
    """One displayed, continuously routed source-to-dependent connection."""

    source: QPointF
    target: QPointF
    source_side: float
    target_side: float
    dependency: TimelineDependency
    emphasized: bool
    route: QPainterPath = field(default_factory=QPainterPath)

    def path(self) -> QPainterPath:
        """Return its complete node-editor wire, never a clipped text fragment."""
        return QPainterPath(self.route)


@dataclass
class _DisplaySnapshot:
    presentation: TemporalPresentation
    layouts: dict[tuple[str, float], TimelineItemLayout]
    text_masks: dict[tuple[str, float], list[QRectF]] = field(default_factory=dict)

    def layout(self, item: EventItem) -> TimelineItemLayout:
        scale = item.scale_factor * item._zoom_level
        key = (item.event.name, scale)
        if key not in self.layouts:
            # Only the active scale is needed; do not retain every wheel step.
            self.layouts = {
                key: timeline_item_layout(self.presentation, item.event.name, scale)
            }
        return self.layouts[key]

    def labels(self, item: EventItem) -> list[QRectF]:
        """Reuse measured masks across repaints and repeated group copies."""
        key = (item.display_name, item.scale_factor * item._zoom_level)
        if key not in self.text_masks:
            self.text_masks = {
                key: _caption_rects(
                    self.layout(item),
                    item.display_name,
                    self.presentation.presence.caption,
                )
            }
        return self.text_masks[key]

    def obstacles(self, item: EventItem) -> list[QRectF]:
        """Protect painted rows and actual text, without phantom future labels."""
        return [*self.labels(item), *(row.rect for row in self.layout(item).rows)]

    def row_bounds(self, item: EventItem, y: float) -> QRectF:
        """Place each socket at the visible side of its own endpoint row."""
        bounds = QRectF()
        for rect in self.obstacles(item):
            if rect.top() <= y <= rect.bottom():
                bounds = bounds.united(rect)
        return bounds


def _port(
    item: EventItem, snapshot: _DisplaySnapshot, endpoint: Endpoint
) -> QPointF | None:
    """Use endpoint glyphs or presence geometry, never a detached length measure."""
    presentation = snapshot.presentation
    display = presentation.start if endpoint == "start" else presentation.end
    if display is not None and display.error:
        return None
    layout = snapshot.layout(item)
    row = layout.rows[0]
    x, y = row.geometry.marker_x, row.y
    if row.geometry.mode == "duration":
        x = row.geometry.left
    if endpoint == "end":
        end_row = next((row for row in layout.rows if row.label == "Ends"), None)
        if end_row is not None:
            x, y = end_row.geometry.marker_x, end_row.y
        elif presentation.authored_duration is not None:
            if presentation.presence.error:
                return None
            # The presence envelope has time coordinates; the measure does not.
            row = layout.rows[-1]
            x, y = row.geometry.right, row.y
        else:
            return None
    return QPointF(x, y)


def _endpoint_side(
    snapshot: _DisplaySnapshot, endpoint: Endpoint, preferred: float
) -> float:
    """A duration's start and end retain their left/right time identity."""
    if (
        not snapshot.presentation.layered
        and snapshot.presentation.presence.kind == "duration"
    ):
        return -1.0 if endpoint == "start" else 1.0
    if endpoint == "end" and snapshot.presentation.authored_duration is not None:
        return 1.0
    return preferred


def _caption_rects(layout: TimelineItemLayout, name: str, text: str) -> list[QRectF]:
    """Text masks using the same fonts and strings as EventItem."""
    title = QFont()
    title.setPointSize(10)
    title.setBold(True)
    caption = QFont(title)
    caption.setPointSize(8)
    caption.setBold(False)
    rects = []
    for y, font, value in (
        (layout.name_y, title, name),
        (layout.caption_y, caption, text),
    ):
        metrics = QFontMetricsF(font)
        rects.append(
            QRectF(
                layout.label_x - 2,
                y - metrics.ascent() - 2,
                metrics.horizontalAdvance(value) + 4,
                metrics.height() + 4,
            )
        )
    for row in layout.rows:
        if row.label:
            rects.append(
                QRectF(
                    layout.label_x - LABEL_GUTTER - 2,
                    row.y - 12,
                    QFontMetricsF(caption).horizontalAdvance(row.label + ":") + 4,
                    18,
                )
            )
        if row.value:
            rects.append(
                QRectF(
                    row.geometry.right + 10,
                    row.y - 12,
                    QFontMetricsF(caption).horizontalAdvance(row.value) + 4,
                    18,
                )
            )
    return rects


class TimelineDependencyLayer:
    """Own presentation caches, without scene objects, timers or database access."""

    def __init__(self) -> None:
        """Start with enabled strands and no retained world or scene objects."""
        self.enabled = True
        self.dependencies: tuple[TimelineDependency, ...] = ()
        self._world: dict[str, Event] = {}
        self._display: dict[str, _DisplaySnapshot] = {}
        self._routing_key: object = None
        self._routing_paths: list[QPainterPath] = []
        self.routing_pending = False

    def set_world_events(self, events: list[Event]) -> None:
        """Replace topology only from a complete accepted generation."""
        self._world = {event.id: event for event in events}
        self.dependencies = timeline_dependencies(events)

    def apply_effects(self, effects: list[LoreMutationEffect]) -> None:
        """Include deletions and repairs even when an event has no visible start."""
        for effect in effects:
            identity = effect["object_id"]
            self._world.pop(identity, None)
            if effect["operation"] == "upsert" and effect["snapshot"] is not None:
                self._world[identity] = Event.from_dict(effect["snapshot"])
        self.dependencies = timeline_dependencies(list(self._world.values()))

    def set_display_events(
        self, events: list[Event], converter: CalendarConverter | None
    ) -> None:
        """Resolve presentation at hydration, never during background painting."""
        self._display = {
            event.id: _DisplaySnapshot(
                event_temporal_presentation(event, converter), {}
            )
            for event in events
            if event.lore_date is not None
        }

    def update_preview(self, event: Event, converter: CalendarConverter | None) -> None:
        """Refresh transient caption geometry without changing accepted topology."""
        self._display[event.id] = _DisplaySnapshot(
            event_temporal_presentation(event, converter), {}
        )

    def curves(
        self,
        items: list[EventItem],
        painter: QPainter,
        minimum_y: float | None = None,
        viewport: QRectF | None = None,
        *,
        prepare: bool = True,
    ) -> tuple[list[DependencyCurve], QPainterPath]:
        """Use current copy positions while preserving cached full-world identity."""
        visible: dict[str, list[EventItem]] = defaultdict(list)
        mask = QPainterPath()
        mask.setFillRule(Qt.FillRule.WindingFill)
        transform = painter.worldTransform()
        for item in items:
            if item.isVisible() and item.event.id in self._display:
                visible[item.event.id].append(item)
                device = item.deviceTransform(transform)
                snapshot = self._display[item.event.id]
                for rect in snapshot.labels(item):
                    mask.addRect(device.mapRect(rect))
        curves = []
        for dependency in self.dependencies:
            sources = visible.get(dependency.source_id, [])
            for target in visible.get(dependency.target_id, []) if sources else []:
                source = min(
                    sources,
                    key=lambda item: (
                        item.data(0) != target.data(0),
                        abs(item.y() - target.y()),
                        item.y(),
                        str(item.data(0)),
                        item.x(),
                    ),
                )
                curve = self._curve(source, target, dependency, transform)
                if curve is not None:
                    curves.append(curve)
        curves.sort(
            key=lambda curve: (
                curve.source.y(),
                curve.source.x(),
                curve.target.y(),
                curve.target.x(),
                curve.dependency.source_id,
                curve.dependency.source_endpoint,
                curve.dependency.target_id,
                curve.dependency.target_endpoint,
            )
        )
        obstacles = [
            item.deviceTransform(transform).mapRect(rect)
            for copies in visible.values()
            for item in copies
            for rect in self._display[item.event.id].obstacles(item)
        ]
        self._route(curves, obstacles, transform, minimum_y, prepare=prepare)
        if viewport is not None:
            # Cull completed paths, never competitors in a shared corridor.
            curves = [
                curve
                for curve in curves
                if curve.path()
                .boundingRect()
                .adjusted(-4, -4, 4, 4)
                .intersects(viewport)
                or QRectF(curve.source, curve.target)
                .normalized()
                .adjusted(-4, -4, 4, 4)
                .intersects(viewport)
            ]
        return curves, mask

    def _route(
        self,
        curves: list[DependencyCurve],
        obstacles: list[QRectF],
        transform: QTransform,
        minimum_y: float | None,
        *,
        prepare: bool = True,
    ) -> None:
        """Reuse routing across repaint/selection changes and simple scrolling."""
        offset = QPointF(transform.dx(), transform.dy())
        wires = [
            Wire(
                curve.source - offset,
                curve.target - offset,
                curve.source_side,
                curve.target_side,
            )
            for curve in curves
        ]
        normalized = [rect.translated(-offset) for rect in obstacles]
        normalized.sort(key=lambda r: (r.x(), r.y(), r.width(), r.height()))
        # The routing floor belongs to content, not the scrolling viewport.
        # Paint still clips all strokes and arrowheads below the sticky ruler.
        floor = (
            min([rect.top() for rect in normalized] + [w.source.y() for w in wires])
            - 24
            if minimum_y is not None and wires
            else None
        )
        key = (
            tuple(
                (
                    wire.source.x(),
                    wire.source.y(),
                    wire.target.x(),
                    wire.target.y(),
                    wire.source_side,
                    wire.target_side,
                )
                for wire in wires
            ),
            tuple(
                (rect.x(), rect.y(), rect.width(), rect.height()) for rect in normalized
            ),
            floor,
        )
        if key != self._routing_key:
            if not prepare:
                self.routing_pending = True
                return
            self._routing_paths = route_wires(
                wires,
                normalized,
                floor,
            )
            self._routing_key = key
        self.routing_pending = False
        translation = QTransform.fromTranslate(offset.x(), offset.y())
        for curve, path in zip(curves, self._routing_paths):
            curve.route = translation.map(path)

    def _curve(
        self,
        source: EventItem,
        target: EventItem,
        dependency: TimelineDependency,
        transform: QTransform,
    ) -> DependencyCurve | None:
        first, second = self._display[source.event.id], self._display[target.event.id]
        start = _port(source, first, dependency.source_endpoint)
        end = _port(target, second, dependency.target_endpoint)
        if start is None or end is None:
            return None
        source_transform = source.deviceTransform(transform)
        target_transform = target.deviceTransform(transform)
        source_side = _endpoint_side(first, dependency.source_endpoint, 1.0)
        target_side = _endpoint_side(second, dependency.target_endpoint, -1.0)
        source_bounds = source_transform.mapRect(first.row_bounds(source, start.y()))
        target_bounds = target_transform.mapRect(second.row_bounds(target, end.y()))
        # A socket belongs to the visible event body, like an ordinary node editor.
        # The endpoint row still identifies start versus end; duration measures
        # remain excluded by _port(). No wire starts inside an opaque text label.
        start = source_transform.map(start)
        end = target_transform.map(end)
        start.setX(
            source_bounds.right() + 2 if source_side > 0 else source_bounds.left() - 2
        )
        end.setX(
            target_bounds.right() + 2 if target_side > 0 else target_bounds.left() - 2
        )
        return DependencyCurve(
            start,
            end,
            source_side,
            target_side,
            dependency,
            source.isSelected() or target.isSelected(),
        )

    def paint(
        self,
        painter: QPainter,
        items: list[EventItem],
        bands: list[GroupBandItem],
        viewport: QRectF,
        theme: dict[str, str],
        *,
        prepared_only: bool = False,
    ) -> None:
        """Paint clipped, constant-width strands behind all interactive content."""
        if not self.enabled or not self.dependencies:
            return
        curves, _ = self.curves(
            items, painter, viewport.top(), viewport, prepare=not prepared_only
        )
        mask = QPainterPath()
        for band in bands:
            if band.isVisible():
                mask.addRect(painter.worldTransform().mapRect(band.sceneBoundingRect()))
        clip = QPainterPath()
        clip.addRect(viewport)
        painter.save()
        try:
            painter.resetTransform()
            painter.setClipPath(clip.subtracted(mask), Qt.ClipOperation.IntersectClip)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            for curve in curves:
                color = QColor(
                    theme[f"timeline_dependency_{curve.dependency.palette_index}"]
                )
                painter.setPen(QPen(color, 2.5 if curve.emphasized else 1.5))
                if curve.route.isEmpty():
                    continue
                painter.drawPath(curve.path())
                painter.setBrush(color)
                painter.drawEllipse(curve.source, 2, 2)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                end = curve.target
                arrow_x = end.x() + curve.target_side * 6
                arrow = QPainterPath(QPointF(arrow_x, end.y() - 4))
                arrow.lineTo(end)
                arrow.lineTo(QPointF(arrow_x, end.y() + 4))
                painter.drawPath(arrow)
        finally:
            painter.restore()
