"""MapHandler - Handles map and marker operations.

This module contains all map and marker-related business logic,
decoupled from the UI layer.  It receives specific dependencies
via constructor injection rather than a reference to MainWindow.

Dialog creation is the responsibility of the widget layer
(``MapWidget``).  This handler only operates on pre-resolved data
received through signals.
"""

import shutil
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional

from PySide6.QtCore import Q_ARG, QMetaObject, QObject, Qt, QTimer, Signal, Slot

from src.commands.map_commands import (
    CreateMapCommand,
    CreateMarkerCommand,
    DeleteMapCommand,
    DeleteMarkerCommand,
    RenameLayerCommand,
    SaveLayerTreeCommand,
    SetLayerOpacityCommand,
    UpdateMapCommand,
    UpdateMarkerAttributeCommand,
    UpdateMarkerColorCommand,
    UpdateMarkerCommand,
    UpdateMarkerIconCommand,
)
from src.core.logging_config import get_logger

if TYPE_CHECKING:
    from src.gui.widgets.map_widget import MapWidget

logger = get_logger(__name__)


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

    def __init__(
        self,
        map_widget: "MapWidget",
        worker: object,
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

        # ── Temporal rasters ──────────────────────────────────────────
        self._current_lore_date: float = 0.0
        # abs_path → MapDataBuffer (avoids re-reading same snapshot file)
        self._snapshot_cache: Dict[str, Any] = {}
        # node_id → abs_path currently shown in scene
        self._current_snapshot_by_node: Dict[str, str] = {}
        self._temporal_debounce_timer = QTimer()
        self._temporal_debounce_timer.setSingleShot(True)
        self._temporal_debounce_timer.setInterval(300)
        self._temporal_debounce_timer.timeout.connect(self._apply_temporal_rasters)

    def load_maps(self) -> None:
        """Requests loading of all maps from the worker thread."""
        QMetaObject.invokeMethod(
            self._worker, "load_maps", Qt.ConnectionType.QueuedConnection
        )

    @Slot(str)
    def on_map_selected(self, map_id: str) -> None:
        """Handler for when a map is selected in the widget. Loads the map image and
        requests markers.

        Args:
            map_id: ID of the selected map.

        """
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
                # Reset to default if no specific scale set (1000 km)
                self._map_widget.view.set_map_width_meters(1_000_000.0)

            # Request markers
            QMetaObject.invokeMethod(
                self._worker,
                "load_markers",
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(str, map_id),
            )

            # Request trajectories
            QMetaObject.invokeMethod(
                self._worker,
                "load_trajectories",
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(str, map_id),
            )

    @Slot(str)
    def reload_markers(self, map_id: str) -> None:
        """Reloads markers for the specified map.

        Args:
            map_id: The ID of the map to reload markers for.

        """
        logger.info(f"Reloading markers for map: {map_id}")
        QMetaObject.invokeMethod(
            self._worker,
            "load_markers",
            Qt.ConnectionType.QueuedConnection,
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
        # Copy image to project assets folder
        source_path = Path(file_path)
        project_dir = Path(self._db_path_accessor()).parent
        assets_dir = project_dir / "assets" / "maps"
        assets_dir.mkdir(parents=True, exist_ok=True)

        # Generate unique filename to avoid conflicts
        unique_suffix = uuid.uuid4().hex[:8]
        dest_filename = f"{source_path.stem}_{unique_suffix}{source_path.suffix}"
        dest_path = assets_dir / dest_filename

        try:
            shutil.copy2(source_path, dest_path)
            logger.info(f"Copied map image to: {dest_path}")
        except Exception as e:
            logger.error(f"Failed to copy image: {e}")
            return

        # Store relative path
        relative_path = str(dest_path.relative_to(project_dir))

        cmd = CreateMapCommand({"name": name.strip(), "image_path": relative_path})
        self.command_requested.emit(cmd)

    def delete_map(self, map_id: str) -> None:
        """Deletes a map after confirmation has already been obtained.

        The confirmation dialog is handled by the widget layer.

        Args:
            map_id: ID of the map to delete.

        """
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

        Restores the persisted layer tree (if any) and auto-registers
        new markers into the hierarchy.  The view transform (pan/zoom)
        is preserved across the clear-and-rebuild cycle.

        Args:
            map_id: The map ID these markers belong to.
            processed_markers: List of dicts with marker data.

        """
        # Verify we are still looking at this map
        current_map_id = self._map_widget.map_selector.currentData()
        if current_map_id != map_id:
            return

        # Preserve the current view transform so the user's pan/zoom
        # position is maintained after the clear-and-rebuild cycle.
        view = self._map_widget.view
        saved_transform = view.transform()
        h_scroll = view.horizontalScrollBar().value()
        v_scroll = view.verticalScrollBar().value()

        # Preserve selection state across clear-and-rebuild
        selected_marker_id: str | None = None
        selected_items = view.scene.selectedItems()
        if selected_items:
            from src.gui.widgets.map.marker_item import MarkerItem

            first = selected_items[0]
            if isinstance(first, MarkerItem):
                selected_marker_id = first.marker_id

        selected_layer_id: str | None = self._map_widget.layer_panel.selected_node_id

        self._map_widget.clear_markers()
        self._marker_object_to_id.clear()  # Reset mapping

        # Restore persisted layer tree from the selected map object
        maps = self._map_widget.maps_data
        selected_map = next((m for m in maps if m.id == map_id), None)
        if selected_map and selected_map.layers is not None:
            self._map_widget._build_layer_model(selected_map.layers)
        else:
            self._map_widget._build_layer_model()

        for marker_data in processed_markers:
            # Add marker to map (also auto-registers a layer node)
            self._map_widget.add_marker(
                marker_id=marker_data["object_id"],
                object_type=marker_data["object_type"],
                label=marker_data["label"],
                x=marker_data["x"],
                y=marker_data["y"],
                icon=marker_data["icon"],
                color=marker_data["color"],
                description=marker_data.get("description", ""),
                lore_date=marker_data.get("lore_date"),
                feature_type=marker_data.get("feature_type", "point"),
                geometry=marker_data.get("geometry"),
                style=marker_data.get("style"),
                visual_attributes=marker_data.get("attributes"),
            )

            # Set lore priority (connection_count) on the MarkerItem
            obj_id = marker_data["object_id"]
            if obj_id in view.markers:
                view.markers[obj_id].connection_count = marker_data.get(
                    "connection_count", 0
                )

            # Store mapping for later updates (object_id -> marker.id)
            self._marker_object_to_id[marker_data["object_id"]] = marker_data["id"]

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

        # Load raster layers for this map
        self.load_raster_layers(map_id)

    @Slot(list)
    def on_trajectories_ready(self, trajectories: list) -> None:
        """Handle trajectories ready signal from DataHandler.

        Args:
            trajectories: List of (marker_id, trajectory_id, keyframes) tuples.

        """
        self._map_widget.set_trajectories(trajectories)

    @Slot(float)
    def on_map_scale_changed(self, width_meters: float) -> None:
        """Handle map scale change from MapWidget.

        Args:
            width_meters: The new width of the map in meters.

        """
        current_map_id = self._map_widget.map_selector.currentData()
        if not current_map_id:
            return

        cmd = UpdateMapCommand(
            current_map_id, {"attributes": {"width_meters": width_meters}}
        )
        self.command_requested.emit(cmd)

    # ------------------------------------------------------------------
    # Layer operations (routed through the command stack)
    # ------------------------------------------------------------------

    @Slot()
    def on_layer_tree_changed(self) -> None:
        """Persist the current layer tree to the database.

        Called whenever the in-memory layer model is mutated.
        """
        map_id = self._map_widget.get_selected_map_id()
        model = self._map_widget.get_layer_model()
        if not map_id or not model:
            return
        tree_dict = model.root.to_dict()
        cmd = SaveLayerTreeCommand(map_id, tree_dict)
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
        """Delete a feature from the database after layer panel removal.

        The graphics item and layer node have already been cleaned up by
        ``MapWidget._on_delete_layer``.  This handler dispatches to the
        correct delete command based on *layer_type*:

        - ``MAP_LAYER_TYPE_RASTER`` → :class:`DeleteRasterLayerCommand`.
        - All other leaf types → :class:`DeleteMarkerCommand`.

        Args:
            object_id: For markers, the entity/event UUID used as the UI
                marker key.  For raster layers, the layer node UUID.
            layer_type: One of the ``MAP_LAYER_TYPE_*`` constants.

        """
        from src.app.constants import MAP_LAYER_TYPE_RASTER

        if layer_type == MAP_LAYER_TYPE_RASTER:
            self.delete_raster_layer(object_id)
            return

        actual_marker_id = self._marker_object_to_id.get(object_id)
        if not actual_marker_id:
            logger.warning("on_layer_feature_deleted: no mapping for %s", object_id)
            return
        del self._marker_object_to_id[object_id]
        cmd = DeleteMarkerCommand(actual_marker_id)
        self.command_requested.emit(cmd)

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
    ) -> None:
        """Create a new raster (heatmap) layer on the current map.

        Args:
            name: Display name for the raster layer.
            width: Buffer width in pixels.
            height: Buffer height in pixels.
            mode: ``"discrete"`` or ``"continuous"``.
            default_value: Initial fill value (0–65535).

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
        )
        self.command_requested.emit(cmd)
        logger.info(
            "Requested raster layer creation: '%s' %dx%d (%s)",
            name,
            width,
            height,
            mode,
        )

    def delete_raster_layer(self, node_id: str) -> None:
        """Delete a raster layer by its layer node ID.

        Args:
            node_id: The layer node UUID for the raster to delete.

        """
        map_id = self._map_widget.get_selected_map_id()
        if not map_id:
            return

        world_root = str(Path(self._db_path_accessor()).parent)

        from src.commands.raster_commands import DeleteRasterLayerCommand

        cmd = DeleteRasterLayerCommand(
            map_id=map_id,
            node_id=node_id,
            world_root=world_root,
        )
        self.command_requested.emit(cmd)
        logger.info("Requested raster layer deletion: %s", node_id)

    def load_raster_layers(self, map_id: str) -> None:
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
            view.scene.removeItem(old_item)
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
                buf = MapDataBuffer.from_file(abs_path)
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
            )

            # Apply persisted blend mode if non-default
            blend_mode = meta.get("blend_mode", "Normal")
            if blend_mode != "Normal":
                item.set_blend_mode(blend_mode)

            # Store raster items on the view for later access
            if not hasattr(view, "_raster_items"):
                view._raster_items = {}
            view._raster_items[node_id] = item
            view.scene.addItem(item)

            # Record base file as the currently displayed snapshot
            self._current_snapshot_by_node[node_id] = abs_path

            logger.info(
                "Loaded raster layer: %s (%s) — scene item added", node_id, file_path
            )

        # Update the layer panel's mode badge metadata
        mode_by_id = {
            m.get("node_id", ""): m.get("mode", "discrete")
            for m in raster_metas
            if m.get("node_id")
        }
        self._map_widget.layer_panel.set_raster_mode_metadata(mode_by_id)

        # Pass full metadata so the legend and class picker can populate
        meta_by_id = {m["node_id"]: m for m in raster_metas if m.get("node_id")}
        self._map_widget.layer_panel.set_raster_layer_metadata(meta_by_id)

        # Connect layer panel signals (guard against duplicate connections)
        layer_panel = self._map_widget.layer_panel
        try:
            layer_panel.raster_stats_requested.disconnect(
                self.on_raster_stats_requested
            )
        except RuntimeError:
            pass
        layer_panel.raster_stats_requested.connect(self.on_raster_stats_requested)

        try:
            layer_panel.raster_blend_mode_changed.disconnect(
                self._on_raster_blend_mode_changed
            )
        except RuntimeError:
            pass
        layer_panel.raster_blend_mode_changed.connect(
            self._on_raster_blend_mode_changed
        )

    # ------------------------------------------------------------------
    # Raster editing handlers
    # ------------------------------------------------------------------

    @Slot(str, tuple, bytes, bytes)
    def on_raster_stroke_completed(
        self,
        node_id: str,
        dirty_region: tuple,
        before_bytes: bytes,
        after_bytes: bytes,
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

        if self._map_widget is None:
            logger.warning("on_raster_stroke_completed: _map_widget is None")
            return
        map_id = self._map_widget.get_selected_map_id()
        if not map_id:
            logger.warning(
                "on_raster_stroke_completed: no current_map_id on map_widget "
                "(node_id=%s dirty=%s)",
                node_id,
                dirty_region,
            )
            return

        logger.debug(
            "on_raster_stroke_completed: node_id=%s map_id=%s dirty=%s "
            "before_bytes=%d after_bytes=%d",
            node_id,
            map_id,
            dirty_region,
            len(before_bytes),
            len(after_bytes),
        )

        cmd = StrokeRasterCommand(
            map_id=map_id,
            node_id=node_id,
            dirty_region=dirty_region,
            before_bytes=before_bytes,
            after_bytes=after_bytes,
        )

        # Inject the live buffer reference
        view = self._map_widget.view
        item = view._raster_items.get(node_id)
        if item is not None:
            cmd.buffer = item.buffer
            logger.debug("on_raster_stroke_completed: buffer injected into command")
        else:
            logger.warning(
                "on_raster_stroke_completed: no raster item for node_id=%s "
                "(registered=%s)",
                node_id,
                list(view._raster_items.keys()),
            )

        # Also save the raster file to disk
        self._save_raster_to_disk(node_id)

        logger.debug("on_raster_stroke_completed: emitting command_requested")
        self.command_requested.emit(cmd)

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

        dialog = RasterPaletteEditor(
            color_map=item.color_map,
            mode=mode,
            value_entity_map=existing_vem,
            buffer_min=None,
            buffer_max=None,
            parent=self._map_widget,
        )
        if mode == "continuous":
            try:
                stats = item.buffer.compute_coverage_stats(item.color_map)
                dialog = RasterPaletteEditor(
                    color_map=item.color_map,
                    mode=mode,
                    value_entity_map=existing_vem,
                    buffer_min=stats.min_val,
                    buffer_max=stats.max_val,
                    parent=self._map_widget,
                )
            except Exception as _exc:
                logger.debug("Could not compute buffer stats: %s", _exc)
        if dialog.exec():
            new_cmap = dialog.result_color_map()
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
                cmd = SetRasterMappingCommand(
                    map_id=map_id,
                    node_id=node_id,
                    new_mapping=new_vem,
                    old_mapping=old_vem,
                    new_color_map=new_cmap.to_dict(),
                    old_color_map=existing_color_map_dict,
                )
                self.command_requested.emit(cmd)
                logger.debug("on_raster_palette_edit: SetRasterMappingCommand emitted")

    @Slot()
    def on_raster_query_requested(self) -> None:
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
        layers = [
            {
                "node_id": m["node_id"],
                "name": m.get("name", m["node_id"][:8]),
                "mode": m.get("mode", "discrete"),
            }
            for m in raster_metas
            if m.get("node_id") in view._raster_items
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

        # Resolve node_ids to arrays
        unique_nodes = list(dict.fromkeys(c["node_id"] for c in conditions))
        arrays_by_node: Dict[str, Any] = {
            nid: view._raster_items[nid].buffer.data
            for nid in unique_nodes
            if nid in view._raster_items
        }

        arrays = [arrays_by_node[n] for n in unique_nodes if n in arrays_by_node]
        normalized = [
            {**c, "index": unique_nodes.index(c["node_id"])}
            for c in conditions
            if c["node_id"] in arrays_by_node
        ]

        if not arrays or not normalized:
            return

        from PySide6.QtCore import QRectF

        from src.gui.widgets.map.map_data_buffer import compute_spatial_query

        try:
            mask = compute_spatial_query(arrays, normalized)
        except Exception as exc:
            logger.warning("Spatial query failed: %s", exc)
            return

        scene_rect: QRectF = (
            view.pixmap_item.boundingRect() if view.pixmap_item else QRectF()
        )
        view.set_query_overlay(mask, scene_rect)
        self._map_widget.layer_panel.set_query_active(True)

    @Slot()
    def on_raster_query_cleared(self) -> None:
        """Remove the spatial query overlay from the map view."""
        self._map_widget.view.clear_query_overlay()
        self._map_widget.layer_panel.set_query_active(False)

    @Slot(str, int, float, float)
    def on_raster_value_probed(
        self, node_id: str, value: int, x_norm: float, y_norm: float
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
            "on_raster_value_probed: node_id=%s value=%d pos=(%.3f,%.3f)",
            node_id,
            value,
            x_norm,
            y_norm,
        )
        if self._map_widget is None:
            return

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

        # Resolve entity name and mode for the probed layer
        entity_name: str | None = None
        label: str | None = None
        layer_mode: str = ""
        for meta in raster_meta:
            if meta.get("node_id") == node_id:
                layer_mode = meta.get("mode", "discrete")
                break
        for r in results:
            if r.node_id == node_id:
                label = r.label
                if r.entity_id:
                    try:
                        from src.services.db_service import DatabaseService

                        db_path = self._db_path_accessor()
                        db = DatabaseService(db_path)
                        entity = db.entity_repository.get(r.entity_id)
                        if entity:
                            entity_name = entity.name
                    except Exception as exc:
                        logger.debug("Could not resolve entity name: %s", exc)
                break

        # Show the probe popup overlay
        self._show_probe_popup(node_id, value, entity_name, label, layer_mode)

    def _show_probe_popup(
        self,
        node_id: str,
        value: int,
        entity_name: str | None,
        label: str | None,
        mode: str = "",
    ) -> None:
        """Display or update the probe popup inside the map view.

        Args:
            node_id: Layer node ID.
            value: Cell value.
            entity_name: Resolved entity name.
            label: Palette label.
            mode: Layer mode (``"discrete"`` or ``"continuous"``).
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
            item.set_blend_mode(new_mode)
            view.scene.update()

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

        self._map_widget.layer_panel.set_raster_layer_notes(
            node_id, bool(new_notes)
        )

    # ------------------------------------------------------------------
    # Temporal rasters
    # ------------------------------------------------------------------

    @Slot(float)
    def on_playhead_changed(self, lore_date: float) -> None:
        """Handle timeline playhead change — debounced raster swap.

        Args:
            lore_date: New playhead position in lore time (float days).
        """
        self._current_lore_date = lore_date
        if self._current_map_id:
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
            if current == best_abs_path:
                continue  # Already showing this snapshot

            buf = self._snapshot_cache.get(best_abs_path)
            if buf is None:
                try:
                    from src.gui.widgets.map.map_data_buffer import MapDataBuffer

                    buf = MapDataBuffer.from_file(best_abs_path)
                    self._snapshot_cache[best_abs_path] = buf
                except Exception as e:
                    logger.warning("Failed to load snapshot %s: %s", best_abs_path, e)
                    continue

            item.swap_buffer(buf)
            self._current_snapshot_by_node[node_id] = best_abs_path
            logger.debug(
                "Temporal raster: node=%s loaded snapshot=%s at lore_date=%.2f",
                node_id,
                best_rel_path,
                self._current_lore_date,
            )

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
            (float(k), v)
            for k, v in snapshots.items()
            if _safe_float(k) is not None and _safe_float(k) <= lore_date
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

        world_root = Path(self._db_path_accessor()).parent
        lore_date = self._current_lore_date

        base_path = meta.get("file_path", f"rasters/{node_id[:8]}.png")
        base_stem = Path(base_path).stem
        snap_filename = f"{base_stem}_snap_{lore_date:.2f}.png"
        snap_rel_path = f"rasters/{snap_filename}"
        snap_abs_path = str(world_root / snap_rel_path)

        try:
            Path(snap_abs_path).parent.mkdir(parents=True, exist_ok=True)
            item.buffer.save(snap_abs_path)
        except Exception as e:
            logger.error("Failed to save snapshot: %s", e)
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(
                self._map_widget,
                "Snapshot Failed",
                f"Could not save snapshot:\n{e}",
            )
            return

        old_snapshots = dict(meta.get("snapshots", {}))
        meta.setdefault("snapshots", {})[str(lore_date)] = snap_rel_path

        self._snapshot_cache[snap_abs_path] = item.buffer
        self._current_snapshot_by_node[node_id] = snap_abs_path

        from src.commands.raster_commands import SetRasterSnapshotCommand

        cmd = SetRasterSnapshotCommand(
            map_id=self._current_map_id,
            node_id=node_id,
            lore_date=lore_date,
            rel_file_path=snap_rel_path,
            old_snapshots=old_snapshots,
        )
        self.command_requested.emit(cmd)

        # Refresh panel snapshot count
        meta_by_id = {m.get("node_id", ""): m for m in raster_metas if m.get("node_id")}
        self._map_widget.layer_panel.set_raster_layer_metadata(meta_by_id)

        snap_count = len(meta.get("snapshots", {}))
        logger.info(
            "Saved snapshot for node=%s at lore_date=%.2f (%d total)",
            node_id,
            lore_date,
            snap_count,
        )
