"""
Map Widget Module.

Provides a graphical map visualization using QGraphicsView/Scene.
Supports panning, zooming, marker management, and scale calibration.
"""

from PySide6.QtWidgets import (
    QGraphicsView,
    QGraphicsScene,
    QGraphicsItem,
    QGraphicsPixmapItem,
    QGraphicsEllipseItem,
    QGraphicsTextItem,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QComboBox,
    QToolBar,
    QSpinBox,
    QDoubleSpinBox,
    QLineEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFileDialog,
    QMessageBox,
)
from PySide6.QtCore import Qt, Signal, QRectF, QPointF, QTimer, QPoint
from PySide6.QtGui import (
    QBrush,
    QPen,
    QColor,
    QPainter,
    QPixmap,
    QTransform,
    QWheelEvent,
    QMouseEvent,
    QCursor,
    QFont,
    QAction,
)
from src.core.theme_manager import ThemeManager
from src.core.maps import GameMap, MapMarker
from src.core.map_math import (
    pixel_to_normalized,
    normalized_to_pixel,
    calculate_distance,
)
import logging
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)


class MarkerItem(QGraphicsEllipseItem):
    """
    Visual representation of a map marker.
    
    Displays as a colored circle with a label showing the object name.
    Supports selection, dragging, and hover effects.
    """

    def __init__(self, marker: MapMarker, object_name: str, color: QColor):
        """
        Initialize a marker item.
        
        Args:
            marker: The MapMarker data object.
            object_name: Display name for the marker.
            color: Color for the marker circle.
        """
        super().__init__(-8, -8, 16, 16)  # 16x16 circle centered at origin
        self.marker = marker
        self.object_name = object_name
        
        # Visual setup
        self.setBrush(QBrush(color))
        self.setPen(QPen(QColor("#FFFFFF"), 2))
        
        # Interaction flags
        self.setFlags(
            QGraphicsItem.ItemIsSelectable
            | QGraphicsItem.ItemIsMovable
            | QGraphicsItem.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        
        # Label
        self.label = QGraphicsTextItem(object_name, self)
        self.label.setDefaultTextColor(QColor("#FFFFFF"))
        self.label.setFont(QFont("Arial", 9))
        self.label.setPos(10, -8)
        
        # Store original position for undo
        self.original_pos = None
        
    def hoverEnterEvent(self, event):
        """Enlarge on hover."""
        self.setScale(1.5)
        self.setZValue(1000)
        super().hoverEnterEvent(event)
        
    def hoverLeaveEvent(self, event):
        """Return to normal size."""
        self.setScale(1.0)
        self.setZValue(0)
        super().hoverLeaveEvent(event)
        
    def itemChange(self, change, value):
        """Track position changes."""
        if change == QGraphicsItem.ItemPositionChange and self.scene():
            # Position is changing - emit signal from parent widget
            pass
        return super().itemChange(change, value)


class MapGraphicsView(QGraphicsView):
    """
    Custom QGraphicsView with panning and zooming support.
    """
    
    marker_moved = Signal(str, float, float)  # marker_id, new_x, new_y
    marker_added = Signal(float, float)  # normalized x, y
    
    def __init__(self, parent=None):
        """Initialize the map graphics view."""
        super().__init__(parent)
        
        # Setup
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.NoDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # Panning state
        self._is_panning = False
        self._pan_start = QPoint()
        
        # Zoom limits
        self._zoom_factor = 1.0
        self._min_zoom = 0.1
        self._max_zoom = 10.0
        
        # Interaction mode
        self._mode = "pan"  # "pan", "add_marker", "measure"
        
    def set_mode(self, mode: str):
        """
        Set the interaction mode.
        
        Args:
            mode: One of "pan", "add_marker", "measure"
        """
        self._mode = mode
        if mode == "pan":
            self.setDragMode(QGraphicsView.NoDrag)
            self.setCursor(Qt.OpenHandCursor)
        elif mode == "add_marker":
            self.setDragMode(QGraphicsView.NoDrag)
            self.setCursor(Qt.CrossCursor)
        elif mode == "measure":
            self.setDragMode(QGraphicsView.NoDrag)
            self.setCursor(Qt.CrossCursor)
            
    def wheelEvent(self, event: QWheelEvent):
        """Handle mouse wheel for zooming."""
        # Calculate zoom factor
        delta = event.angleDelta().y()
        factor = 1.2 if delta > 0 else 1 / 1.2
        
        # Apply zoom with limits
        new_zoom = self._zoom_factor * factor
        if self._min_zoom <= new_zoom <= self._max_zoom:
            self.scale(factor, factor)
            self._zoom_factor = new_zoom
            
    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press for panning and marker placement."""
        if event.button() == Qt.MiddleButton or (
            event.button() == Qt.LeftButton and self._mode == "pan"
        ):
            # Start panning
            self._is_panning = True
            self._pan_start = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
        elif event.button() == Qt.LeftButton and self._mode == "add_marker":
            # Add marker at click position
            scene_pos = self.mapToScene(event.pos())
            # Convert to normalized coordinates
            if self.scene() and hasattr(self.scene(), 'map_pixmap_item'):
                pixmap_item = self.scene().map_pixmap_item
                pixmap_rect = pixmap_item.boundingRect()
                
                # Get position relative to pixmap
                local_pos = pixmap_item.mapFromScene(scene_pos)
                
                if pixmap_rect.contains(local_pos):
                    # Normalize
                    norm_x = local_pos.x() / pixmap_rect.width()
                    norm_y = local_pos.y() / pixmap_rect.height()
                    self.marker_added.emit(norm_x, norm_y)
            event.accept()
        else:
            super().mousePressEvent(event)
            
    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle mouse move for panning."""
        if self._is_panning:
            delta = event.pos() - self._pan_start
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - delta.x()
            )
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - delta.y()
            )
            self._pan_start = event.pos()
            event.accept()
        else:
            super().mouseMoveEvent(event)
            
    def mouseReleaseEvent(self, event: QMouseEvent):
        """Handle mouse release to end panning."""
        if event.button() == Qt.MiddleButton or (
            self._is_panning and event.button() == Qt.LeftButton
        ):
            self._is_panning = False
            self.setCursor(Qt.OpenHandCursor if self._mode == "pan" else Qt.CrossCursor)
            event.accept()
        else:
            super().mouseReleaseEvent(event)
            
    def reset_zoom(self):
        """Reset zoom to 100%."""
        self.resetTransform()
        self._zoom_factor = 1.0
        
    def fit_in_view(self):
        """Fit the entire map in view."""
        if self.scene():
            self.fitInView(self.scene().sceneRect(), Qt.KeepAspectRatio)
            # Update zoom factor
            transform = self.transform()
            self._zoom_factor = transform.m11()


class CalibrationDialog(QDialog):
    """
    Dialog for calibrating map scale.
    
    Allows user to set real-world dimensions for the map.
    """
    
    def __init__(self, current_map: Optional[GameMap] = None, parent=None):
        """
        Initialize calibration dialog.
        
        Args:
            current_map: Current map to show existing calibration.
            parent: Parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle("Calibrate Map Scale")
        self.setModal(True)
        
        # Form layout
        layout = QFormLayout(self)
        
        # Real width
        self.real_width_spin = QDoubleSpinBox()
        self.real_width_spin.setRange(0.1, 1000000.0)
        self.real_width_spin.setDecimals(2)
        self.real_width_spin.setValue(
            current_map.real_width if current_map else 100.0
        )
        layout.addRow("Real Width:", self.real_width_spin)
        
        # Distance unit
        self.unit_combo = QComboBox()
        self.unit_combo.addItems(["m", "km", "mi", "ft", "units"])
        if current_map:
            index = self.unit_combo.findText(current_map.distance_unit)
            if index >= 0:
                self.unit_combo.setCurrentIndex(index)
        layout.addRow("Distance Unit:", self.unit_combo)
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        
    def get_calibration(self):
        """
        Get calibration values.
        
        Returns:
            Tuple of (real_width, distance_unit)
        """
        return (
            self.real_width_spin.value(),
            self.unit_combo.currentText()
        )


class MapWidget(QWidget):
    """
    Complete map widget with toolbar and view.
    
    Provides comprehensive map management including:
    - Loading different maps
    - Pan and zoom navigation
    - Marker placement and management
    - Scale calibration
    - Distance measurement
    """
    
    map_changed = Signal(str)  # map_id
    marker_position_changed = Signal(str, float, float)  # marker_id, x, y
    marker_placement_requested = Signal(float, float)  # x, y (normalized)
    calibration_changed = Signal(float, str)  # real_width, unit
    
    def __init__(self, parent=None):
        """Initialize the map widget."""
        super().__init__(parent)
        
        # State
        self.current_map: Optional[GameMap] = None
        self.markers: Dict[str, MarkerItem] = {}  # marker_id -> MarkerItem
        
        # Setup UI
        self._setup_ui()
        
        # Theme
        self._apply_theme()
        
    def _setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Toolbar
        toolbar = self._create_toolbar()
        layout.addWidget(toolbar)
        
        # Status bar
        self.status_bar = QLabel("No map loaded")
        self.status_bar.setStyleSheet("padding: 4px; background: #2c2c2c;")
        layout.addWidget(self.status_bar)
        
        # Graphics view and scene
        self.scene = QGraphicsScene()
        self.view = MapGraphicsView()
        self.view.setScene(self.scene)
        layout.addWidget(self.view)
        
        # Connect signals
        self.view.marker_added.connect(self._on_marker_added)
        
    def _create_toolbar(self) -> QToolBar:
        """Create the toolbar with all controls."""
        toolbar = QToolBar()
        toolbar.setMovable(False)
        
        # Map selector
        toolbar.addWidget(QLabel("Map:"))
        self.map_combo = QComboBox()
        self.map_combo.setMinimumWidth(200)
        self.map_combo.currentTextChanged.connect(self._on_map_selection_changed)
        toolbar.addWidget(self.map_combo)
        
        toolbar.addSeparator()
        
        # Load map button
        load_btn = QPushButton("Load Map...")
        load_btn.clicked.connect(self._on_load_map)
        toolbar.addWidget(load_btn)
        
        toolbar.addSeparator()
        
        # Navigation tools
        pan_btn = QPushButton("Pan")
        pan_btn.setCheckable(True)
        pan_btn.setChecked(True)
        pan_btn.clicked.connect(lambda: self._set_mode("pan"))
        toolbar.addWidget(pan_btn)
        
        zoom_in_btn = QPushButton("Zoom +")
        zoom_in_btn.clicked.connect(self._zoom_in)
        toolbar.addWidget(zoom_in_btn)
        
        zoom_out_btn = QPushButton("Zoom -")
        zoom_out_btn.clicked.connect(self._zoom_out)
        toolbar.addWidget(zoom_out_btn)
        
        reset_btn = QPushButton("Reset View")
        reset_btn.clicked.connect(self._reset_view)
        toolbar.addWidget(reset_btn)
        
        fit_btn = QPushButton("Fit")
        fit_btn.clicked.connect(self._fit_in_view)
        toolbar.addWidget(fit_btn)
        
        toolbar.addSeparator()
        
        # Marker tools
        add_marker_btn = QPushButton("Add Marker")
        add_marker_btn.setCheckable(True)
        add_marker_btn.clicked.connect(lambda: self._set_mode("add_marker"))
        toolbar.addWidget(add_marker_btn)
        
        toolbar.addSeparator()
        
        # Calibration
        calibrate_btn = QPushButton("Calibrate Scale")
        calibrate_btn.clicked.connect(self._on_calibrate)
        toolbar.addWidget(calibrate_btn)
        
        # Store buttons for mode switching
        self.mode_buttons = {
            "pan": pan_btn,
            "add_marker": add_marker_btn,
        }
        
        return toolbar
        
    def _apply_theme(self):
        """Apply theme to the widget."""
        try:
            theme = ThemeManager()
            if theme and theme.current_theme:
                colors = theme.current_theme
                
                # Scene background
                self.scene.setBackgroundBrush(QBrush(QColor(colors.get("background", "#1e1e1e"))))
        except Exception as e:
            # Theme may not be available during testing
            logger.debug(f"Could not apply theme: {e}")
            
    def load_map(self, game_map: GameMap, image_path: str):
        """
        Load a map into the widget.
        
        Args:
            game_map: GameMap object with metadata.
            image_path: Absolute path to the map image file.
        """
        self.current_map = game_map
        
        # Clear scene
        self.scene.clear()
        self.markers.clear()
        
        # Load image
        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            logger.error(f"Failed to load map image: {image_path}")
            self.status_bar.setText(f"Error: Could not load {image_path}")
            return
            
        # Add pixmap to scene
        pixmap_item = QGraphicsPixmapItem(pixmap)
        self.scene.addItem(pixmap_item)
        self.scene.map_pixmap_item = pixmap_item  # Store reference
        
        # Set scene rect to image bounds
        self.scene.setSceneRect(pixmap_item.boundingRect())
        
        # Fit in view
        self.view.fitInView(pixmap_item, Qt.KeepAspectRatio)
        
        # Update status
        self._update_status()
        
        logger.info(f"Loaded map: {game_map.name} ({pixmap.width()}x{pixmap.height()})")
        
    def add_marker(self, marker: MapMarker, object_name: str, color: QColor = None):
        """
        Add a marker to the map.
        
        Args:
            marker: MapMarker object with position data.
            object_name: Display name for the marker.
            color: Color for the marker (optional).
        """
        if not self.current_map or not hasattr(self.scene, 'map_pixmap_item'):
            logger.warning("Cannot add marker: no map loaded")
            return
            
        if color is None:
            color = QColor("#E74C3C")  # Default red
            
        # Create marker item
        marker_item = MarkerItem(marker, object_name, color)
        
        # Convert normalized to pixel coordinates
        pixmap_item = self.scene.map_pixmap_item
        pixmap_rect = pixmap_item.boundingRect()
        
        pixel_x = marker.x * pixmap_rect.width()
        pixel_y = marker.y * pixmap_rect.height()
        
        # Position relative to pixmap
        marker_item.setPos(pixel_x, pixel_y)
        marker_item.setParentItem(pixmap_item)
        
        # Store marker
        self.markers[marker.id] = marker_item
        
        logger.debug(f"Added marker {object_name} at ({marker.x:.3f}, {marker.y:.3f})")
        
    def remove_marker(self, marker_id: str):
        """
        Remove a marker from the map.
        
        Args:
            marker_id: ID of the marker to remove.
        """
        if marker_id in self.markers:
            item = self.markers[marker_id]
            self.scene.removeItem(item)
            del self.markers[marker_id]
            logger.debug(f"Removed marker {marker_id}")
            
    def clear_markers(self):
        """Remove all markers from the map."""
        for marker_id in list(self.markers.keys()):
            self.remove_marker(marker_id)
            
    def update_marker_position(self, marker_id: str, x: float, y: float):
        """
        Update a marker's position.
        
        Args:
            marker_id: ID of the marker to update.
            x: New normalized x coordinate.
            y: New normalized y coordinate.
        """
        if marker_id not in self.markers:
            return
            
        marker_item = self.markers[marker_id]
        
        # Convert normalized to pixel
        if hasattr(self.scene, 'map_pixmap_item'):
            pixmap_rect = self.scene.map_pixmap_item.boundingRect()
            pixel_x = x * pixmap_rect.width()
            pixel_y = y * pixmap_rect.height()
            marker_item.setPos(pixel_x, pixel_y)
            
            # Update marker data
            marker_item.marker.x = x
            marker_item.marker.y = y
            
    def get_available_maps(self) -> List[str]:
        """
        Get list of available map names.
        
        Returns:
            List of map names.
        """
        # This would typically come from database
        # For now, return combo box items
        return [
            self.map_combo.itemText(i)
            for i in range(self.map_combo.count())
        ]
        
    def set_available_maps(self, map_names: List[str]):
        """
        Set the available maps in the dropdown.
        
        Args:
            map_names: List of map names to populate dropdown.
        """
        self.map_combo.clear()
        self.map_combo.addItems(map_names)
        
    def _set_mode(self, mode: str):
        """
        Set interaction mode and update UI.
        
        Args:
            mode: "pan", "add_marker", or "measure"
        """
        self.view.set_mode(mode)
        
        # Update button states
        for mode_name, button in self.mode_buttons.items():
            button.setChecked(mode_name == mode)
            
        # Update status
        mode_text = {
            "pan": "Pan mode - drag to move map",
            "add_marker": "Add marker mode - click to place marker",
            "measure": "Measure mode - click two points"
        }
        logger.debug(f"Mode changed to: {mode}")
        
    def _zoom_in(self):
        """Zoom in."""
        self.view.scale(1.2, 1.2)
        self.view._zoom_factor *= 1.2
        self._update_status()
        
    def _zoom_out(self):
        """Zoom out."""
        self.view.scale(1/1.2, 1/1.2)
        self.view._zoom_factor /= 1.2
        self._update_status()
        
    def _reset_view(self):
        """Reset zoom to 100%."""
        self.view.reset_zoom()
        self._update_status()
        
    def _fit_in_view(self):
        """Fit map in view."""
        self.view.fit_in_view()
        self._update_status()
        
    def _on_map_selection_changed(self, map_name: str):
        """Handle map selection from dropdown."""
        if map_name:
            self.map_changed.emit(map_name)
            
    def _on_load_map(self):
        """Handle load map button click."""
        # This would open a dialog to import a new map
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Map Image",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp)"
        )
        
        if file_path:
            # Emit signal or handle map import
            logger.info(f"Selected map file: {file_path}")
            # You would create a new GameMap and import the image here
            
    def _on_marker_added(self, norm_x: float, norm_y: float):
        """
        Handle marker placement request.
        
        Args:
            norm_x: Normalized x coordinate.
            norm_y: Normalized y coordinate.
        """
        self.marker_placement_requested.emit(norm_x, norm_y)
        
    def _on_calibrate(self):
        """Show calibration dialog."""
        dialog = CalibrationDialog(self.current_map, self)
        if dialog.exec() == QDialog.Accepted:
            real_width, unit = dialog.get_calibration()
            self.calibration_changed.emit(real_width, unit)
            
            # Update current map if loaded
            if self.current_map:
                self.current_map.real_width = real_width
                self.current_map.distance_unit = unit
                self._update_status()
                
    def _update_status(self):
        """Update the status bar with current map info."""
        if not self.current_map:
            self.status_bar.setText("No map loaded")
            return
            
        zoom_pct = int(self.view._zoom_factor * 100)
        status_text = (
            f"{self.current_map.name} | "
            f"{self.current_map.reference_width}x{self.current_map.reference_height} | "
            f"Scale: {self.current_map.real_width:.1f} {self.current_map.distance_unit} | "
            f"Zoom: {zoom_pct}% | "
            f"Markers: {len(self.markers)}"
        )
        self.status_bar.setText(status_text)
