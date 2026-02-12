"""MapHandler - Handles map and marker operations for MainWindow.

This module contains all map and marker-related functionality extracted from
MainWindow to reduce its size and improve maintainability.
"""

import shutil
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Q_ARG, QMetaObject, QObject, Qt, Slot
from PySide6.QtWidgets import QFileDialog, QInputDialog, QMessageBox

from src.app.constants import IMAGE_FILE_FILTER
from src.commands.entity_commands import CreateEntityCommand
from src.commands.event_commands import CreateEventCommand
from src.commands.map_commands import (
    CreateMapCommand,
    CreateMarkerCommand,
    DeleteMapCommand,
    DeleteMarkerCommand,
    RenameLayerCommand,
    SaveLayerTreeCommand,
    SetLayerOpacityCommand,
    UpdateMapCommand,
    UpdateMarkerColorCommand,
    UpdateMarkerCommand,
    UpdateMarkerIconCommand,
)
from src.core.logging_config import get_logger

if TYPE_CHECKING:
    from src.app.main_window import MainWindow

logger = get_logger(__name__)


class MapHandler(QObject):
    """Manages map and marker operations for the MainWindow.

    This class encapsulates all functionality related to:
    - Loading and displaying maps
    - Creating, deleting, and modifying maps
    - Creating, deleting, and modifying markers
    - Handling marker interactions (clicks, drag-drop, updates)
    """

    def __init__(self, main_window: "MainWindow") -> None:
        """Initialize the MapHandler.

        Args:
            main_window: Reference to the MainWindow instance.

        """
        super().__init__()
        self.window = main_window
        # Mapping from object_id to actual marker.id for position updates
        self._marker_object_to_id: dict[str, str] = {}

    def load_maps(self) -> None:
        """Requests loading of all maps from the worker thread."""
        QMetaObject.invokeMethod(
            self.window.worker, "load_maps", Qt.ConnectionType.QueuedConnection
        )

    @Slot(str)
    def on_map_selected(self, map_id: str) -> None:
        """Handler for when a map is selected in the widget. Loads the map image and
        requests markers.

        Args:
            map_id: ID of the selected map.

        """
        # Find map object
        maps = self.window.map_widget._maps_data
        selected_map = next((m for m in maps if m.id == map_id), None)
        if selected_map and selected_map.image_path:
            # Resolve relative path against project directory
            image_path = selected_map.image_path
            if not Path(image_path).is_absolute():
                # Use main thread's db_path for path calculations
                project_dir = Path(self.window.db_path).parent
                image_path = str(project_dir / image_path)

            self.window.map_widget.load_map(image_path)

            # Restore scale
            width_meters = selected_map.attributes.get("width_meters")
            if width_meters:
                self.window.map_widget.view.set_map_width_meters(float(width_meters))
            else:
                # Reset to default if no specific scale set (1000 km)
                self.window.map_widget.view.set_map_width_meters(1_000_000.0)

            # Request markers
            QMetaObject.invokeMethod(
                self.window.worker,
                "load_markers",
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(str, map_id),
            )

            # Request trajectories
            QMetaObject.invokeMethod(
                self.window.worker,
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
            self.window.worker,
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
        map_id = self.window.map_widget.get_selected_map_id()
        if map_id:
            logger.info(f"Reloading markers for current map: {map_id}")
            self.reload_markers(map_id)
        else:
            logger.debug("No map selected, skipping marker reload")

    def create_map(self) -> None:
        """Creates a new map via dialogs."""
        # 1. Select Image
        file_path, _ = QFileDialog.getOpenFileName(
            self.window, "Select Map Image", "", IMAGE_FILE_FILTER
        )
        if not file_path:
            return

        # 2. Enter Name
        name, ok = QInputDialog.getText(self.window, "New Map", "Map Name:")
        if not ok or not name.strip():
            return

        # 3. Copy image to project assets folder
        source_path = Path(file_path)
        # Use main thread's db_path for path calculations
        project_dir = Path(self.window.db_path).parent
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
            QMessageBox.warning(self.window, "Error", f"Failed to copy image: {e}")
            return

        # Store relative path
        relative_path = str(dest_path.relative_to(project_dir))

        cmd = CreateMapCommand({"name": name.strip(), "image_path": relative_path})
        self.window.command_requested.emit(cmd)

    def delete_map(self) -> None:
        """Deletes the currently selected map."""
        map_id = self.window.map_widget.map_selector.currentData()
        if not map_id:
            return

        confirm = QMessageBox.question(
            self.window,
            "Delete Map",
            "Are you sure you want to delete this map and all its markers?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            cmd = DeleteMapCommand(map_id)
            self.window.command_requested.emit(cmd)

    # ------------------------------------------------------------------
    # Sentinel values for "create new" options in the selection dialog
    # ------------------------------------------------------------------
    _NEW_ENTITY_SENTINEL = "<New Entity...>"
    _NEW_EVENT_SENTINEL = "<New Event...>"

    def _select_or_create_object(
        self, dialog_title: str, dialog_label: str
    ) -> tuple[str, str, str] | None:
        """Shows a selection dialog with existing items + new-item options.

        Returns:
            Tuple of (object_id, object_type, name) on success, or None
            if the user cancels.

        """
        # Build list of items to choose from
        items: list[str] = [
            self._NEW_ENTITY_SENTINEL,
            self._NEW_EVENT_SENTINEL,
        ]
        for e in self.window._cached_entities:
            items.append(f"{e.name} (Entity)")
        for e in self.window._cached_events:
            items.append(f"{e.name} (Event)")

        # Sort existing items, but keep sentinels at top
        sentinels = items[:2]
        existing = sorted(items[2:])
        items = sentinels + existing

        item_text, ok = QInputDialog.getItem(
            self.window, dialog_title, dialog_label, items, 0, False
        )
        if not ok or not item_text:
            return None

        # --- Handle "create new" sentinels ---
        if item_text == self._NEW_ENTITY_SENTINEL:
            return self._create_new_entity_inline()
        if item_text == self._NEW_EVENT_SENTINEL:
            return self._create_new_event_inline()

        # --- Handle existing item selection ---
        if item_text.endswith(" (Entity)"):
            name = item_text[:-9]
            obj = next(
                (e for e in self.window._cached_entities if e.name == name), None
            )
            if obj:
                return obj.id, "entity", obj.name
        elif item_text.endswith(" (Event)"):
            name = item_text[:-8]
            obj = next((e for e in self.window._cached_events if e.name == name), None)
            if obj:
                return obj.id, "event", obj.name

        return None

    def _create_new_entity_inline(self) -> tuple[str, str, str] | None:
        """Prompts for a name and emits a CreateEntityCommand.

        Returns:
            Tuple of (new_id, 'entity', name) or None if cancelled.

        """
        name, ok = QInputDialog.getText(self.window, "New Entity", "Entity Name:")
        if not ok or not name.strip():
            return None

        name = name.strip()
        new_id = str(uuid.uuid4())
        cmd = CreateEntityCommand({"id": new_id, "name": name, "type": "Location"})
        self.window.command_requested.emit(cmd)
        logger.info(f"Created new entity '{name}' ({new_id}) from map")
        return new_id, "entity", name

    def _create_new_event_inline(self) -> tuple[str, str, str] | None:
        """Prompts for a name and emits a CreateEventCommand.

        Returns:
            Tuple of (new_id, 'event', name) or None if cancelled.

        """
        name, ok = QInputDialog.getText(self.window, "New Event", "Event Name:")
        if not ok or not name.strip():
            return None

        name = name.strip()
        new_id = str(uuid.uuid4())
        cmd = CreateEventCommand({"id": new_id, "name": name, "lore_date": 0.0})
        self.window.command_requested.emit(cmd)
        logger.info(f"Created new event '{name}' ({new_id}) from map")
        return new_id, "event", name

    def create_marker(self, x: float, y: float) -> None:
        """Creates a new marker at the given normalized coordinates.

        Prompts the user to select an existing Entity/Event or create a new one.

        Args:
            x: Normalized X coordinate [0.0, 1.0].
            y: Normalized Y coordinate [0.0, 1.0].

        """
        map_id = self.window.map_widget.map_selector.currentData()
        if not map_id:
            QMessageBox.warning(
                self.window, "No Map", "Please create or select a map first."
            )
            return

        result = self._select_or_create_object("Add Marker", "Select Object:")
        if not result:
            return

        obj_id, obj_type, name = result
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
        self.window.command_requested.emit(cmd)

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
        map_id = self.window.map_widget.get_selected_map_id()
        if not map_id:
            QMessageBox.warning(self.window, "No Map", "Please select a map first.")
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
        self.window.command_requested.emit(cmd)
        logger.info(f"Creating marker for {item_type} '{item_name}' via drag-drop")

    @Slot(str, list)
    def on_feature_drawn(self, feature_type: str, geometry: list) -> None:
        """Handle feature creation from drawing mode.

        Prompts the user to select an existing Entity/Event or create a new
        one, then creates the feature with the drawn geometry.

        Args:
            feature_type: 'path' or 'region'.
            geometry: List of normalized coordinate dicts.

        """
        map_id = self.window.map_widget.get_selected_map_id()
        if not map_id:
            QMessageBox.warning(
                self.window, "No Map", "Please create or select a map first."
            )
            return

        result = self._select_or_create_object(
            f"Link {feature_type.title()}",
            f"Select object for this {feature_type}:",
        )
        if not result:
            return

        obj_id, obj_type, name = result

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
        self.window.command_requested.emit(cmd)
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
        self.window.command_requested.emit(cmd)
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
        self.window.command_requested.emit(cmd)
        logger.info(f"Geometry updated for {marker_id} ({n} vertices)")

    def delete_marker(self, marker_id: str) -> None:
        """Deletes a marker.

        Args:
            marker_id: The object_id from the UI (not the actual marker.id).

        """
        # Translate object_id to actual marker ID
        actual_marker_id = self._marker_object_to_id.get(marker_id)
        if not actual_marker_id:
            logger.warning(f"No marker mapping found for object_id: {marker_id}")
            return

        confirm = QMessageBox.question(
            self.window,
            "Delete Marker",
            "Remove this marker?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            # Remove marker from UI immediately for instant feedback
            self.window.map_widget.remove_marker(marker_id)
            # Also remove from mapping
            del self._marker_object_to_id[marker_id]
            # Then execute the database command
            cmd = DeleteMarkerCommand(actual_marker_id)
            self.window.command_requested.emit(cmd)

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
        # Delegate to NavigationCoordinator for unified selection handling
        self.window.navigation_coordinator.set_global_selection(object_type, marker_id)

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
        self.window.command_requested.emit(cmd)

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
        self.window.command_requested.emit(cmd)

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
        self.window.command_requested.emit(cmd)

    @Slot(list)
    def on_maps_ready(self, maps: list) -> None:
        """Handle maps ready signal from DataHandler.

        Args:
            maps: List of Map objects.

        """
        self.window.map_widget.set_maps(maps)

        # Auto-select first map if none selected
        if maps:
            current_id = self.window.map_widget.map_selector.currentData()
            if not current_id:
                self.window.map_widget.select_map(maps[0].id)

    @Slot(str, list)
    def on_markers_ready(self, map_id: str, processed_markers: list) -> None:
        """Handle markers ready signal from DataHandler.

        Restores the persisted layer tree (if any) and auto-registers
        new markers into the hierarchy.

        Args:
            map_id: The map ID these markers belong to.
            processed_markers: List of dicts with marker data.

        """
        # Verify we are still looking at this map
        current_map_id = self.window.map_widget.map_selector.currentData()
        if current_map_id != map_id:
            return

        self.window.map_widget.clear_markers()
        self._marker_object_to_id.clear()  # Reset mapping

        # Restore persisted layer tree from the selected map object
        maps = self.window.map_widget._maps_data
        selected_map = next((m for m in maps if m.id == map_id), None)
        if selected_map and selected_map.layers is not None:
            self.window.map_widget._build_layer_model(selected_map.layers)
        else:
            self.window.map_widget._build_layer_model()

        for marker_data in processed_markers:
            # Add marker to map (also auto-registers a layer node)
            self.window.map_widget.add_marker(
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
            )

            # Store mapping for later updates (object_id -> marker.id)
            self._marker_object_to_id[marker_data["object_id"]] = marker_data["id"]

    @Slot(list)
    def on_trajectories_ready(self, trajectories: list) -> None:
        """Handle trajectories ready signal from DataHandler.

        Args:
            trajectories: List of (marker_id, trajectory_id, keyframes) tuples.

        """
        self.window.map_widget.set_trajectories(trajectories)

    @Slot(float)
    def on_map_scale_changed(self, width_meters: float) -> None:
        """Handle map scale change from MapWidget.

        Args:
            width_meters: The new width of the map in meters.

        """
        current_map_id = self.window.map_widget.map_selector.currentData()
        if not current_map_id:
            return

        cmd = UpdateMapCommand(
            current_map_id, {"attributes": {"width_meters": width_meters}}
        )
        self.window.command_requested.emit(cmd)

    # ------------------------------------------------------------------
    # Layer operations (routed through the command stack)
    # ------------------------------------------------------------------

    @Slot()
    def on_layer_tree_changed(self) -> None:
        """Persist the current layer tree to the database.

        Called whenever the in-memory layer model is mutated.
        """
        map_id = self.window.map_widget.get_selected_map_id()
        model = self.window.map_widget.get_layer_model()
        if not map_id or not model:
            return
        tree_dict = model.root.to_dict()
        cmd = SaveLayerTreeCommand(map_id, tree_dict)
        self.window.command_requested.emit(cmd)

    @Slot(str, float)
    def on_layer_opacity_changed(self, node_id: str, opacity: float) -> None:
        """Handle layer opacity change via the command stack.

        Args:
            node_id: ID of the layer node.
            opacity: New opacity (0.0–1.0).

        """
        map_id = self.window.map_widget.get_selected_map_id()
        if not map_id:
            return
        cmd = SetLayerOpacityCommand(map_id, node_id, opacity)
        self.window.command_requested.emit(cmd)

    @Slot(str, str)
    def on_layer_renamed(self, node_id: str, new_name: str) -> None:
        """Handle layer rename via the command stack.

        Passes the current in-memory tree snapshot to avoid stale-DB
        reads when the rename command executes on the worker thread.

        Args:
            node_id: ID of the layer node.
            new_name: New display name.

        """
        map_id = self.window.map_widget.get_selected_map_id()
        if not map_id:
            return
        # Serialize the current in-memory tree (already renamed by the UI)
        model = self.window.map_widget.get_layer_model()
        tree_dict = model.root.to_dict() if model else None
        cmd = RenameLayerCommand(map_id, node_id, new_name, tree_dict)
        self.window.command_requested.emit(cmd)
