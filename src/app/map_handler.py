"""MapHandler - Handles map and marker operations.

This module contains all map and marker-related business logic,
decoupled from the UI layer.  It receives specific dependencies
via constructor injection rather than a reference to MainWindow.

Dialog creation is the responsibility of the widget layer
(``MapWidget``).  This handler only operates on pre-resolved data
received through signals.
"""

import uuid
from collections import OrderedDict
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional, Set, cast

import numpy as np
from PySide6.QtCore import (
    Q_ARG,
    QObject,
    QThreadPool,
    QTimer,
    Signal,
    Slot,
)
from PySide6.QtWidgets import QMessageBox

from src.app.constants import (
    MAP_ROLE_DETAIL,
    MAP_ROLE_MASTER,
    TEMPORAL_SNAPSHOT_CACHE_MAX,
)
from src.app.qt_invocation import invoke_queued
from src.commands.layer_commands import UpdateLayerTreeCommand
from src.commands.map_commands import (
    ApplyMarkerAppearanceCommand,
    CreateMapCommand,
    CreateMarkerCommand,
    DeleteMapCommand,
    DeleteMarkerCommand,
    RegisterDetailMapCommand,
    RenameLayerCommand,
    SetLayerOpacityCommand,
    SetMasterMapCommand,
    UpdateMapCommand,
    UpdateMarkerAttributeCommand,
    UpdateMarkerColorCommand,
    UpdateMarkerCommand,
    UpdateMarkerIconCommand,
)
from src.core.logging_config import get_logger
from src.core.map import MapLayerNode
from src.services.map_nesting_service import MapNestingService, NestingValidationError
from src.services.repositories.map_repository import MapRepository

if TYPE_CHECKING:
    from src.gui.widgets.map.map_graphics_view import MapGraphicsView
    from src.gui.widgets.map_widget import MapWidget

logger = get_logger(__name__)

_REGION_COMPONENT_COUNT = 4
_RGBA_COMPONENT_COUNT = 4


def _safe_float(value: Any) -> Optional[float]:
    """Safely convert a value to float, returning None on error.

    Args:
        value: Value to convert.

    Returns:
        float if conversion succeeds, ``None`` otherwise.
    """
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class MapHandler(QObject):
    """Manages map and marker operations.

    This class encapsulates all business logic related to:
    - Loading and displaying maps
    - Creating, deleting, and modifying maps
    - Creating, deleting, and modifying markers
    - Handling marker interactions (clicks, drag-drop, updates)

    Dependencies are injected via the constructor — this handler
    never accesses ``MainWindow`` directly.
    """

    # Emitted when a command should be executed on the worker thread.
    command_requested = Signal(object)
    raster_save_state_changed = Signal(str, str, str)

    def __init__(
        self,
        map_widget: "MapWidget",
        worker: QObject,
        db_path_accessor: Callable[[], str],
        navigation_set_selection: Callable[[str, str], None],
    ) -> None:
        """Initialize the MapHandler.

        Args:
            map_widget: The MapWidget instance (UI layer).
            worker: The DatabaseWorker for async DB operations.
                Must support ``load_maps``, ``load_markers``, and
                ``load_trajectories`` methods invocable via
                ``QMetaObject.invokeMethod``.
            db_path_accessor: Callable that returns the current DB path.
            navigation_set_selection: Callable(object_type, object_id) for
                unified selection handling.

        """
        super().__init__()
        self._map_widget = map_widget
        self._worker = worker
        self._db_path_accessor = db_path_accessor
        self._navigation_set_selection = navigation_set_selection
        # Mapping from object_id to actual marker.id for position updates
        self._marker_object_to_id: dict[str, str] = {}
        # Track the most recently loaded map ID for raster operations
        self._current_map_id: Optional[str] = None
        # Track the map ID whose markers are currently loaded (for incremental diff)
        self._loaded_markers_map_id: Optional[str] = None
        # Snapshot of last-loaded marker data keyed by object_id (for diff)
        self._loaded_marker_data: dict[str, dict] = {}
        # Whether raster layer panel signals have been connected
        self._raster_signals_connected: bool = False
        # Set when maps_data was just freshly reloaded; consumed by the first
        # on_markers_ready that follows so newly-injected layer nodes
        # (e.g. from CreateRasterLayerCommand) are synced into the model.
        self._pending_layer_node_sync: bool = False

        # ── Temporal rasters ──────────────────────────────────────────
        self._current_lore_date: float = 0.0
        # abs_path → MapDataBuffer (avoids re-reading same snapshot file)
        self._snapshot_cache: OrderedDict[tuple[Any, ...], Any] = OrderedDict()
        self._snapshot_cache_max: int = TEMPORAL_SNAPSHOT_CACHE_MAX
        # node_id → abs_path currently shown in scene
        self._current_snapshot_by_node: Dict[str, str] = {}
        self._current_snapshot_identity_by_node: Dict[str, tuple[Any, ...]] = {}
        self._raster_edit_target_by_node: Dict[str, str] = {}
        self._pending_raster_strokes: dict[str, list[Any]] = {}
        self._failed_raster_nodes: set[str] = set()
        self._temporal_debounce_timer = QTimer()
        self._temporal_debounce_timer.setSingleShot(True)
        self._temporal_debounce_timer.setInterval(300)
        self._temporal_debounce_timer.timeout.connect(self._apply_temporal_rasters)

    def _lookup_cached_world_item_name(self, item_id: str | None) -> str | None:
        """Resolve an entity/event name from the widget's cached data.

        Args:
            item_id: Entity or event ID to resolve.

        Returns:
            The cached display name, or ``None`` if not found.
        """
        if not item_id or self._map_widget is None:
            return None

        for entity in getattr(self._map_widget, "_cached_entities", []):
            if getattr(entity, "id", None) == item_id:
                return getattr(entity, "name", None)

        for event in getattr(self._map_widget, "_cached_events", []):
            if getattr(event, "id", None) == item_id:
                return getattr(event, "name", None)

        return None

    def load_maps(self) -> None:
        """Requests loading of all maps from the worker thread."""
        invoke_queued(self._worker, "load_maps")

    @Slot(str)
    def on_map_selected(self, map_id: str) -> None:
        """Handler for when a map is selected in the widget. Loads the map image and
        requests markers.

        Args:
            map_id: ID of the selected map.

        """
        if not self.has_pending_raster_strokes():
            self._failed_raster_nodes.clear()

        # Find map object
        maps = self._map_widget.maps_data
        selected_map = next((m for m in maps if m.id == map_id), None)
        if selected_map and selected_map.image_path:
            # Resolve relative path against project directory
            image_path = selected_map.image_path
            if not Path(image_path).is_absolute():
                project_dir = Path(self._db_path_accessor()).parent
                image_path = str(project_dir / image_path)

            # Propagate world root so the icon picker can show project icons
            world_root = str(Path(self._db_path_accessor()).parent)
            self._map_widget.view.set_world_root(world_root)

            # Only load the map image if it's different from the current one
            # This preserves the view transform (zoom/pan) during map list refreshes
            if self._map_widget.view.current_image_path != image_path:
                self._map_widget.load_map(image_path)

            # Restore scale
            width_meters = selected_map.attributes.get("width_meters")
            if width_meters:
                self._map_widget.view.set_map_width_meters(float(width_meters))
            else:
                self._map_widget.view.clear_map_scale()

            # Request markers
            invoke_queued(
                self._worker,
                "load_markers",
                Q_ARG(str, map_id),
            )

            # Request trajectories
            invoke_queued(
                self._worker,
                "load_trajectories",
                Q_ARG(str, map_id),
            )
            invoke_queued(
                self._worker,
                "load_feature_geometry_states",
                Q_ARG(str, map_id),
            )

            # Load footprint overlays for detail-map children.
            self._load_footprints_for_map(selected_map, maps)

            # Update breadcrumb navigation.
            self._load_breadcrumb_for_map(selected_map, maps)

    @Slot(str)
    def reload_markers(self, map_id: str) -> None:
        """Reloads markers for the specified map.

        Args:
            map_id: The ID of the map to reload markers for.

        """
        logger.info(f"Reloading markers for map: {map_id}")
        invoke_queued(
            self._worker,
            "load_markers",
            Q_ARG(str, map_id),
        )

    @Slot()
    def reload_markers_for_current_map(self) -> None:
        """Reloads markers for the currently selected map.

        Used when a marker command completes but we don't have the map_id in the command
        result.
        """
        map_id = self._map_widget.get_selected_map_id()
        if map_id:
            logger.info(f"Reloading markers for current map: {map_id}")
            self.reload_markers(map_id)
        else:
            logger.debug("No map selected, skipping marker reload")

    def create_map(self, file_path: str, name: str) -> None:
        """Creates a new map from a pre-selected image and name.

        The dialog interaction (file selection, name input) is handled
        by the widget layer before this method is called.

        Args:
            file_path: Absolute path to the source image file.
            name: Display name for the map.

        """
        source_path = Path(file_path)
        unique_suffix = uuid.uuid4().hex[:8]
        dest_filename = f"{source_path.stem}_{unique_suffix}{source_path.suffix}"
        relative_path = (Path("assets") / "maps" / dest_filename).as_posix()
        cmd = CreateMapCommand(
            {"name": name.strip(), "image_path": relative_path},
            source_image_path=str(source_path.resolve()),
        )
        self.command_requested.emit(cmd)

    def delete_map(self, map_id: str) -> None:
        """Deletes a map after confirmation has already been obtained.

        The confirmation dialog is handled by the widget layer.

        Args:
            map_id: ID of the map to delete.

        """
        self._map_widget.exit_editing_modes()
        cmd = DeleteMapCommand(map_id)
        self.command_requested.emit(cmd)

    def create_marker(
        self,
        map_id: str,
        obj_id: str,
        obj_type: str,
        name: str,
        x: float,
        y: float,
    ) -> None:
        """Creates a new marker at the given normalised coordinates.

        The object selection dialog is handled by the widget layer.

        Args:
            map_id: ID of the target map.
            obj_id: UUID of the linked entity or event.
            obj_type: ``'entity'`` or ``'event'``.
            name: Display label for the marker.
            x: Normalised X coordinate [0.0, 1.0].
            y: Normalised Y coordinate [0.0, 1.0].

        """
        cmd = CreateMarkerCommand(
            {
                "map_id": map_id,
                "object_id": obj_id,
                "object_type": obj_type,
                "x": x,
                "y": y,
                "label": name,
            }
        )
        self.command_requested.emit(cmd)

    def on_marker_dropped(
        self, item_id: str, item_type: str, item_name: str, x: float, y: float
    ) -> None:
        """Handle marker creation from drag-drop.

        Args:
            item_id: ID of the dropped entity/event.
            item_type: 'entity' or 'event'.
            item_name: Display name of the item.
            x: Normalized X coordinate [0.0, 1.0].
            y: Normalized Y coordinate [0.0, 1.0].

        """
        map_id = self._map_widget.get_selected_map_id()
        if not map_id:
            logger.warning("on_marker_dropped: no map selected")
            return

        cmd = CreateMarkerCommand(
            {
                "map_id": map_id,
                "object_id": item_id,
                "object_type": item_type,
                "x": x,
                "y": y,
                "label": item_name,
            }
        )
        self.command_requested.emit(cmd)
        logger.info(f"Creating marker for {item_type} '{item_name}' via drag-drop")

    @Slot(str, list)
    def on_feature_drawn(
        self,
        map_id: str,
        obj_id: str,
        obj_type: str,
        name: str,
        feature_type: str,
        geometry: list,
    ) -> None:
        """Handle feature creation from drawing mode.

        The object selection dialog is handled by the widget layer.

        Args:
            map_id: ID of the target map.
            obj_id: UUID of the linked entity or event.
            obj_type: ``'entity'`` or ``'event'``.
            name: Display label for the feature.
            feature_type: 'path' or 'region'.
            geometry: List of normalized coordinate dicts.

        """
        # Compute centroid for anchor
        n = len(geometry)
        cx = sum(pt["x"] for pt in geometry) / n
        cy = sum(pt["y"] for pt in geometry) / n

        cmd = CreateMarkerCommand(
            {
                "map_id": map_id,
                "object_id": obj_id,
                "object_type": obj_type,
                "x": cx,
                "y": cy,
                "label": name,
                "feature_type": feature_type,
                "geometry": geometry,
            }
        )
        self.command_requested.emit(cmd)
        logger.info(f"Creating {feature_type} '{name}' with {len(geometry)} vertices")

    @Slot(str, dict)
    def on_feature_style_changed(self, marker_id: str, new_style: dict) -> None:
        """Persists a feature style change via UpdateMarkerCommand.

        Args:
            marker_id: The object_id of the feature.
            new_style: Updated style dict.

        """
        actual_marker_id = self._marker_object_to_id.get(marker_id)
        if not actual_marker_id:
            logger.warning(f"No marker mapping for style update: {marker_id}")
            return

        cmd = UpdateMarkerCommand(actual_marker_id, {"style": new_style})
        self.command_requested.emit(cmd)
        logger.info(f"Style updated for {marker_id}")

    @Slot(str, list)
    def on_feature_geometry_changed(self, marker_id: str, geometry: list) -> None:
        """Persists a feature geometry change via UpdateMarkerCommand.

        Recalculates the anchor to the centroid of the new geometry.

        Args:
            marker_id: The object_id of the feature.
            geometry: Updated list of normalized coordinate dicts.

        """
        actual_marker_id = self._marker_object_to_id.get(marker_id)
        if not actual_marker_id:
            logger.warning(f"No marker mapping for geometry update: {marker_id}")
            return

        # Recalculate anchor (centroid)
        n = len(geometry)
        if n > 0:
            cx = sum(pt["x"] for pt in geometry) / n
            cy = sum(pt["y"] for pt in geometry) / n
        else:
            cx, cy = 0.5, 0.5

        cmd = UpdateMarkerCommand(
            actual_marker_id, {"geometry": geometry, "x": cx, "y": cy}
        )
        self.command_requested.emit(cmd)
        logger.info(f"Geometry updated for {marker_id} ({n} vertices)")

    def delete_marker(self, marker_id: str) -> None:
        """Deletes a marker after confirmation has already been obtained.

        The confirmation dialog is handled by the widget layer.

        Args:
            marker_id: The object_id from the UI (not the actual marker.id).

        """
        # Translate object_id to actual marker ID
        actual_marker_id = self._marker_object_to_id.get(marker_id)
        if not actual_marker_id:
            logger.warning(f"No marker mapping found for object_id: {marker_id}")
            return

        # Remove marker from UI immediately for instant feedback
        self._map_widget.remove_marker(marker_id)
        # Also remove from mapping
        del self._marker_object_to_id[marker_id]
        # Then execute the database command
        cmd = DeleteMarkerCommand(actual_marker_id)
        self.command_requested.emit(cmd)

    @Slot(str, str)
    def on_marker_clicked(self, marker_id: str, object_type: str) -> None:
        """Handle marker click from MapWidget.

        Args:
            marker_id: The ID of the item.
            object_type: 'event' or 'entity'.

        """
        logger.info(
            f"on_marker_clicked called: marker_id={marker_id}, "
            f"object_type={object_type}"
        )
        # Delegate to the injected navigation callable for unified selection
        self._navigation_set_selection(object_type, marker_id)

    @Slot(str, str)
    def on_marker_icon_changed(self, marker_id: str, icon: str) -> None:
        """Handle marker icon change from MapWidget.

        Args:
            marker_id: ID of the marker (actually object_id from view).
            icon: New icon filename.

        """
        # Translate object_id to actual marker ID
        actual_marker_id = self._marker_object_to_id.get(marker_id)
        if not actual_marker_id:
            logger.warning(f"No marker mapping found for object_id: {marker_id}")
            return
        cmd = UpdateMarkerIconCommand(marker_id=actual_marker_id, icon=icon)
        self.command_requested.emit(cmd)

    @Slot(str, str)
    def on_marker_color_changed(self, marker_id: str, color: str) -> None:
        """Handle marker color change from MapWidget.

        Args:
            marker_id: ID of the marker (actually object_id from view).
            color: New color hex code.

        """
        # Translate object_id to actual marker ID
        actual_marker_id = self._marker_object_to_id.get(marker_id)
        if not actual_marker_id:
            logger.warning(f"No marker mapping found for object_id: {marker_id}")
            return
        cmd = UpdateMarkerColorCommand(marker_id=actual_marker_id, color=color)
        self.command_requested.emit(cmd)

    @Slot(str, dict)
    def on_marker_visual_style_changed(self, marker_id: str, updates: dict) -> None:
        """Persists visual style changes via UpdateMarkerAttributeCommand.

        Args:
            marker_id: The object_id of the marker from the view.
            updates: Dictionary of ``_v_*`` attribute overrides.

        """
        actual_marker_id = self._marker_object_to_id.get(marker_id)
        if not actual_marker_id:
            logger.warning(f"No marker mapping for visual style update: {marker_id}")
            return

        cmd = UpdateMarkerAttributeCommand(actual_marker_id, updates)
        self.command_requested.emit(cmd)
        logger.info(f"Visual style updated for {marker_id}: {list(updates.keys())}")

    @Slot(str, dict)
    def on_marker_appearance_changed(self, marker_id: str, appearance: dict) -> None:
        """Persist one complete marker appearance as an atomic command."""
        actual_marker_id = self._marker_object_to_id.get(marker_id)
        if not actual_marker_id:
            logger.warning("No marker mapping for appearance update: %s", marker_id)
            return
        command = ApplyMarkerAppearanceCommand(actual_marker_id, appearance)
        self.command_requested.emit(command)
        logger.info("Marker appearance updated for %s", marker_id)

    @Slot(str, float, float)
    def on_marker_position_changed(self, marker_id: str, x: float, y: float) -> None:
        """Handle marker position change from MapWidget.

        Args:
            marker_id: ID of the marker (actually object_id from view).
            x: New normalized X coordinate.
            y: New normalized Y coordinate.

        """
        # Translate object_id to actual marker ID
        actual_marker_id = self._marker_object_to_id.get(marker_id)
        if not actual_marker_id:
            logger.warning(f"No marker mapping found for object_id: {marker_id}")
            return
        cmd = UpdateMarkerCommand(
            marker_id=actual_marker_id, update_data={"x": x, "y": y}
        )
        self.command_requested.emit(cmd)

    @Slot(list)
    def on_maps_ready(self, maps: list) -> None:
        """Handle maps ready signal from DataHandler.

        Args:
            maps: List of Map objects.

        """
        # Preserve the currently selected map ID to avoid triggering a reload
        current_map_id = self._map_widget.get_selected_map_id()

        self._map_widget.set_maps(maps)
        self._pending_layer_node_sync = True

        # Restore the previous selection if it still exists
        if current_map_id and any(m.id == current_map_id for m in maps):
            self._map_widget.select_map(current_map_id)

        # Auto-select first map if none selected
        if maps:
            current_id = self._map_widget.map_selector.currentData()
            if not current_id:
                self._map_widget.select_map(maps[0].id)

    @Slot(str, list)
    def on_markers_ready(self, map_id: str, processed_markers: list) -> None:
        """Handle markers ready signal from DataHandler.

        When reloading the same map, performs an incremental diff to
        avoid a full clear-and-rebuild.  Only adds/removes/updates
        markers that actually changed.  Falls back to full rebuild
        on map switch.

        Args:
            map_id: The map ID these markers belong to.
            processed_markers: List of dicts with marker data.

        """
        # Verify we are still looking at this map
        current_map_id = self._map_widget.map_selector.currentData()
        if current_map_id != map_id:
            return

        if map_id == self._loaded_markers_map_id:
            self._incremental_marker_update(map_id, processed_markers)
            # If a command (e.g. CreateRasterLayerCommand) injected new nodes
            # into maps_data since the last reload, sync them into the model
            # now that maps_data is guaranteed fresh.
            if self._pending_layer_node_sync:
                self._pending_layer_node_sync = False
                model = self._map_widget.get_layer_model()
                selected_map = next(
                    (m for m in self._map_widget.maps_data if m.id == map_id),
                    None,
                )
                if selected_map and selected_map.layers and model:
                    db_tree = selected_map.layers.to_dict()
                    live_tree = model.root.to_dict()
                    if db_tree != live_tree:
                        db_ids = self._collect_node_ids(selected_map.layers)
                        mem_ids = self._collect_node_ids(model.root)
                        missing_in_model = db_ids - mem_ids
                        stale_in_model = mem_ids - db_ids
                        logger.debug(
                            "on_markers_ready: layer tree differs from fresh "
                            "maps_data (missing=%d, stale=%d, db=%d, mem=%d) — "
                            "rebuilding layer model",
                            len(missing_in_model),
                            len(stale_in_model),
                            len(db_ids),
                            len(mem_ids),
                        )
                        self._map_widget.rebuild_layer_model(selected_map.layers)
        else:
            # Full rebuild already resynchronises the model from fresh maps_data.
            self._pending_layer_node_sync = False
            self._full_marker_rebuild(map_id, processed_markers)

        # Load raster layers for this map
        self.load_raster_layers(map_id)

    # -- Layer tree helpers --------------------------------------------

    @staticmethod
    def _collect_node_ids(node: Optional[MapLayerNode]) -> Set[str]:
        """Recursively collect all node IDs from a MapLayerNode tree."""
        ids: Set[str] = set()
        if node is None:
            return ids
        ids.add(node.id)
        for child in node.children:
            ids.update(MapHandler._collect_node_ids(child))
        return ids

    # -- Marker diff helpers -------------------------------------------

    @staticmethod
    def _marker_diff_keys(marker_data: dict) -> dict:
        """Extract the properties relevant for diff comparison."""
        return {
            "x": marker_data["x"],
            "y": marker_data["y"],
            "label": marker_data["label"],
            "icon": marker_data["icon"],
            "color": marker_data["color"],
            "summary": marker_data.get("summary", ""),
            "feature_type": marker_data.get("feature_type", "point"),
            "geometry": marker_data.get("geometry"),
            "connection_count": marker_data.get("connection_count", 0),
        }

    def _incremental_marker_update(
        self, map_id: str, processed_markers: list
    ) -> None:
        """Update markers incrementally — only add/remove/update changed."""
        view = self._map_widget.view
        incoming = {m["object_id"]: m for m in processed_markers}
        incoming_ids = set(incoming.keys())
        existing_ids = set(self._loaded_marker_data.keys())

        to_remove = existing_ids - incoming_ids
        to_add = incoming_ids - existing_ids
        to_check = existing_ids & incoming_ids

        # Remove departed markers — use the widget method so the layer panel
        # node is unregistered too (not just the graphics-scene item).
        for mid in to_remove:
            self._map_widget.remove_marker(mid)
            self._marker_object_to_id.pop(mid, None)

        # Add newcomers
        for mid in to_add:
            self._add_single_marker(view, incoming[mid])

        # Update changed markers (position, label, etc.)
        for mid in to_check:
            old = self._marker_diff_keys(self._loaded_marker_data[mid])
            new = self._marker_diff_keys(incoming[mid])
            if old != new:
                # Re-add (handles icon/label/feature_type changes cleanly)
                self._map_widget.view.remove_marker(mid)
                self._add_single_marker(view, incoming[mid])

        # Update snapshot
        self._loaded_marker_data = {m["object_id"]: m for m in processed_markers}

    def _full_marker_rebuild(
        self, map_id: str, processed_markers: list
    ) -> None:
        """Full clear-and-rebuild — used on map switch."""
        view = self._map_widget.view
        saved_transform = view.transform()
        h_scroll = view.horizontalScrollBar().value()
        v_scroll = view.verticalScrollBar().value()

        # Preserve selection state across clear-and-rebuild
        selected_marker_id: str | None = None
        selected_items = view.graphics_scene.selectedItems()
        if selected_items:
            from src.gui.widgets.map.marker_item import MarkerItem

            first = selected_items[0]
            if isinstance(first, MarkerItem):
                selected_marker_id = first.marker_id

        selected_layer_id: str | None = self._map_widget.layer_panel.selected_node_id

        self._map_widget.clear_markers()
        self._marker_object_to_id.clear()

        # Restore persisted layer tree from the selected map object
        maps = self._map_widget.maps_data
        selected_map = next((m for m in maps if m.id == map_id), None)
        if selected_map and selected_map.layers is not None:
            self._map_widget.rebuild_layer_model(selected_map.layers)
        else:
            self._map_widget.rebuild_layer_model()

        for marker_data in processed_markers:
            self._add_single_marker(view, marker_data)

        # Restore the view transform after rebuilding
        view.setTransform(saved_transform)
        view.horizontalScrollBar().setValue(h_scroll)
        view.verticalScrollBar().setValue(v_scroll)

        # Restore selection state
        if selected_marker_id:
            item = view.find_item_by_id(selected_marker_id)
            if item is not None:
                item.setSelected(True)

        if selected_layer_id:
            self._map_widget.layer_panel.select_node(selected_layer_id)

        self._loaded_markers_map_id = map_id
        self._loaded_marker_data = {m["object_id"]: m for m in processed_markers}

    def _add_single_marker(self, view: "MapGraphicsView", marker_data: dict) -> None:
        """Add one marker and update bookkeeping."""
        self._map_widget.add_marker(
            marker_id=marker_data["object_id"],
            object_type=marker_data["object_type"],
            label=marker_data["label"],
            x=marker_data["x"],
            y=marker_data["y"],
            icon=marker_data["icon"],
            color=marker_data["color"],
            description=marker_data.get("summary", ""),
            lore_date=marker_data.get("lore_date"),
            feature_type=marker_data.get("feature_type", "point"),
            geometry=marker_data.get("geometry"),
            style=marker_data.get("style"),
            visual_attributes=marker_data.get("attributes"),
        )

        obj_id = marker_data["object_id"]
        if obj_id in view.markers:
            view.markers[obj_id].connection_count = marker_data.get(
                "connection_count", 0
            )
        elif obj_id in view.feature_items:
            view.feature_items[obj_id].connection_count = marker_data.get(
                "connection_count", 0
            )
        self._marker_object_to_id[marker_data["object_id"]] = marker_data["id"]

    @Slot(str, list)
    def on_trajectories_ready(self, map_id: str, trajectories: list) -> None:
        """Handle trajectories ready signal from DataHandler.

        Args:
            map_id: ID of the map that produced the snapshots.
            trajectories: JSON-safe trajectory snapshot dictionaries.

        """
        if map_id != self._map_widget.get_selected_map_id():
            return
        self._map_widget.set_trajectories(trajectories)

    @Slot(float)
    def on_map_scale_changed(self, width_meters: float) -> None:
        """Compatibility wrapper for callers that update only map width.

        Args:
            width_meters: The new width of the map in meters.

        """
        self.on_map_settings_changed({"width_meters": width_meters})

    @Slot(dict)
    def on_map_settings_changed(self, updates: dict) -> None:
        """Persist map attribute updates as one undoable command."""
        current_map_id = self._map_widget.map_selector.currentData()
        if not current_map_id:
            return
        cmd = UpdateMapCommand(current_map_id, {"attributes": dict(updates)})
        self.command_requested.emit(cmd)

    # ------------------------------------------------------------------
    # Map nesting (master / detail) operations
    # ------------------------------------------------------------------

    @Slot(str)
    def on_set_master_map_requested(self, map_id: str) -> None:
        """Dispatch a :class:`SetMasterMapCommand` for ``map_id``.

        Args:
            map_id: ID of the map to mark as the world's master.

        """
        if not map_id:
            return
        self.command_requested.emit(SetMasterMapCommand(map_id))

    @Slot(str, str, dict)
    def on_register_detail_map_requested(
        self, detail_map_id: str, parent_map_id: str, registration: dict
    ) -> None:
        """Dispatch a :class:`RegisterDetailMapCommand`.

        Args:
            detail_map_id: ID of the map being registered as a detail.
            parent_map_id: ID of the chosen parent (master or detail) map.
            registration: Aspect-locked-affine registration payload.

        """
        if not detail_map_id or not parent_map_id or not registration:
            return
        self.command_requested.emit(
            RegisterDetailMapCommand(detail_map_id, parent_map_id, registration)
        )

    @Slot(str)
    def on_detail_map_clicked(self, detail_map_id: str) -> None:
        """Navigate to a detail map when its footprint is clicked.

        Args:
            detail_map_id: ID of the detail map to switch to.

        """
        if not detail_map_id:
            return
        self._map_widget.select_map(detail_map_id)

    @Slot(str, str, dict)
    def on_footprint_edit_confirmed(
        self, detail_map_id: str, parent_map_id: str, registration: dict
    ) -> None:
        """Dispatch a :class:`RegisterDetailMapCommand` after canvas edit.

        Called when the user presses Enter to confirm an interactive
        footprint placement.

        Args:
            detail_map_id: ID of the detail map whose footprint was edited.
            parent_map_id: ID of the parent map.
            registration: Updated aspect-locked-affine registration.

        """
        self.on_register_detail_map_requested(detail_map_id, parent_map_id, registration)

    def _load_footprints_for_map(self, current_map: Any, all_maps: list) -> None:
        """Load footprint overlays for the children of ``current_map``.

        Only maps that have the ``master`` or ``detail`` role can have
        children, so for ordinary maps this is a fast no-op.

        Args:
            current_map: The ``Map`` object currently loaded in the view.
            all_maps: All maps in the current world.

        """
        role = (current_map.attributes or {}).get("map_role")
        if role not in (MAP_ROLE_MASTER, MAP_ROLE_DETAIL):
            self._map_widget.view.clear_footprints()
            return

        children = MapRepository.get_children_of(current_map.id, all_maps)
        if not children:
            self._map_widget.view.clear_footprints()
            return

        footprint_data = []
        for child in children:
            attrs = child.attributes or {}
            registration = attrs.get("registration")
            if registration is None:
                continue
            abs_path = self._map_widget._resolve_world_image_path(
                child.image_path or ""
            )
            footprint_data.append(
                {
                    "id": child.id,
                    "name": child.name,
                    "parent_map_id": current_map.id,
                    "registration": registration,
                    "image_path": abs_path,
                }
            )

        self._map_widget.view.set_footprints(footprint_data)
        self._map_widget._try_activate_pending_footprint_edit()

    def _load_breadcrumb_for_map(self, current_map: Any, all_maps: list) -> None:
        """Build and display the breadcrumb chain for ``current_map``.

        The chain runs from the root ancestor down to ``current_map``.
        Plain maps (no ``map_role``) and the master map alone both
        produce a short chain that hides the breadcrumb.

        Args:
            current_map: The ``Map`` object currently loaded in the view.
            all_maps: All maps in the current world.

        """
        try:
            ancestors = list(
                MapNestingService.iter_ancestors(current_map.id, all_maps)
            )
        except NestingValidationError:
            ancestors = []

        # ancestors is ordered nearest → farthest; reverse to get root first.
        chain = [
            (m.id, str(getattr(m, "name", m.id))) for m in reversed(ancestors)
        ]
        chain.append(
            (
                current_map.id,
                str(getattr(current_map, "name", current_map.id)),
            )
        )
        self._map_widget.set_breadcrumb(chain)

    # ------------------------------------------------------------------
    # Layer operations (routed through the command stack)
    # ------------------------------------------------------------------

    @Slot()
    def on_layer_tree_changed(self) -> None:
        """Persist the current layer tree to the database.

        Queues an ``UpdateLayerTreeCommand`` whenever the in-memory layer tree
        is mutated so the change is durable on the worker thread.
        """
        map_id = self._map_widget.get_selected_map_id()
        model = self._map_widget.get_layer_model()
        if not map_id or not model:
            return
        tree_dict = model.root.to_dict()
        cmd = UpdateLayerTreeCommand(map_id, tree_dict)
        self.command_requested.emit(cmd)

    @Slot(str, float, float)
    def on_layer_opacity_changed(
        self, node_id: str, opacity: float, old_opacity: float
    ) -> None:
        """Handle layer opacity change via the command stack.

        Args:
            node_id: ID of the layer node.
            opacity: New opacity (0.0–1.0).
            old_opacity: Previous opacity (for undo).

        """
        map_id = self._map_widget.get_selected_map_id()
        if not map_id:
            return

        # Snapshot the tree to avoid stale DB reads (race condition fix)
        model = self._map_widget.get_layer_model()
        tree_dict = model.root.to_dict() if model else None

        cmd = SetLayerOpacityCommand(
            map_id, node_id, opacity, old_opacity, layer_tree_dict=tree_dict
        )
        self.command_requested.emit(cmd)

    @Slot(str, str)
    def on_layer_renamed(self, node_id: str, new_name: str) -> None:
        """Handle layer rename via the command stack.

        Passes the current in-memory tree snapshot to avoid stale-DB
        reads when the rename command executes on the worker thread.

        Args:
            node_id: ID of the layer node (same as object_id).
            new_name: New display name.

        """
        map_id = self._map_widget.get_selected_map_id()
        if not map_id:
            return
        # Serialize the current in-memory tree (already renamed by the UI)
        model = self._map_widget.get_layer_model()
        tree_dict = model.root.to_dict() if model else None
        # Resolve actual marker DB id from the object_id mapping
        actual_marker_id = self._marker_object_to_id.get(node_id)
        cmd = RenameLayerCommand(map_id, node_id, new_name, tree_dict, actual_marker_id)
        self.command_requested.emit(cmd)

    @Slot(str, str)
    def on_layer_feature_deleted(self, object_id: str, layer_type: str) -> None:
        """Delete a canonical layer subtree through one reversible command.

        Args:
            object_id: For markers, the entity/event UUID used as the UI
                marker key.  For raster layers, the layer node UUID.
            layer_type: One of the ``MAP_LAYER_TYPE_*`` constants.

        """
        del layer_type
        map_id = self._map_widget.get_selected_map_id()
        if not map_id:
            logger.warning("on_layer_feature_deleted: no map selected")
            return
        from src.commands.layer_commands import DeleteLayerSubtreeCommand

        cmd = DeleteLayerSubtreeCommand(map_id, object_id)
        self.command_requested.emit(cmd)

    @Slot(str, dict)
    def on_layer_properties_changed(
        self, node_id: str, properties: dict
    ) -> None:
        """Persist a contextual layer-inspector edit."""
        map_id = self._map_widget.get_selected_map_id()
        if not map_id:
            return
        from src.commands.layer_commands import (
            UpdateLayerPropertiesCommand,
        )

        self.command_requested.emit(
            UpdateLayerPropertiesCommand(map_id, node_id, properties)
        )

    # ------------------------------------------------------------------
    # Raster layer operations
    # ------------------------------------------------------------------

    def create_raster_layer(
        self,
        name: str,
        width: int,
        height: int,
        mode: str = "discrete",
        default_value: int = 0,
        import_path: str = "",
        display_min: Optional[float] = None,
        display_max: Optional[float] = None,
        unit: str = "",
    ) -> None:
        """Create a new raster (heatmap) layer on the current map.

        Args:
            name: Display name for the raster layer.
            width: Buffer width in pixels.
            height: Buffer height in pixels.
            mode: ``"discrete"`` or ``"continuous"``.
            default_value: Initial fill value (0–65535).
            import_path: Optional filesystem path to an image file to import as
                the layer's initial pixel data.  When non-empty, the image is
                converted to uint16 and scaled to ``width × height``.
            display_min: Real-world value mapped to pixel value 0, or ``None``
                to infer from metadata (continuous mode only).
            display_max: Real-world value mapped to pixel value 65535, or
                ``None`` to infer from metadata (continuous mode only).
            unit: Optional unit label (e.g. ``"m"``, ``"°C"``).

        """
        map_id = self._map_widget.get_selected_map_id()
        if not map_id:
            logger.warning("create_raster_layer: no map selected")
            return

        world_root = str(Path(self._db_path_accessor()).parent)

        from src.commands.raster_commands import CreateRasterLayerCommand

        cmd = CreateRasterLayerCommand(
            map_id=map_id,
            name=name,
            width=width,
            height=height,
            mode=mode,
            default_value=default_value,
            world_root=world_root,
            import_path=import_path,
            display_min=display_min,
            display_max=display_max,
            unit=unit,
        )
        self.command_requested.emit(cmd)
        logger.info(
            "Requested raster layer creation: '%s' %dx%d (%s) import=%r "
            "display=[%s..%s] unit=%r",
            name,
            width,
            height,
            mode,
            import_path or None,
            display_min,
            display_max,
            unit,
        )

    def delete_raster_layer(self, node_id: str) -> None:
        """Delete a raster layer by its layer node ID.

        Args:
            node_id: The layer node UUID for the raster to delete.

        """
        map_id = self._map_widget.get_selected_map_id()
        if not map_id:
            return

        from src.commands.layer_commands import DeleteLayerSubtreeCommand

        cmd = DeleteLayerSubtreeCommand(map_id=map_id, node_id=node_id)
        self.command_requested.emit(cmd)
        logger.info("Requested raster layer deletion: %s", node_id)

    def load_raster_layers(self, map_id: str) -> None:  # noqa: C901
        """Load and display raster layers for the given map.

        Reads ``maps.attributes["raster_layers"]`` metadata and creates
        :class:`RasterLayerItem` instances in the scene.

        Args:
            map_id: The map to load rasters for.

        """
        logger.debug("load_raster_layers: map_id=%s", map_id)
        # Clear temporal state when map changes; always clear node tracking
        if map_id != self._current_map_id:
            self._snapshot_cache.clear()
            self._current_snapshot_identity_by_node.clear()
            # Clear query overlay when switching maps
            try:
                self._map_widget.view.clear_query_overlay()
                self._map_widget.layer_panel.set_query_active(False)
            except Exception:
                pass
        self._current_snapshot_by_node.clear()
        self._current_map_id = map_id
        maps = self._map_widget.maps_data
        selected_map = next((m for m in maps if m.id == map_id), None)
        if not selected_map:
            logger.warning(
                "load_raster_layers: map_id=%s not found in maps_data", map_id
            )
            return

        raster_metas = (selected_map.attributes or {}).get("raster_layers", [])

        world_root = str(Path(self._db_path_accessor()).parent)
        logger.debug(
            "load_raster_layers: world_root=%s raster_count=%d",
            world_root,
            len(raster_metas),
        )
        view = self._map_widget.view

        # Always clear old raster items first to avoid stale duplicates on reload
        old_count = len(view._raster_items)
        for old_item in list(view._raster_items.values()):
            view.graphics_scene.removeItem(old_item)
        view._raster_items.clear()
        if old_count:
            logger.debug(
                "load_raster_layers: cleared %d existing raster items", old_count
            )

        if not raster_metas:
            logger.debug(
                "load_raster_layers: no raster_layers metadata — nothing to load"
            )
            return

        if not view.pixmap_item:
            logger.warning(
                "load_raster_layers: pixmap_item is None — map image not loaded yet, "
                "raster layers will not be shown (map_id=%s)",
                map_id,
            )
            return

        scene_rect = view.pixmap_item.boundingRect()
        logger.debug("load_raster_layers: scene_rect=%s", scene_rect)

        from src.gui.widgets.map.map_data_buffer import ColorMap, MapDataBuffer
        from src.gui.widgets.map.raster_layer_item import RasterLayerItem

        for meta in raster_metas:
            node_id = meta.get("node_id", "")
            file_path = meta.get("file_path", "")
            abs_path = str(Path(world_root) / file_path)
            logger.debug(
                "load_raster_layers: loading node_id=%s file=%s abs=%s",
                node_id,
                file_path,
                abs_path,
            )

            try:
                buf = MapDataBuffer.from_file(
                    abs_path,
                    mode=str(meta.get("mode", "continuous")),
                )
                logger.debug(
                    "load_raster_layers: loaded buffer %dx%d for node_id=%s",
                    buf.width,
                    buf.height,
                    node_id,
                )
            except Exception as e:
                logger.error("Failed to load raster %s: %s", file_path, e)
                continue

            color_map_data = meta.get("color_map", {})
            color_map = ColorMap.from_dict(color_map_data)
            logger.debug(
                "load_raster_layers: color_map type=%s entries=%d",
                color_map.type,
                len(color_map.entries) if color_map.type == "palette" else -1,
            )

            item = RasterLayerItem(
                buffer=buf,
                color_map=color_map,
                scene_rect=scene_rect,
                node_id=node_id,
                mode=str(meta.get("mode", "continuous")),
            )

            # Apply persisted blend mode if non-default
            blend_mode = meta.get("blend_mode", "Normal")
            if blend_mode != "Normal":
                # Composition modes beyond SourceOver are only honoured by the
                # software rasteriser — switch the viewport before rendering.
                view.ensure_software_rendering()
                item.set_blend_mode(blend_mode)

            # Store raster items on the view for later access
            if not hasattr(view, "_raster_items"):
                view._raster_items = {}
            view._raster_items[node_id] = item
            view.graphics_scene.addItem(item)

            # Record base file as the currently displayed snapshot
            self._current_snapshot_by_node[node_id] = abs_path

            logger.info(
                "Loaded raster layer: %s (%s) — scene item added", node_id, file_path
            )

        # Build mode + metadata dicts in a single pass
        mode_by_id: Dict[str, str] = {}
        meta_by_id: Dict[str, dict] = {}
        for m in raster_metas:
            nid = m.get("node_id", "")
            if nid:
                mode_by_id[nid] = m.get("mode", "discrete")
                meta_by_id[nid] = m
        self._map_widget.layer_panel.set_raster_mode_metadata(mode_by_id)

        # Build name map from cached entities/events (no main-thread DB access)
        cached_names: Dict[str, str] = {}
        for entity in getattr(self._map_widget, "_cached_entities", []):
            cached_names[getattr(entity, "id", "")] = getattr(entity, "name", "")
        for event in getattr(self._map_widget, "_cached_events", []):
            cached_names[getattr(event, "id", "")] = getattr(event, "name", "")

        from src.gui.widgets.map.raster_mapping import normalize_value_entity_map

        name_map_by_id: Dict[str, Dict[str, str]] = {}
        for meta in raster_metas:
            node_id_meta = meta.get("node_id", "")
            if not node_id_meta:
                continue
            vem = normalize_value_entity_map(meta.get("value_entity_map", {}))
            entity_ids = {
                m.get("entity_id")
                for m in vem.get("mappings", [])
                if m.get("entity_id")
            }
            layer_name_map = {
                eid: cached_names[eid] for eid in entity_ids if eid in cached_names
            }
            if layer_name_map:
                name_map_by_id[node_id_meta] = layer_name_map

        self._map_widget.layer_panel.set_raster_layer_metadata(
            meta_by_id, name_map_by_id
        )

        # Connect layer panel signals (once only)
        if not self._raster_signals_connected:
            layer_panel = self._map_widget.layer_panel
            layer_panel.raster_stats_requested.connect(
                self.on_raster_stats_requested
            )
            layer_panel.raster_blend_mode_changed.connect(
                self._on_raster_blend_mode_changed
            )
            layer_panel.raster_snapshot_delete_requested.connect(
                self.on_raster_snapshot_delete_requested
            )
            self._raster_signals_connected = True

        # Apply dynamic z-values from the layer model now that raster items
        # are registered in view._raster_items.  Raster items default to
        # the static MAP_LAYER_Z_RASTER at construction; without this call
        # they'd stay pinned there until the user next moved a layer.
        if getattr(view, "_layer_model", None) is not None:
            view._on_layer_order_changed()

    # ------------------------------------------------------------------
    # Raster editing handlers
    # ------------------------------------------------------------------

    @Slot(str, object)
    def on_raster_stroke_completed(
        self,
        node_id: str,
        patches_or_region: object,
        before_bytes: bytes | None = None,
        after_bytes: bytes | None = None,
    ) -> None:
        """Handle a completed raster brush stroke.

        Creates a :class:`StrokeRasterCommand` and emits it for
        the command coordinator.

        Args:
            node_id: Raster layer node ID.
            dirty_region: ``(min_col, min_row, max_col, max_row)``.
            before_bytes: Raw buffer bytes before the stroke.
            after_bytes: Raw buffer bytes after the stroke.
        """
        from src.commands.raster_commands import StrokeRasterCommand
        from src.core.map_state import RasterPatch

        if self._map_widget is None:
            logger.warning("on_raster_stroke_completed: _map_widget is None")
            return
        map_id = self._map_widget.get_selected_map_id()
        if not map_id:
            logger.warning(
                "on_raster_stroke_completed: no current_map_id on map_widget "
                "(node_id=%s patches=%s)",
                node_id,
                patches_or_region,
            )
            return

        target_file = self._editable_raster_target(map_id, node_id)
        if isinstance(patches_or_region, tuple):
            region = tuple(int(value) for value in patches_or_region)
            item = self._map_widget.view._raster_items.get(node_id)
            rgba = bool(
                item is not None
                and item.buffer.pixel_format.value == "rgba8"
            )
            height = region[3] - region[1] + 1
            width = region[2] - region[0] + 1
            payloads = [
                {
                    "region": region,
                    "shape": (height, width, 4) if rgba else (height, width),
                    "dtype": "uint8" if rgba else "uint16",
                    "before_bytes": before_bytes or b"",
                    "after_bytes": after_bytes or b"",
                }
            ]
        elif isinstance(patches_or_region, list):
            payloads = patches_or_region
        else:
            logger.warning("Invalid raster patch payload: %r", patches_or_region)
            return
        raster_patches: list[RasterPatch] = []
        for payload in payloads:
            if not isinstance(payload, dict):
                continue
            region_values = tuple(int(value) for value in payload["region"])
            if len(region_values) != _REGION_COMPONENT_COUNT:
                continue
            region = (
                region_values[0],
                region_values[1],
                region_values[2],
                region_values[3],
            )
            raster_patches.append(
                RasterPatch(
                    map_id=map_id,
                    node_id=node_id,
                    target_file=target_file,
                    region=region,
                    shape=tuple(int(value) for value in payload["shape"]),
                    dtype=str(payload["dtype"]),
                    before_data=bytes(
                        cast(
                            "bytes | bytearray | memoryview | tuple[int, ...]",
                            payload["before_bytes"],
                        )
                    ),
                    after_data=bytes(
                        cast(
                            "bytes | bytearray | memoryview | tuple[int, ...]",
                            payload["after_bytes"],
                        )
                    ),
                )
            )
        patches = raster_patches
        if not patches:
            return
        logger.debug(
            "on_raster_stroke_completed: node_id=%s map_id=%s patches=%d",
            node_id,
            map_id,
            len(patches),
        )

        cmd = StrokeRasterCommand(
            map_id=map_id,
            node_id=node_id,
            target_file=target_file,
            patches=patches,
        )

        if not cmd.target_file:
            for patch in reversed(cmd.patches):
                self._apply_raster_patch_to_view(
                    node_id, patch.region, patch.before_data, patch.dtype
                )
            QMessageBox.information(
                self._map_widget,
                "Historical raster is read-only",
                "Create or select an editable state before painting this "
                "raster at the current lore date.",
            )
            return

        if node_id in self._failed_raster_nodes:
            for patch in reversed(cmd.patches):
                self._apply_raster_patch_to_view(
                    node_id, patch.region, patch.before_data, patch.dtype
                )
            QMessageBox.warning(
                self._map_widget,
                "Raster editing paused",
                "This raster has an unresolved persistence failure. Reload "
                "the map or select an editable state before continuing.",
            )
            return

        pending = self._pending_raster_strokes.setdefault(node_id, [])
        pending.append(cmd)
        self.raster_save_state_changed.emit(node_id, "saving", "")
        if len(pending) == 1:
            logger.debug(
                "on_raster_stroke_completed: emitting head of raster queue"
            )
            self.command_requested.emit(cmd)

    def _editable_raster_target(self, map_id: str, node_id: str) -> str:
        """Return an explicit edit target, or a safe unsnapshotted base."""
        explicit = self._raster_edit_target_by_node.get(node_id)
        if explicit:
            return explicit
        selected_map = next(
            (item for item in self._map_widget.maps_data if item.id == map_id),
            None,
        )
        if selected_map is None:
            return ""
        for metadata in (selected_map.attributes or {}).get(
            "raster_layers", []
        ):
            if metadata.get("node_id") != node_id:
                continue
            if metadata.get("snapshots"):
                return ""
            return str(metadata.get("file_path", ""))
        return ""

    def _apply_raster_patch_to_view(
        self,
        node_id: str,
        region: tuple,
        raw: bytes,
        dtype: str = "uint16",
    ) -> None:
        """Apply immutable raster bytes to the GUI buffer on the main thread."""
        item = self._map_widget.view._raster_items.get(node_id)
        if item is None:
            return
        min_col, min_row, max_col, max_row = region
        width = max_col - min_col + 1
        height = max_row - min_row + 1
        if dtype == "uint8":
            array = np.frombuffer(raw, dtype=np.uint8).reshape((height, width, 4))
        else:
            array = np.frombuffer(raw, dtype=np.uint16).reshape((height, width))
        item.buffer.set_region(min_col, min_row, array)
        item.update_region((min_col, min_row, max_col, max_row))

    @Slot(object)
    def on_command_effects(self, result: object) -> None:
        """Apply worker-produced serializable effects on the Qt main thread."""
        data = getattr(result, "data", {}) or {}
        command_id = str(data.get("command_id", ""))
        command = self._pending_stroke_by_id(command_id)
        if command is not None:
            self._finalize_raster_stroke(
                command, bool(getattr(result, "success", False))
            )
        if not bool(getattr(result, "success", False)):
            command_name = str(getattr(result, "command_name", ""))
            if command is None and any(
                token in command_name
                for token in ("Map", "Marker", "Layer", "Raster")
            ):
                self.load_maps()
                if self._current_map_id:
                    self.reload_markers(self._current_map_id)
            return
        for effect in data.get("effects", []):
            kind = effect.get("kind")
            node_id = str(effect.get("node_id", ""))
            if kind == "raster_patch":
                from src.core.map_state import RasterPatch

                raw = RasterPatch._decode(str(effect["data"]))
                self._apply_raster_patch_to_view(
                    node_id,
                    tuple(int(value) for value in effect["region"]),
                    raw,
                    str(effect.get("dtype", "uint16")),
                )
            elif kind == "raster_edit_target":
                relative_path = str(effect["file_path"])
                self._raster_edit_target_by_node[node_id] = relative_path
                lore_date = effect.get("lore_date")
                label = (
                    f"Dated state ({float(lore_date):.2f})"
                    if lore_date is not None
                    else "Dated state"
                )
                self._map_widget.layer_panel.set_raster_edit_target(
                    node_id,
                    label,
                )
                self._failed_raster_nodes.discard(node_id)
                absolute_path = str(
                    Path(self._db_path_accessor()).parent / relative_path
                )
                self._invalidate_snapshot_cache(node_id, absolute_path)
                self._current_snapshot_by_node[node_id] = absolute_path
                self._current_snapshot_identity_by_node.pop(node_id, None)
            elif kind == "raster_edit_target_cleared":
                self._raster_edit_target_by_node.pop(node_id, None)
                self._map_widget.layer_panel.clear_raster_edit_targets(node_id)
                self._invalidate_snapshot_cache(node_id)
                self._current_snapshot_by_node.pop(node_id, None)
                self._current_snapshot_identity_by_node.pop(node_id, None)

    def _finalize_raster_stroke(self, command: Any, success: bool) -> None:
        """Finalize a per-raster stroke queue and unwind dependent failures."""
        node_id = str(command.node_id)
        pending = self._pending_raster_strokes.get(node_id, [])
        if command not in pending:
            return
        if success:
            pending.remove(command)
            if not pending:
                self._pending_raster_strokes.pop(node_id, None)
                self.raster_save_state_changed.emit(node_id, "saved", "")
            else:
                self.command_requested.emit(pending[0])
            return

        for queued in reversed(pending):
            for patch in reversed(queued.patches):
                self._apply_raster_patch_to_view(
                    node_id,
                    patch.region,
                    patch.before_data,
                    patch.dtype,
                )
        self._pending_raster_strokes.pop(node_id, None)
        self._failed_raster_nodes.add(node_id)
        self.raster_save_state_changed.emit(
            node_id,
            "failed",
            "Save failed — editing paused",
        )
        QMessageBox.critical(
            self._map_widget,
            "Raster save failed",
            "The failed stroke and all dependent queued strokes were reverted. "
            "Raster editing is paused until the map or editable state is reloaded.",
        )

    def _pending_stroke_by_id(self, command_id: str) -> Optional[Any]:
        """Resolve a main-thread stroke without crossing the command object back."""
        if not command_id:
            return None
        return next(
            (
                command
                for pending in self._pending_raster_strokes.values()
                for command in pending
                if command.command_id == command_id
            ),
            None,
        )

    def has_pending_raster_strokes(self) -> bool:
        """Return whether raster writes are still queued on the worker."""
        return any(self._pending_raster_strokes.values())

    @staticmethod
    def _snapshot_cache_key(
        node_id: str, absolute_path: str
    ) -> tuple[Any, ...]:
        """Build an immutable cache identity from owner, path, and file state."""
        try:
            stat = Path(absolute_path).stat()
        except OSError:
            # Let the renderer produce the actionable load error. A missing-file
            # identity is replaced as soon as the file appears and can be statted.
            return (node_id, absolute_path, None, None)
        return (node_id, absolute_path, stat.st_mtime_ns, stat.st_size)

    def _invalidate_snapshot_cache(
        self, node_id: str, absolute_path: str = ""
    ) -> None:
        """Invalidate cached copies owned by a node and optional path."""
        stale = [
            key
            for key in self._snapshot_cache
            if key[0] == node_id and (not absolute_path or key[1] == absolute_path)
        ]
        for key in stale:
            self._snapshot_cache.pop(key, None)

    @Slot(str)
    def on_raster_palette_edit(self, node_id: str) -> None:
        """Open the palette editor for a raster layer.

        Args:
            node_id: Raster layer node ID.
        """
        logger.debug("on_raster_palette_edit: node_id=%s", node_id)
        if self._map_widget is None:
            logger.warning("on_raster_palette_edit: _map_widget is None")
            return
        view = self._map_widget.view
        item = view._raster_items.get(node_id)
        if item is None:
            logger.warning(
                "on_raster_palette_edit: no item for node_id=%s (registered=%s)",
                node_id,
                list(view._raster_items.keys()),
            )
            return

        from src.gui.widgets.map.raster_palette_editor import RasterPaletteEditor

        # Determine mode and retrieve existing value_entity_map and color_map from metadata
        mode = "discrete"
        existing_vem: dict = {}
        existing_color_map_dict: Optional[dict] = None
        maps = self._map_widget.maps_data
        map_id = self._map_widget.get_selected_map_id()
        selected_map = (
            next((m for m in maps if m.id == map_id), None) if map_id else None
        )
        if selected_map:
            for rl in (selected_map.attributes or {}).get("raster_layers", []):
                if rl.get("node_id") == node_id:
                    mode = rl.get("mode", "discrete")
                    existing_vem = dict(rl.get("value_entity_map") or {})
                    existing_color_map_dict = rl.get("color_map")
                    break
        logger.debug(
            "on_raster_palette_edit: mode=%s color_map_type=%s",
            mode,
            item.color_map.type,
        )

        # For discrete layers that still carry a gradient color_map (created by
        # older code before the palette initialisation fix), synthesise a proper
        # palette ColorMap from the VEM so the editor table is populated correctly.
        # Without this, the palette block in _populate_discrete_rows is skipped,
        # the table appears empty, and saving produces an empty palette → black layer.
        if mode == "discrete" and item.color_map.type != "palette":
            from src.gui.widgets.map.map_data_buffer import ColorEntry
            from src.gui.widgets.map.map_data_buffer import ColorMap as _CM
            from src.gui.widgets.map.raster_mapping import normalize_value_entity_map

            vem_norm = normalize_value_entity_map(existing_vem)
            synthetic_entries = [
                ColorEntry(
                    value=int(m["value"]),
                    color="#808080",
                    entity_id=m.get("entity_id"),
                    label=m.get("label"),
                )
                for m in vem_norm.get("mappings", [])
                if m.get("value") is not None
            ]
            effective_color_map = _CM(type="palette", entries=synthetic_entries)
        else:
            effective_color_map = item.color_map

        dialog = RasterPaletteEditor(
            color_map=effective_color_map,
            mode=mode,
            value_entity_map=existing_vem,
            buffer_min=None,
            buffer_max=None,
            entities=list(getattr(self._map_widget, "_cached_entities", [])),
            events=list(getattr(self._map_widget, "_cached_events", [])),
            parent=self._map_widget,
        )
        if mode == "continuous":
            try:
                stats = item.buffer.compute_coverage_stats(item.color_map)
                dialog = RasterPaletteEditor(
                    color_map=effective_color_map,
                    mode=mode,
                    value_entity_map=existing_vem,
                    buffer_min=stats.min_val,
                    buffer_max=stats.max_val,
                    entities=list(getattr(self._map_widget, "_cached_entities", [])),
                    events=list(getattr(self._map_widget, "_cached_events", [])),
                    parent=self._map_widget,
                )
            except Exception as _exc:
                logger.debug("Could not compute buffer stats: %s", _exc)
        if dialog.exec():
            new_cmap = dialog.result_color_map()
            if mode == "color" and new_cmap.type != "passthrough":
                logger.warning(
                    "on_raster_palette_edit: coercing color layer %s back to passthrough "
                    "from incompatible color_map type=%s",
                    node_id,
                    new_cmap.type,
                )
                from src.gui.widgets.map.map_data_buffer import ColorMap as _CM

                new_cmap = _CM(
                    type="passthrough",
                    linked_entity_id=new_cmap.linked_entity_id,
                    linked_entity_type=new_cmap.linked_entity_type,
                )
            logger.debug(
                "on_raster_palette_edit: applying new color_map type=%s", new_cmap.type
            )
            item.update_display(new_cmap)
            logger.debug("on_raster_palette_edit: display updated")

            # Persist the colour map and semantic value→item mapping together
            if map_id:
                from src.commands.raster_commands import SetRasterMappingCommand
                from src.gui.widgets.map.raster_mapping import (
                    normalize_value_entity_map,
                )

                new_vem = dialog.result_value_entity_map()
                old_vem = normalize_value_entity_map(existing_vem)
                new_cmap_dict = new_cmap.to_dict()

                # Update maps_data in-memory immediately so the entity/event
                # editor reflects the new link without waiting for the DB
                # round-trip (SetRasterMappingCommand no longer triggers a
                # full reload, so we must keep the in-memory state in sync).
                if selected_map:
                    for rl in (selected_map.attributes or {}).get("raster_layers", []):
                        if rl.get("node_id") == node_id:
                            rl["color_map"] = new_cmap_dict
                            rl["value_entity_map"] = new_vem
                            break

                cmd = SetRasterMappingCommand(
                    map_id=map_id,
                    node_id=node_id,
                    new_mapping=new_vem,
                    old_mapping=old_vem,
                    new_color_map=new_cmap_dict,
                    old_color_map=existing_color_map_dict,
                )
                self.command_requested.emit(cmd)
                logger.debug("on_raster_palette_edit: SetRasterMappingCommand emitted")

    @Slot()
    def on_raster_query_requested(self) -> None:  # noqa: C901
        """Open the cross-layer spatial query dialog and display the result overlay."""
        if not self._current_map_id:
            return
        view = self._map_widget.view
        if not view._raster_items:
            return

        maps = self._map_widget.maps_data
        selected_map = next((m for m in maps if m.id == self._current_map_id), None)
        if not selected_map:
            return

        raster_metas = (selected_map.attributes or {}).get("raster_layers", [])

        # raster_metas never store names; names live in the layer tree.
        # Flatten the tree into {node_id: display_name} so we can show
        # human-readable names in the dialog and resolve them back afterwards.
        def _collect_node_names(
            node: Any, acc: Dict[str, str]
        ) -> None:
            acc[node.id] = node.name
            for child in node.children:
                _collect_node_names(child, acc)

        node_id_to_name: Dict[str, str] = {}
        if selected_map.layers:
            _collect_node_names(selected_map.layers, node_id_to_name)

        layers = [
            {
                "node_id": m["node_id"],
                "name": node_id_to_name.get(m["node_id"], m["node_id"][:8]),
                "mode": m.get("mode", "discrete"),
            }
            for m in raster_metas
            if m.get("node_id") in view._raster_items
            and m.get("mode", "discrete") != "color"
        ]
        if not layers:
            return

        from src.gui.dialogs.raster_query_dialog import RasterQueryDialog

        dlg = RasterQueryDialog(layers=layers, parent=self._map_widget)
        if not dlg.exec():
            return

        conditions = dlg.conditions
        if not conditions:
            return

        # Legacy name-based conditions remain readable, while new dialog rows
        # carry canonical node UUIDs.
        name_to_nodes: dict[str, list[str]] = {}
        available_ids = {str(layer["node_id"]) for layer in layers}
        for layer in layers:
            name_to_nodes.setdefault(str(layer["name"]), []).append(
                str(layer["node_id"])
            )
        resolved_nodes: list[str] = []
        for condition in conditions:
            node_id = str(condition.get("node_id", ""))
            if not node_id:
                matches = name_to_nodes.get(str(condition.get("name", "")), [])
                if len(matches) != 1:
                    QMessageBox.warning(
                        self._map_widget,
                        "Spatial Query Failed",
                        "A legacy layer name is missing or ambiguous. "
                        "Select the layer again by its UUID-backed choice.",
                    )
                    return
                node_id = matches[0]
            if node_id not in available_ids:
                QMessageBox.warning(
                    self._map_widget,
                    "Spatial Query Failed",
                    f"Raster layer is unavailable: {node_id}",
                )
                return
            resolved_nodes.append(node_id)

        unique_nodes = list(dict.fromkeys(resolved_nodes))
        arrays_by_node: Dict[str, Any] = {
            nid: view._raster_items[nid].buffer.data
            for nid in unique_nodes
            if nid in view._raster_items
        }

        arrays = [arrays_by_node[n] for n in unique_nodes if n in arrays_by_node]
        normalized: list[Dict[str, Any]] = []
        for condition, node_id in zip(conditions, resolved_nodes):
            if node_id not in arrays_by_node:
                QMessageBox.warning(
                    self._map_widget,
                    "Spatial Query Failed",
                    f"Raster data is not loaded: {node_id}",
                )
                return
            normalized.append(
                {**condition, "index": unique_nodes.index(node_id)}
            )

        if not arrays or not normalized:
            return

        modes_by_node = {
            str(metadata.get("node_id")): str(
                metadata.get("mode", "discrete")
            )
            for metadata in raster_metas
        }
        modes = [
            modes_by_node[node_id]
            for node_id in unique_nodes
            if node_id in arrays_by_node
        ]

        from src.app.raster_query_task import RasterQueryTask

        task = RasterQueryTask(arrays, modes, normalized)
        task.signals.finished.connect(self._on_raster_query_finished)
        task.signals.failed.connect(self._on_raster_query_failed)
        QThreadPool.globalInstance().start(task)

    @Slot(object)
    def _on_raster_query_finished(self, mask: object) -> None:
        """Render a worker-produced query mask on the Qt main thread."""
        from PySide6.QtCore import QRectF

        view = self._map_widget.view
        scene_rect: QRectF = (
            view.pixmap_item.boundingRect() if view.pixmap_item else QRectF()
        )
        view.set_query_overlay(mask, scene_rect)
        self._map_widget.layer_panel.set_query_active(True)

    @Slot(str)
    def _on_raster_query_failed(self, message: str) -> None:
        """Display a visible query failure on the Qt main thread."""
        logger.warning("Spatial query failed: %s", message)
        QMessageBox.warning(
            self._map_widget,
            "Spatial Query Failed",
            message,
        )

    @Slot()
    def on_raster_query_cleared(self) -> None:
        """Remove the spatial query overlay from the map view."""
        self._map_widget.view.clear_query_overlay()
        self._map_widget.layer_panel.set_query_active(False)

    @Slot(str, object, float, float)
    def on_raster_value_probed(
        self,
        node_id: str,
        value: object,
        x_norm: float,
        y_norm: float,
    ) -> None:
        """Handle a raster sample/probe event and display the result.

        Resolves the value to an entity name (if mapped) and shows a
        floating :class:`RasterProbePopup` overlay in the view.

        Args:
            node_id: Raster layer node ID.
            value: Raw 16-bit cell value.
            x_norm: Normalised X coordinate [0, 1].
            y_norm: Normalised Y coordinate [0, 1].
        """
        logger.debug(
            "on_raster_value_probed: node_id=%s value=%s pos=(%.3f,%.3f)",
            node_id,
            value,
            x_norm,
            y_norm,
        )
        if self._map_widget is None:
            return
        rgba_value = (
            tuple(int(channel) for channel in value)
            if isinstance(value, tuple)
            else None
        )
        if rgba_value is None and not isinstance(value, int):
            return
        raw_value = 0 if rgba_value is not None else int(cast(int, value))
        if rgba_value is not None and len(rgba_value) == _RGBA_COMPONENT_COUNT:
            rgba_color = cast(tuple[int, int, int, int], rgba_value)
            self._map_widget.layer_panel.set_raster_paint_color(rgba_color)

        from src.gui.widgets.map.raster_mapping import probe_all_layers

        view = self._map_widget.view
        map_id = self._map_widget.get_selected_map_id()
        maps = self._map_widget.maps_data
        selected_map = (
            next((m for m in maps if m.id == map_id), None) if map_id else None
        )
        raster_meta = (
            (selected_map.attributes or {}).get("raster_layers", [])
            if selected_map
            else []
        )

        results = probe_all_layers(view._raster_items, raster_meta, x_norm, y_norm)

        # Resolve entity name, mode, and display value for the probed layer
        entity_name: str | None = None
        label: str | None = None
        layer_mode: str = ""
        display_value: str | None = None
        continuous_linked_id: str | None = None
        for meta in raster_meta:
            if meta.get("node_id") == node_id:
                layer_mode = meta.get("mode", "discrete")
                cmap_dict = meta.get("color_map") or {}
                if cmap_dict.get("display_min") is not None:
                    try:
                        from src.gui.widgets.map.map_data_buffer import (
                            ColorMap,
                            format_display_value,
                        )

                        cmap = ColorMap.from_dict(cmap_dict)
                        display_value = format_display_value(cmap, raw_value)
                    except Exception as exc:
                        logger.debug("Could not format display value: %s", exc)
                # Continuous layers link the whole layer to one entity/event
                continuous_linked_id = cmap_dict.get("linked_entity_id") or None
                break
        for r in results:
            if r.node_id == node_id:
                label = r.label
                if r.entity_id:
                    entity_name = self._lookup_cached_world_item_name(r.entity_id)
                break
        # For continuous linked layers, resolve the whole-layer entity name
        # (the VEM is empty for these, so probe_all_layers won't find it)
        if entity_name is None and continuous_linked_id:
            entity_name = self._lookup_cached_world_item_name(continuous_linked_id)

        # Show the probe popup overlay
        self._show_probe_popup(
            node_id,
            raw_value,
            entity_name,
            label,
            layer_mode,
            (
                f"RGBA {rgba_value}"
                if rgba_value is not None
                else display_value
            ),
        )

    def _show_probe_popup(
        self,
        node_id: str,
        value: int,
        entity_name: str | None,
        label: str | None,
        mode: str = "",
        display_value: str | None = None,
    ) -> None:
        """Display or update the probe popup inside the map view.

        Args:
            node_id: Layer node ID.
            value: Cell value.
            entity_name: Resolved entity name.
            label: Palette label.
            mode: Layer mode (``"discrete"`` or ``"continuous"``).
            display_value: Formatted real-world value string, or ``None``.
        """
        if self._map_widget is None:
            return
        from src.gui.widgets.map.raster_probe_popup import RasterProbePopup

        view = self._map_widget.view
        popup = getattr(view, "_probe_popup", None)
        if popup is None:
            popup = RasterProbePopup(view)
            view._probe_popup = popup  # type: ignore[attr-defined]
        popup.show_result(
            node_id=node_id,
            value=value,
            entity_name=entity_name,
            label=label,
            mode=mode,
            display_value=display_value,
        )

    def _save_raster_to_disk(self, node_id: str) -> None:
        """Persist the raster buffer to its PNG file on disk."""
        if self._map_widget is None:
            logger.warning("_save_raster_to_disk: _map_widget is None")
            return
        view = self._map_widget.view
        item = view._raster_items.get(node_id)
        if item is None:
            logger.warning(
                "_save_raster_to_disk: no item for node_id=%s (registered=%s)",
                node_id,
                list(view._raster_items.keys()),
            )
            return

        map_id = self._map_widget.get_selected_map_id()
        if not map_id:
            logger.warning("_save_raster_to_disk: no current_map_id")
            return

        maps = self._map_widget.maps_data
        selected_map = next((m for m in maps if m.id == map_id), None)
        if not selected_map:
            logger.warning(
                "_save_raster_to_disk: map_id=%s not found in maps_data", map_id
            )
            return

        try:
            world_root = str(Path(self._db_path_accessor()).parent)
            for rl in (selected_map.attributes or {}).get("raster_layers", []):
                if rl.get("node_id") == node_id:
                    file_path = rl.get("file_path", "")
                    if file_path:
                        full_path = str(Path(world_root) / file_path)
                        logger.debug(
                            "_save_raster_to_disk: saving node_id=%s → %s",
                            node_id,
                            full_path,
                        )
                        item.buffer.save(full_path)
                        logger.info("Raster saved to disk: %s", full_path)
                    else:
                        logger.warning(
                            "_save_raster_to_disk: empty file_path for node_id=%s",
                            node_id,
                        )
                    break
            else:
                logger.warning(
                    "_save_raster_to_disk: node_id=%s not found in raster_layers metadata",
                    node_id,
                )
        except Exception as e:
            logger.error("Failed to save raster to disk: %s", e)

    def _find_map_id_for_node(self, node_id: str) -> Optional[str]:
        """Find which map owns the given raster layer node.

        Searches the in-memory ``maps_data`` to locate the map whose
        ``raster_layers`` metadata contains *node_id*.

        Args:
            node_id: Raster layer node ID to look up.

        Returns:
            Map ID string, or ``None`` if not found.
        """
        maps = self._map_widget.maps_data
        for map_obj in maps:
            for rl in (map_obj.attributes or {}).get("raster_layers", []):
                if rl.get("node_id") == node_id:
                    return map_obj.id
        return None

    @Slot(str)
    def on_raster_stats_requested(self, node_id: str) -> None:
        """Open the coverage statistics dialog for the given raster layer.

        Args:
            node_id: Raster layer node ID.
        """
        logger.debug("on_raster_stats_requested: node_id=%s", node_id)
        if self._map_widget is None:
            return
        view = self._map_widget.view
        item = view._raster_items.get(node_id)
        if item is None:
            logger.warning("on_raster_stats_requested: no item for node_id=%s", node_id)
            return

        # Find metadata for this layer
        map_id = self._find_map_id_for_node(node_id)
        meta: dict = {}
        if map_id:
            maps = self._map_widget.maps_data
            selected_map = next((m for m in maps if m.id == map_id), None)
            if selected_map:
                for rl in (selected_map.attributes or {}).get("raster_layers", []):
                    if rl.get("node_id") == node_id:
                        meta = rl
                        break

        from src.gui.widgets.map.map_data_buffer import ColorMap

        color_map = ColorMap.from_dict(meta.get("color_map", {}))
        vem = meta.get("value_entity_map", {})
        stats = item.buffer.compute_coverage_stats(color_map, vem)

        from src.gui.widgets.map.raster_stats_panel import RasterStatsPanel

        layer_name = meta.get("name", node_id)
        dlg = RasterStatsPanel(stats, layer_name=layer_name, parent=self._map_widget)
        dlg.exec()

    @Slot(str, str, str)
    def _on_raster_blend_mode_changed(
        self, node_id: str, new_mode: str, old_mode: str
    ) -> None:
        """Apply blend mode change immediately and persist via command.

        Args:
            node_id: Raster layer node ID.
            new_mode: New blend mode name.
            old_mode: Previous blend mode name (for undo).
        """
        logger.debug(
            "_on_raster_blend_mode_changed: node_id=%s %s→%s",
            node_id,
            old_mode,
            new_mode,
        )
        view = self._map_widget.view
        item = view._raster_items.get(node_id)
        if item is not None:
            if new_mode != "Normal":
                # Ensure composition modes work correctly (OpenGL ignores them).
                view.ensure_software_rendering()
            item.set_blend_mode(new_mode)
            view.graphics_scene.update()

        map_id = self._find_map_id_for_node(node_id)
        if map_id:
            from src.commands.raster_commands import SetRasterBlendModeCommand

            cmd = SetRasterBlendModeCommand(
                map_id=map_id,
                node_id=node_id,
                new_mode=new_mode,
                old_mode=old_mode,
            )
            self.command_requested.emit(cmd)

    @Slot(str)
    def on_raster_gradient_sub_mode_changed(self, sub_mode: str) -> None:
        """Update the gradient sub-mode on the active raster edit tool.

        Args:
            sub_mode: One of ``"linear"``, ``"radial"``, or ``"reflected"``.
        """
        logger.debug("on_raster_gradient_sub_mode_changed: sub_mode=%s", sub_mode)
        view = self._map_widget.view
        view._raster_edit_tool.set_gradient_sub_mode(sub_mode)

    @Slot(str)
    def on_raster_notes_requested(self, node_id: str) -> None:
        """Open the notes editor dialog for the given raster layer.

        Loads existing notes from layer metadata, shows the dialog, and
        persists changes via :class:`~src.commands.raster_commands.SetRasterNotesCommand`.

        Args:
            node_id: Raster layer node ID.
        """
        logger.debug("on_raster_notes_requested: node_id=%s", node_id)

        maps = self._map_widget.maps_data
        layer_name = node_id
        current_notes = ""
        for map_obj in maps:
            for rl in (map_obj.attributes or {}).get("raster_layers", []):
                if rl.get("node_id") == node_id:
                    layer_name = rl.get("name", node_id)
                    current_notes = rl.get("notes", "")
                    break

        from src.gui.dialogs.raster_notes_dialog import RasterNotesDialog

        dlg = RasterNotesDialog(
            layer_name=layer_name,
            current_notes=current_notes,
            parent=self._map_widget,
        )
        if dlg.exec() != RasterNotesDialog.DialogCode.Accepted:
            return

        new_notes = dlg.get_notes()
        if new_notes == current_notes:
            return

        map_id = self._find_map_id_for_node(node_id)
        if not map_id:
            logger.warning("on_raster_notes_requested: no map_id for %s", node_id)
            return

        from src.commands.raster_commands import SetRasterNotesCommand

        cmd = SetRasterNotesCommand(
            map_id=map_id,
            node_id=node_id,
            notes=new_notes,
            old_notes=current_notes,
        )
        self.command_requested.emit(cmd)

        self._map_widget.layer_panel.set_raster_layer_notes(node_id, bool(new_notes))

    # ------------------------------------------------------------------
    # Temporal rasters
    # ------------------------------------------------------------------

    @Slot(float)
    def on_playhead_changed(self, lore_date: float) -> None:
        """Handle timeline playhead change — immediate apply with debounce.

        Applies temporal rasters immediately when the debounce timer is
        idle (single-step or slow scrubbing).  During rapid scrubbing the
        timer is already active, so we skip the immediate apply and let
        the debounce coalesce into a single update when scrubbing stops.

        Args:
            lore_date: New playhead position in lore time (float days).
        """
        self._current_lore_date = lore_date
        self._raster_edit_target_by_node.clear()
        self._map_widget.layer_panel.clear_raster_edit_targets()
        self._map_widget.view.stop_raster_editing()
        self._map_widget.layer_panel.reset_edit_toggle()
        if not self._current_map_id:
            return

        # Apply immediately when no debounce is pending
        if not self._temporal_debounce_timer.isActive():
            self._apply_temporal_rasters()

        # Start/restart debounce to coalesce rapid scrubbing
        self._temporal_debounce_timer.start()

    def _apply_temporal_rasters(self) -> None:
        """Load the appropriate snapshot for each raster layer at current lore date.

        Called after the debounce timer fires.
        """
        if not self._current_map_id:
            return

        maps = self._map_widget.maps_data
        selected_map = next((m for m in maps if m.id == self._current_map_id), None)
        if not selected_map:
            return

        raster_metas = (selected_map.attributes or {}).get("raster_layers", [])
        if not raster_metas:
            return

        world_root = str(Path(self._db_path_accessor()).parent)
        view = self._map_widget.view

        for meta in raster_metas:
            node_id = meta.get("node_id", "")
            if not node_id:
                continue
            item = view._raster_items.get(node_id)
            if item is None:
                continue

            best_rel_path = self._find_best_snapshot_path(meta, self._current_lore_date)
            if not best_rel_path:
                continue
            best_abs_path = str(Path(world_root) / best_rel_path)

            current = self._current_snapshot_by_node.get(node_id)
            cache_key = self._snapshot_cache_key(node_id, best_abs_path)
            if (
                current == best_abs_path
                and self._current_snapshot_identity_by_node.get(node_id)
                == cache_key
            ):
                continue  # Already showing this snapshot

            buf = self._snapshot_cache.get(cache_key)
            if buf is None:
                try:
                    from src.gui.widgets.map.map_data_buffer import MapDataBuffer

                    buf = MapDataBuffer.from_file(
                        best_abs_path,
                        mode=str(meta.get("mode", "continuous")),
                    )
                    self._snapshot_cache[cache_key] = buf
                except Exception as e:
                    logger.warning("Failed to load snapshot %s: %s", best_abs_path, e)
                    continue
            else:
                # Move to end so recently-used entries survive eviction
                self._snapshot_cache.move_to_end(cache_key)

            item.swap_buffer(buf)
            self._current_snapshot_by_node[node_id] = best_abs_path
            self._current_snapshot_identity_by_node[node_id] = cache_key
            logger.debug(
                "Temporal raster: node=%s loaded snapshot=%s at lore_date=%.2f",
                node_id,
                best_rel_path,
                self._current_lore_date,
            )

        self._evict_snapshot_cache()

    def _evict_snapshot_cache(self) -> None:
        """Remove the oldest entries from ``_snapshot_cache`` when it exceeds the limit.

        Uses FIFO order of the underlying :class:`OrderedDict` so that
        the least-recently-inserted (or least-recently-accessed, since
        ``_apply_temporal_rasters`` calls ``move_to_end`` on hits) entries
        are evicted first.
        """
        while len(self._snapshot_cache) > self._snapshot_cache_max:
            evicted_key, _ = self._snapshot_cache.popitem(last=False)
            logger.debug("Evicted snapshot cache entry: %s", evicted_key)

    def _find_best_snapshot_path(self, meta: Dict[str, Any], lore_date: float) -> str:
        """Find the best (nearest past) snapshot file path for a given lore date.

        Args:
            meta: Raster layer metadata dict with optional ``snapshots`` key.
            lore_date: Current playhead time.

        Returns:
            Relative file path to display.  Falls back to
            ``meta['file_path']`` if no snapshot at or before *lore_date*
            exists.
        """
        snapshots: Dict[str, str] = meta.get("snapshots", {})
        base_path: str = meta.get("file_path", "")
        if not snapshots:
            return base_path
        valid = [
            (date, v)
            for k, v in snapshots.items()
            if (date := _safe_float(k)) is not None and date <= lore_date
        ]
        if not valid:
            return base_path
        _, path = max(valid, key=lambda x: x[0])
        return path

    @Slot(str)
    def on_raster_snapshot_requested(self, node_id: str) -> None:
        """Save a snapshot of the current raster buffer at the current lore date.

        Writes the buffer to a PNG file and persists the metadata via
        :class:`~src.commands.raster_commands.SetRasterSnapshotCommand`.

        Args:
            node_id: The raster layer node to snapshot.
        """
        if not self._current_map_id:
            logger.warning("on_raster_snapshot_requested: no current map")
            return

        view = self._map_widget.view
        item = view._raster_items.get(node_id)
        if item is None:
            logger.warning(
                "on_raster_snapshot_requested: no raster item for %s", node_id
            )
            return

        maps = self._map_widget.maps_data
        selected_map = next((m for m in maps if m.id == self._current_map_id), None)
        if not selected_map:
            return

        raster_metas = (selected_map.attributes or {}).get("raster_layers", [])
        meta = next((m for m in raster_metas if m.get("node_id") == node_id), None)
        if meta is None:
            return

        lore_date = self._current_lore_date
        try:
            from PIL import Image as PilImage

            rgba = getattr(item.buffer, "_rgba_data", None)
            if rgba is not None:
                image = PilImage.fromarray(rgba.copy(), mode="RGBA")
            else:
                image = PilImage.fromarray(item.buffer.data.copy())
            encoded = BytesIO()
            image.save(encoded, format="PNG", compress_level=1)
        except Exception as e:
            logger.error("Failed to encode snapshot: %s", e)
            QMessageBox.warning(
                self._map_widget,
                "Snapshot Failed",
                f"Could not prepare snapshot:\n{e}",
            )
            return

        from src.services.raster_asset_service import RasterAssetService

        world_root = Path(self._db_path_accessor()).parent
        snap_rel_path = RasterAssetService(world_root).allocate_snapshot_path(
            node_id
        )
        old_snapshots = dict(meta.get("snapshots", {}))

        from src.commands.raster_commands import SetRasterSnapshotCommand

        cmd = SetRasterSnapshotCommand(
            map_id=self._current_map_id,
            node_id=node_id,
            lore_date=lore_date,
            rel_file_path=snap_rel_path,
            old_snapshots=old_snapshots,
            image_bytes=encoded.getvalue(),
        )
        self.command_requested.emit(cmd)
        logger.info(
            "Requested editable raster state for node=%s at lore_date=%.17g",
            node_id,
            lore_date,
        )

    @Slot(str, float)
    def on_raster_snapshot_selected(self, node_id: str, lore_date: float) -> None:
        """Handle selecting a snapshot row by jumping the timeline playhead."""
        _ = node_id
        self._map_widget.jump_to_time_requested.emit(lore_date)

    @Slot(str)
    def on_raster_base_edit_requested(self, node_id: str) -> None:
        """Explicitly display and select the undated base raster for editing."""
        metadata = self._raster_metadata(node_id)
        if metadata is not None:
            self._select_raster_edit_target(
                node_id,
                str(metadata.get("file_path", "")),
                "Base",
            )

    @Slot(str, float)
    def on_raster_snapshot_edit_requested(
        self, node_id: str, lore_date: float
    ) -> None:
        """Explicitly select an exact dated state as the editable target."""
        metadata = self._raster_metadata(node_id)
        if metadata is None:
            return
        exact_path = ""
        for key, path in dict(metadata.get("snapshots", {})).items():
            try:
                if float(key) == lore_date:
                    exact_path = str(path)
                    break
            except (TypeError, ValueError):
                continue
        if not exact_path:
            QMessageBox.warning(
                self._map_widget,
                "Raster state unavailable",
                "No exact raster state exists at this lore date.",
            )
            return
        self.on_raster_snapshot_selected(node_id, lore_date)
        self._select_raster_edit_target(
            node_id,
            exact_path,
            f"Dated state ({lore_date:.2f})",
        )

    def _raster_metadata(self, node_id: str) -> Optional[dict[str, Any]]:
        """Return current metadata for a raster node from loaded map state."""
        map_id = self._map_widget.get_selected_map_id()
        selected_map = next(
            (item for item in self._map_widget.maps_data if item.id == map_id),
            None,
        )
        if selected_map is None:
            return None
        return next(
            (
                item
                for item in (selected_map.attributes or {}).get(
                    "raster_layers", []
                )
                if item.get("node_id") == node_id
            ),
            None,
        )

    def _select_raster_edit_target(
        self,
        node_id: str,
        relative_path: str,
        label: str = "Base",
    ) -> None:
        """Load one immutable file copy and select it as the paint target."""
        if not relative_path or self._pending_raster_strokes.get(node_id):
            QMessageBox.warning(
                self._map_widget,
                "Raster state unavailable",
                "Wait for pending raster strokes before changing edit targets.",
            )
            return
        absolute_path = str(Path(self._db_path_accessor()).parent / relative_path)
        try:
            from src.gui.widgets.map.map_data_buffer import MapDataBuffer

            metadata = self._raster_metadata(node_id)
            buffer = MapDataBuffer.from_file(
                absolute_path,
                mode=str((metadata or {}).get("mode", "continuous")),
            )
            cache_key = self._snapshot_cache_key(node_id, absolute_path)
        except Exception as exc:
            QMessageBox.warning(
                self._map_widget,
                "Raster state unavailable",
                str(exc),
            )
            return
        item = self._map_widget.view._raster_items.get(node_id)
        if item is None:
            return
        item.swap_buffer(buffer)
        self._snapshot_cache[cache_key] = buffer
        self._current_snapshot_by_node[node_id] = absolute_path
        self._current_snapshot_identity_by_node[node_id] = cache_key
        self._raster_edit_target_by_node[node_id] = relative_path
        self._failed_raster_nodes.discard(node_id)
        self._map_widget.layer_panel.set_raster_edit_target(node_id, label)
        self._evict_snapshot_cache()

    @Slot(str, float)
    def on_raster_snapshot_delete_requested(self, node_id: str, lore_date: float) -> None:
        """Delete a snapshot at a lore date for a given raster layer."""
        if not self._current_map_id:
            return

        maps = self._map_widget.maps_data
        selected_map = next((m for m in maps if m.id == self._current_map_id), None)
        if not selected_map:
            return

        raster_metas = (selected_map.attributes or {}).get("raster_layers", [])
        meta = next((m for m in raster_metas if m.get("node_id") == node_id), None)
        if meta is None:
            return

        snapshots: Dict[str, str] = dict(meta.get("snapshots", {}))
        target_key: Optional[str] = None
        for key in snapshots:
            val = _safe_float(key)
            if val is not None and val == lore_date:
                target_key = key
                break
        if target_key is None:
            return

        answer = QMessageBox.question(
            self._map_widget,
            "Delete Snapshot",
            (
                f"Delete snapshot at lore day {lore_date:.2f}?\n"
                "This removes the snapshot file from disk."
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        rel_path = snapshots.get(target_key, "")
        if not rel_path:
            return

        old_snapshots = dict(snapshots)

        world_root = Path(self._db_path_accessor()).parent

        from src.commands.raster_commands import RemoveRasterSnapshotCommand

        cmd = RemoveRasterSnapshotCommand(
            map_id=self._current_map_id,
            node_id=node_id,
            lore_date=lore_date,
            rel_file_path=rel_path,
            world_root=str(world_root),
            old_snapshots=old_snapshots,
        )
        self.command_requested.emit(cmd)
