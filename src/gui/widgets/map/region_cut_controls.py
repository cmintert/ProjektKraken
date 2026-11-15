"""Controls and canvas preview for a single cut in a region edit session."""

from collections.abc import Callable
from typing import TYPE_CHECKING, Literal

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QPainterPath
from PySide6.QtWidgets import QComboBox, QLabel, QVBoxLayout, QWidget
from shiboken6 import isValid

from src.core.region_geometry import MIN_REGION_VERTICES, CutResult, Geometry, Point
from src.gui.utils.help_context import declare_inspection
from src.gui.utils.style_helper import StyleHelper
from src.gui.widgets.action_flow_layout import ActionFlowLayout
from src.gui.widgets.map.feature_items import RegionItem
from src.gui.widgets.map.region_paths import region_path
from src.gui.widgets.map.region_preview import RegionPreview
from src.gui.widgets.standard_buttons import StandardButton

if TYPE_CHECKING:
    from src.gui.widgets.map.map_graphics_view import MapGraphicsView

CutMode = Literal["closed", "choose", "draw", "pick", "result"]


class RegionCutControls(QWidget):
    """Collect a cutter and show the calculated replacement before acceptance."""

    pick_requested = Signal()
    preview_requested = Signal(object)
    accepted = Signal(object)
    mode_changed = Signal()

    def __init__(self, view: "MapGraphicsView", parent: QWidget) -> None:
        """Build the actions, candidate picker, and feedback for Cut."""
        super().__init__(parent)
        self._view = view
        self._mode: CutMode = "closed"
        self._target_id: str | None = None
        self._points: list[Point] = []
        self._result: CutResult | None = None
        self._original: Geometry | None = None
        self._overlay: RegionPreview | None = None
        self._suppressed: RegionItem | None = None

        layout = QVBoxLayout(self)
        StyleHelper.apply_panel_spacing(layout)
        self.start = self._button("Cut area", self._start, layout)
        choices = ActionFlowLayout()
        choices.setContentsMargins(0, 0, 0, 0)
        self.draw = self._button("Draw cutter", self._start_drawing, choices)
        self.pick = self._button("Pick region", self.pick_requested.emit, choices)
        choices.addStretch()
        layout.addLayout(choices)
        self.regions = declare_inspection(
            QComboBox(self),
            "region-cut-cutter|map.historical-geometry|help-inspect-region-cut-cutter",
        )
        self.regions.setAccessibleName("Cutter region")
        self.regions.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.regions.currentIndexChanged.connect(self._candidate_changed)
        layout.addWidget(self.regions)
        self.message = QLabel(self)
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        actions = ActionFlowLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        self.preview = self._button("Preview cut", self._request_preview, actions)
        self.use = self._button("Use cut", self._accept, actions)
        self.cancel = self._button("Cancel cut", self.close_cut, actions)
        actions.addStretch()
        layout.addLayout(actions)
        self.set_target(None)
        self.restyle()

    def _button(
        self,
        label: str,
        callback: Callable[[], object],
        layout: QVBoxLayout | ActionFlowLayout,
    ) -> StandardButton:
        button = StandardButton(label, self)
        button.clicked.connect(callback)
        layout.addWidget(button)
        return button

    @property
    def active(self) -> bool:
        """Whether Cut owns the current authoring interaction."""
        return self._mode != "closed"

    @property
    def has_draft(self) -> bool:
        """Whether the user has entered a cutter or reached its preview."""
        return self.active and bool(
            self._points or self.regions.currentIndex() >= 0 or self._result
        )

    def set_target(self, object_id: str | None) -> None:
        """Show Cut for a managed region target."""
        if self._target_id != object_id:
            self.close_cut()
            self._target_id = object_id
        self.setVisible(object_id is not None)
        self._refresh()

    def _start(self) -> None:
        self._set_mode("choose", "Draw a cutter or choose an existing region.")

    def _start_drawing(self) -> None:
        self._clear_preview()
        self._points.clear()
        self._set_mode(
            "draw", "Click the map to draw the cutter, then preview the cut."
        )
        self._view.setFocus(Qt.FocusReason.OtherFocusReason)

    def show_candidates(
        self, candidates: list[tuple[str, Geometry]], source: str
    ) -> None:
        """Show copied candidate shapes resolved for the target's Base or date."""
        self._clear_preview()
        self.regions.blockSignals(True)
        self.regions.clear()
        for label, geometry in candidates:
            self.regions.addItem(label, geometry)
        self.regions.setCurrentIndex(-1)
        self.regions.blockSignals(False)
        self._set_mode(
            "pick",
            f"Choose a cutter from {source}."
            if candidates
            else f"No other regions available from {source}.",
        )
        self.regions.setFocus(Qt.FocusReason.OtherFocusReason)

    def _candidate_changed(self) -> None:
        if self._mode != "pick":
            return
        geometry = self.regions.currentData()
        if geometry:
            self._show_geometry((geometry,))
        self._refresh()

    def handle_mouse_press(self, pos: QPointF) -> bool:
        """Collect a cutter vertex while leaving navigation to the map."""
        if not self.active:
            return False
        pixmap = self._view.pixmap_item
        if self._mode != "draw" or pixmap is None:
            return True
        if not pixmap.contains(pixmap.mapFromScene(pos)):
            return True
        snap = self._view._snapping_manager.snap_point(pos, self._view.transform())
        x, y = self._view.coord_system.to_normalized(snap.pos if snap.snapped else pos)
        point = self._view.coord_system.clamp_normalized(x, y)
        if not self._points or self._points[-1] != point:
            self._points.append(point)
        if len(self._points) > 1:
            self._show_geometry((self._drawing_geometry(),))
        self._refresh()
        return True

    def _drawing_geometry(self) -> Geometry:
        return [{"x": x, "y": y} for x, y in self._points]

    def confirm_step(self) -> bool:
        """Handle Enter within the current Cut step."""
        if not self.active:
            return False
        if self._mode == "result":
            self._accept()
        else:
            self._request_preview()
        return True

    def _request_preview(self) -> None:
        if self._mode == "draw" and len(self._points) >= MIN_REGION_VERTICES:
            self.preview_requested.emit(self._drawing_geometry())
        elif self._mode == "pick" and self.regions.currentIndex() >= 0:
            self.preview_requested.emit(self.regions.currentData())

    def show_result(self, result: CutResult, original: Geometry) -> None:
        """Preview every surviving polygon without changing the target draft."""
        self._result = result
        self._original = original
        self._render_result(result, original)
        self._set_mode(
            "result", result.explanation or "Previewing the area that remains."
        )
        (self.use if result.status == "ready" else self.cancel).setFocus(
            Qt.FocusReason.OtherFocusReason
        )

    def restyle(self) -> None:
        """Refresh styles and any visible overlay after a theme switch."""
        style = StyleHelper.get_action_role_style("secondary")
        for button in (
            self.start,
            self.draw,
            self.pick,
            self.preview,
            self.use,
            self.cancel,
        ):
            button.setStyleSheet(style)
        if self._overlay is not None:
            self._overlay.restyle()

    def rebind_preview(self) -> None:
        """Restore the pending preview after the target scene item is rebuilt."""
        if not self.active:
            return
        self._view._vertex_editor.set_handles_visible(False)
        if self._result is not None and self._original is not None:
            self._clear_preview()
            self._render_result(self._result, self._original)

    def _render_result(self, result: CutResult, original: Geometry) -> None:
        polygons = tuple(part.to_geometry() for part in result.polygons)
        if polygons or result.status == "empty":
            item = self._view.feature_items.get(self._target_id or "")
            if isinstance(item, RegionItem):
                self._suppressed = item
                item.set_preview_suppressed(True)
        if polygons:
            self._show_geometry(polygons, filled=True)
        elif result.status == "empty":
            self._show_geometry((original,))
        else:
            self._clear_preview()

    def _accept(self) -> None:
        if self._result is None or self._result.status != "ready":
            return
        geometry = self._result.polygons[0].to_geometry()
        self.close_cut()
        self.accepted.emit(geometry)

    def _show_geometry(
        self, geometries: tuple[Geometry, ...], *, filled: bool = False
    ) -> None:
        pixmap = self._view.pixmap_item
        if pixmap is None:
            return
        path = QPainterPath()
        path.setFillRule(Qt.FillRule.OddEvenFill)
        for geometry in geometries:
            path.addPath(region_path(geometry, pixmap.sceneBoundingRect()))
        if self._overlay is None:
            self._overlay = RegionPreview(self._view.graphics_scene)
        self._overlay.show_path(path, filled=filled)

    def _clear_preview(self) -> None:
        if self._overlay is not None:
            self._overlay.clear()
            self._overlay = None
        if self._suppressed is not None and isValid(self._suppressed):
            self._suppressed.set_preview_suppressed(False)
        self._suppressed = None

    def close_cut(self) -> bool:
        """Discard the cutter and restore the unchanged edit draft."""
        if not self.active:
            return False
        self._clear_preview()
        self._points.clear()
        self.regions.clear()
        self._result = None
        self._original = None
        self._set_mode("closed", "")
        return True

    def _set_mode(self, mode: CutMode, message: str) -> None:
        self._mode = mode
        self.message.setText(message)
        self._refresh()
        self._view._vertex_editor.set_handles_visible(not self.active)
        self.mode_changed.emit()

    def _refresh(self) -> None:
        self.start.setVisible(not self.active)
        self.draw.setVisible(self._mode in ("choose", "draw", "pick"))
        self.pick.setVisible(self._mode in ("choose", "draw", "pick"))
        self.regions.setVisible(self._mode == "pick")
        self.message.setVisible(self.active)
        self.preview.setVisible(self._mode in ("draw", "pick"))
        self.preview.setEnabled(
            len(self._points) >= MIN_REGION_VERTICES
            if self._mode == "draw"
            else self.regions.currentIndex() >= 0
        )
        self.use.setVisible(self._mode == "result")
        self.use.setEnabled(self._result is not None and self._result.status == "ready")
        self.cancel.setVisible(self.active)
