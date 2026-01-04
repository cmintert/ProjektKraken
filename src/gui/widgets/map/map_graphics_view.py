"""
Map Graphics View Module.

Provides the MapGraphicsView class for rendering and interacting with the map.
"""

import json
import logging
from typing import Dict, Optional

from PySide6.QtCore import QPointF, QSize, Qt, Signal
from PySide6.QtGui import (
    QAction,
    QBrush,
    QColor,
    QContextMenuEvent,
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
    QMouseEvent,
    QPainter,
    QPixmap,
    QResizeEvent,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QColorDialog,
    QDialog,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QMenu,
    QWidget,
)

from src.core.theme_manager import ThemeManager
from src.gui.widgets.map.icon_picker_dialog import IconPickerDialog
from src.gui.widgets.map.marker_item import MarkerItem

logger = logging.getLogger(__name__)


class MapGraphicsView(QGraphicsView):
    """
    Graphics view for displaying a map image with draggable markers.

    Signals:
        marker_moved: Emitted when a marker is dragged to a new position.
                     Args: (marker_id: str, x: float, y: float)
                     Coordinates are normalized [0.0, 1.0] relative to map image.
    """

    marker_moved = Signal(str, float, float)
    marker_clicked = Signal(str, str)  # marker_id, object_type
    add_marker_requested = Signal(float, float)  # x, y (normalized)
    delete_marker_requested = Signal(str)  # marker_id
    change_marker_icon_requested = Signal(str, str)  # marker_id, new_icon
    change_marker_color_requested = Signal(str, str)  # marker_id, new_color_hex
    marker_drop_requested = Signal(str, str, str, float, float)  # id, type, name, x, y

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Initializes the MapGraphicsView.

        Args:
            parent: Parent widget.
        """
        super().__init__(parent)

        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)

        # View settings
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

        # Map and markers
        self.pixmap_item: Optional[QGraphicsPixmapItem] = None
        self.markers: Dict[str, MarkerItem] = {}

        # Theme
        self.tm = ThemeManager()
        self.tm.theme_changed.connect(self._update_theme)
        self._update_theme(self.tm.get_theme())

        # Enable drop support for drag-from-explorer
        self.setAcceptDrops(True)

    def minimumSizeHint(self) -> QSize:
        """
        Override minimum size hint to allow resizing below map image size.

        By default, QGraphicsView uses the scene rect to determine
        its minimum size, which prevents the dock from being resized
        smaller than the map image. We override this to allow free resizing.

        Returns:
            QSize: A small minimum size (200x150) to allow shrinking.
        """
        from PySide6.QtCore import QSize

        return QSize(200, 150)

    def _update_theme(self, theme: dict) -> None:
        """Updates the scene background."""
        self.scene.setBackgroundBrush(QBrush(QColor(theme["app_bg"])))

    def load_map(self, image_path: str) -> bool:
        """
        Loads a map image into the view.

        Args:
            image_path: Path to the image file.

        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            pixmap = QPixmap(image_path)
            if pixmap.isNull():
                logger.error(f"Failed to load map image: {image_path}")
                return False

            # Clear existing map
            if self.pixmap_item:
                self.scene.removeItem(self.pixmap_item)

            # Add new map
            self.pixmap_item = QGraphicsPixmapItem(pixmap)
            self.pixmap_item.setZValue(0)  # Behind markers
            self.scene.addItem(self.pixmap_item)

            # Fit view to map
            self.fitInView(self.pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)
            self.scene.setSceneRect(self.pixmap_item.boundingRect())

            logger.info(f"Loaded map: {image_path}")
            return True

        except Exception as e:
            logger.error(f"Error loading map: {e}")
            return False

    def resizeEvent(self, event: QResizeEvent) -> None:
        """
        Handle resize events.
        Note: We no longer auto-fit here to allow the user to maintain zoom level.
        """
        super().resizeEvent(event)

    def fit_to_view(self) -> None:
        """Fits the map to the current view size."""
        if self.pixmap_item:
            self.fitInView(self.pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)
            logger.debug("Fit map to view.")

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """
        Handle mouse press to implement Smart Drag.
        If clicking a marker, disable view panning.
        If clicking background, enable view panning.
        """
        item = self.itemAt(event.pos())
        logger.debug(f"Mouse Press at {event.pos()}. Item found: {item}")

        if isinstance(item, MarkerItem):
            logger.debug(f"Click on Marker {item.marker_id}. Setting NoDrag.")
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
        else:
            logger.debug("Click on background. Setting ScrollHandDrag.")
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Reset drag mode on release."""
        logger.debug("Mouse Release. Resetting to ScrollHandDrag.")
        super().mouseReleaseEvent(event)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

    def add_marker(
        self,
        marker_id: str,
        object_type: str,
        label: str,
        x: float,
        y: float,
        icon: Optional[str] = None,
        color: Optional[str] = None,
    ) -> None:
        """
        Adds a marker to the map at normalized coordinates.

        Args:
            marker_id: Unique identifier for the marker.
            object_type: Type of object ('entity' or 'event').
            label: Marker label text.
            x: Normalized X coordinate [0.0, 1.0].
            y: Normalized Y coordinate [0.0, 1.0].
            icon: Optional icon filename (e.g., 'castle.svg').
        """
        if not self.pixmap_item:
            logger.warning("Cannot add marker: no map loaded")
            return

        # Remove existing marker if present
        if marker_id in self.markers:
            self.scene.removeItem(self.markers[marker_id])
            del self.markers[marker_id]

        # Create new marker with optional icon and color
        marker = MarkerItem(
            marker_id, object_type, label, self.pixmap_item, icon, color
        )

        # Convert normalized to scene coordinates
        scene_pos = self._normalized_to_scene(x, y)
        marker.setPos(scene_pos)

        # Add to scene and track
        self.scene.addItem(marker)
        self.markers[marker_id] = marker

        # Connect click signal
        marker.clicked.connect(self.marker_clicked.emit)

        logger.debug(
            f"Added marker {marker_id} ({label}) at normalized ({x:.3f}, {y:.3f}), "
            f"icon={icon}"
        )

    def update_marker_position(self, marker_id: str, x: float, y: float) -> None:
        """
        Updates a marker's position to new normalized coordinates.

        Args:
            marker_id: Unique identifier for the marker.
            x: Normalized X coordinate [0.0, 1.0].
            y: Normalized Y coordinate [0.0, 1.0].
        """
        if marker_id not in self.markers:
            logger.warning(f"Cannot update: marker {marker_id} not found")
            return

        marker = self.markers[marker_id]
        scene_pos = self._normalized_to_scene(x, y)
        marker.setPos(scene_pos)

        logger.debug(f"Updated marker {marker_id} to normalized ({x:.3f}, {y:.3f})")

    def remove_marker(self, marker_id: str) -> None:
        """
        Removes a marker from the map.

        Args:
            marker_id: Unique identifier for the marker to remove.
        """
        if marker_id in self.markers:
            self.scene.removeItem(self.markers[marker_id])
            del self.markers[marker_id]
            logger.debug(f"Removed marker {marker_id}")

    def clear_markers(self) -> None:
        """Removes all markers from the map."""
        for marker in list(self.markers.values()):
            self.scene.removeItem(marker)
        self.markers.clear()
        logger.debug("Cleared all markers")

    def _normalized_to_scene(self, x: float, y: float) -> QPointF:
        """
        Converts normalized coordinates to scene coordinates.

        Args:
            x: Normalized X coordinate [0.0, 1.0].
            y: Normalized Y coordinate [0.0, 1.0].

        Returns:
            QPointF: Scene coordinates.
        """
        if not self.pixmap_item:
            return QPointF(0, 0)

        pixmap_rect = self.pixmap_item.sceneBoundingRect()
        scene_x = pixmap_rect.left() + (x * pixmap_rect.width())
        scene_y = pixmap_rect.top() + (y * pixmap_rect.height())

        return QPointF(scene_x, scene_y)

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Handle mouse wheel for zooming."""
        # Sensitivity
        zoom_in_factor = 1.25
        zoom_out_factor = 1 / zoom_in_factor

        # Check zoom direction
        if event.angleDelta().y() > 0:
            factor = zoom_in_factor
        else:
            factor = zoom_out_factor

        self.scale(factor, factor)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """
        Accept drag events with our custom MIME type.
        """
        from src.gui.widgets.unified_list import KRAKEN_ITEM_MIME_TYPE

        if event.mimeData().hasFormat(KRAKEN_ITEM_MIME_TYPE):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        """
        Allow drop only over the map pixmap.
        """
        from src.gui.widgets.unified_list import KRAKEN_ITEM_MIME_TYPE

        if not event.mimeData().hasFormat(KRAKEN_ITEM_MIME_TYPE):
            event.ignore()
            return

        if not self.pixmap_item:
            event.ignore()
            return

        # Check if over map
        scene_pos = self.mapToScene(event.position().toPoint())
        if self.pixmap_item.contains(scene_pos):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        """
        Handle drop of item from Project Explorer to create a marker.
        """
        from src.gui.widgets.unified_list import KRAKEN_ITEM_MIME_TYPE

        if not event.mimeData().hasFormat(KRAKEN_ITEM_MIME_TYPE):
            event.ignore()
            return

        if not self.pixmap_item:
            event.ignore()
            return

        # Get drop position
        scene_pos = self.mapToScene(event.position().toPoint())

        # Check if within map bounds
        if not self.pixmap_item.contains(scene_pos):
            event.ignore()
            return

        # Calculate normalized coordinates
        pixmap_rect = self.pixmap_item.sceneBoundingRect()
        rel_x = scene_pos.x() - pixmap_rect.left()
        rel_y = scene_pos.y() - pixmap_rect.top()

        norm_x = rel_x / pixmap_rect.width() if pixmap_rect.width() > 0 else 0.0
        norm_y = rel_y / pixmap_rect.height() if pixmap_rect.height() > 0 else 0.0

        # Clamp to [0, 1]
        norm_x = max(0.0, min(1.0, norm_x))
        norm_y = max(0.0, min(1.0, norm_y))

        # Parse MIME data
        try:
            data_bytes = event.mimeData().data(KRAKEN_ITEM_MIME_TYPE).data()
            data = json.loads(data_bytes.decode("utf-8"))

            item_id = data.get("id")
            item_type = data.get("type")
            item_name = data.get("name", "Unknown")

            if item_id and item_type:
                self.marker_drop_requested.emit(
                    item_id, item_type, item_name, norm_x, norm_y
                )
                event.acceptProposedAction()
                logger.info(
                    f"Dropped {item_type} '{item_name}' at ({norm_x:.3f}, {norm_y:.3f})"
                )
            else:
                event.ignore()
        except Exception as e:
            logger.error(f"Failed to parse drop data: {e}")
            event.ignore()

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        """
        Handles context menu events for adding/removing markers.
        """
        if not self.pixmap_item:
            return

        # Check if we clicked on a marker
        item = self.itemAt(event.pos())
        if isinstance(item, MarkerItem):
            menu = QMenu(self)

            # Change Icon action
            change_icon_action = QAction("Change Icon...", self)
            change_icon_action.triggered.connect(lambda: self._show_icon_picker(item))
            menu.addAction(change_icon_action)

            # Change Color action
            change_color_action = QAction("Change Color...", self)
            change_color_action.triggered.connect(lambda: self._show_color_picker(item))
            menu.addAction(change_color_action)

            menu.addSeparator()

            # Delete action
            delete_action = QAction("Delete Marker", self)
            delete_action.triggered.connect(
                lambda: self.delete_marker_requested.emit(item.marker_id)
            )
            menu.addAction(delete_action)
            menu.exec(event.globalPos())
        else:
            # Clicked on map (or empty space)
            # Convert screen pos to scene pos
            scene_pos = self.mapToScene(event.pos())

            # Check if within map bounds
            if self.pixmap_item.contains(scene_pos):
                pixmap_rect = self.pixmap_item.sceneBoundingRect()
                rel_x = scene_pos.x() - pixmap_rect.left()
                rel_y = scene_pos.y() - pixmap_rect.top()

                width = pixmap_rect.width()
                height = pixmap_rect.height()

                if width > 0 and height > 0:
                    norm_x = rel_x / width
                    norm_y = rel_y / height

                    menu = QMenu(self)
                    add_action = QAction("Add Marker", self)
                    add_action.triggered.connect(
                        lambda: self.add_marker_requested.emit(norm_x, norm_y)
                    )
                    menu.addAction(add_action)
                    menu.exec(event.globalPos())

    def _show_icon_picker(self, marker_item: MarkerItem) -> None:
        """
        Shows the icon picker dialog for a marker.

        Args:
            marker_item: The marker to change the icon for.
        """
        dialog = IconPickerDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_icon = dialog.selected_icon
            if selected_icon:
                marker_item.set_icon(selected_icon)
                self.change_marker_icon_requested.emit(
                    marker_item.marker_id, selected_icon
                )

    def _show_color_picker(self, marker_item: MarkerItem) -> None:
        """
        Shows the color picker dialog for a marker.

        Args:
            marker_item: The marker to change the color for.
        """
        initial_color = marker_item.get_color() or "#FFFFFF"
        color = QColorDialog.getColor(
            QColor(initial_color), self, "Select Marker Color"
        )

        if color.isValid():
            color_hex = color.name().upper()
            marker_item.set_color(color_hex)
            self.change_marker_color_requested.emit(marker_item.marker_id, color_hex)
