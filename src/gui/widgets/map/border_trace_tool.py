"""Transient two-point border selection for the region drawing tool."""

from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF
from PySide6.QtGui import QPainterPath
from PySide6.QtWidgets import QGraphicsItem

from src.core.border_trace import RingPosition, border_routes, simple_draft
from src.core.region_geometry import Point, geometry_rings, ring_points
from src.gui.widgets.map.feature_items import RegionItem
from src.gui.widgets.map.region_paths import scene_point
from src.gui.widgets.map.region_preview import RegionPreview

if TYPE_CHECKING:
    from src.gui.widgets.map.map_graphics_view import MapGraphicsView
    from src.gui.widgets.map.snapping_manager import SnappingManager, SnapResult


class BorderTraceTool:
    """Capture one displayed ring and preview either route between two clicks."""

    def __init__(self, view: "MapGraphicsView", snapping: "SnappingManager") -> None:
        """Initialize trace state without adding scene items."""
        self._view = view
        self._snapping = snapping
        self.active = False
        self.can_use = False
        self.message = ""
        self._source: tuple[QGraphicsItem, int] | None = None
        self._ring: tuple[Point, ...] = ()
        self._start: RingPosition | None = None
        self._routes: tuple[tuple[Point, ...], ...] = ()
        self._index = 0
        self._preview: RegionPreview | None = None

    @property
    def has_routes(self) -> bool:
        """Whether both endpoints have been selected."""
        return bool(self._routes)

    def report(self, message: str) -> None:
        """Show feedback in the drawing controls."""
        self.message = message
        self._view.border_trace_changed.emit()

    def start(self) -> None:
        """Enter trace mode without changing the draft."""
        self.cancel()
        self.active = True
        self.report("Pick the first point on an existing region border.")

    def cancel(self) -> None:
        """Clear the temporary selection and preserve accepted draft points."""
        changed = self.active or bool(self.message)
        self.active = self.can_use = False
        self._source = None
        self._start = None
        self._ring = ()
        self._routes = ()
        self._index = 0
        if self._preview is not None:
            self._preview.clear()
            self._preview = None
        if changed:
            self._view._hide_snap_indicator()
            self.report("")

    def restyle(self) -> None:
        """Update the trace overlay after a theme switch."""
        if self._preview is not None:
            self._preview.restyle()

    def _snap(self, scene_pos: QPointF) -> "SnapResult":
        return self._snapping.snap_point(
            scene_pos, self._view.transform(), trace=True, source=self._source
        )

    def hover(self, scene_pos: QPointF) -> None:
        """Show which endpoint a click would select."""
        result = self._snap(scene_pos)
        if result.snapped and not self.has_routes:
            self._view._show_snap_indicator(result.pos, result.snap_type)
        else:
            self._view._hide_snap_indicator()

    def pick(self, pos: QPointF, draft: tuple[Point, ...]) -> None:
        """Pick one point on the source ring."""
        pixmap = self._view.pixmap_item
        if pixmap is None or self.has_routes:
            return
        result = self._snap(pos)
        item, point = result.source_item, result.ring_position
        if not isinstance(item, RegionItem) or point is None:
            self.report(
                "Pick a point on the same border."
                if self._start
                else "Pick a point on an existing region border."
            )
            return
        ring = ring_points(geometry_rings(item._geometry)[result.ring_index])
        if self._start is None:
            self._source = (item, result.ring_index)
            self._ring, self._start = ring, point
            self._show_first(result.pos)
            self.report(
                f"Pick the second point on {item.label or 'this region'}'s border."
            )
            return
        if ring != self._ring:
            self.cancel()
            self.report("The source border changed. Start the trace again.")
            return
        rect = pixmap.sceneBoundingRect()
        self._routes = border_routes(
            ring, self._start, point, rect.width(), rect.height()
        )
        if not self._routes:
            self.report("Pick a different point on the border.")
            return
        self._show_route(draft)

    def switch_route(self, draft: tuple[Point, ...]) -> None:
        """Select the other route between the same endpoints."""
        if self.has_routes:
            self._index = 1 - self._index
            self._show_route(draft)

    def append_points(self, draft: tuple[Point, ...]) -> tuple[Point, ...]:
        """Return the arc with a shared starting vertex removed."""
        route = self._routes[self._index]
        return route[1:] if draft and draft[-1] == route[0] else route

    def _show_route(self, draft: tuple[Point, ...]) -> None:
        route = self.append_points(draft)
        self.can_use = simple_draft(draft + route)
        self._show_path(route, draft[-1:])
        self._view._hide_snap_indicator()
        self.report(
            "Previewing the border. Switch routes or use this border."
            if self.can_use
            else "This route crosses the draft. Switch routes or cancel."
        )

    def _show_first(self, pos: QPointF) -> None:
        radius = 3 / max(self._view.transform().m11(), 1e-9)
        path = QPainterPath()
        path.addEllipse(pos, radius, radius)
        self._preview = RegionPreview(self._view.graphics_scene)
        self._preview.show_path(path)

    def _show_path(
        self, route: tuple[Point, ...], connector: tuple[Point, ...]
    ) -> None:
        if not (route and self._view.pixmap_item):
            return
        rect = self._view.pixmap_item.sceneBoundingRect()
        points = connector + route
        path = QPainterPath(scene_point(points[0], rect))
        for point in points[1:]:
            path.lineTo(scene_point(point, rect))
        if self._preview is None:
            self._preview = RegionPreview(self._view.graphics_scene)
        self._preview.show_path(path)
