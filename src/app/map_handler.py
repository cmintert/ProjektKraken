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
from typing import TYPE_CHECKING, Callable

from PySide6.QtCore import Q_ARG, QMetaObject, QObject, Qt, Signal, Slot

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

    @Slot(str)
    def on_layer_feature_deleted(self, object_id: str) -> None:
        """Delete a marker from the database after layer panel removal.

        The graphics item and layer node have already been cleaned up by
        ``MapWidget._on_delete_layer``.  This handler only fires the
        ``DeleteMarkerCommand`` to persist the deletion.

        Args:
            object_id: The entity/event UUID used as the UI marker key.

        """
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
        maps = self._map_widget.maps_data
        selected_map = next((m for m in maps if m.id == map_id), None)
        if not selected_map:
            return

        raster_metas = (selected_map.attributes or {}).get("raster_layers", [])
        if not raster_metas:
            return

        world_root = str(Path(self._db_path_accessor()).parent)
        view = self._map_widget.view

        if not view.pixmap_item:
            logger.debug("load_raster_layers: no map pixmap loaded yet")
            return

        scene_rect = view.pixmap_item.boundingRect()

        from src.gui.widgets.map.map_data_buffer import ColorMap, MapDataBuffer
        from src.gui.widgets.map.raster_layer_item import RasterLayerItem

        for meta in raster_metas:
            node_id = meta.get("node_id", "")
            file_path = meta.get("file_path", "")
            abs_path = str(Path(world_root) / file_path)

            try:
                buf = MapDataBuffer.from_file(abs_path)
            except Exception as e:
                logger.error("Failed to load raster %s: %s", file_path, e)
                continue

            color_map_data = meta.get("color_map", {})
            color_map = ColorMap.from_dict(color_map_data)

            item = RasterLayerItem(
                buffer=buf,
                color_map=color_map,
                scene_rect=scene_rect,
                node_id=node_id,
            )

            # Store raster items on the view for later access
            if not hasattr(view, "_raster_items"):
                view._raster_items = {}
            view._raster_items[node_id] = item
            view.scene.addItem(item)

            logger.info("Loaded raster layer: %s (%s)", node_id, file_path)
