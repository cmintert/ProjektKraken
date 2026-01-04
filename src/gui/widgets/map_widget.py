"""
Map Widget Module.

Main entry point for map visualization. Provides MapWidget wrapper
that combines MapGraphicsView with map management controls.

The map components have been refactored into separate modules for better
maintainability:
- map/marker_item.py - MarkerItem rendering
- map/map_graphics_view.py - Main view with zoom/pan and interaction
- map/icon_picker_dialog.py - Icon selection dialog
"""

import logging
import os
from typing import List, Optional

from PySide6.QtCore import Signal, Slot
from PySide6.QtGui import (
    QAction,
)
from PySide6.QtWidgets import (
    QComboBox,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from src.core.paths import get_resource_path
from src.gui.widgets.map.map_graphics_view import MapGraphicsView

logger = logging.getLogger(__name__)

# Path to marker icons
MARKER_ICONS_PATH = get_resource_path(os.path.join("assets", "icons", "markers"))


def get_available_icons() -> List[str]:
    """
    Returns a list of available marker icon filenames.

    Returns:
        List[str]: List of .svg filenames in the markers folder.
    """
    if not os.path.exists(MARKER_ICONS_PATH):
        return []
    return [f for f in os.listdir(MARKER_ICONS_PATH) if f.endswith(".svg")]


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
    marker_clicked = Signal(str, str)
    create_map_requested = Signal()
    delete_map_requested = Signal()
    map_selected = Signal(str)  # map_id
    create_marker_requested = Signal(float, float)  # x, y normalized
    delete_marker_requested = Signal(str)  # marker_id
    change_marker_icon_requested = Signal(str, str)  # marker_id, new_icon
    change_marker_color_requested = Signal(str, str)  # marker_id, new_color_hex
    marker_drop_requested = Signal(str, str, str, float, float)  # id, type, name, x, y

    def __init__(self, parent: Optional[QWidget] = None) -> None:
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
        self.view.marker_clicked.connect(self.marker_clicked.emit)
        self.view.add_marker_requested.connect(self.create_marker_requested.emit)
        self.view.delete_marker_requested.connect(self.delete_marker_requested.emit)
        self.view.change_marker_icon_requested.connect(
            self.change_marker_icon_requested.emit
        )
        self.view.change_marker_color_requested.connect(
            self.change_marker_color_requested.emit
        )
        self.view.marker_drop_requested.connect(self.marker_drop_requested.emit)

        self._maps_data = []  # List of maps for selector

    def set_maps(self, maps: list) -> None:
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

    def select_map(self, map_id: str) -> None:
        """Selects the map with the given ID in the dropdown."""
        index = self.map_selector.findData(map_id)
        if index >= 0:
            logger.debug(f"Selecting map index {index} for id {map_id}")
            self.map_selector.setCurrentIndex(index)
        else:
            logger.warning(f"Map ID {map_id} not found in selector")

    @Slot(int)
    def _on_map_selected(self, index: int) -> None:
        """Handle map selection change."""
        if index >= 0:
            map_id = self.map_selector.itemData(index)
            self.map_selected.emit(map_id)

    def get_selected_map_id(self) -> Optional[str]:
        """
        Returns the currently selected map ID.

        Returns:
            Optional[str]: The map ID, or None if no map is selected.
        """
        index = self.map_selector.currentIndex()
        if index >= 0:
            return self.map_selector.itemData(index)
        return None

    @Slot(str, float, float)
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
        color: Optional[str] = None,
    ) -> None:
        """
        Adds a marker to the map.

        Args:
            marker_id: Unique identifier for the marker.
            object_type: Type of object ('entity' or 'event').
            label: Marker label text.
            x: Normalized X coordinate [0.0, 1.0].
            y: Normalized Y coordinate [0.0, 1.0].
            icon: Optional icon filename.
            color: Optional color hex string.
        """
        self.view.add_marker(marker_id, object_type, label, x, y, icon, color)

    def update_marker_position(self, marker_id: str, x: float, y: float) -> None:
        """
        Updates a marker's position.

        Args:
            marker_id: Unique identifier for the marker.
            x: Normalized X coordinate.
            y: Normalized Y coordinate.
        """
        self.view.update_marker_position(marker_id, x, y)

    def remove_marker(self, marker_id: str) -> None:
        """
        Removes a marker from the map.

        Args:
            marker_id: ID of the marker to remove.
        """
        self.view.remove_marker(marker_id)

    def clear_markers(self) -> None:
        """Removes all markers from the map."""
