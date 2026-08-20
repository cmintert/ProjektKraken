"""Marker Manager for the Map Graphics View.

Manages CRUD operations for markers (points) and features (paths, regions):
factory routing, temporal state updates, and item tracking.
"""

import logging
from typing import TYPE_CHECKING, Dict, Optional

import shiboken6
from PySide6.QtWidgets import QGraphicsItem

from src.core.marker import FEATURE_TYPE_PATH, FEATURE_TYPE_REGION
from src.core.marker_appearance import MARKER_ICON_ATTRIBUTE
from src.gui.constants import MAP_LAYER_Z_MARKERS
from src.gui.widgets.map.feature_items import PathItem, RegionItem
from src.gui.widgets.map.marker_item import MarkerItem

if TYPE_CHECKING:
    from src.gui.widgets.map.map_graphics_view import MapGraphicsView

logger = logging.getLogger(__name__)


class MarkerManager:
    """Manages markers and features on the map.

    Handles creation (factory pattern), updates, removal, temporal
    state filtering, and item lookup.

    Args:
        view: The parent MapGraphicsView.
    """

    def __init__(self, view: "MapGraphicsView") -> None:
        """Initialize marker ownership for one map graphics view."""
        self._view = view
        self.markers: Dict[str, MarkerItem] = {}
        self.feature_items: Dict[str, PathItem | RegionItem] = {}

    def add_marker(
        self,
        marker_id: str,
        object_type: str,
        label: str,
        x: float,
        y: float,
        icon: Optional[str] = None,
        color: Optional[str] = None,
        description: Optional[str] = None,
        lore_date: Optional[float] = None,
        feature_type: str = "point",
        geometry: Optional[list] = None,
        style: Optional[dict] = None,
        visual_attributes: Optional[Dict] = None,
    ) -> None:
        """Adds a marker or feature to the map at normalized coordinates.

        Uses a factory pattern: point features become MarkerItem, path
        features become PathItem, and region features become RegionItem.

        Args:
            marker_id: Unique identifier for the marker.
            object_type: Type of object ('entity' or 'event').
            label: Marker label text.
            x: Normalized X coordinate [0.0, 1.0] (anchor).
            y: Normalized Y coordinate [0.0, 1.0] (anchor).
            icon: Optional icon filename.
            color: Optional color hex string.
            description: Optional description for tooltip.
            lore_date: Optional lore timestamp for temporal filtering.
            feature_type: 'point', 'path', or 'region'.
            geometry: Optional list of coordinate dicts.
            style: Optional visual override dict.
            visual_attributes: Optional dict with ``_v_*`` visual override keys.
        """
        if not self._view.pixmap_item:
            logger.warning("Cannot add marker: no map loaded")
            return

        # Remove existing marker/feature if present
        if marker_id in self.markers:
            self._view.graphics_scene.removeItem(self.markers[marker_id])
            del self.markers[marker_id]
        if marker_id in self.feature_items:
            self._view.graphics_scene.removeItem(self.feature_items[marker_id])
            del self.feature_items[marker_id]

        # Factory: route by feature_type
        if feature_type == FEATURE_TYPE_PATH and geometry:
            path_item = PathItem(
                marker_id=marker_id,
                object_type=object_type,
                label=label,
                pixmap_item=self._view.pixmap_item,
                geometry=geometry,
                anchor_x=x,
                anchor_y=y,
                style=style,
                description=description,
                lore_date=lore_date,
                map_width_meters=self._view.map_width_meters,
            )
            self._view.graphics_scene.addItem(path_item)
            self.feature_items[marker_id] = path_item
            path_item.clicked.connect(self._view.marker_clicked.emit)
            return

        if feature_type == FEATURE_TYPE_REGION and geometry:
            region_item = RegionItem(
                marker_id=marker_id,
                object_type=object_type,
                label=label,
                pixmap_item=self._view.pixmap_item,
                geometry=geometry,
                anchor_x=x,
                anchor_y=y,
                style=style,
                description=description,
                lore_date=lore_date,
                map_width_meters=self._view.map_width_meters,
            )
            self._view.graphics_scene.addItem(region_item)
            self.feature_items[marker_id] = region_item
            region_item.clicked.connect(self._view.marker_clicked.emit)
            return

        # Default: point marker
        attributes = dict(visual_attributes or {})
        if icon is not None:
            attributes[MARKER_ICON_ATTRIBUTE] = icon
        definition = self._view.marker_icon_catalog.resolve_attributes(attributes)
        marker = MarkerItem(
            marker_id,
            object_type,
            label,
            self._view.pixmap_item,
            icon,
            color,
            description,
            lore_date,
            visual_attributes=visual_attributes,
            world_root=self._view._world_root,
            map_width_meters=self._view.map_width_meters,
            icon_definition=definition,
        )

        scene_pos = self._view.coord_system.to_scene(x, y)
        marker.setPos(scene_pos)
        marker.setZValue(MAP_LAYER_Z_MARKERS)

        self._view.graphics_scene.addItem(marker)
        self.markers[marker_id] = marker
        marker.clicked.connect(self._view.marker_clicked.emit)

    def update_marker_position(self, marker_id: str, x: float, y: float) -> None:
        """Update a marker's position to new normalized coordinates.

        Args:
            marker_id: Unique identifier for the marker to update.
            x: New X coordinate (normalized 0-1).
            y: New Y coordinate (normalized 0-1).
        """
        if marker_id not in self.markers:
            logger.warning(f"Cannot update: marker {marker_id} not found")
            return

        marker = self.markers[marker_id]
        scene_pos = self._view.coord_system.to_scene(x, y)
        marker.setPos(scene_pos)

    def update_feature_geometry(
        self,
        marker_id: str,
        geometry: list[dict[str, float]],
        anchor_x: float,
        anchor_y: float,
    ) -> None:
        """Update one path or region in place."""
        item = self.feature_items.get(marker_id)
        if item is None:
            return
        item.set_geometry(geometry, anchor_x, anchor_y)

    def remove_marker(self, marker_id: str) -> None:
        """Remove a marker or feature from the map.

        Args:
            marker_id: Unique identifier for the marker to remove.
        """
        if marker_id in self.markers:
            item = self.markers[marker_id]
            if shiboken6.isValid(item):
                try:
                    self._view.graphics_scene.removeItem(item)
                except RuntimeError:
                    logger.debug(
                        "remove_marker: C++ object already deleted for %s", marker_id
                    )
            del self.markers[marker_id]
            logger.debug(f"Removed marker {marker_id}")
        if marker_id in self.feature_items:
            feature_item = self.feature_items[marker_id]
            if shiboken6.isValid(feature_item):
                try:
                    self._view.graphics_scene.removeItem(feature_item)
                except RuntimeError:
                    logger.debug(
                        "remove_marker: feature C++ object already deleted for %s",
                        marker_id,
                    )
            del self.feature_items[marker_id]
            logger.debug(f"Removed feature {marker_id}")

    def clear_markers(self) -> None:
        """Remove all markers and features from the map."""
        for marker in list(self.markers.values()):
            if shiboken6.isValid(marker):
                try:
                    self._view.graphics_scene.removeItem(marker)
                except RuntimeError:
                    pass
        self.markers.clear()
        for item in list(self.feature_items.values()):
            if shiboken6.isValid(item):
                try:
                    self._view.graphics_scene.removeItem(item)
                except RuntimeError:
                    pass
        self.feature_items.clear()

    def update_markers_temporal_state(
        self, playhead_time: float, current_time: float
    ) -> None:
        """Updates the temporal visual state of all markers and features.

        Args:
            playhead_time: The current playhead position.
            current_time: The current lore time.
        """
        all_items = list(self.markers.values()) + list(self.feature_items.values())
        for item in all_items:
            if item.lore_date is None:
                item.set_temporal_state(is_future=False, is_past=False)
                continue
            is_future = item.lore_date > playhead_time
            is_past = item.lore_date <= playhead_time
            item.set_temporal_state(is_future=is_future, is_past=is_past)

    def find_item(self, item_id: str) -> Optional[QGraphicsItem]:
        """Look up a graphics item by its ID.

        Searches both markers and feature items.

        Args:
            item_id: The ID to search for.

        Returns:
            The matching QGraphicsItem, or None.
        """
        if item_id in self.markers:
            return self.markers[item_id]
        if item_id in self.feature_items:
            return self.feature_items[item_id]
        return None
