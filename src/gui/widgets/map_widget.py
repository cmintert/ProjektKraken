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
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.core.marker import Marker
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
    marker_keyframe_changed = Signal(str, float, float, float)  # marker_id, t, x, y

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

        # Toolbar Layout (Styled Buttons instead of QToolBar for consistency)
        top_bar = QHBoxLayout()
        # Use standard spacing from StyleHelper if available, else manual
        top_bar.setSpacing(8)
        top_bar.setContentsMargins(8, 8, 8, 8)

        # Map Selector
        self.map_selector = QComboBox()
        self.map_selector.setMinimumWidth(200)
        self.map_selector.currentIndexChanged.connect(self._on_map_selected)
        top_bar.addWidget(self.map_selector)

        # New Map Button
        self.btn_new_map = QPushButton("New Map")
        self.btn_new_map.clicked.connect(self.create_map_requested.emit)
        from src.gui.utils.style_helper import StyleHelper

        self.btn_new_map.setStyleSheet(StyleHelper.get_primary_button_style())
        top_bar.addWidget(self.btn_new_map)

        # Delete Map Button
        self.btn_delete_map = QPushButton("Delete Map")
        self.btn_delete_map.clicked.connect(self.delete_map_requested.emit)
        self.btn_delete_map.setStyleSheet(StyleHelper.get_destructive_button_style())
        top_bar.addWidget(self.btn_delete_map)

        # Spacer
        top_bar.addStretch()

        # Record Mode Toggle
        self.btn_record = QPushButton("Record")
        self.btn_record.setCheckable(True)
        self.btn_record.toggled.connect(self.view.set_record_mode)
        # We can style this to look like a red record button when checked
        # For now standard checkable button
        top_bar.addWidget(self.btn_record)

        # Fit View Button
        self.btn_fit_view = QPushButton("Fit View")
        self.btn_fit_view.clicked.connect(self.view.fit_to_view)
        top_bar.addWidget(self.btn_fit_view)

        layout.addLayout(top_bar)

        # Add View
        layout.addWidget(self.view)

        # Connect signals
        self.view.marker_moved.connect(self._on_marker_moved)
        self.view.marker_keyframe_changed.connect(self._on_marker_keyframe_changed)
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

    @Slot(float)
    def set_current_time(self, current_time: float) -> None:
        """
        Updates the current time for temporal display.

        Args:
            current_time: The new time from the timeline.
        """
        self.view.update_temporal_state(current_time)

    @Slot(str, float, float)
    def _on_marker_moved(self, marker_id: str, x: float, y: float) -> None:
        """
        Handles marker movement from the view.

        Updates the widget's marker position or keyframe depending on mode.

        Args:
            marker_id: ID of the moved marker.
            x: New normalized X coordinate.
            y: New normalized Y coordinate.
        """
        if self.view.record_mode:
            # Record Mode: Update/Create keyframe at current time
            t = self.view.current_time
            self.marker_keyframe_changed.emit(marker_id, t, x, y)
            logger.debug(f"Record Mode: Keyframe for {marker_id} at t={t}")
        else:
            # Standard Mode: Update static position
            self.update_marker_position(marker_id, x, y)
            self.marker_position_changed.emit(marker_id, x, y)
            logger.debug(f"Standard Mode: Moved {marker_id} to ({x:.3f}, {y:.3f})")

    @Slot(str, float, float, float)
    def _on_marker_keyframe_changed(
        self, marker_id: str, t: float, x: float, y: float
    ) -> None:
        """Handle keyframe movement from handles."""
        self.marker_keyframe_changed.emit(marker_id, t, x, y)

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
        marker_data: Optional[Marker] = None,
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
            marker_data: Core Marker object.
        """
        self.view.add_marker(
            marker_id, object_type, label, x, y, icon, color, marker_data
        )

    def update_marker_position(self, marker_id: str, x: float, y: float) -> None:
        """
        Updates a marker's position.

        Args:
            marker_id: Unique identifier for the marker.
            x: Normalized X coordinate.
            y: Normalized Y coordinate.
        """
        self.view.update_marker_position(marker_id, x, y)

    def update_marker_visuals(
        self,
        marker_id: str,
        label: str,
        icon: Optional[str] = None,
        color: Optional[str] = None,
    ) -> None:
        """
        Updates a marker's visuals.

        Args:
            marker_id: Unique identifier for the marker.
            label: New label text.
            icon: Optional new icon.
            color: Optional new color.
        """
        self.view.update_marker_visuals(marker_id, label, icon, color)

    def remove_marker(self, marker_id: str) -> None:
        """
        Removes a marker from the map.

        Args:
            marker_id: ID of the marker to remove.
        """
        self.view.remove_marker(marker_id)

    def clear_markers(self) -> None:
        """Removes all markers from the map."""
