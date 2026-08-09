"""Trajectory Renderer for the Map Graphics View.

Manages trajectory path visualization, keyframe dots, date labels,
calendar integration, and pulsing animations.
"""

import logging
from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import QPointF, QPropertyAnimation, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QPainter,
    QPainterPath,
    QPen,
    QTransform,
)
from PySide6.QtWidgets import (
    QGraphicsObject,
    QGraphicsPathItem,
    QStyleOptionGraphicsItem,
    QWidget,
)

from src.app.constants import MAP_LAYER_Z_TRAJECTORIES
from src.core.calendar import CalendarConverter
from src.core.theme_manager import ThemeManager
from src.core.trajectory import SEGMENT_MODE_STEP, SegmentKey, SegmentMode

if TYPE_CHECKING:
    from src.gui.widgets.map.map_graphics_view import KeyframeItem, MapGraphicsView

logger = logging.getLogger(__name__)

# Colors — fallback defaults; resolved from ThemeManager at runtime
KEYFRAME_COLOR_DEFAULT = "#f1c40f"  # Yellow (fallback)
TRAJECTORY_PATH_COLOR = "#3498db"  # Blue (fallback)

# Layout Constants
KEYFRAME_LABEL_FONT_FAMILY = "Segoe UI"
KEYFRAME_LABEL_FONT_SIZE = 12
KEYFRAME_LABEL_OFFSET_X = -10
KEYFRAME_LABEL_OFFSET_Y = 10
KEYFRAME_LABEL_MIN_SIZE_PT = 8
KEYFRAME_LABEL_MAX_SIZE_PT = 10


class KeyframeLabelItem(QGraphicsObject):
    """Custom graphics item for keyframe labels with a themed background pill."""

    def __init__(self, text: str, parent: Optional[QGraphicsObject] = None) -> None:
        super().__init__(parent)
        self._text = text
        self._font = QFont(KEYFRAME_LABEL_FONT_FAMILY, KEYFRAME_LABEL_FONT_SIZE)
        self.setFlag(QGraphicsObject.GraphicsItemFlag.ItemIgnoresTransformations)

        self._padding_x = 6
        self._padding_y = 2
        self._rect = QRectF()
        self._update_rect()

    def _update_rect(self) -> None:
        fm = QFontMetrics(self._font)
        text_rect = fm.boundingRect(self._text)
        width = text_rect.width() + self._padding_x * 2
        height = text_rect.height() + self._padding_y * 2
        self.prepareGeometryChange()
        self._rect = QRectF(0, 0, float(width), float(height))

    def boundingRect(self) -> QRectF:
        return self._rect

    def setText(self, text: str) -> None:
        if self._text != text:
            self._text = text
            self._update_rect()
            self.update()

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: Optional[QWidget] = None,
    ) -> None:
        theme = ThemeManager().get_theme()
        bg_color = QColor(theme.get("surface", "#1A1A1A"))
        text_color = QColor(theme.get("text_main", "#FFFFFF"))
        border_color = QColor(theme.get("border", "#333333"))

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw the pill background
        painter.setBrush(QBrush(bg_color))
        painter.setPen(QPen(border_color, 1))

        radius = self._rect.height() / 2.0
        painter.drawRoundedRect(self._rect, radius, radius)

        # Draw the text
        painter.setFont(self._font)
        painter.setPen(QPen(text_color))
        painter.drawText(self._rect, Qt.AlignmentFlag.AlignCenter, self._text)


class TrajectoryPathItem(QGraphicsPathItem):
    """Passive playback path carrying its owning marker identity."""

    def __init__(self, marker_id: str, path: QPainterPath) -> None:
        super().__init__(path)
        self.marker_id = marker_id


class TrajectoryRenderer:
    """Manages trajectory path, keyframes, labels, and animations.

    Args:
        view: The parent MapGraphicsView.
    """

    def __init__(self, view: "MapGraphicsView") -> None:
        self._view = view

        self.trajectory_path_item: Optional[QGraphicsPathItem] = None
        self.relocation_path_items: list[QGraphicsPathItem] = []
        self.keyframe_items: list["KeyframeItem"] = []
        self.keyframe_label_items: list[KeyframeLabelItem] = []
        self._calendar_converter: Optional[CalendarConverter] = None
        self.trigger_first_use_animation: bool = False
        self._animations: list[QPropertyAnimation] = []
        self._marker_id: str | None = None
        self._keyframes: list = []
        self._segment_modes: dict[SegmentKey, SegmentMode] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def show_trajectory(
        self,
        marker_id: str,
        keyframes: list,
        segment_modes: dict[SegmentKey, SegmentMode] | None = None,
    ) -> None:
        """Visualizes the trajectory path and keyframes.

        Args:
            marker_id: The ID of the marker owning this trajectory.
            keyframes: List of Keyframe objects.
        """
        from src.gui.widgets.map.map_graphics_view import KeyframeItem

        self.clear_trajectory()
        self._marker_id = marker_id
        self._keyframes = list(keyframes)
        self._segment_modes = dict(segment_modes or {})
        if not keyframes or len(keyframes) < 2:
            return

        view_scale = (
            self._view.transform().m11() if self._view.transform().m11() > 0 else 1.0
        )
        dot_radius = max(3.0 / view_scale, 3.0)

        # Trajectories now live in a fixed low-layer (0.2-0.4) below all markers
        # and features, rather than inheriting from the marker's current layer.
        base_z = MAP_LAYER_Z_TRAJECTORIES

        for kf in keyframes:
            pos = self._view.coord_system.to_scene(kf.x, kf.y)
            dot = KeyframeItem(
                marker_id,
                kf.t,
                kf.x,
                kf.y,
                QRectF(
                    -dot_radius,
                    -dot_radius,
                    dot_radius * 2,
                    dot_radius * 2,
                ),
            )
            dot.setPos(pos)
            _theme = ThemeManager().get_theme()
            dot.setBrush(
                QBrush(
                    QColor(
                        _theme.get("accent_secondary", KEYFRAME_COLOR_DEFAULT)
                    )
                )
            )
            dot.setPen(QPen(Qt.PenStyle.NoPen))
            dot.setZValue(base_z - 0.2)
            self._view.graphics_scene.addItem(dot)
            self.keyframe_items.append(dot)

            # Add date label
            if self._calendar_converter:
                try:
                    date_str = self._calendar_converter.format_date(kf.t)
                except Exception as e:
                    logger.warning(
                        f"Calendar formatting failed for keyframe at {kf.t}: {e}"
                    )
                    date_str = f"{kf.t:.0f}"
            else:
                date_str = f"{kf.t:.0f}"

            label = KeyframeLabelItem(date_str)
            label.setPos(pos)
            label.setZValue(base_z - 0.1)
            label.setTransform(
                QTransform().translate(KEYFRAME_LABEL_OFFSET_X, KEYFRAME_LABEL_OFFSET_Y)
            )
            self._view.graphics_scene.addItem(label)
            self.keyframe_label_items.append(label)

        self._update_trajectory_path(base_z)
        self.update_label_scales()

        if self.trigger_first_use_animation:
            logger.debug(
                f"Triggering pulsing animation for {len(self.keyframe_items)} keyframes"
            )
            self.trigger_first_use_animation = False
            for dot in self.keyframe_items:
                self._pulse_item(dot)

        self._view._schedule_label_layout()

    def update_z_values(self) -> None:
        """Updates Z-values for active trajectory components to match marker."""
        if not self.keyframe_items:
            return

        # Trajectories now live in a fixed low-layer (0.2-0.4) below all markers
        # and features, rather than inheriting from the marker's current layer.
        base_z = MAP_LAYER_Z_TRAJECTORIES

        if self.trajectory_path_item:
            self.trajectory_path_item.setZValue(base_z - 0.3)

        for item in self.relocation_path_items:
            item.setZValue(base_z - 0.25)

        for dot in self.keyframe_items:
            dot.setZValue(base_z - 0.2)

        for label in self.keyframe_label_items:
            label.setZValue(base_z - 0.1)

    def clear_trajectory(self) -> None:
        """Clears the rendered trajectory path, keyframes, and labels."""
        if self.trajectory_path_item:
            self._view.graphics_scene.removeItem(self.trajectory_path_item)
            self.trajectory_path_item = None

        for relocation_item in self.relocation_path_items:
            self._view.graphics_scene.removeItem(relocation_item)
        self.relocation_path_items.clear()

        for keyframe_item in self.keyframe_items:
            self._view.graphics_scene.removeItem(keyframe_item)
        self.keyframe_items.clear()

        for label in self.keyframe_label_items:
            self._view.graphics_scene.removeItem(label)
        self.keyframe_label_items.clear()

        self._marker_id = None
        self._keyframes = []
        self._segment_modes = {}

        self._view._schedule_label_layout()

    def set_calendar_converter(self, converter: CalendarConverter) -> None:
        """Sets the calendar converter for formatting keyframe date labels.

        Args:
            converter: A calendar converter with format_date(t) method.
        """
        self._calendar_converter = converter

    def update_label_scales(self) -> None:
        """Updates the scale of keyframe labels based on current zoom level."""
        view_scale = self._view.transform().m11()
        if view_scale <= 0:
            return

        min_s = KEYFRAME_LABEL_MIN_SIZE_PT / KEYFRAME_LABEL_FONT_SIZE
        max_s = KEYFRAME_LABEL_MAX_SIZE_PT / KEYFRAME_LABEL_FONT_SIZE

        s = max(min_s, min(view_scale, max_s))

        transform = (
            QTransform()
            .translate(KEYFRAME_LABEL_OFFSET_X, KEYFRAME_LABEL_OFFSET_Y)
            .scale(s, s)
        )

        for label in self.keyframe_label_items:
            label.setTransform(transform)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _pulse_item(self, item: QGraphicsObject) -> None:
        """Pulses the given item 3 times (scale 1.0 -> 1.1 -> 1.0)."""
        item.setTransformOriginPoint(0, 0)

        animation = QPropertyAnimation(item, b"scale_val")
        animation.setDuration(600)
        animation.setStartValue(1.0)
        animation.setKeyValueAt(0.5, 1.1)
        animation.setEndValue(1.0)
        animation.setLoopCount(3)

        self._animations.append(animation)
        animation.finished.connect(lambda a=animation: self._on_animation_finished(a))

        animation.start()

    def _update_trajectory_path(self, base_z: float = MAP_LAYER_Z_TRAJECTORIES) -> None:
        """Re-draws the trajectory path based on current keyframe positions."""
        if not self.keyframe_items or len(self.keyframe_items) < 2:
            if self.trajectory_path_item:
                self._view.graphics_scene.removeItem(self.trajectory_path_item)
                self.trajectory_path_item = None
            return

        sorted_pairs = sorted(
            zip(self._keyframes, self.keyframe_items),
            key=lambda pair: pair[0].t,
        )

        path = QPainterPath()
        start = sorted_pairs[0][1].scenePos()
        path.moveTo(start)

        for (start_keyframe, start_item), (end_keyframe, end_item) in zip(
            sorted_pairs, sorted_pairs[1:]
        ):
            pair = (start_keyframe.keyframe_id, end_keyframe.keyframe_id)
            if (
                None not in pair
                and self._segment_modes.get(pair) == SEGMENT_MODE_STEP
            ):
                path.moveTo(end_item.scenePos())
                self._add_relocation_connector(
                    start_item.scenePos(), end_item.scenePos(), base_z
                )
            else:
                path.lineTo(end_item.scenePos())

        if not self.trajectory_path_item:
            self.trajectory_path_item = self._create_trajectory_item(path, base_z)
            self._view.graphics_scene.addItem(self.trajectory_path_item)
        else:
            self.trajectory_path_item.setPath(path)

    def _add_relocation_connector(
        self, start: QPointF, end: QPointF, base_z: float
    ) -> None:
        """Draw two separated strokes so relocation never reads as travel."""
        delta = end - start
        path = QPainterPath()
        path.moveTo(start)
        path.lineTo(start + delta * 0.38)
        path.moveTo(start + delta * 0.62)
        path.lineTo(end)
        item = QGraphicsPathItem(path)
        theme = ThemeManager().get_theme()
        pen = QPen(QColor(theme.get("warning", "#e67e22")), 2)
        pen.setStyle(Qt.PenStyle.DashDotLine)
        item.setPen(pen)
        item.setToolTip("Relocation — no travel route is implied")
        item.setZValue(base_z - 0.25)
        self._view.graphics_scene.addItem(item)
        self.relocation_path_items.append(item)

    def _create_trajectory_item(
        self, path: QPainterPath, base_z: float
    ) -> QGraphicsPathItem:
        """Creates and configures the trajectory path item."""
        item = TrajectoryPathItem(self._marker_id or "", path)
        _theme = ThemeManager().get_theme()
        pen = QPen(QColor(_theme.get("primary", TRAJECTORY_PATH_COLOR)), 1)
        pen.setStyle(Qt.PenStyle.DashLine)
        item.setPen(pen)
        item.setZValue(base_z - 0.3)
        return item

    def cleanup(self) -> None:
        """Stop all running animations and release resources.

        Safe to call multiple times.  Must be called before the renderer's
        parent view is torn down so that pending ``finished`` callbacks cannot
        fire on a partially-destroyed object.
        """
        for anim in list(self._animations):
            anim.stop()
        self._animations.clear()

    def _on_animation_finished(self, animation: QPropertyAnimation) -> None:
        """Remove a completed animation from the tracking list.

        Args:
            animation: The animation that just finished.
        """
        try:
            self._animations.remove(animation)
        except ValueError:
            pass  # already removed by cleanup()
