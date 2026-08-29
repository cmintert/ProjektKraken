"""MapHandler - Handles map and marker operations.

This module contains all map and marker-related business logic,
decoupled from the UI layer.  It receives specific dependencies
via constructor injection rather than a reference to MainWindow.

Dialog creation is the responsibility of the widget layer
(``MapWidget``).  This handler only operates on pre-resolved data
received through signals.
"""

import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Optional, Set

from PySide6.QtCore import (
    Q_ARG,
    QObject,
    Signal,
    Slot,
)

from src.app.constants import (
    MAP_ROLE_DETAIL,
    MAP_ROLE_MASTER,
)
from src.app.qt_invocation import invoke_queued
from src.app.raster_controller import RasterController
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
)
from src.core.logging_config import get_logger
from src.core.map import MapLayerNode
from src.services.map_nesting_service import MapNestingService, NestingValidationError
from src.services.marker_icon_catalog import MarkerIconCatalog
from src.services.repositories.map_repository import MapRepository

if TYPE_CHECKING:
    from src.gui.widgets.map.map_graphics_view import MapGraphicsView
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
        # Track the map ID whose markers are currently loaded (for incremental diff)
        self._loaded_markers_map_id: Optional[str] = None
        # Snapshot of last-loaded marker data keyed by object_id (for diff)
        self._loaded_marker_data: dict[str, dict] = {}
        # Set after maps_data reload until the next marker refresh synchronizes
        # the complete layer model, including raster nodes.
        self._pending_layer_node_sync = False
        self._raster_controller = RasterController(
            map_widget=map_widget,
            db_path_accessor=db_path_accessor,
            parent=self,
        )
        self._raster_controller.command_requested.connect(self.command_requested.emit)
        self._raster_controller.raster_save_state_changed.connect(
            self.raster_save_state_changed.emit
        )

    def load_maps(self) -> None:
        """Request loading of all maps from the worker thread."""
        invoke_queued(self._worker, "load_maps")

    @Slot(str)
    def on_map_selected(self, map_id: str) -> None:
        """Load a selected map and request its dependent spatial data."""
        self._raster_controller.on_map_selected(map_id)

        maps = self._map_widget.maps_data
        selected_map = next((item for item in maps if item.id == map_id), None)
        if not selected_map or not selected_map.image_path:
            return

        image_path = selected_map.image_path
        if not Path(image_path).is_absolute():
            project_dir = Path(self._db_path_accessor()).parent
            image_path = str(project_dir / image_path)

        world_root = str(Path(self._db_path_accessor()).parent)
        self._map_widget.view.set_world_root(world_root)
        if self._map_widget.view.current_image_path != image_path:
            self._map_widget.load_map(image_path)

        width_meters = selected_map.attributes.get("width_meters")
        if width_meters:
            self._map_widget.view.set_map_width_meters(float(width_meters))
        else:
            self._map_widget.view.clear_map_scale()

        invoke_queued(self._worker, "load_markers", Q_ARG(str, map_id))
        invoke_queued(self._worker, "load_trajectories", Q_ARG(str, map_id))
        invoke_queued(
            self._worker,
            "load_feature_geometry_states",
            Q_ARG(str, map_id),
        )
        self._load_footprints_for_map(selected_map, maps)
        self._load_breadcrumb_for_map(selected_map, maps)

    @Slot(str)
    def reload_markers(self, map_id: str) -> None:
        """Reload markers for one map through the worker thread."""
        logger.info("Reloading markers for map: %s", map_id)
        invoke_queued(self._worker, "load_markers", Q_ARG(str, map_id))

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
                "attributes": self._new_marker_attributes(),
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
                "attributes": self._new_marker_attributes(),
            }
        )
        self.command_requested.emit(cmd)
        logger.info(f"Creating marker for {item_type} '{item_name}' via drag-drop")

    def _new_marker_attributes(self) -> dict[str, Any]:
        """Build persistent default appearance attributes for a new point marker."""
        pixmap_item = self._map_widget.view.pixmap_item
        image_width = (
            pixmap_item.boundingRect().width() if pixmap_item is not None else 0.0
        )
        return MarkerIconCatalog.load().new_marker_attributes(image_width)

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
            "color": marker_data["color"],
            "summary": marker_data.get("summary", ""),
            "feature_type": marker_data.get("feature_type", "point"),
            "geometry": marker_data.get("geometry"),
            "connection_count": marker_data.get("connection_count", 0),
            "attributes": marker_data.get("attributes", {}),
        }

    def _incremental_marker_update(self, map_id: str, processed_markers: list) -> None:
        """Update markers incrementally — only add/remove/update changed."""
        view = self._map_widget.view
        saved_transform = view.transform()
        h_scroll = view.horizontalScrollBar().value()
        v_scroll = view.verticalScrollBar().value()
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

        # Replacing a selected marker with different artwork geometry can make
        # QGraphicsView adjust its scroll bars. Keep the map viewport anchored
        # across the incremental refresh just as the full rebuild path does.
        view.setTransform(saved_transform)
        view.horizontalScrollBar().setValue(h_scroll)
        view.verticalScrollBar().setValue(v_scroll)

    def _full_marker_rebuild(self, map_id: str, processed_markers: list) -> None:
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
        self.on_register_detail_map_requested(
            detail_map_id, parent_map_id, registration
        )

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
            ancestors = list(MapNestingService.iter_ancestors(current_map.id, all_maps))
        except NestingValidationError:
            ancestors = []

        # ancestors is ordered nearest → farthest; reverse to get root first.
        chain = [(m.id, str(getattr(m, "name", m.id))) for m in reversed(ancestors)]
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
    def on_layer_properties_changed(self, node_id: str, properties: dict) -> None:
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
        """Delegate to the raster capability controller."""
        self._raster_controller.create_raster_layer(
            name,
            width,
            height,
            mode,
            default_value,
            import_path,
            display_min,
            display_max,
            unit,
        )

    def delete_raster_layer(self, node_id: str) -> None:
        """Delegate to the raster capability controller."""
        self._raster_controller.delete_raster_layer(node_id)

    def load_raster_layers(self, map_id: str) -> None:  # noqa: C901
        """Delegate to the raster capability controller."""
        self._raster_controller.load_raster_layers(map_id)

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
        """Delegate to the raster capability controller."""
        self._raster_controller.on_raster_stroke_completed(
            node_id, patches_or_region, before_bytes, after_bytes
        )

    @Slot(object)
    def on_command_effects(self, result: object) -> None:
        """Delegate raster effects and retain generic failed-command reloads."""
        self._raster_controller.on_command_effects(result)
        if bool(getattr(result, "success", False)):
            return
        command_name = str(getattr(result, "command_name", ""))
        if any(token in command_name for token in ("Map", "Marker", "Layer", "Raster")):
            self.load_maps()
            loaded_map_id = self._raster_controller.loaded_map_id
            if loaded_map_id:
                self.reload_markers(loaded_map_id)

    def has_pending_raster_strokes(self) -> bool:
        """Delegate to the raster capability controller."""
        return self._raster_controller.has_pending_raster_strokes()

    @Slot(str)
    def on_raster_palette_edit(self, node_id: str) -> None:
        """Delegate to the raster capability controller."""
        self._raster_controller.on_raster_palette_edit(node_id)

    @Slot()
    def on_raster_query_requested(self) -> None:  # noqa: C901
        """Delegate to the raster capability controller."""
        self._raster_controller.on_raster_query_requested()

    @Slot()
    def on_raster_query_cleared(self) -> None:
        """Delegate to the raster capability controller."""
        self._raster_controller.on_raster_query_cleared()

    @Slot(str, object, float, float)
    def on_raster_value_probed(
        self,
        node_id: str,
        value: object,
        x_norm: float,
        y_norm: float,
    ) -> None:
        """Delegate to the raster capability controller."""
        self._raster_controller.on_raster_value_probed(node_id, value, x_norm, y_norm)

    @Slot(str)
    def on_raster_stats_requested(self, node_id: str) -> None:
        """Delegate to the raster capability controller."""
        self._raster_controller.on_raster_stats_requested(node_id)

    @Slot(str)
    def on_raster_gradient_sub_mode_changed(self, sub_mode: str) -> None:
        """Delegate to the raster capability controller."""
        self._raster_controller.on_raster_gradient_sub_mode_changed(sub_mode)

    @Slot(str)
    def on_raster_notes_requested(self, node_id: str) -> None:
        """Delegate to the raster capability controller."""
        self._raster_controller.on_raster_notes_requested(node_id)

    # ------------------------------------------------------------------
    # Temporal rasters
    # ------------------------------------------------------------------

    @Slot(float)
    def on_playhead_changed(self, lore_date: float) -> None:
        """Delegate to the raster capability controller."""
        self._raster_controller.on_playhead_changed(lore_date)

    @Slot(str)
    def on_raster_snapshot_requested(self, node_id: str) -> None:
        """Delegate to the raster capability controller."""
        self._raster_controller.on_raster_snapshot_requested(node_id)

    @Slot(str, float)
    def on_raster_snapshot_selected(self, node_id: str, lore_date: float) -> None:
        """Delegate to the raster capability controller."""
        self._raster_controller.on_raster_snapshot_selected(node_id, lore_date)

    @Slot(str)
    def on_raster_base_edit_requested(self, node_id: str) -> None:
        """Delegate to the raster capability controller."""
        self._raster_controller.on_raster_base_edit_requested(node_id)

    @Slot(str, float)
    def on_raster_snapshot_edit_requested(self, node_id: str, lore_date: float) -> None:
        """Delegate to the raster capability controller."""
        self._raster_controller.on_raster_snapshot_edit_requested(node_id, lore_date)

    @Slot(str, float)
    def on_raster_snapshot_delete_requested(
        self, node_id: str, lore_date: float
    ) -> None:
        """Delegate to the raster capability controller."""
        self._raster_controller.on_raster_snapshot_delete_requested(node_id, lore_date)
