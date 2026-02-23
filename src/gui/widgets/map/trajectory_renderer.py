"""Trajectory Renderer for the Map Graphics View.

Manages trajectory path visualization, keyframe dots, date labels,
calendar integration, and pulsing animations.
"""

import logging
from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import QPropertyAnimation, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QPainterPath,
    QPen,
    QTransform,
    QPainter,
    QFontMetrics,
)
from PySide6.QtWidgets import (
    QGraphicsObject,
    QGraphicsPathItem,
)

from src.app.constants import MAP_LAYER_Z_MARKERS
from src.core.trajectory import KEYFRAME_TIME_EPSILON

from src.core.theme_manager import ThemeManager

if TYPE_CHECKING:
    from src.gui.widgets.map.map_graphics_view import KeyframeItem, MapGraphicsView

logger = logging.getLogger(__name__)

# Colors
KEYFRAME_COLOR_DEFAULT = "#f1c40f"  # Yellow
KEYFRAME_LABEL_COLOR = "#000000"  # Black
TRAJECTORY_PATH_COLOR = "#3498db"  # Blue

# Layout Constants
KEYFRAME_LABEL_FONT_FAMILY = "Segoe UI"
KEYFRAME_LABEL_FONT_SIZE = 12
KEYFRAME_LABEL_OFFSET_X = -10
KEYFRAME_LABEL_OFFSET_Y = 10
KEYFRAME_LABEL_MIN_SIZE_PT = 8
KEYFRAME_LABEL_MAX_SIZE_PT = 10


class KeyframeLabelItem(QGraphicsObject):
    """Custom graphics item for keyframe labels with a themed background pill."""

    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self._text = text
        self._font = QFont(KEYFRAME_LABEL_FONT_FAMILY, KEYFRAME_LABEL_FONT_SIZE)
        self.setFlag(QGraphicsObject.GraphicsItemFlag.ItemIgnoresTransformations)

        self._padding_x = 6
        self._padding_y = 2
        self._rect = QRectF()
        self._label_scale: float = 1.0
        self._update_rect()

    def _update_rect(self):
        fm = QFontMetrics(self._font)
        text_rect = fm.boundingRect(self._text)
        width = text_rect.width() + self._padding_x * 2
        height = text_rect.height() + self._padding_y * 2
        self.prepareGeometryChange()
        self._rect = QRectF(0, 0, float(width), float(height))

    def boundingRect(self) -> QRectF:
        return self._rect

    def setText(self, text: str):
        if self._text != text:
            self._text = text
            self._update_rect()
            self.update()

    def set_label_scale(self, scale: float) -> None:
        """Stores the current label display scale.

        Called by :meth:`TrajectoryRenderer.update_label_scales` whenever
        the zoom level changes.  The stored value is used by
        :meth:`apply_label_position` when rebuilding the transform.

        Args:
            scale: The scale factor to apply to the label.
        """
        self._label_scale = scale

    def apply_label_position(
        self, offset_x: float, offset_y: float, is_visible: bool
    ) -> None:
        """Applies a computed label offset and visibility.

        Called by :class:`LabelManager` after each layout pass.

        Args:
            offset_x: X translation offset (device pixels).
            offset_y: Y translation offset (device pixels).
            is_visible: Whether the label should be shown.
        """
        self.setTransform(
            QTransform()
            .translate(offset_x, offset_y)
            .scale(self._label_scale, self._label_scale)
        )
        self.setVisible(is_visible)

    def paint(self, painter: QPainter, option, widget=None):
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


class TrajectoryRenderer:
    """Manages trajectory path, keyframes, labels, and animations.

    Args:
        view: The parent MapGraphicsView.
    """

    def __init__(self, view: "MapGraphicsView") -> None:
        self._view = view

        self.trajectory_path_item: Optional[QGraphicsPathItem] = None
        self.keyframe_items: list["KeyframeItem"] = []
        self.keyframe_label_items: list[KeyframeLabelItem] = []
        self._calendar_converter: Optional[object] = None
        self.trigger_first_use_animation: bool = False
        self._animations: list[QPropertyAnimation] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def show_trajectory(self, marker_id: str, keyframes: list) -> None:
        """Visualizes the trajectory path and keyframes.

        Args:
            marker_id: The ID of the marker owning this trajectory.
            keyframes: List of Keyframe objects.
        """
        from src.gui.widgets.map.map_graphics_view import KeyframeItem

        self.clear_trajectory()
        if not keyframes or len(keyframes) < 2:
            return

        view_scale = (
            self._view.transform().m11() if self._view.transform().m11() > 0 else 1.0
        )
        dot_radius = max(3.0 / view_scale, 3.0)

        marker = self._view._marker_manager.find_item(marker_id)
        base_z = marker.zValue() if marker else MAP_LAYER_Z_MARKERS

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
                self._on_keyframe_dropped,
                self._update_trajectory_path,
            )
            dot.setPos(pos)
            dot.setBrush(QBrush(QColor(KEYFRAME_COLOR_DEFAULT)))
            dot.setPen(QPen(Qt.PenStyle.NoPen))
            dot.setZValue(base_z - 0.2)
            self._view.scene.addItem(dot)
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
            # Hidden until the label engine places it.
            label.setVisible(False)
            self._view.scene.addItem(label)
            self.keyframe_label_items.append(label)

        self._update_trajectory_path(base_z)
        self.update_label_scales()

        if self.trigger_first_use_animation:
            logger.debug(
                f"Triggering pulsing animation for "
                f"{len(self.keyframe_items)} keyframes"
            )
            self.trigger_first_use_animation = False
            for dot in self.keyframe_items:
                self._pulse_item(dot)

        self._view._schedule_label_layout()

    def update_z_values(self) -> None:
        """Updates Z-values for active trajectory components to match marker."""
        if not self.keyframe_items:
            return

        marker_id = self.keyframe_items[0].marker_id
        marker = self._view._marker_manager.find_item(marker_id)
        base_z = marker.zValue() if marker else MAP_LAYER_Z_MARKERS

        if self.trajectory_path_item:
            self.trajectory_path_item.setZValue(base_z - 0.3)

        for dot in self.keyframe_items:
            dot.setZValue(base_z - 0.2)

        for label in self.keyframe_label_items:
            label.setZValue(base_z - 0.1)

    def clear_trajectory(self) -> None:
        """Clears the rendered trajectory path, keyframes, and labels."""
        if self.trajectory_path_item:
            self._view.scene.removeItem(self.trajectory_path_item)
            self.trajectory_path_item = None

        for item in self.keyframe_items:
            self._view.scene.removeItem(item)
        self.keyframe_items.clear()

        for label in self.keyframe_label_items:
            self._view.scene.removeItem(label)
        self.keyframe_label_items.clear()

        self._view._schedule_label_layout()

    def set_calendar_converter(self, converter: object) -> None:
        """Sets the calendar converter for formatting keyframe date labels.

        Args:
            converter: A calendar converter with format_date(t) method.
        """
        self._calendar_converter = converter

    def set_keyframe_pinned(self, marker_id: str, t: float, pinned: bool) -> None:
        """Set visual pinned state for a specific keyframe.

        Args:
            marker_id: The marker ID.
            t: The keyframe time.
            pinned: Whether to pin the keyframe.
        """
        from src.gui.widgets.map.map_graphics_view import KeyframeItem

        for item in self.keyframe_items:
            if (
                isinstance(item, KeyframeItem)
                and item.marker_id == marker_id
                and abs(item.t - t) < KEYFRAME_TIME_EPSILON
            ):
                item.set_pinned(pinned)
                logger.debug(f"Set keyframe {marker_id} at t={t} pinned={pinned}")
                return

    def update_keyframe_label(self, marker_id: str, t: float, new_time: float) -> None:
        """Updates the label of a specific keyframe to show a new time/date.

        Args:
            marker_id: The marker ID.
            t: The keyframe time to find.
            new_time: The new time value to display.
        """
        from src.gui.widgets.map.map_graphics_view import KeyframeItem

        for i, item in enumerate(self.keyframe_items):
            if (
                isinstance(item, KeyframeItem)
                and item.marker_id == marker_id
                and abs(item.t - t) < KEYFRAME_TIME_EPSILON
            ):
                if i < len(self.keyframe_label_items):
                    label = self.keyframe_label_items[i]
                    if self._calendar_converter:
                        try:
                            text = self._calendar_converter.format_date(new_time)
                        except Exception as e:
                            logger.warning(
                                f"Calendar formatting failed for "
                                f"time {new_time}: {e}"
                            )
                            text = f"{new_time:.0f}"
                    else:
                        text = f"{new_time:.0f}"
                    label.setText(text)
                return

    def update_label_scales(self) -> None:
        """Updates the scale of keyframe labels based on current zoom level.

        Stores the computed scale on each label so that
        :meth:`KeyframeLabelItem.apply_label_position` can rebuild the
        transform with the correct scale after a layout pass.
        """
        view_scale = self._view.transform().m11()
        if view_scale <= 0:
            return

        min_s = KEYFRAME_LABEL_MIN_SIZE_PT / KEYFRAME_LABEL_FONT_SIZE
        max_s = KEYFRAME_LABEL_MAX_SIZE_PT / KEYFRAME_LABEL_FONT_SIZE

        s = max(min_s, min(view_scale, max_s))

        for label in self.keyframe_label_items:
            label.set_label_scale(s)

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
        animation.finished.connect(lambda: self._animations.remove(animation))

        animation.start()

    def _update_trajectory_path(self, base_z: float = MAP_LAYER_Z_MARKERS) -> None:
        """Re-draws the trajectory path based on current keyframe positions."""
        if not self.keyframe_items or len(self.keyframe_items) < 2:
            if self.trajectory_path_item:
                self._view.scene.removeItem(self.trajectory_path_item)
                self.trajectory_path_item = None
            return

        sorted_items = sorted(self.keyframe_items, key=lambda item: item.t)

        path = QPainterPath()
        start = sorted_items[0].scenePos()
        path.moveTo(start)

        for i in range(1, len(sorted_items)):
            path.lineTo(sorted_items[i].scenePos())

        if not self.trajectory_path_item:
            self.trajectory_path_item = self._create_trajectory_item(path, base_z)
            self._view.scene.addItem(self.trajectory_path_item)
        else:
            self.trajectory_path_item.setPath(path)

    def _create_trajectory_item(
        self, path: QPainterPath, base_z: float
    ) -> QGraphicsPathItem:
        """Creates and configures the trajectory path item."""
        item = QGraphicsPathItem(path)
        pen = QPen(QColor(TRAJECTORY_PATH_COLOR), 1)
        pen.setStyle(Qt.PenStyle.DashLine)
        item.setPen(pen)
        item.setZValue(base_z - 0.3)
        return item

    def _on_keyframe_dropped(self, item: "KeyframeItem") -> None:
        """Callback when a keyframe dot is released after dragging."""
        scene_pos = item.scenePos()
        norm_pos = self._view.coord_system.to_normalized(scene_pos)
        x, y = norm_pos

        logger.info(
            f"Keyframe dropped for {item.marker_id} "
            f"at t={item.t}: ({x:.3f}, {y:.3f})"
        )
        self._view.keyframe_moved.emit(item.marker_id, item.t, x, y)
