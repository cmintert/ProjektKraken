"""
Map Widget Module.

Provides an interactive map view with draggable markers using QGraphicsView/Scene.
Supports normalized coordinates [0.0, 1.0] for markers independent of image size.
"""

from PySide6.QtWidgets import (
    QGraphicsView,
    QGraphicsScene,
    QGraphicsItem,
    QGraphicsPixmapItem,
    QGraphicsEllipseItem,
    QWidget,
    QVBoxLayout,
    QToolBar,
    QComboBox,
    QMenu,
)
from PySide6.QtCore import Qt, Signal, QPointF
from PySide6.QtGui import (
    QBrush,
    QPen,
    QColor,
    QPainter,
    QPixmap,
    QCursor,
    QAction,
)
from src.core.theme_manager import ThemeManager
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)


class MarkerItem(QGraphicsEllipseItem):
    """
    Draggable circular marker on a map.

    Represents an entity or event at a specific location on the map.
    Emits signals through the parent MapGraphicsView when dragged.
    """

    MARKER_RADIUS = 8
    COLORS = {
        "entity": QColor("#3498DB"),  # Blue
        "event": QColor("#F39C12"),  # Orange
        "default": QColor("#888888"),  # Gray
    }

    def __init__(
        self, marker_id: str, object_type: str, pixmap_item: QGraphicsPixmapItem
    ):
        """
        Initializes a MarkerItem.

        Args:
            marker_id: Unique identifier for the marker.
            object_type: Type of object ('entity' or 'event').
            pixmap_item: Reference to the map pixmap item for coordinate conversion.
        """
        super().__init__(
            -self.MARKER_RADIUS,
            -self.MARKER_RADIUS,
            self.MARKER_RADIUS * 2,
            self.MARKER_RADIUS * 2,
        )

        self.marker_id = marker_id
        self.object_type = object_type
        self.pixmap_item = pixmap_item

        # Styling
        color = self.COLORS.get(object_type, self.COLORS["default"])
        self.setBrush(QBrush(color))
        self.setPen(QPen(QColor(255, 255, 255), 2))

        # Make draggable
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)

        # Cursor hint
        self.setCursor(QCursor(Qt.PointingHandCursor))

        # Z-value to appear on top of the map
        self.setZValue(10)

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value):
        """
        Called when the item's state changes.

        Detects position changes and emits a signal with normalized coordinates.

        Args:
            change: The type of change.
            value: The new value.

        Returns:
            The processed value.
        """
        if change == QGraphicsItem.ItemPositionHasChanged:
            # Get the marker's current position in scene coordinates
            scene_pos = self.pos()

            # Convert to normalized coordinates [0.0, 1.0] relative to pixmap
            if self.pixmap_item and self.pixmap_item.pixmap():
                pixmap_rect = self.pixmap_item.sceneBoundingRect()

                # Calculate position relative to pixmap top-left
                rel_x = scene_pos.x() - pixmap_rect.left()
                rel_y = scene_pos.y() - pixmap_rect.top()

                # Normalize to [0.0, 1.0]
                norm_x = rel_x / pixmap_rect.width() if pixmap_rect.width() > 0 else 0.0
                norm_y = (
                    rel_y / pixmap_rect.height() if pixmap_rect.height() > 0 else 0.0
                )

                # Clamp to [0.0, 1.0]
                norm_x = max(0.0, min(1.0, norm_x))
                norm_y = max(0.0, min(1.0, norm_y))

                # Emit signal through the graphics view
                if self.scene() and self.scene().views():
                    view = self.scene().views()[0]
                    if isinstance(view, MapGraphicsView):
                        view.marker_moved.emit(self.marker_id, norm_x, norm_y)
                        logger.debug(
                            f"Marker {self.marker_id} moved to normalized "
                            f"({norm_x:.3f}, {norm_y:.3f})"
                        )

        return super().itemChange(change, value)


class MapGraphicsView(QGraphicsView):
    """
    Graphics view for displaying a map image with draggable markers.

    Signals:
        marker_moved: Emitted when a marker is dragged to a new position.
                     Args: (marker_id: str, x: float, y: float)
                     Coordinates are normalized [0.0, 1.0] relative to map image.
    """

    marker_moved = Signal(str, float, float)
    add_marker_requested = Signal(float, float)  # x, y (normalized)
    delete_marker_requested = Signal(str)  # marker_id

    def __init__(self, parent=None):
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
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)

        # Map and markers
        self.pixmap_item: Optional[QGraphicsPixmapItem] = None
        self.markers: Dict[str, MarkerItem] = {}

        # Theme
        self.tm = ThemeManager()
        self.tm.theme_changed.connect(self._update_theme)
        self._update_theme(self.tm.get_theme())

    def _update_theme(self, theme):
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
            self.fitInView(self.pixmap_item, Qt.KeepAspectRatio)
            self.scene.setSceneRect(self.pixmap_item.boundingRect())

            logger.info(f"Loaded map: {image_path}")
            return True

        except Exception as e:
            logger.error(f"Error loading map: {e}")
            return False

    def resizeEvent(self, event):
        """
        Handle resize events to keep the map fitted in the view.
        """
        super().resizeEvent(event)
        if self.pixmap_item:
            self.fitInView(self.pixmap_item, Qt.KeepAspectRatio)

    def add_marker(self, marker_id: str, object_type: str, x: float, y: float) -> None:
        """
        Adds a marker to the map at normalized coordinates.

        Args:
            marker_id: Unique identifier for the marker.
            object_type: Type of object ('entity' or 'event').
            x: Normalized X coordinate [0.0, 1.0].
            y: Normalized Y coordinate [0.0, 1.0].
        """
        if not self.pixmap_item:
            logger.warning("Cannot add marker: no map loaded")
            return

        # Remove existing marker if present
        if marker_id in self.markers:
            self.scene.removeItem(self.markers[marker_id])
            del self.markers[marker_id]

        # Create new marker
        marker = MarkerItem(marker_id, object_type, self.pixmap_item)

        # Convert normalized to scene coordinates
        scene_pos = self._normalized_to_scene(x, y)
        marker.setPos(scene_pos)

        # Add to scene and track
        self.scene.addItem(marker)
        self.markers[marker_id] = marker

        logger.debug(f"Added marker {marker_id} at normalized ({x:.3f}, {y:.3f})")

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

    def wheelEvent(self, event):
        """Handle mouse wheel for zooming."""
        # Zoom factor
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)

    def contextMenuEvent(self, event):
        """
        Handles context menu events for adding/removing markers.
        """
        if not self.pixmap_item:
            return

        # Check if we clicked on a marker
        item = self.itemAt(event.pos())
        if isinstance(item, MarkerItem):
            menu = QMenu(self)
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


class MapWidget(QWidget):
    """
    Container widget for the map view.

    Provides a clean interface to the map system with signal routing.

    Signals:
        marker_position_changed: Emitted when a marker is moved by the user.
                                Args: (marker_id: str, x: float, y: float)
                                Coordinates are normalized [0.0, 1.0].
    """

    marker_position_changed = Signal(str, float, float)
    create_map_requested = Signal()
    delete_map_requested = Signal()
    map_selected = Signal(str)  # map_id
    create_marker_requested = Signal(float, float)  # x, y normalized
    delete_marker_requested = Signal(str)  # marker_id

    def __init__(self, parent=None):
        """
        Initializes the MapWidget.

        Args:
            parent: Parent widget.
        """
        super().__init__(parent)

        # Create view
        self.view = MapGraphicsView(self)

        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        # Toolbar
        self.toolbar = QToolBar(self)
        layout.addWidget(self.toolbar)

        # Map Selector
        self.map_selector = QComboBox()
        self.map_selector.setMinimumWidth(200)
        self.map_selector.currentIndexChanged.connect(self._on_map_selected)
        self.toolbar.addWidget(self.map_selector)

        # Actions
        self.action_new_map = QAction("New Map", self)
        self.action_new_map.triggered.connect(self.create_map_requested.emit)
        self.toolbar.addAction(self.action_new_map)

        self.action_delete_map = QAction("Delete Map", self)
        self.action_delete_map.triggered.connect(self.delete_map_requested.emit)
        self.toolbar.addAction(self.action_delete_map)

        # Add View (after toolbar)
        layout.addWidget(self.view)

        # Connect signals
        self.view.marker_moved.connect(self._on_marker_moved)
        self.view.add_marker_requested.connect(self.create_marker_requested.emit)
        self.view.delete_marker_requested.connect(self.delete_marker_requested.emit)

        self._maps_data = []  # List of maps for selector

    def set_maps(self, maps: list):
        """
        Populates the map selector with available maps.

        Args:
            maps: List of Map objects.
        """
        self.map_selector.blockSignals(True)
        self.map_selector.clear()
        self._maps_data = maps

        for m in maps:
            self.map_selector.addItem(m.name, m.id)

        self.map_selector.setCurrentIndex(-1)
        self.map_selector.blockSignals(False)

    def select_map(self, map_id: str):
        """Selects the map with the given ID in the dropdown."""
        index = self.map_selector.findData(map_id)
        if index >= 0:
            logger.debug(f"Selecting map index {index} for id {map_id}")
            self.map_selector.setCurrentIndex(index)
        else:
            logger.warning(f"Map ID {map_id} not found in selector")

    def _on_map_selected(self, index):
        """Handle map selection change."""
        if index >= 0:
            map_id = self.map_selector.itemData(index)
            self.map_selected.emit(map_id)

    def _on_marker_moved(self, marker_id: str, x: float, y: float) -> None:
        """
        Handles marker movement from the view.

        Updates the widget's marker position and emits signal for persistence.

        Args:
            marker_id: ID of the moved marker.
            x: New normalized X coordinate.
            y: New normalized Y coordinate.
        """
        # Update marker position in widget
        self.update_marker_position(marker_id, x, y)

        # Emit signal so app layer can persist the change
        self.marker_position_changed.emit(marker_id, x, y)

        logger.debug(f"MapWidget: marker {marker_id} moved to ({x:.3f}, {y:.3f})")

    def load_map(self, image_path: str) -> bool:
        """
        Loads a map image.

        Args:
            image_path: Path to the image file.

        Returns:
            bool: True if successful, False otherwise.
        """
        return self.view.load_map(image_path)

    def add_marker(self, marker_id: str, object_type: str, x: float, y: float) -> None:
        """
        Adds a marker to the map.

        Args:
            marker_id: Unique identifier for the marker.
            object_type: Type of object ('entity' or 'event').
            x: Normalized X coordinate [0.0, 1.0].
            y: Normalized Y coordinate [0.0, 1.0].
        """
        self.view.add_marker(marker_id, object_type, x, y)

    def update_marker_position(self, marker_id: str, x: float, y: float) -> None:
        """
        Updates a marker's position.

        Args:
            marker_id: Unique identifier for the marker.
            x: Normalized X coordinate [0.0, 1.0].
            y: Normalized Y coordinate [0.0, 1.0].
        """
        self.view.update_marker_position(marker_id, x, y)

    def remove_marker(self, marker_id: str) -> None:
        """
        Removes a marker from the map.

        Args:
            marker_id: Unique identifier for the marker.
        """
        self.view.remove_marker(marker_id)

    def clear_markers(self) -> None:
        """Removes all markers from the map."""
        self.view.clear_markers()
