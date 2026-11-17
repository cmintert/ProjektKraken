"""Read-only projection presentation with explicit source-map navigation."""

from collections.abc import Callable
from functools import partial
from typing import Any

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QAction, QColor, QKeyEvent, QPainterPath, QPen
from PySide6.QtWidgets import (
    QGraphicsPathItem,
    QGraphicsSceneMouseEvent,
    QMenu,
    QMessageBox,
)
from shiboken6 import isValid

from src.core.projected_geometry import ProjectedGeometry
from src.core.theme_manager import ThemeManager
from src.gui.utils.help_context import declare_inspection
from src.gui.widgets.map.map_graphics_view import MapGraphicsView


class ProjectedPoint(QGraphicsPathItem):
    """Non-draggable, selectable symbol that opens its authoritative source."""

    def __init__(self, data: dict[str, Any], activate: Callable[[], None]) -> None:
        """Use theme-owned identity roles and constant-size point geometry."""
        path = QPainterPath()
        path.addEllipse(-5, -5, 10, 10)
        super().__init__(path)
        self.activate = activate
        color = QColor(ThemeManager().get_theme()[f"{data['object_type']}_main"])
        self.setPen(QPen(color, 2))
        self.setBrush(Qt.BrushStyle.NoBrush)
        self.setFlag(self.GraphicsItemFlag.ItemIgnoresTransformations)
        self.setFlag(self.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(self.GraphicsItemFlag.ItemIsFocusable)
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        self.setOpacity(data["opacity"])
        provenance = ""
        if data.get("feature_type") in {"path", "region"}:
            provenance = (
                "\nDated geometry" if data.get("state_id") else "\nBase Geometry"
            )
        self.setToolTip(
            f"{data['label']} — from {data['source_name']}{provenance}\n"
            "Read-only projection. Double-click or press Enter to open the source map."
        )

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent) -> None:  # noqa: N802
        """Navigate deliberately without starting an edit on the derived item."""
        self.activate()
        event.accept()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        """Enter follows the source; editing keys never mutate a projection."""
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.activate()
            event.accept()
        elif event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            event.accept()
        else:
            super().keyPressEvent(event)


class ConnectedFeatures(QObject):
    """Own a separate ephemeral overlay; never enter the authored layer tree."""

    changed = Signal()
    source_requested = Signal(str)

    def __init__(self, view: MapGraphicsView, menu: QMenu) -> None:
        """Append native settings actions after the host populates its menu."""
        super().__init__(view)
        self.view = view
        self.enabled = False
        self.include_detail = False
        self.issues: list[str] = []
        self.items: list[ProjectedPoint] = []
        menu.aboutToShow.connect(lambda: self.populate(menu))

    def populate(self, menu: QMenu) -> None:
        """Collect display preferences using existing native menu conventions."""
        menu.addSeparator()
        for label, key, checked, meaning in (
            (
                "Show connected map features",
                "enabled",
                self.enabled,
                "map.projection.enabled|map.hierarchy|help-map-connected-features",
            ),
            (
                "Include smaller-map detail",
                "include_detail",
                self.include_detail,
                "map.projection.include_detail|map.hierarchy|help-map-connected-features",
            ),
        ):
            action = declare_inspection(
                QAction(label, menu),
                meaning,
            )
            action.setCheckable(True)
            action.setChecked(checked)
            action.setEnabled(key == "enabled" or self.enabled)
            action.toggled.connect(lambda value, name=key: self.configure(name, value))
            menu.addAction(action)
        issues = declare_inspection(
            QAction("View projection issues…", menu),
            "map.projection.issues|map.hierarchy|help-map-projection-issues",
        )
        issues.setEnabled(self.enabled and bool(self.issues))
        issues.triggered.connect(self.show_issues)
        menu.addAction(issues)

    def configure(self, key: str, value: bool) -> None:
        """Emit session-only intent; no authoring command or settings persistence."""
        setattr(self, key, value)
        self.changed.emit()

    def show_issues(self) -> None:
        """Explain ambiguity without choosing or changing an authored source."""
        box = QMessageBox(self.view)
        box.setWindowTitle("Connected map features")
        box.setTextFormat(Qt.TextFormat.PlainText)
        box.setText("\n".join(self.issues))
        box.exec()

    def clear(self) -> None:
        """Remove only this overlay's items, preserving authored selections/drafts."""
        for item in self.items:
            if isValid(item) and item.scene() is not None:
                item.scene().removeItem(item)
        self.items.clear()

    def display(self, frame: dict[str, Any]) -> None:
        """Render a worker-resolved frame in normalized target coordinates."""
        self.clear()
        self.issues = frame.get("issues", [])
        image = self.view.pixmap_item
        if image is None:
            return
        bounds = image.boundingRect()
        for data in frame.get("points", []):
            item = ProjectedPoint(
                data,
                partial(self.source_requested.emit, data["source_map"]),
            )
            item.setPos(data["x"] * bounds.width(), data["y"] * bounds.height())
            item.setZValue(100)
            self.view.graphics_scene.addItem(item)
            self.items.append(item)
        for data in frame.get("geometries", []):
            shape = ProjectedShape(
                data,
                bounds.width(),
                bounds.height(),
                partial(self.source_requested.emit, data["source_map"]),
            )
            shape.setZValue(99)
            self.view.graphics_scene.addItem(shape)
            self.items.append(shape)


class ProjectedShape(ProjectedPoint):
    """One read-only source item containing every clipped line/polygon component."""

    def __init__(
        self,
        data: dict[str, Any],
        width: float,
        height: float,
        activate: Callable[[], None],
    ) -> None:
        """Build independent closed rings using odd-even hole-aware hit geometry."""
        super().__init__(data, activate)
        self.setFlag(self.GraphicsItemFlag.ItemIgnoresTransformations, False)
        geometry = ProjectedGeometry.from_dict(data)
        path = QPainterPath()
        path.setFillRule(Qt.FillRule.OddEvenFill)
        for polygon in geometry.polygons:
            for ring in (polygon.outer, *polygon.holes):
                self._append_ring(path, ring, width, height, closed=True)
        for line in geometry.lines:
            self._append_ring(path, line, width, height, closed=False)
        self.setPath(path)
        pen = self.pen()
        pen.setCosmetic(True)
        self.setPen(pen)

    @staticmethod
    def _append_ring(
        path: QPainterPath,
        points: tuple[tuple[float, float], ...],
        width: float,
        height: float,
        *,
        closed: bool,
    ) -> None:
        if not points:
            return
        path.moveTo(points[0][0] * width, points[0][1] * height)
        for x, y in points[1:]:
            path.lineTo(x * width, y * height)
        if closed:
            path.closeSubpath()
