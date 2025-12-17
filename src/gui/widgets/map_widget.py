"""
Map Widget Module.

Provides an interactive map view with draggable markers using QGraphicsView/Scene.
Supports normalized coordinates [0.0, 1.0] for markers independent of image size.
"""

import os
from PySide6.QtWidgets import (
    QGraphicsView,
    QGraphicsScene,
    QGraphicsItem,
    QGraphicsPixmapItem,
    QWidget,
    QVBoxLayout,
    QToolBar,
    QComboBox,
    QMenu,
    QDialog,
    QGridLayout,
    QPushButton,
    QLabel,
    QScrollArea,
    QFrame,
)
from PySide6.QtCore import Qt, Signal, QPointF, QRectF
from PySide6.QtGui import (
    QBrush,
    QPen,
    QColor,
    QPainter,
    QPixmap,
    QCursor,
    QAction,
)
from PySide6.QtSvg import QSvgRenderer
from src.core.theme_manager import ThemeManager
from typing import Optional, Dict, List
import logging

logger = logging.getLogger(__name__)

# Path to marker icons
MARKER_ICONS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "assets", "icons", "markers"
)


def get_available_icons() -> List[str]:
    """
    Returns a list of available marker icon filenames.

    Returns:
        List[str]: List of .svg filenames in the markers folder.
    """
    if not os.path.exists(MARKER_ICONS_PATH):
        return []
    return [f for f in os.listdir(MARKER_ICONS_PATH) if f.endswith(".svg")]


class MarkerItem(QGraphicsItem):
    """
    Draggable marker on a map with customizable SVG icon.

    Represents an entity or event at a specific location on the map.
    Emits signals through the parent MapGraphicsView when dragged.
    Supports custom SVG icons with fallback to colored circles.
    """

    MARKER_SIZE = 24  # Size of the marker icon
    COLORS = {
        "entity": QColor("#3498DB"),  # Blue
        "event": QColor("#F39C12"),  # Orange
        "default": QColor("#888888"),  # Gray
    }
    DEFAULT_ICON = "map-pin.svg"

    def __init__(
        self,
        marker_id: str,
        object_type: str,
        label: str,
        pixmap_item: QGraphicsPixmapItem,
        icon: Optional[str] = None,
    ):
        """
        Initializes a MarkerItem.

        Args:
            marker_id: Unique identifier for the marker.
            object_type: Type of object ('entity' or 'event').
            label: Label text for the marker (tooltip).
            pixmap_item: Reference to the map pixmap item for coordinate conversion.
            icon: Optional icon filename (e.g., 'castle.svg'). Falls back to circle.
        """
        super().__init__()

        self.marker_id = marker_id
        self.object_type = object_type
        self.label = label
        self.pixmap_item = pixmap_item
        self._icon_name = icon
        self._svg_renderer: Optional[QSvgRenderer] = None
        self._color = self.COLORS.get(object_type, self.COLORS["default"])

        # Load icon if specified
        self._load_icon(icon)

        logger.debug(
            f"Created MarkerItem {marker_id} with label: {label}, icon: {icon}"
        )

        # Tooltip
        self.setToolTip(label)

        # Make draggable
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)

        # Cursor hint
        self.setCursor(QCursor(Qt.PointingHandCursor))

        # Z-value to appear on top of the map
        self.setZValue(10)

        # Drag tracking
        self._is_dragging = False
        self._drag_start_pos = None

    def _load_icon(self, icon_name: Optional[str]) -> None:
        """
        Loads an SVG icon for the marker.

        Args:
            icon_name: Filename of the icon (e.g., 'castle.svg').
        """
        if not icon_name:
            icon_name = self.DEFAULT_ICON

        icon_path = os.path.join(MARKER_ICONS_PATH, icon_name)
        if os.path.exists(icon_path):
            self._svg_renderer = QSvgRenderer(icon_path)
            if not self._svg_renderer.isValid():
                logger.warning(f"Invalid SVG file: {icon_path}")
                self._svg_renderer = None
            else:
                self._icon_name = icon_name
        else:
            logger.debug(f"Icon not found: {icon_path}, using fallback circle")
            self._svg_renderer = None

    def set_icon(self, icon_name: str) -> None:
        """
        Changes the marker's icon.

        Args:
            icon_name: Filename of the new icon.
        """
        self._load_icon(icon_name)
        self.update()

    def get_icon(self) -> Optional[str]:
        """
        Returns the current icon filename.

        Returns:
            Optional[str]: The icon filename or None if using fallback.
        """
        return self._icon_name

    def boundingRect(self) -> QRectF:
        """
        Returns the bounding rectangle for the marker.

        Returns:
            QRectF: The bounding rect centered on (0, 0).
        """
        half = self.MARKER_SIZE / 2
        return QRectF(-half, -half, self.MARKER_SIZE, self.MARKER_SIZE)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        """
        Paints the marker, either as an SVG icon or fallback circle.

        Args:
            painter: The QPainter to use.
            option: Style options.
            widget: The widget being painted on.
        """
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.boundingRect()

        if self._svg_renderer and self._svg_renderer.isValid():
            # Render SVG with color tinting
            # First draw a shadow/background
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor(0, 0, 0, 50)))
            painter.drawEllipse(rect.adjusted(2, 2, 2, 2))

            # Render the SVG
            self._svg_renderer.render(painter, rect)

            # Draw selection highlight
            if self.isSelected():
                painter.setPen(QPen(QColor(255, 255, 255), 2))
                painter.setBrush(Qt.NoBrush)
                painter.drawRect(rect)
        else:
            # Fallback to colored circle
            painter.setPen(QPen(QColor(255, 255, 255), 2))
            painter.setBrush(QBrush(self._color))
            painter.drawEllipse(rect)

    def mousePressEvent(self, event):
        """Track drag start."""
        if event.button() == Qt.LeftButton:
            self._is_dragging = True
            self._drag_start_pos = self.pos()
            logger.debug(
                f"Marker {self.marker_id} drag started at {self._drag_start_pos}"
            )
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        """Emit position change on drag end."""
        if event.button() == Qt.LeftButton and self._is_dragging:
            self._is_dragging = False
            # Calculate final normalized position
            if self.pixmap_item and self.pixmap_item.pixmap():
                scene_pos = self.pos()
                pixmap_rect = self.pixmap_item.sceneBoundingRect()

                rel_x = scene_pos.x() - pixmap_rect.left()
                rel_y = scene_pos.y() - pixmap_rect.top()

                norm_x = rel_x / pixmap_rect.width() if pixmap_rect.width() > 0 else 0.0
                norm_y = (
                    rel_y / pixmap_rect.height() if pixmap_rect.height() > 0 else 0.0
                )

                norm_x = max(0.0, min(1.0, norm_x))
                norm_y = max(0.0, min(1.0, norm_y))

                # Emit only on release
                if self.scene() and self.scene().views():
                    view = self.scene().views()[0]
                    if isinstance(view, MapGraphicsView):
                        view.marker_moved.emit(self.marker_id, norm_x, norm_y)
                        logger.debug(
                            f"Marker {self.marker_id} drag ended at normalized "
                            f"({norm_x:.3f}, {norm_y:.3f})"
                        )
        super().mouseReleaseEvent(event)

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value):
        """
        Called when the item's state changes.

        Note: We no longer emit marker_moved here. Position updates
        are only emitted on mouseReleaseEvent to avoid flooding.

        Args:
            change: The type of change.
            value: The new value.

        Returns:
            The processed value.
        """
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
    change_marker_icon_requested = Signal(str, str)  # marker_id, new_icon

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
        Handle resize events.
        Note: We no longer auto-fit here to allow the user to maintain zoom level.
        """
        super().resizeEvent(event)

    def fit_to_view(self):
        """Fits the map to the current view size."""
        if self.pixmap_item:
            self.fitInView(self.pixmap_item, Qt.KeepAspectRatio)
            logger.debug("Fit map to view.")

    def mousePressEvent(self, event):
        """
        Handle mouse press to implement Smart Drag.
        If clicking a marker, disable view panning.
        If clicking background, enable view panning.
        """
        item = self.itemAt(event.pos())
        logger.debug(f"Mouse Press at {event.pos()}. Item found: {item}")

        if isinstance(item, MarkerItem):
            logger.debug(f"Click on Marker {item.marker_id}. Setting NoDrag.")
            self.setDragMode(QGraphicsView.NoDrag)
        else:
            logger.debug("Click on background. Setting ScrollHandDrag.")
            self.setDragMode(QGraphicsView.ScrollHandDrag)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        """Reset drag mode on release."""
        logger.debug("Mouse Release. Resetting to ScrollHandDrag.")
        super().mouseReleaseEvent(event)
        self.setDragMode(QGraphicsView.ScrollHandDrag)

    def add_marker(
        self,
        marker_id: str,
        object_type: str,
        label: str,
        x: float,
        y: float,
        icon: Optional[str] = None,
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

        # Create new marker with optional icon
        marker = MarkerItem(marker_id, object_type, label, self.pixmap_item, icon)

        # Convert normalized to scene coordinates
        scene_pos = self._normalized_to_scene(x, y)
        marker.setPos(scene_pos)

        # Add to scene and track
        self.scene.addItem(marker)
        self.markers[marker_id] = marker

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

    def wheelEvent(self, event):
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

            # Change Icon action
            change_icon_action = QAction("Change Icon...", self)
            change_icon_action.triggered.connect(lambda: self._show_icon_picker(item))
            menu.addAction(change_icon_action)

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
        if dialog.exec() == QDialog.Accepted:
            selected_icon = dialog.selected_icon
            if selected_icon:
                marker_item.set_icon(selected_icon)
                self.change_marker_icon_requested.emit(
                    marker_item.marker_id, selected_icon
                )


class IconPickerDialog(QDialog):
    """
    Dialog for selecting a marker icon from available SVG icons.

    Displays a grid of icon buttons that the user can click to select.
    """

    def __init__(self, parent=None):
        """
        Initializes the IconPickerDialog.

        Args:
            parent: Parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle("Select Marker Icon")
        self.setMinimumSize(300, 200)
        self.selected_icon: Optional[str] = None

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Sets up the dialog UI."""
        layout = QVBoxLayout(self)

        # Scroll area for icons
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        # Container for icon grid
        container = QWidget()
        grid = QGridLayout(container)
        grid.setSpacing(8)

        # Load available icons
        icons = get_available_icons()
        if not icons:
            label = QLabel("No icons found in assets/icons/markers/")
            layout.addWidget(label)
            return

        # Create icon buttons in a grid
        cols = 4
        for i, icon_name in enumerate(sorted(icons)):
            row = i // cols
            col = i % cols

            btn = QPushButton()
            btn.setFixedSize(48, 48)
            btn.setToolTip(icon_name.replace(".svg", ""))

            # Load icon preview
            icon_path = os.path.join(MARKER_ICONS_PATH, icon_name)
            pixmap = QPixmap(icon_path)
            if not pixmap.isNull():
                btn.setIcon(pixmap.scaled(32, 32, Qt.KeepAspectRatio))
                btn.setIconSize(pixmap.size())

            # Connect click
            btn.clicked.connect(
                lambda checked, name=icon_name: self._on_icon_selected(name)
            )
            grid.addWidget(btn, row, col)

        scroll.setWidget(container)
        layout.addWidget(scroll)

    def _on_icon_selected(self, icon_name: str) -> None:
        """
        Handles icon selection.

        Args:
            icon_name: The selected icon filename.
        """
        self.selected_icon = icon_name
        self.accept()


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
    change_marker_icon_requested = Signal(str, str)  # marker_id, new_icon

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

        self.toolbar.addSeparator()

        self.action_fit_view = QAction("Fit to View", self)
        self.action_fit_view.triggered.connect(self.view.fit_to_view)
        self.toolbar.addAction(self.action_fit_view)

        # Add View (after toolbar)
        layout.addWidget(self.view)

        # Connect signals
        self.view.marker_moved.connect(self._on_marker_moved)
        self.view.add_marker_requested.connect(self.create_marker_requested.emit)
        self.view.delete_marker_requested.connect(self.delete_marker_requested.emit)
        self.view.change_marker_icon_requested.connect(
            self.change_marker_icon_requested.emit
        )

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

    def add_marker(
        self,
        marker_id: str,
        object_type: str,
        label: str,
        x: float,
        y: float,
        icon: Optional[str] = None,
    ) -> None:
        """
        Adds a marker to the map.

        Args:
            marker_id: Unique identifier for the marker.
            object_type: Type of object ('entity' or 'event').
            label: Marker label.
            x: Normalized X coordinate [0.0, 1.0].
            y: Normalized Y coordinate [0.0, 1.0].
            icon: Optional icon filename.
        """
        self.view.add_marker(marker_id, object_type, label, x, y, icon)

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
