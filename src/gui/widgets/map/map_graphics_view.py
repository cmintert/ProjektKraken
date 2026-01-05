"""
Map Graphics View Module.

Provides the MapGraphicsView class for rendering and interacting with the map.
"""

import json
import logging
from typing import Dict, Optional

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
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

from src.core.marker import Marker
from src.core.theme_manager import ThemeManager
from src.gui.widgets.map.icon_picker_dialog import IconPickerDialog
from src.gui.widgets.map.marker_item import MarkerItem
from src.gui.widgets.map.motion_path_item import MotionPathItem

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
    marker_keyframe_changed = Signal(
        str, float, float, float
    )  # marker_id, t, norm_x, norm_y
    marker_keyframe_deleted = Signal(str, float)  # marker_id, t
    marker_keyframe_duplicated = Signal(
        str, float, float, float
    )  # marker_id, source_t, norm_x, norm_y
    edit_keyframe_requested = Signal(str, float)  # marker_id, t

    marker_clicked = Signal(str, str)  # marker_id, object_type
    marker_drop_requested = Signal(str, str, str, float, float)
    add_marker_requested = Signal(float, float)
    delete_marker_requested = Signal(str)
    change_marker_icon_requested = Signal(str, str)
    change_marker_color_requested = Signal(str, str)

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
        self.motion_paths: Dict[str, MotionPathItem] = {}

        # State
        self.current_time = 0.0
        self.record_mode = False
        self.current_map_path: Optional[str] = None
        self._last_motion_path_marker_id: Optional[str] = None  # Sticky path visibility

        # Theme
        self.tm = ThemeManager()
        self.tm.theme_changed.connect(self._update_theme)
        self._update_theme(self.tm.get_theme())

        # Selection changes for motion paths
        self.scene.selectionChanged.connect(self._on_selection_changed)

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

            # Check if this is a reload of the same map
            is_reload = self.current_map_path == image_path

            # Clear existing map
            if self.pixmap_item:
                self.scene.removeItem(self.pixmap_item)

            # Add new map
            self.pixmap_item = QGraphicsPixmapItem(pixmap)
            self.pixmap_item.setZValue(0)  # Behind markers
            self.scene.addItem(self.pixmap_item)

            self.scene.setSceneRect(self.pixmap_item.boundingRect())

            # Only reset view if it's a new map
            if not is_reload:
                self.fitInView(self.pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)
                self.current_map_path = image_path

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

        In Record Mode, clicking a marker creates/updates a keyframe.
        """
        item = self.itemAt(event.pos())
        logger.debug(f"Mouse Press at {event.pos()}. Item found: {item}")

        if isinstance(item, MarkerItem):
            logger.debug(
                f"Click on Marker {item.marker_id}. "
                f"Record Mode: {self.record_mode}. Setting NoDrag."
            )
            self.setDragMode(QGraphicsView.DragMode.NoDrag)

            # Store press position and marker for Record Mode handling
            self._press_pos = self.mapToScene(event.pos())
            self._press_marker = item
        else:
            logger.debug("Click on background. Setting ScrollHandDrag.")
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            self._press_pos = None
            self._press_marker = None
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """
        Reset drag mode on release.

        In Record Mode, if clicking (not dragging) a marker, create/update keyframe.
        """
        logger.debug("Mouse Release. Resetting to ScrollHandDrag.")

        # Check for Record Mode keyframe creation
        if (
            self.record_mode
            and hasattr(self, "_press_marker")
            and self._press_marker is not None
            and hasattr(self, "_press_pos")
        ):

            release_pos = self.mapToScene(event.pos())
            distance = (release_pos - self._press_pos).manhattanLength()

            logger.info(
                f"Record Mode: Checking click on marker "
                f"{self._press_marker.marker_id}. Distance: {distance}"
            )

            # If minimal movement (click, not drag)
            if distance < 10:  # Threshold for click vs drag
                marker_id = self._press_marker.marker_id
                logger.info(
                    f"Record Mode: Creating/updating keyframe for {marker_id} "
                    f"at time {self.current_time}"
                )

                # Get normalized coordinates from marker's current position
                if self.pixmap_item:
                    marker_scene_pos = self._press_marker.scenePos()
                    norm_x, norm_y = self._scene_to_normalized(
                        marker_scene_pos.x(), marker_scene_pos.y()
                    )

                    logger.info(
                        f"Record Mode: Emitting keyframe_changed for {marker_id}: "
                        f"t={self.current_time}, x={norm_x:.3f}, y={norm_y:.3f}"
                    )

                    # Emit keyframe change signal
                    self.marker_keyframe_changed.emit(
                        marker_id, self.current_time, norm_x, norm_y
                    )

        # Clean up
        self._press_marker = None
        self._press_pos = None

        super().mouseReleaseEvent(event)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

    def drawForeground(self, painter: QPainter, rect: QRectF) -> None:
        """Draw overlay for record mode."""
        super().drawForeground(painter, rect)
        # Using stylesheet for border is simpler and sufficient.
        pass

    def add_marker(
        self,
        marker_id: str,
        object_type: str,
        label: str,
        x: float,
        y: float,
        icon: Optional[str] = None,
        color: Optional[str] = None,
        marker_data: Optional[Marker] = None,
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
            color: Optional color hex.
            marker_data: Core Marker data object (for temporal logic).
        """
        if not self.pixmap_item:
            logger.warning("Cannot add marker: no map loaded")
            return

        # Remove existing marker if present
        if marker_id in self.markers:
            self.scene.removeItem(self.markers[marker_id])
            del self.markers[marker_id]

        # Remove existing motion path if present
        if marker_id in self.motion_paths:
            self.scene.removeItem(self.motion_paths[marker_id])
            del self.motion_paths[marker_id]

        # Create new marker with optional icon and color
        marker = MarkerItem(
            marker_id, object_type, label, self.pixmap_item, icon, color, marker_data
        )

        # Convert normalized to scene coordinates
        scene_pos = self._normalized_to_scene(x, y)
        marker.setPos(scene_pos)

        # Add to scene and track
        self.scene.addItem(marker)
        self.markers[marker_id] = marker

        # Create motion path item if we have data
        if marker_data and marker_data.attributes.get("temporal", {}).get("enabled"):
            motion_path = MotionPathItem(marker_id)
            self.scene.addItem(motion_path)
            self.motion_paths[marker_id] = motion_path

            logger.debug(
                f"Created motion path for {marker_id} with "
                f"{len(marker_data.attributes['temporal']['keyframes'])} keyframes"
            )

            # Connect Keyframe Signals
            motion_path.keyframe_moved.connect(self._on_keyframe_moved)
            motion_path.keyframe_deleted.connect(self._on_keyframe_deleted)
            motion_path.keyframe_duplicated.connect(self._on_keyframe_duplicated)
            motion_path.keyframe_double_clicked.connect(
                self._on_keyframe_double_clicked
            )

            # Initial update of path with current map dimensions
            rect = self.pixmap_item.sceneBoundingRect()
            motion_path.update_path(
                marker_data.attributes["temporal"]["keyframes"],
                rect.width(),
                rect.height(),
            )
            motion_path.setVisible(False)  # Hidden by default until selected
            logger.debug(f"Motion path for {marker_id} initialized and hidden")
        else:
            logger.debug(
                f"No motion path created for {marker_id} - "
                f"temporal_enabled={marker_data.attributes.get('temporal', {}).get('enabled') if marker_data else 'no_data'}"
            )

        # Connect click signal
        marker.clicked.connect(self.marker_clicked.emit)

        logger.debug(
            f"Added marker {marker_id} ({label}) at normalized ({x:.3f}, {y:.3f})"
        )

    def _on_keyframe_moved(
        self, marker_id: str, t: float, scene_x: float, scene_y: float
    ) -> None:
        """
        Handle keyframe movement from MotionPathItem.
        Normalize coordinates and bubble up.
        """
        norm_x, norm_y = self._scene_to_normalized(scene_x, scene_y)
        self.marker_keyframe_changed.emit(marker_id, t, norm_x, norm_y)

    def _on_keyframe_duplicated(
        self, marker_id: str, source_t: float, scene_x: float, scene_y: float
    ) -> None:
        """Handle keyframe duplication."""
        norm_x, norm_y = self._scene_to_normalized(scene_x, scene_y)
        self.marker_keyframe_duplicated.emit(marker_id, source_t, norm_x, norm_y)

    def _on_keyframe_deleted(self, marker_id: str, t: float) -> None:
        """Handle keyframe deletion."""
        self.marker_keyframe_deleted.emit(marker_id, t)

    def _on_keyframe_double_clicked(self, marker_id: str, t: float) -> None:
        """Handle keyframe edit request."""
        self.edit_keyframe_requested.emit(marker_id, t)

    def _scene_to_normalized(
        self, scene_x: float, scene_y: float
    ) -> tuple[float, float]:
        """Helper to convert scene coords to normalized."""
        if not self.pixmap_item:
            return 0.0, 0.0

        pixmap_rect = self.pixmap_item.sceneBoundingRect()
        rel_x = scene_x - pixmap_rect.left()
        rel_y = scene_y - pixmap_rect.top()

        width = pixmap_rect.width()
        height = pixmap_rect.height()

        norm_x = rel_x / width if width > 0 else 0.0
        norm_y = rel_y / height if height > 0 else 0.0
        return norm_x, norm_y

    def update_temporal_state(self, current_time: float) -> None:
        """
        Updates all markers and motion paths for the given time.
        """
        self.current_time = current_time

        for marker in self.markers.values():
            marker.update_temporal_state(current_time)

    def _on_selection_changed(self) -> None:
        """
        Show motion paths for selected markers.
        Uses sticky visibility: path stays visible until a different marker is selected.
        """
        from src.gui.widgets.map.motion_path_item import HandleItem

        selected_items = self.scene.selectedItems()
        selected_ids = set()

        logger.debug(f"Selection changed: {len(selected_items)} items selected")

        # Check what is currently selected
        for item in selected_items:
            if isinstance(item, MarkerItem):
                selected_ids.add(item.marker_id)
                logger.debug(f"  - Selected marker: {item.marker_id}")
            elif isinstance(item, HandleItem):
                # If a handle is selected, keep its parent motion path visible
                parent = item.parentItem()
                if isinstance(parent, MotionPathItem):
                    selected_ids.add(parent.marker_id)
                    logger.debug(
                        f"  - Selected handle, keeping path for {parent.marker_id}"
                    )
            elif isinstance(item, MotionPathItem):
                # If path is selected directly, keep it visible
                selected_ids.add(item.marker_id)
                logger.debug(f"  - Selected motion path for marker: {item.marker_id}")

        # Sticky behavior: if nothing marker-related is selected, keep showing last path
        if not selected_ids and self._last_motion_path_marker_id:
            selected_ids.add(self._last_motion_path_marker_id)
            logger.debug(
                f"  - No selection, keeping last path: {self._last_motion_path_marker_id}"
            )
        elif selected_ids:
            # Update last shown marker (pick first if multiple)
            self._last_motion_path_marker_id = next(iter(selected_ids))

        # Update visibility
        logger.debug(f"Total motion paths: {len(self.motion_paths)}")
        for mid, path in self.motion_paths.items():
            should_be_visible = mid in selected_ids
            path.setVisible(should_be_visible)
            logger.debug(f"  - Motion path for {mid}: visible={should_be_visible}")

    def set_record_mode(self, enabled: bool) -> None:
        """Sets the recording mode state."""
        self.record_mode = enabled
        logger.info(f"Map Record Mode: {enabled}")

        # Visual cues
        if enabled:
            self.setStyleSheet("border: 4px solid #c0392b;")
            self.setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.setStyleSheet("border: none;")
            self.unsetCursor()

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

    def update_marker_visuals(
        self,
        marker_id: str,
        label: str,
        icon: Optional[str] = None,
        color: Optional[str] = None,
    ) -> None:
        """
        Updates a marker's visual properties (label, icon, color).

        Args:
            marker_id: Unique identifier for the marker.
            label: New label text (tooltip).
            icon: Optional new icon filename.
            color: Optional new color hex string.
        """
        if marker_id not in self.markers:
            # This is expected if the updated item is not on the current map
            return
        marker = self.markers[marker_id]

        logger.debug(
            f"Updating marker {marker_id}: Old Label='{marker.label}', "
            f"New Label='{label}'"
        )

        # Update label/tooltip
        marker.label = label
        marker.setToolTip(label)

        # Update icon if provided (not None and not empty)
        if icon:
            logger.debug(f"Updating marker {marker_id}: Icon -> {icon}")
            marker.set_icon(icon)

        # Update color if provided (not None and not empty)
        if color:
            logger.debug(f"Updating marker {marker_id}: Color -> {color}")
            marker.set_color(color)

        # Force update just in case
        marker.update()

        logger.info(
            f"Updated visuals for marker {marker_id} complete. "
            f"Tooltip set to: {marker.toolTip()}"
        )

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
