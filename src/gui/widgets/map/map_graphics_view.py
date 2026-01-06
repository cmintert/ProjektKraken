"""
Map Graphics View Module.

Provides the MapGraphicsView class for rendering and interacting with the map.
"""

import json
import logging
from typing import Dict, Optional

from PySide6.QtCore import QPoint, QPointF, QRectF, QSize, Qt, Signal
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
    QGraphicsEllipseItem,
    QGraphicsPathItem,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QMenu,
    QWidget,
)
from PySide6.QtGui import QPainterPath, QPen

from src.core.theme_manager import ThemeManager
from src.gui.widgets.map.coordinate_system import MapCoordinateSystem
from src.gui.widgets.map.icon_picker_dialog import IconPickerDialog
from src.gui.widgets.map.marker_item import MarkerItem
from src.gui.widgets.map.scale_bar_painter import ScaleBarPainter

logger = logging.getLogger(__name__)

# Layer Z-Values
LAYER_MAP_BG = 0
LAYER_TRAJECTORIES = 5
LAYER_MARKERS = 10
LAYER_UI_OVERLAY = 100


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
    mouse_coordinates_changed = Signal(
        float, float, bool
    )  # x, y (normalized), in_bounds

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Initializes the MapGraphicsView.

        Args:
            parent: Parent widget.
        """
        super().__init__(parent)

        # Initialize Coordinate System
        self.coord_system = MapCoordinateSystem()

        # Set OpenGL Viewport (Safe Fallback)
        import os

        force_software = os.environ.get("KRAKEN_NO_OPENGL", "").lower() in (
            "1",
            "true",
            "yes",
        )

        if not force_software:
            try:
                from PySide6.QtOpenGLWidgets import QOpenGLWidget

                self.setViewport(QOpenGLWidget())
                logger.debug("Initialized MapGraphicsView with OpenGL Viewport.")
            except ImportError:
                logger.warning(
                    "QtOpenGLWidgets not available. Requesting software rendering."
                )
            except Exception as e:
                logger.warning(
                    f"Failed to initialize OpenGL viewport: {e}. "
                    "Falling back to software rendering."
                )
        else:
            logger.info(
                "OpenGL disabled via KRAKEN_NO_OPENGL. Using software rendering."
            )

        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)

        # View settings
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setMouseTracking(True)  # Enable mouse tracking for coordinates

        # Disable scrollbars for infinite canvas feel
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Map and markers
        self.pixmap_item: Optional[QGraphicsPixmapItem] = None
        self.markers: Dict[str, MarkerItem] = {}

        # Theme
        self.tm = ThemeManager()
        self.tm.theme_changed.connect(self._update_theme)
        self._update_theme(self.tm.get_theme())

        # Enable drop support for drag-from-explorer
        self.setAcceptDrops(True)

        # Temporal state (for future trajectory animation)
        self._current_time: float = 0.0

        # Trajectory Visualization
        self.trajectory_path_item: Optional[QGraphicsPathItem] = None
        self.keyframe_items: list[QGraphicsEllipseItem] = []

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

        # Scale Bar
        self.scale_bar_painter = ScaleBarPainter()
        self.map_width_meters = 1_000_000.0  # Default 1000km

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
            # Add new map
            self.pixmap_item = QGraphicsPixmapItem(pixmap)
            self.pixmap_item.setZValue(LAYER_MAP_BG)
            self.scene.addItem(self.pixmap_item)

            # Update coordinate system bounds
            self.coord_system.set_scene_rect(self.pixmap_item.boundingRect())

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

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """
        Handle mouse move to track coordinates.
        Does not interfere with drag operations as we call super().
        """
        super().mouseMoveEvent(event)

        if self.pixmap_item:
            # Map view pos to scene pos
            scene_pos = self.mapToScene(event.pos())

            # Check if within map bounds (convert to item-local coordinates)
            item_pos = self.pixmap_item.mapFromScene(scene_pos)
            if self.pixmap_item.contains(item_pos):
                norm_pos = self.coord_system.to_normalized(scene_pos)
                self.mouse_coordinates_changed.emit(norm_pos[0], norm_pos[1], True)
            else:
                self.mouse_coordinates_changed.emit(0.0, 0.0, False)

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
        scene_pos = self.coord_system.to_scene(x, y)
        marker.setPos(scene_pos)
        marker.setZValue(LAYER_MARKERS)

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
        marker = self.markers[marker_id]
        scene_pos = self.coord_system.to_scene(x, y)
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
        [DEPRECATED] Use self.coord_system.to_scene instead.
        Kept temporarily if external callers use it, but should be removed.
        """
        return self.coord_system.to_scene(x, y)

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Handle mouse wheel for zooming."""
        # Sensitivity
        zoom_in_factor = 1.25
        zoom_out_factor = 1 / zoom_in_factor

        # Check zoom direction
        factor = zoom_in_factor if event.angleDelta().y() > 0 else zoom_out_factor

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

        # Check if over map (convert to item-local coordinates)
        scene_pos = self.mapToScene(event.position().toPoint())
        item_pos = self.pixmap_item.mapFromScene(scene_pos)
        if self.pixmap_item.contains(item_pos):
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

        # Check if within map bounds (convert to item-local coordinates)
        item_pos = self.pixmap_item.mapFromScene(scene_pos)
        if not self.pixmap_item.contains(item_pos):
            event.ignore()
            return

        # Calculate normalized coordinates
        # Calculate normalized coordinates
        norm_x, norm_y = self.coord_system.to_normalized(scene_pos)
        norm_x, norm_y = self.coord_system.clamp_normalized(norm_x, norm_y)

        # Parse MIME data
        if not self._handle_drop_data(event, norm_x, norm_y):
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
            self._show_marker_context_menu(item, event.globalPos())
        else:
            # Clicked on map (or empty space)
            # Convert screen pos to scene pos
            scene_pos = self.mapToScene(event.pos())

            # Check if within map bounds (convert to item-local coordinates)
            item_pos = self.pixmap_item.mapFromScene(scene_pos)
            if self.pixmap_item.contains(item_pos):
                self._show_map_background_context_menu(scene_pos, event.globalPos())

    def set_map_width_meters(self, width_meters: float) -> None:
        """
        Sets the real-world width of the map for scale calculation.

        Args:
            width_meters: Width of the map image in meters.
        """
        if width_meters <= 0:
            logger.warning(f"Invalid map width: {width_meters}. Ignoring.")
            return

        self.map_width_meters = width_meters
        # Trigger repaint to update scale bar
        self.viewport().update()

    def drawForeground(self, painter: QPainter, rect: QRectF) -> None:
        """
        Draw overlay elements on top of the scene.
        Using drawForeground allows us to hook into the render loop correctly,
        even with an OpenGL viewport.
        We reset the transform to draw in window coordinates.
        """
        super().drawForeground(painter, rect)

        # Draw Scale Bar Overlay
        if self.pixmap_item and self.map_width_meters > 0:
            # Use pixmap bounding rect width for calculation to rely on image size,
            # not dynamic scene rect which can expand.
            image_width_px = self.pixmap_item.boundingRect().width()
            if image_width_px > 0:
                # Calculate resolution: meters per scene unit (pixel)
                base_resolution = self.map_width_meters / image_width_px

                # Adjust for current view zoom (m11 is horizontal scale)
                view_scale = self.transform().m11()

                if view_scale > 0:
                    current_resolution = base_resolution / view_scale

                    # Save painter state (Scene coordinates)
                    painter.save()

                    # Reset transform to draw in Viewport (Pixel) coordinates
                    painter.resetTransform()

                    # Draw Scale Bar
                    self.scale_bar_painter.paint(
                        painter, QRectF(self.viewport().rect()), current_resolution
                    )

                    # Restore painter state
                    painter.restore()

    def _show_icon_picker(self, marker_item: MarkerItem) -> None:
        """
        Shows the icon picker dialog for a marker.

        Args:
            marker_item: The marker to change the icon for.
        """
        dialog = IconPickerDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted and (
            selected_icon := dialog.selected_icon
        ):
            marker_item.set_icon(selected_icon)
            self.change_marker_icon_requested.emit(marker_item.marker_id, selected_icon)

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

    def _handle_drop_data(
        self, event: QDropEvent, norm_x: float, norm_y: float
    ) -> bool:
        """
        Parses drop data and emits marker request.
        """
        from src.gui.widgets.unified_list import KRAKEN_ITEM_MIME_TYPE

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
                return True
        except Exception as e:
            logger.error(f"Failed to parse drop data: {e}")

        return False

    def _show_marker_context_menu(self, item: MarkerItem, global_pos: QPoint) -> None:
        """
        Shows context menu for a marker.
        """
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
        menu.exec(global_pos)

    def _show_map_background_context_menu(
        self, scene_pos: QPointF, global_pos: QPoint
    ) -> None:
        """
        Shows context menu for adding a marker at a specific location.
        """
        # Unpack tuple to avoid closure issues with lambda
        norm_x, norm_y = self.coord_system.to_normalized(scene_pos)
        menu = QMenu(self)
        add_action = QAction("Add Marker Here", self)
        add_action.triggered.connect(
            lambda: self.add_marker_requested.emit(norm_x, norm_y)
        )
        menu.addAction(add_action)
        menu.exec(global_pos)

    def show_trajectory(self, keyframes: list) -> None:
        """
        Visualizes the trajectory path and keyframes.

        Args:
            keyframes: List of Keyframe objects.
        """
        self.clear_trajectory()
        if not keyframes or len(keyframes) < 2:
            return

        # Create Path
        path = QPainterPath()
        start = self.coord_system.to_scene(keyframes[0].x, keyframes[0].y)
        path.moveTo(start)

        for i in range(1, len(keyframes)):
            kf = keyframes[i]
            pos = self.coord_system.to_scene(kf.x, kf.y)
            path.lineTo(pos)

        self.trajectory_path_item = QGraphicsPathItem(path)
        pen = QPen(QColor("#3498db"), 2)  # Blue path
        pen.setStyle(Qt.PenStyle.DashLine)
        self.trajectory_path_item.setPen(pen)
        self.trajectory_path_item.setZValue(LAYER_TRAJECTORIES)
        self.scene.addItem(self.trajectory_path_item)

        # Create Keyframe Dots with dynamic size scaling
        # Use a fixed visual size (e.g., 8px) divided by view scale
        view_scale = self.transform().m11()
        dot_radius = 4.0 / view_scale if view_scale > 0 else 4.0

        for kf in keyframes:
            pos = self.coord_system.to_scene(kf.x, kf.y)
            dot = QGraphicsEllipseItem(
                pos.x() - dot_radius,
                pos.y() - dot_radius,
                dot_radius * 2,
                dot_radius * 2,
            )
            dot.setBrush(QBrush(QColor("#f1c40f")))  # Yellow dots
            dot.setPen(QPen(Qt.PenStyle.NoPen))
            dot.setZValue(LAYER_TRAJECTORIES + 1)
            self.scene.addItem(dot)
            self.keyframe_items.append(dot)

    def clear_trajectory(self) -> None:
        """Clears the rendered trajectory path and keyframes."""
        if self.trajectory_path_item:
            self.scene.removeItem(self.trajectory_path_item)
            self.trajectory_path_item = None

        for item in self.keyframe_items:
            self.scene.removeItem(item)
        self.keyframe_items.clear()
