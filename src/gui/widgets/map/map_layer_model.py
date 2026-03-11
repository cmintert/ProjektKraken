"""Hierarchical Layer Model for the Map Widget.

Implements a ``QAbstractItemModel`` that manages a tree of
:class:`~src.core.map.MapLayerNode` objects. The model supports:

* **Visibility inheritance** — hiding a parent hides all descendants.
* **Mutually-exclusive groups** — only one child may be visible at a time.
* **Drag-and-drop reordering** — controlling render (Z) order.
* **Opacity propagation** — group opacity multiplies with child opacity.
* **Scale-dependent visibility** — layers hide based on zoom level.
* **Visibility presets** — save / load named "Map Themes".
"""

import logging
from typing import Any, Dict, List, Optional, Sequence

from PySide6.QtCore import (
    QAbstractItemModel,
    QMimeData,
    QModelIndex,
    Qt,
    Signal,
    Slot,
)

from src.app.constants import (
    MAP_LAYER_DEFAULT_OPACITY,
    MAP_LAYER_TYPE_GROUP,
    MAP_LAYER_TYPE_MARKER,
    MAP_LAYER_TYPE_PATH,
    MAP_LAYER_TYPE_RASTER,
    MAP_LAYER_TYPE_REGION,
    MAP_LAYER_TYPE_SNAPSHOT,
    MAP_LAYER_Z_BASE,
    MAP_LAYER_Z_SPACING,
)
from src.core.map import MapLayerNode
from src.core.theme_manager import ThemeManager
from src.gui.utils.icon_loader import load_icon

logger = logging.getLogger(__name__)

# Internal MIME type for drag-and-drop reordering
_LAYER_MIME_TYPE = "application/x-kraken-layer-node-id"

# Icons are now handled via DecorationRole with themes (LOW-11)


class MapLayerModel(QAbstractItemModel):
    """Tree model that manages the hierarchical layer structure.

    Signals:
        layer_visibility_changed: Emitted when a node's effective visibility
            changes.  Payload is ``(node_id: str, visible: bool)``.
        layer_opacity_changed: Emitted when a node's effective opacity
            changes.  Payload is ``(node_id: str, opacity: float)``.
        layer_order_changed: Emitted after rows are moved/reordered.
        layer_tree_changed: Emitted whenever the tree is mutated (add,
            remove, reorder, visibility, opacity, rename).  Used as a
            single hook for auto-persistence.

    """

    layer_visibility_changed = Signal(str, bool)
    layer_opacity_changed = Signal(str, float)
    layer_order_changed = Signal()
    layer_tree_changed = Signal()

    # Columns
    COL_NAME = 0
    COLUMN_COUNT = 1

    # Custom roles for layer-specific data
    LayerTypeRole = Qt.ItemDataRole.UserRole + 1
    OpacityRole = Qt.ItemDataRole.UserRole + 2
    NodeIdRole = Qt.ItemDataRole.UserRole + 3

    def __init__(
        self,
        root: Optional[MapLayerNode] = None,
        parent: Any = None,
    ) -> None:
        """Initialise the model with an optional root layer node.

        Args:
            root: Root of the layer tree.  If ``None`` a default empty
                root group is created.
            parent: Qt parent object.

        """
        super().__init__(parent)
        self._root: MapLayerNode = root or MapLayerNode(
            name="Root", layer_type=MAP_LAYER_TYPE_GROUP
        )
        self._zoom_cache: Dict[str, bool] = {}
        self._last_zoom: Optional[float] = None
        self._last_time: Optional[float] = None
        self._icon_cache: Dict[str, Any] = {}
        ThemeManager().theme_changed.connect(self._on_theme_changed)

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    @property
    def root(self) -> MapLayerNode:
        """The invisible root node."""
        return self._root

    def node_from_index(self, index: QModelIndex) -> MapLayerNode:
        """Return the :class:`MapLayerNode` for a given model index.

        Args:
            index: A valid model index, or an invalid index for the root.

        Returns:
            MapLayerNode: The corresponding node.

        """
        if not index.isValid():
            return self._root
        return index.internalPointer()  # type: ignore[return-value]

    def index_from_node(self, node: MapLayerNode) -> QModelIndex:
        """Build a :class:`QModelIndex` for the given node.

        Args:
            node: A node that belongs to this model's tree.

        Returns:
            QModelIndex: A valid index, or an invalid index if *node* is
                the root.

        """
        if node is self._root:
            return QModelIndex()
        parent_node = self._find_parent(node)
        if parent_node is None:
            return QModelIndex()
        row = parent_node.children.index(node)
        return self.createIndex(row, 0, node)

    def find_node_by_id(self, node_id: str) -> Optional[MapLayerNode]:
        """Walk the tree and return the first node whose ``id`` matches.

        Args:
            node_id: The UUID string to search for.

        Returns:
            Optional[MapLayerNode]: The matching node, or ``None``.

        """
        return self._find_by_id(self._root, node_id)

    # ------------------------------------------------------------------
    # QAbstractItemModel interface
    # ------------------------------------------------------------------

    def index(
        self,
        row: int,
        column: int,
        parent: QModelIndex = QModelIndex(),
    ) -> QModelIndex:
        """Return a model index for the item at (*row*, *column*) under *parent*.

        Args:
            row: Row number.
            column: Column number.
            parent: Parent index.

        Returns:
            QModelIndex: A valid index or an invalid one if out of range.

        """
        if not self.hasIndex(row, column, parent):
            return QModelIndex()
        parent_node = self.node_from_index(parent)
        if row < len(parent_node.children):
            child = parent_node.children[row]
            return self.createIndex(row, column, child)
        return QModelIndex()

    def parent(self, index: QModelIndex) -> QModelIndex:  # type: ignore[override]
        """Return the parent index of *index*.

        Args:
            index: A model index.

        Returns:
            QModelIndex: Parent index, or invalid index for top-level items.

        """
        if not index.isValid():
            return QModelIndex()
        child_node: MapLayerNode = index.internalPointer()  # type: ignore[assignment]
        parent_node = self._find_parent(child_node)
        if parent_node is None or parent_node is self._root:
            return QModelIndex()
        grandparent = self._find_parent(parent_node)
        if grandparent is None:
            return QModelIndex()
        row = grandparent.children.index(parent_node)
        return self.createIndex(row, 0, parent_node)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """Return the number of children under *parent*.

        Args:
            parent: Parent index.

        Returns:
            int: Child count.

        """
        node = self.node_from_index(parent)
        return len(node.children)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """Return the column count (always 1).

        Args:
            parent: Parent index (unused).

        Returns:
            int: Column count.

        """
        return self.COLUMN_COUNT

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        """Return data for the requested role.

        Args:
            index: Model index.
            role: Qt item data role.

        Returns:
            Any: Role-specific data.

        """
        if not index.isValid():
            return None
        node = self.node_from_index(index)
        if node.layer_type == MAP_LAYER_TYPE_SNAPSHOT:
            if role == Qt.ItemDataRole.DisplayRole:
                return node.name
            if role == self.LayerTypeRole:
                return node.layer_type
            if role == self.NodeIdRole:
                return node.id
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            return node.name
        if role == Qt.ItemDataRole.DecorationRole:
            return self._get_icon(node.layer_type)
        if role == Qt.ItemDataRole.CheckStateRole:
            return Qt.CheckState.Checked if node.visible else Qt.CheckState.Unchecked
        if role == self.LayerTypeRole:
            return node.layer_type
        if role == self.OpacityRole:
            return node.opacity
        if role == self.NodeIdRole:
            return node.id
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        """Return item flags (checkable, drag/drop enabled).

        Args:
            index: Model index.

        Returns:
            Qt.ItemFlag: Combined flags.

        """
        if not index.isValid():
            return Qt.ItemFlag.ItemIsDropEnabled
        node = self.node_from_index(index)
        if node.layer_type == MAP_LAYER_TYPE_SNAPSHOT:
            return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        base = (
            Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsSelectable
            | Qt.ItemFlag.ItemIsUserCheckable
            | Qt.ItemFlag.ItemIsDragEnabled
        )
        node = self.node_from_index(index)
        if node.layer_type == MAP_LAYER_TYPE_GROUP:
            base |= Qt.ItemFlag.ItemIsDropEnabled
        return base

    def setData(
        self,
        index: QModelIndex,
        value: Any,
        role: int = Qt.ItemDataRole.EditRole,
    ) -> bool:
        """Set data for the requested role.

        Args:
            index: Model index.
            value: New value.
            role: Qt item data role.

        Returns:
            bool: ``True`` if the data was set successfully.

        """
        if not index.isValid():
            return False
        node = self.node_from_index(index)
        if role == Qt.ItemDataRole.CheckStateRole:
            new_visible = value == Qt.CheckState.Checked.value
            self.set_node_visible(node, new_visible)
            return True
        if role == Qt.ItemDataRole.EditRole:
            node.name = str(value)
            self.dataChanged.emit(index, index, [role])
            return True
        return False

    # ------------------------------------------------------------------
    # Drag-and-drop support
    # ------------------------------------------------------------------

    def supportedDropActions(self) -> Qt.DropAction:
        """Declare supported drop actions.

        Returns:
            Qt.DropAction: Move action.

        """
        return Qt.DropAction.MoveAction

    def mimeTypes(self) -> List[str]:
        """Return supported MIME types.

        Returns:
            List[str]: List with our custom MIME type.

        """
        return [_LAYER_MIME_TYPE]

    def mimeData(self, indexes: Sequence[QModelIndex]) -> QMimeData:
        """Encode dragged indexes into MIME data.

        Args:
            indexes: Selected model indexes.

        Returns:
            QMimeData: Encoded data.

        """
        mime = QMimeData()
        ids = []
        for idx in indexes:
            if idx.isValid():
                node = self.node_from_index(idx)
                ids.append(node.id)
        mime.setData(_LAYER_MIME_TYPE, "\n".join(ids).encode("utf-8"))
        return mime

    def dropMimeData(
        self,
        data: QMimeData,
        action: Qt.DropAction,
        row: int,
        column: int,
        parent: QModelIndex,
    ) -> bool:
        """Handle a drop operation (reorder layers).

        Args:
            data: MIME payload.
            action: Drop action.
            row: Target row (-1 means append).
            column: Target column.
            parent: Target parent index.

        Returns:
            bool: ``True`` if the drop was accepted.

        """
        if action == Qt.DropAction.IgnoreAction:
            return True
        if not data.hasFormat(_LAYER_MIME_TYPE):
            return False

        raw = bytes(data.data(_LAYER_MIME_TYPE)).decode("utf-8")
        node_ids = [nid for nid in raw.split("\n") if nid]

        target_parent = self.node_from_index(parent)

        for node_id in node_ids:
            node = self.find_node_by_id(node_id)
            if node is None:
                continue
            # Prevent dropping a node into its own subtree
            if self._is_descendant(node, target_parent):
                continue

            old_parent = self._find_parent(node)
            if old_parent is None:
                continue

            old_row = old_parent.children.index(node)
            old_parent_index = self.index_from_node(old_parent)

            self.beginRemoveRows(old_parent_index, old_row, old_row)
            old_parent.children.pop(old_row)
            self.endRemoveRows()

            # Compute insertion row
            insert_row = row if row >= 0 else len(target_parent.children)
            # Adjust insert_row if same parent and row shifted
            if target_parent is old_parent and insert_row > old_row:
                insert_row = max(0, insert_row - 1)

            target_parent_index = self.index_from_node(target_parent)
            insert_row = min(insert_row, len(target_parent.children))

            self.beginInsertRows(target_parent_index, insert_row, insert_row)
            target_parent.children.insert(insert_row, node)
            self.endInsertRows()

        self.layer_order_changed.emit()
        self.layer_tree_changed.emit()
        return True

    # ------------------------------------------------------------------
    # Layer manipulation API
    # ------------------------------------------------------------------

    def set_node_visible(self, node: MapLayerNode, visible: bool) -> None:
        """Set a node's visibility, honouring mutually-exclusive groups.

        When the parent is mutually exclusive and *visible* is ``True``,
        all siblings are turned off first.

        Args:
            node: Target node.
            visible: New visibility state.

        """
        parent = self._find_parent(node)

        # Mutually-exclusive logic: turning *on* disables siblings
        if visible and parent is not None and parent.mutually_exclusive:
            for sibling in parent.children:
                if sibling is not node and sibling.visible:
                    sibling.visible = False
                    sib_idx = self.index_from_node(sibling)
                    self.dataChanged.emit(
                        sib_idx,
                        sib_idx,
                        [Qt.ItemDataRole.CheckStateRole],
                    )
                    self._emit_subtree_visibility(sibling)

        node.visible = visible
        self.invalidate_cache()
        idx = self.index_from_node(node)
        self.dataChanged.emit(idx, idx, [Qt.ItemDataRole.CheckStateRole])
        self._emit_subtree_visibility(node)
        self.layer_tree_changed.emit()

    def set_node_opacity(
        self, node: MapLayerNode, opacity: float, preview: bool = False
    ) -> None:
        """Set a node's local opacity and propagate changes.

        Args:
            node: Target node.
            opacity: New opacity value (0.0–1.0).
            preview: If True, skips emitting ``layer_tree_changed`` (auto-save).
                Use this for live slider updates to avoid flooding the DB.

        """
        node.opacity = max(0.0, min(1.0, opacity))
        self.invalidate_cache()
        self._emit_subtree_opacity(node)
        if not preview:
            self.layer_tree_changed.emit()

    def add_layer(
        self,
        parent_index: QModelIndex,
        node: MapLayerNode,
        row: int = -1,
    ) -> QModelIndex:
        """Insert a new layer node under the given parent.

        Args:
            parent_index: Parent model index (invalid = root).
            node: The node to insert.
            row: Insertion position (-1 to append).

        Returns:
            QModelIndex: Index of the newly inserted node.

        """
        parent_node = self.node_from_index(parent_index)
        insert_row = row if row >= 0 else len(parent_node.children)
        self.beginInsertRows(parent_index, insert_row, insert_row)
        parent_node.children.insert(insert_row, node)
        self.endInsertRows()
        self.invalidate_cache()
        self.layer_order_changed.emit()
        self.layer_tree_changed.emit()
        return self.index(insert_row, 0, parent_index)

    def remove_layer(self, index: QModelIndex) -> bool:
        """Remove the layer at *index*.

        Args:
            index: Model index to remove.

        Returns:
            bool: ``True`` if removed successfully.

        """
        if not index.isValid():
            return False
        node = self.node_from_index(index)
        parent = self._find_parent(node)
        if parent is None:
            return False
        row = parent.children.index(node)
        parent_index = self.index_from_node(parent)
        self.beginRemoveRows(parent_index, row, row)
        parent.children.pop(row)
        self.endRemoveRows()
        self.invalidate_cache()
        self.layer_order_changed.emit()
        self.layer_tree_changed.emit()
        return True

    def move_layer(
        self,
        source_index: QModelIndex,
        target_parent_index: QModelIndex,
        target_row: int,
    ) -> bool:
        """Move a layer from one position to another.

        Args:
            source_index: Current model index of the layer.
            target_parent_index: New parent index.
            target_row: Row under the new parent.

        Returns:
            bool: ``True`` on success.

        """
        if not source_index.isValid():
            return False
        node = self.node_from_index(source_index)
        old_parent = self._find_parent(node)
        if old_parent is None:
            return False
        old_row = old_parent.children.index(node)
        old_parent_index = self.index_from_node(old_parent)

        self.beginRemoveRows(old_parent_index, old_row, old_row)
        old_parent.children.pop(old_row)
        self.endRemoveRows()

        new_parent = self.node_from_index(target_parent_index)
        insert_row = min(target_row, len(new_parent.children))
        self.beginInsertRows(target_parent_index, insert_row, insert_row)
        new_parent.children.insert(insert_row, node)
        self.endInsertRows()

        self.invalidate_cache()
        self.layer_order_changed.emit()
        self.layer_tree_changed.emit()
        return True

    def set_virtual_snapshot_children(
        self,
        parent_node_id: str,
        virtual_nodes: List[MapLayerNode],
    ) -> None:
        """Replace virtual snapshot children for a raster node.

        Does NOT emit ``layer_tree_changed`` — these are ephemeral
        display-only nodes that must not be persisted.

        Args:
            parent_node_id: ID of the raster node to update.
            virtual_nodes: Replacement list (pass ``[]`` to clear).
        """
        parent = self.find_node_by_id(parent_node_id)
        if parent is None:
            return
        parent_index = self.index_from_node(parent)

        old_virtual_rows = [
            i for i, c in enumerate(parent.children) if getattr(c, "virtual", False)
        ]
        if old_virtual_rows:
            first = old_virtual_rows[0]
            last = old_virtual_rows[-1]
            self.beginRemoveRows(parent_index, first, last)
            parent.children = [
                c for c in parent.children if not getattr(c, "virtual", False)
            ]
            self.endRemoveRows()

        if virtual_nodes:
            first_row = len(parent.children)
            last_row = first_row + len(virtual_nodes) - 1
            self.beginInsertRows(parent_index, first_row, last_row)
            parent.children.extend(virtual_nodes)
            self.endInsertRows()

    # ------------------------------------------------------------------
    # Z-order computation
    # ------------------------------------------------------------------

    def compute_z_order(self) -> Dict[str, float]:
        """Walk the tree depth-first and assign ascending Z-values.

        Returns:
            Dict[str, float]: Mapping of node id → Z-value.

        """
        result: Dict[str, float] = {}
        self._assign_z(self._root, result)
        return result

    # ------------------------------------------------------------------
    # Visibility presets ("Map Themes")
    # ------------------------------------------------------------------

    def save_preset(self) -> Dict[str, Any]:
        """Capture the current visibility/opacity state of all nodes.

        Returns:
            Dict[str, Any]: Serialisable snapshot keyed by node id.

        """
        snapshot: Dict[str, Any] = {}
        self._snapshot_state(self._root, snapshot)
        return snapshot

    def load_preset(self, preset: Dict[str, Any]) -> None:
        """Restore a previously saved visibility/opacity snapshot.

        Args:
            preset: Snapshot produced by :meth:`save_preset`.

        """
        self._restore_state(self._root, preset)
        # Refresh everything
        top_left = self.index(0, 0)
        bottom_right = (
            self.index(self.rowCount() - 1, 0) if self.rowCount() > 0 else top_left
        )
        self.dataChanged.emit(
            top_left,
            bottom_right,
            [Qt.ItemDataRole.CheckStateRole],
        )
        self._emit_subtree_visibility(self._root)
        self._emit_subtree_opacity(self._root)

    # ------------------------------------------------------------------
    # Scale-dependent visibility query
    # ------------------------------------------------------------------

    def visible_at_zoom(self, node: MapLayerNode, zoom_level: float) -> bool:
        """Check whether *node* should be visible at the given zoom level.

        This combines the node's own ``visible`` flag with its
        ``min_zoom`` / ``max_zoom`` range **and** the effective visibility
        inherited from ancestors.

        Args:
            node: The layer node.
            zoom_level: Current view zoom level.

        Returns:
            bool: ``True`` if the node should be rendered.

        """
        if not node.visible:
            return False
        if zoom_level < node.min_zoom:
            return False
        if zoom_level > node.max_zoom:
            return False
        parent = self._find_parent(node)
        if parent is not None and parent is not self._root:
            return self.visible_at_zoom(parent, zoom_level)
        return True

    def visible_at_time(self, node: MapLayerNode, current_time: float) -> bool:
        """Check whether *node* should be visible at the given lore time.

        A node is time-visible if:
        - It has no ``start_date`` and no ``end_date`` (always visible), or
        - ``start_date <= current_time`` and ``current_time <= end_date``.

        Ancestor visibility is also checked.

        Args:
            node: The layer node.
            current_time: Current playhead time in lore-date units.

        Returns:
            bool: ``True`` if the node should be rendered at this time.

        """
        if not node.visible:
            return False
        if node.start_date is not None and current_time < node.start_date:
            return False
        if node.end_date is not None and current_time > node.end_date:
            return False
        parent = self._find_parent(node)
        if parent is not None and parent is not self._root:
            return self.visible_at_time(parent, current_time)
        return True

    def compute_visibility(
        self,
        zoom_level: float,
        current_time: Optional[float] = None,
    ) -> Dict[str, bool]:
        """Compute effective visibility for all leaf nodes.

        Uses caching: if *zoom_level* and *current_time* haven't changed
        since the last call, the cached result is returned immediately.

        Args:
            zoom_level: Current view zoom level.
            current_time: Current playhead time (``None`` = ignore temporal).

        Returns:
            Dict[str, bool]: Mapping of node id → effective visibility.

        """
        if (
            zoom_level == self._last_zoom
            and current_time == self._last_time
            and self._zoom_cache
        ):
            return self._zoom_cache

        self._last_zoom = zoom_level
        self._last_time = current_time
        self._zoom_cache = {}
        self._compute_vis_recursive(
            self._root, zoom_level, current_time, self._zoom_cache
        )
        return self._zoom_cache

    def invalidate_cache(self) -> None:
        """Force the visibility cache to be recomputed on next query."""
        self._zoom_cache = {}
        self._last_zoom = None
        self._last_time = None

    @Slot()
    def _on_theme_changed(self) -> None:
        """Clear the icon cache when the theme changes."""
        self._icon_cache.clear()
        self.layoutChanged.emit()

    def _get_icon(self, layer_type: str) -> Any:
        """Return a themed QIcon for the given layer type, using caching."""
        if layer_type in self._icon_cache:
            return self._icon_cache[layer_type]

        theme = ThemeManager().get_theme()
        icon: Optional[Any] = None

        if layer_type == MAP_LAYER_TYPE_GROUP:
            icon = load_icon(
                "default_assets/icons/ui_icons/folder.svg", theme.get("text_main")
            )
        elif layer_type == MAP_LAYER_TYPE_MARKER:
            icon = load_icon(
                "default_assets/icons/markers/map-pin.svg", theme.get("primary")
            )
        elif layer_type == MAP_LAYER_TYPE_PATH:
            icon = load_icon(
                "default_assets/icons/markers/polyline.svg",
                theme.get("accent_secondary"),
            )
        elif layer_type == MAP_LAYER_TYPE_REGION:
            icon = load_icon(
                "default_assets/icons/markers/polygon.svg",
                theme.get("accent_secondary"),
            )
        elif layer_type == MAP_LAYER_TYPE_RASTER:
            icon = load_icon(
                "default_assets/icons/markers/grid-raster.svg",
                theme.get("accent_secondary"),
            )

        if icon:
            self._icon_cache[layer_type] = icon
        return icon

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _find_parent(
        self, node: MapLayerNode, current: Optional[MapLayerNode] = None
    ) -> Optional[MapLayerNode]:
        """Find the parent of *node* by walking from *current* (default: root).

        Args:
            node: The child node to locate.
            current: Starting node for the search.

        Returns:
            Optional[MapLayerNode]: Parent node, or ``None`` if not found.

        """
        if current is None:
            current = self._root
        for child in current.children:
            if child is node:
                return current
            found = self._find_parent(node, child)
            if found is not None:
                return found
        return None

    def _find_by_id(self, node: MapLayerNode, node_id: str) -> Optional[MapLayerNode]:
        """Recursively search for a node by id.

        Args:
            node: Current node.
            node_id: Target id.

        Returns:
            Optional[MapLayerNode]: The matching node, or ``None``.

        """
        if node.id == node_id:
            return node
        for child in node.children:
            found = self._find_by_id(child, node_id)
            if found is not None:
                return found
        return None

    def _is_descendant(self, ancestor: MapLayerNode, candidate: MapLayerNode) -> bool:
        """Return ``True`` if *candidate* is *ancestor* or a descendant of it.

        Args:
            ancestor: Potential ancestor node.
            candidate: Node to test.

        Returns:
            bool: ``True`` if *candidate* is in *ancestor*'s subtree.

        """
        if candidate is ancestor:
            return True
        for child in ancestor.children:
            if self._is_descendant(child, candidate):
                return True
        return False

    def _emit_subtree_visibility(self, node: MapLayerNode) -> None:
        """Emit visibility-changed signals for *node* and all descendants.

        Args:
            node: Starting node.

        """
        eff = self._effective_visible(node)
        self.layer_visibility_changed.emit(node.id, eff)
        for child in node.children:
            self._emit_subtree_visibility(child)

    def _emit_subtree_opacity(self, node: MapLayerNode) -> None:
        """Emit opacity-changed signals for *node* and all descendants.

        Args:
            node: Starting node.

        """
        eff = self._effective_opacity(node)
        self.layer_opacity_changed.emit(node.id, eff)
        for child in node.children:
            self._emit_subtree_opacity(child)

    def _effective_visible(self, node: MapLayerNode) -> bool:
        """Compute effective visibility by walking up the parent chain.

        Args:
            node: Target node.

        Returns:
            bool: ``True`` if visible through the entire ancestor chain.

        """
        if not node.visible:
            return False
        parent = self._find_parent(node)
        if parent is not None and parent is not self._root:
            return self._effective_visible(parent)
        return True

    def _effective_opacity(self, node: MapLayerNode) -> float:
        """Compute effective opacity by walking up the parent chain.

        Args:
            node: Target node.

        Returns:
            float: Product of all opacities from root to *node*.

        """
        opacity = node.opacity
        parent = self._find_parent(node)
        if parent is not None and parent is not self._root:
            opacity *= self._effective_opacity(parent)
        return opacity

    _z_counter: float = 0.0

    def _assign_z(
        self,
        node: MapLayerNode,
        result: Dict[str, float],
        counter: Optional[float] = None,
    ) -> float:
        """Depth-first Z assignment.

        Args:
            node: Current node.
            result: Accumulator dict.
            counter: Current Z counter value. ``None`` means start fresh.

        Returns:
            float: Updated counter after processing this subtree.

        """
        if counter is None:
            counter = MAP_LAYER_Z_BASE
        if node is not self._root:
            result[node.id] = counter
            counter += MAP_LAYER_Z_SPACING
        for child in node.children:
            counter = self._assign_z(child, result, counter)
        return counter

    def _snapshot_state(
        self,
        node: MapLayerNode,
        snapshot: Dict[str, Any],
    ) -> None:
        """Recursively capture visibility/opacity.

        Args:
            node: Current node.
            snapshot: Accumulator.

        """
        snapshot[node.id] = {
            "visible": node.visible,
            "opacity": node.opacity,
        }
        for child in node.children:
            self._snapshot_state(child, snapshot)

    def _restore_state(
        self,
        node: MapLayerNode,
        preset: Dict[str, Any],
    ) -> None:
        """Recursively restore visibility/opacity from a preset.

        Args:
            node: Current node.
            preset: State snapshot.

        """
        if node.id in preset:
            state = preset[node.id]
            node.visible = state.get("visible", True)
            node.opacity = float(state.get("opacity", MAP_LAYER_DEFAULT_OPACITY))
        for child in node.children:
            self._restore_state(child, preset)

    def _compute_vis_recursive(
        self,
        node: MapLayerNode,
        zoom_level: float,
        current_time: Optional[float],
        result: Dict[str, bool],
    ) -> None:
        """Walk the tree and collect visibility for each node.

        Args:
            node: Current node.
            zoom_level: Current view zoom level.
            current_time: Current playhead time (or ``None``).
            result: Accumulator dict.

        """
        if node is not self._root:
            vis = self.visible_at_zoom(node, zoom_level)
            if vis and current_time is not None:
                vis = self.visible_at_time(node, current_time)
            result[node.id] = vis
        for child in node.children:
            self._compute_vis_recursive(child, zoom_level, current_time, result)
