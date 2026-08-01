"""Map Layer Management Mixin.

Provides layer tree CRUD, registration, and selection synchronization
for the MapWidget.
"""

import logging
from typing import TYPE_CHECKING, List, Optional, Tuple, cast

from PySide6.QtCore import Qt, SignalInstance, Slot
from PySide6.QtWidgets import QMessageBox, QWidget

from src.app.constants import (
    MAP_LAYER_BASEMAP_NODE_ID,
    MAP_LAYER_DEFAULT_GROUP_NAME,
    MAP_LAYER_TYPE_BASEMAP,
    MAP_LAYER_TYPE_GROUP,
    MAP_LAYER_TYPE_MARKER,
    MAP_LAYER_TYPE_PATH,
    MAP_LAYER_TYPE_REGION,
)
from src.core.map import MapLayerNode
from src.gui.widgets.map.map_layer_model import MapLayerModel

if TYPE_CHECKING:
    from src.gui.widgets.map.map_graphics_view import MapGraphicsView
    from src.gui.widgets.map.map_layer_panel import MapLayerPanel

logger = logging.getLogger(__name__)


class MapLayerMixin:
    """Mixin providing layer management for MapWidget.

    Requires the host class to have:
        - self.view: MapGraphicsView
        - self.layer_panel: MapLayerPanel
        - self._layer_model: Optional[MapLayerModel]
        - self.layer_tree_changed: Signal
        - self.layer_delete_feature_requested: Signal(str, str)
        - self.layer_rename_requested: Signal(str, str)
        - self.layer_opacity_change_requested: Signal(str, float, float)
    """

    if TYPE_CHECKING:
        view: MapGraphicsView
        layer_panel: MapLayerPanel
        layer_tree_changed: SignalInstance
        layer_delete_feature_requested: SignalInstance
        layer_rename_requested: SignalInstance
        layer_opacity_change_requested: SignalInstance
        create_raster_layer_requested: SignalInstance
        raster_edit_requested: SignalInstance
        raster_edit_stopped: SignalInstance

    def rebuild_layer_model(self, root: Optional[MapLayerNode] = None) -> MapLayerModel:
        """Create (or replace) the layer model and wire it to the view.

        Args:
            root: An existing layer tree root.  If ``None`` a default
                root with a "Default" group is created.

        Returns:
            MapLayerModel: The newly created model.

        """
        if root is None:
            root = MapLayerNode(
                name="Root",
                layer_type=MAP_LAYER_TYPE_GROUP,
                children=[
                    MapLayerNode(
                        name=MAP_LAYER_DEFAULT_GROUP_NAME,
                        layer_type=MAP_LAYER_TYPE_GROUP,
                    ),
                ],
            )
        self._ensure_basemap_node(root)
        model = MapLayerModel(root=root)
        self._layer_model = model
        self.view.set_layer_model(model)
        self.layer_panel.set_model(model)
        # Forward model mutations → widget signal for command-stack persistence
        model.layer_tree_changed.connect(self.layer_tree_changed.emit)
        # Apply the persisted basemap state to the pixmap item immediately
        # (the view's signal handlers only fire on *changes*, not initial sync).
        self._sync_basemap_to_view()
        return model

    @staticmethod
    def _ensure_basemap_node(root: MapLayerNode) -> None:
        """Guarantee a pinned basemap node exists as ``root``'s last child.

        Args:
            root: The layer tree root to augment in-place.
        """
        for child in root.children:
            if child.id == MAP_LAYER_BASEMAP_NODE_ID:
                # Already present — re-assert the layer type in case the
                # tree was persisted under an older schema.
                child.layer_type = MAP_LAYER_TYPE_BASEMAP
                if root.children[-1] is not child:
                    # Move basemap to end via index swap (avoid O(n) remove()).
                    idx = root.children.index(child)
                    root.children[idx], root.children[-1] = (
                        root.children[-1],
                        root.children[idx],
                    )
                return
        basemap = MapLayerNode(
            name="Base Map",
            layer_type=MAP_LAYER_TYPE_BASEMAP,
            id=MAP_LAYER_BASEMAP_NODE_ID,
        )
        root.children.append(basemap)

    def _insert_row_before_basemap(self) -> int:
        """Get the row index to insert layers before the pinned basemap.

        Returns:
            int: Row index for insertion (one before basemap at end).
        """
        model = self._ensure_layer_model()
        return max(0, len(model.root.children) - 1)

    def _sync_basemap_to_view(self) -> None:
        """Apply the basemap node's visibility/opacity to the pixmap item."""
        if self._layer_model is None:
            return
        pixmap_item = getattr(self.view, "pixmap_item", None)
        if pixmap_item is None:
            return
        node = self._layer_model.find_node_by_id(MAP_LAYER_BASEMAP_NODE_ID)
        if node is None:
            return
        try:
            pixmap_item.setVisible(node.visible)
            pixmap_item.setOpacity(node.opacity)
        except RuntimeError:
            # pixmap_item was deleted — ignore
            pass

    def _ensure_layer_model(self) -> MapLayerModel:
        """Return the current layer model, creating one if needed.

        Returns:
            MapLayerModel: The active layer model.

        """
        if self._layer_model is None:
            return self.rebuild_layer_model()
        return self._layer_model

    def _default_group(self) -> MapLayerNode:
        """Return the "Default" group in the layer tree, creating it if needed.

        Returns:
            MapLayerNode: The default group node.

        """
        model = self._ensure_layer_model()
        # Try to find an existing "Default" group
        for child in model.root.children:
            if (
                child.layer_type == MAP_LAYER_TYPE_GROUP
                and child.name == MAP_LAYER_DEFAULT_GROUP_NAME
            ):
                return child
        # Create one
        node = MapLayerNode(
            name=MAP_LAYER_DEFAULT_GROUP_NAME,
            layer_type=MAP_LAYER_TYPE_GROUP,
        )
        root_idx = model.index_from_node(model.root)
        model.add_layer(root_idx, node, row=self._insert_row_before_basemap())
        return node

    @staticmethod
    def _feature_type_to_layer_type(feature_type: str) -> str:
        """Map a feature_type string to a layer_type constant.

        Args:
            feature_type: 'point', 'path', or 'region'.

        Returns:
            str: The corresponding MAP_LAYER_TYPE_* constant.

        """
        if feature_type == "path":
            return MAP_LAYER_TYPE_PATH
        if feature_type == "region":
            return MAP_LAYER_TYPE_REGION
        return MAP_LAYER_TYPE_MARKER

    def _register_layer_node(
        self,
        marker_id: str,
        label: str,
        feature_type: str = "point",
    ) -> None:
        """Register a new feature as a layer node under the Default group.

        If a node with this ID already exists in the tree, it is skipped.

        Args:
            marker_id: Unique identifier (same as graphics item key).
            label: Display name for the layer.
            feature_type: 'point', 'path', or 'region'.

        """
        model = self._ensure_layer_model()
        if model.find_node_by_id(marker_id) is not None:
            return  # Already tracked

        layer_type = self._feature_type_to_layer_type(feature_type)
        node = MapLayerNode(name=label, layer_type=layer_type, id=marker_id)
        default_group = self._default_group()
        parent_idx = model.index_from_node(default_group)
        model.add_layer(parent_idx, node)

    def _unregister_layer_node(self, marker_id: str) -> None:
        """Remove a layer node when the corresponding feature is deleted.

        Prevents "zombie nodes" (MEDIUM-7).

        Args:
            marker_id: ID of the node to remove.

        """
        if self._layer_model is None:
            return
        node = self._layer_model.find_node_by_id(marker_id)
        if node is None:
            return
        idx = self._layer_model.index_from_node(node)
        self._layer_model.remove_layer(idx)

    @Slot(str, str)
    def _on_marker_clicked_select_layer(self, marker_id: str, object_type: str) -> None:
        """Bi-directional selection: marker click → highlight in layer panel.

        Args:
            marker_id: The clicked marker's ID.
            object_type: 'entity' or 'event' (unused here).

        """
        self.layer_panel.select_node(marker_id)

    @Slot(str)
    def _on_layer_panel_selected(self, node_id: str) -> None:
        """Bi-directional selection: layer panel click → select on map.

        Args:
            node_id: The clicked layer node's ID.

        """
        # Select the graphics item on the map
        item = self.view.find_item_by_id(node_id)
        if item is not None:
            self.view.graphics_scene.clearSelection()
            item.setSelected(True)

    @Slot(str)
    def _on_create_group(self, name: str) -> None:
        """Handle request to create a new layer group.

        The group is added under the root of the layer tree.

        Args:
            name: Display name for the new group.

        """
        model = self._ensure_layer_model()
        node = MapLayerNode(name=name, layer_type=MAP_LAYER_TYPE_GROUP)
        root_idx = model.index_from_node(model.root)
        model.add_layer(root_idx, node, row=self._insert_row_before_basemap())
        logger.info(f"Created layer group: {name}")

    @Slot(str)
    def _on_create_layer(self, name: str) -> None:
        """Handle request to create a new leaf layer.

        The layer is added under the selected group, or the Default group
        if no group is selected.

        Args:
            name: Display name for the new layer.

        """
        model = self._ensure_layer_model()
        node = MapLayerNode(name=name, layer_type=MAP_LAYER_TYPE_MARKER)

        # Find a suitable parent — the selected node if it's a group,
        # else the Default group
        parent_node = None
        selected_id = self.layer_panel.selected_node_id
        if selected_id:
            selected_node = model.find_node_by_id(selected_id)
            if selected_node and selected_node.layer_type == MAP_LAYER_TYPE_GROUP:
                parent_node = selected_node

        if parent_node is None:
            parent_node = self._default_group()

        parent_idx = model.index_from_node(parent_node)
        model.add_layer(parent_idx, node)
        logger.info(f"Created layer: {name}")

    @Slot(str)
    def _on_delete_layer(self, node_id: str) -> None:
        """Handle request to delete a layer.

        Removes graphics items, the layer node from the tree, and emits
        ``layer_delete_feature_requested`` for each leaf feature so
        the database marker is also deleted.

        Args:
            node_id: ID of the layer node to delete.

        """
        if self._layer_model is None:
            return
        node = self._layer_model.find_node_by_id(node_id)
        if node is None:
            return

        # Don't delete the root
        if node is self._layer_model.root:
            logger.warning("Cannot delete the root node")
            return

        # Pinned basemap node — cannot be removed
        if node.id == MAP_LAYER_BASEMAP_NODE_ID:
            logger.info("Cannot delete the base-map layer node")
            return

        nodes = self._collect_subtree_nodes(node)
        group_count = sum(
            item.layer_type == MAP_LAYER_TYPE_GROUP for item in nodes
        )
        raster_ids = {
            item.id for item in nodes if item.layer_type == "raster"
        }
        feature_count = sum(
            item.layer_type not in {MAP_LAYER_TYPE_GROUP, "raster"}
            for item in nodes
        )
        snapshot_count = 0
        for map_obj in getattr(self, "maps_data", []) or []:
            metadata = (map_obj.attributes or {}).get("raster_layers", [])
            snapshot_count += sum(
                len(item.get("snapshots", {}))
                for item in metadata
                if item.get("node_id") in raster_ids
            )

        if group_count or raster_ids:
            details = (
                f"Delete '{node.name}'?\n\n"
                f"Groups: {group_count}\n"
                f"Features: {feature_count}\n"
                f"Raster layers: {len(raster_ids)}\n"
                f"Temporal states: {snapshot_count}\n\n"
                "The complete operation can be undone."
            )
            answer = QMessageBox.question(
                cast(QWidget, self),
                "Delete layer",
                details,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        exit_editing_modes = getattr(self, "exit_editing_modes", None)
        if callable(exit_editing_modes):
            exit_editing_modes()

        # The canonical tree and all descendant data are removed together by
        # one worker command.  The UI is refreshed only after command success.
        self.layer_delete_feature_requested.emit(node_id, node.layer_type)

    def _collect_subtree_nodes(self, node: MapLayerNode) -> List[MapLayerNode]:
        """Return ``node`` and all descendants in display order."""
        nodes = [node]
        for child in node.children:
            nodes.extend(self._collect_subtree_nodes(child))
        return nodes

    def _collect_leaf_ids(self, node: MapLayerNode) -> List[Tuple[str, str]]:
        """Recursively collect IDs and types of all leaf (non-group) nodes.

        Args:
            node: The root node to search.

        Returns:
            List of (node_id, layer_type) tuples for all leaf nodes.

        """
        ids: List[Tuple[str, str]] = []
        if node.layer_type != MAP_LAYER_TYPE_GROUP:
            ids.append((node.id, node.layer_type))
        for child in node.children:
            ids.extend(self._collect_leaf_ids(child))
        return ids

    def _remove_children_graphics(self, group_node: MapLayerNode) -> None:
        """Recursively remove graphics items for all children of a group.

        Args:
            group_node: The parent group node.

        """
        for child in group_node.children:
            if child.layer_type == MAP_LAYER_TYPE_GROUP:
                self._remove_children_graphics(child)
            else:
                self.view.remove_marker(child.id)

    @Slot(str, str)
    def _on_layer_renamed(self, node_id: str, new_name: str) -> None:
        """Handle a layer rename from the panel.

        Updates the node name in the model, refreshes the view, and emits
        a signal so the command stack can persist the change.

        Args:
            node_id: ID of the renamed node.
            new_name: The new display name.

        """
        if self._layer_model is None:
            return
        node = self._layer_model.find_node_by_id(node_id)
        if node is None:
            return

        node.name = new_name
        idx = self._layer_model.index_from_node(node)
        self._layer_model.dataChanged.emit(idx, idx, [Qt.ItemDataRole.DisplayRole])
        self.layer_rename_requested.emit(node_id, new_name)

    @Slot(str, float, float)
    def _on_layer_opacity_changed(
        self, node_id: str, opacity: float, old_opacity: float
    ) -> None:
        """Handle opacity change from the panel's slider.

        The model is already updated by the panel; this emits a signal
        so the command stack can persist the change.

        Args:
            node_id: ID of the node whose opacity changed.
            opacity: New opacity (0.0–1.0).
            old_opacity: Previous opacity (for undo).

        """
        self.layer_opacity_change_requested.emit(node_id, opacity, old_opacity)

    @Slot()
    def _on_create_raster_layer(self) -> None:
        """Open the raster layer dialog and emit the creation signal."""
        from src.gui.widgets.map.raster_layer_dialog import RasterLayerDialog

        logger.debug("_on_create_raster_layer: opening dialog")
        map_aspect = 1.0
        view = getattr(self, "view", None)
        if view is not None:
            pixmap_item = getattr(view, "pixmap_item", None)
            if pixmap_item is not None:
                r = pixmap_item.boundingRect()
                if r.width() > 0 and r.height() > 0:
                    map_aspect = r.width() / r.height()
        dialog = RasterLayerDialog(
            parent=getattr(self, "window", lambda: None)(),
            map_aspect=map_aspect,
        )
        if dialog.exec():
            data = dialog.result_data()
            import_path = data.get("import_path", "")
            display_min = data.get("display_min")
            display_max = data.get("display_max")
            unit = data.get("unit", "")
            logger.debug(
                "_on_create_raster_layer: accepted — name=%r size=%dx%d mode=%s "
                "default=%d import_path=%r display=[%s..%s] unit=%r",
                data["name"],
                data["width"],
                data["height"],
                data["mode"],
                data["default_value"],
                import_path,
                display_min,
                display_max,
                unit,
            )
            self.create_raster_layer_requested.emit(
                data["name"],
                data["width"],
                data["height"],
                data["mode"],
                data["default_value"],
                import_path,
                display_min,
                display_max,
                unit,
            )
        else:
            logger.debug("_on_create_raster_layer: dialog cancelled")

    @Slot(str)
    def _on_raster_edit_requested(self, node_id: str) -> None:
        """Start raster editing mode in the graphics view."""
        from src.gui.widgets.map.raster_edit_tool import RasterEditMode

        view = getattr(self, "view", None)
        panel = getattr(self, "layer_panel", None)
        if view is None or panel is None:
            logger.warning(
                "_on_raster_edit_requested: view=%s panel=%s — cannot start editing",
                view,
                panel,
            )
            return

        # Apply current tool settings
        tool = view._raster_edit_tool
        mode_name = panel.raster_tool_mode
        mode_map = {
            "brush": RasterEditMode.BRUSH,
            "fill": RasterEditMode.FILL,
            "gradient": RasterEditMode.GRADIENT,
            "sample": RasterEditMode.SAMPLE,
        }
        tool.mode = mode_map.get(mode_name, RasterEditMode.BRUSH)
        tool.brush_size = panel.raster_brush_size
        tool.paint_value = panel.raster_paint_value
        tool.falloff = panel.raster_falloff
        tool.falloff_curve = panel.raster_falloff_curve
        tool.brush_opacity = panel.raster_brush_opacity
        tool.paint_color = panel.raster_paint_color
        tool.fill_tolerance = panel.raster_fill_tolerance
        tool.set_gradient_targets(
            panel.raster_gradient_from,
            panel.raster_gradient_to,
        )
        tool.set_gradient_sub_mode(panel.raster_gradient_sub_mode)

        logger.debug(
            "_on_raster_edit_requested: node_id=%s mode=%s brush_size=%d "
            "paint_value=%d falloff=%.2f registered_items=%s",
            node_id,
            tool.mode.name,
            tool.brush_size,
            tool.paint_value,
            tool.falloff,
            list(view._raster_items.keys()),
        )

        view.start_raster_editing(node_id)
        # Transfer keyboard focus to the map view so Space-to-pan works
        # immediately without requiring a mouse click on the canvas first.
        view.setFocus(Qt.FocusReason.OtherFocusReason)
        self.raster_edit_requested.emit(node_id)

    @Slot()
    def _on_raster_edit_stopped(self) -> None:
        """Stop raster editing mode in the graphics view."""
        logger.debug("_on_raster_edit_stopped: stopping raster edit")
        view = getattr(self, "view", None)
        if view is not None:
            view.stop_raster_editing()
        else:
            logger.warning("_on_raster_edit_stopped: no view available")
        self.raster_edit_stopped.emit()

    @Slot()
    def _on_raster_settings_changed(self) -> None:
        """Push updated tool settings from the panel to the active tool.

        The tool *mode* is always synced so that passive Sample probing
        works without requiring active edit mode.  Other brush parameters
        are only pushed while editing is active.
        """
        from src.gui.widgets.map.raster_edit_tool import RasterEditMode

        view = getattr(self, "view", None)
        panel = getattr(self, "layer_panel", None)
        if view is None or panel is None:
            return

        tool = view._raster_edit_tool
        mode_map = {
            "brush": RasterEditMode.BRUSH,
            "fill": RasterEditMode.FILL,
            "gradient": RasterEditMode.GRADIENT,
            "sample": RasterEditMode.SAMPLE,
        }
        # Always sync mode so passive Sample works without entering Edit.
        tool.mode = mode_map.get(panel.raster_tool_mode, RasterEditMode.BRUSH)

        if not tool.is_active:
            return

        tool.brush_size = panel.raster_brush_size
        tool.paint_value = panel.raster_paint_value
        tool.falloff = panel.raster_falloff
        tool.falloff_curve = panel.raster_falloff_curve
        tool.brush_opacity = panel.raster_brush_opacity
        tool.paint_color = panel.raster_paint_color
        tool.fill_tolerance = panel.raster_fill_tolerance
        tool.set_gradient_targets(
            panel.raster_gradient_from,
            panel.raster_gradient_to,
        )
        tool.set_gradient_sub_mode(panel.raster_gradient_sub_mode)

        logger.debug(
            "_on_raster_settings_changed: mode=%s brush_size=%d "
            "paint_value=%d falloff=%.2f curve=%s opacity=%.2f",
            tool.mode.name,
            tool.brush_size,
            tool.paint_value,
            tool.falloff,
            tool.falloff_curve,
            tool.brush_opacity,
        )

    def get_layer_model(self) -> Optional[MapLayerModel]:
        """Return the current layer model (if any).

        Returns:
            Optional[MapLayerModel]: The active layer model.

        """
        return self._layer_model
