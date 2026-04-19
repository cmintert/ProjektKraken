"""Commands for managing the hierarchical layer system.

These commands handle layer-tree operations: visibility toggling,
reordering, opacity changes, renaming, and bulk persistence.
All commands persist the layer tree to the map's ``attributes["layers"]``
JSON column.
"""

import copy
import logging
from typing import Any, Dict, Optional

from src.commands.base_command import BaseCommand, CommandResult
from src.core.map import MapLayerNode
from src.services.db_service import DatabaseService

logger = logging.getLogger(__name__)


def _find_layer_node(root: MapLayerNode, node_id: str) -> Optional[MapLayerNode]:
    """Walk the tree to find a node by ID.

    Args:
        root: Root of the layer tree.
        node_id: Target node ID.

    Returns:
        Optional[MapLayerNode]: The matching node or ``None``.

    """
    if root.id == node_id:
        return root
    for child in root.children:
        found = _find_layer_node(child, node_id)
        if found:
            return found
    return None


class SetLayerVisibilityCommand(BaseCommand):
    """Command to toggle a layer node's visibility (undoable).

    Persists the layer tree to the map's attributes after the change.
    """

    def __init__(
        self,
        map_id: str,
        node_id: str,
        visible: bool,
        layer_tree_dict: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialise the command.

        Args:
            map_id: The map whose layer tree is being modified.
            node_id: ID of the layer node to toggle.
            visible: New visibility state.
            layer_tree_dict: Optional pre-serialised tree snapshot.
                When provided, avoids stale DB reads.

        """
        super().__init__()
        self.map_id = map_id
        self.node_id = node_id
        self.visible = visible
        self.layer_tree_dict = layer_tree_dict
        self._previous_visible: Optional[bool] = None

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Execute the visibility change and persist.

        When ``layer_tree_dict`` is provided, uses the snapshot (which
        already reflects the user's change) as the source of truth and
        writes it directly — avoiding stale-DB-read races where a
        concurrent change on the worker thread would be undone.

        Args:
            db_service: The database service.

        Returns:
            CommandResult: Result of the operation.

        """
        try:
            map_obj = db_service.map_repo.get_map(self.map_id)
            if not map_obj:
                return CommandResult(
                    success=False,
                    message="Map not found.",
                    command_name="SetLayerVisibilityCommand",
                )

            attrs = dict(map_obj.attributes) if map_obj.attributes else {}

            if self.layer_tree_dict is not None:
                # Record previous visibility from DB tree for undo
                if map_obj.layers:
                    db_node = _find_layer_node(map_obj.layers, self.node_id)
                    if db_node:
                        self._previous_visible = db_node.visible

                attrs["layers"] = self.layer_tree_dict
                map_obj.attributes = attrs
                # Clear layers so insert_map won't re-serialize the
                # stale in-memory tree over our snapshot.
                map_obj.layers = None
                db_service.map_repo.insert_map(map_obj)
            else:
                if not map_obj.layers:
                    return CommandResult(
                        success=False,
                        message="Map layers not found.",
                        command_name="SetLayerVisibilityCommand",
                    )

                node = _find_layer_node(map_obj.layers, self.node_id)
                if not node:
                    return CommandResult(
                        success=False,
                        message=f"Layer node {self.node_id} not found.",
                        command_name="SetLayerVisibilityCommand",
                    )

                self._previous_visible = node.visible
                node.visible = self.visible

                attrs["layers"] = map_obj.layers.to_dict()
                map_obj.attributes = attrs
                db_service.map_repo.insert_map(map_obj)

            self._is_executed = True
            return CommandResult(
                success=True,
                message=f"Layer visibility set to {self.visible}.",
                command_name="SetLayerVisibilityCommand",
            )
        except Exception as e:
            logger.error(f"SetLayerVisibilityCommand failed: {e}")
            return CommandResult(
                success=False,
                message=str(e),
                command_name="SetLayerVisibilityCommand",
            )

    def undo(self, db_service: DatabaseService) -> None:
        """Revert the visibility change.

        Args:
            db_service: The database service.

        """
        if self._is_executed and self._previous_visible is not None:
            map_obj = db_service.map_repo.get_map(self.map_id)
            if map_obj and map_obj.layers:
                node = _find_layer_node(map_obj.layers, self.node_id)
                if node:
                    node.visible = self._previous_visible
                    attrs = dict(map_obj.attributes) if map_obj.attributes else {}
                    attrs["layers"] = map_obj.layers.to_dict()
                    map_obj.attributes = attrs
                    db_service.map_repo.insert_map(map_obj)
            self._is_executed = False

    def to_dict(self) -> dict:
        """Serialize command to dictionary."""
        return {
            "map_id": self.map_id,
            "node_id": self.node_id,
            "visible": self.visible,
            "layer_tree_dict": self.layer_tree_dict,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SetLayerVisibilityCommand":
        """Deserialize command from dictionary."""
        return cls(
            data["map_id"],
            data["node_id"],
            data["visible"],
            data.get("layer_tree_dict"),
        )


class MoveLayerCommand(BaseCommand):
    """Command to move a layer to a new position (undoable).

    Persists the layer tree to the map's attributes after the change.
    """

    def __init__(
        self,
        map_id: str,
        node_id: str,
        new_parent_id: str,
        new_row: int,
    ) -> None:
        """Initialise the command.

        Args:
            map_id: The map whose layer tree is being modified.
            node_id: ID of the layer node to move.
            new_parent_id: ID of the new parent group.
            new_row: Target row under the new parent.

        """
        super().__init__()
        self.map_id = map_id
        self.node_id = node_id
        self.new_parent_id = new_parent_id
        self.new_row = new_row
        self._old_parent_id: Optional[str] = None
        self._old_row: Optional[int] = None

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Execute the move and persist.

        Args:
            db_service: The database service.

        Returns:
            CommandResult: Result of the operation.

        """
        try:
            map_obj = db_service.map_repo.get_map(self.map_id)
            if not map_obj or not map_obj.layers:
                return CommandResult(
                    success=False,
                    message="Map or layers not found.",
                    command_name="MoveLayerCommand",
                )

            node = _find_layer_node(map_obj.layers, self.node_id)
            if not node:
                return CommandResult(
                    success=False,
                    message=f"Layer node {self.node_id} not found.",
                    command_name="MoveLayerCommand",
                )

            # Find current parent
            old_parent = self._find_parent(map_obj.layers, node)
            if not old_parent:
                return CommandResult(
                    success=False,
                    message="Cannot find current parent.",
                    command_name="MoveLayerCommand",
                )

            self._old_parent_id = old_parent.id
            self._old_row = old_parent.children.index(node)

            # Clone the tree before mutating so that a persist failure
            # does not leave the original map_obj in an inconsistent state.
            cloned_map = copy.deepcopy(map_obj)
            cloned_node = _find_layer_node(cloned_map.layers, self.node_id)
            if cloned_node is None:
                # Should never happen since we already found the node above,
                # but guard against deepcopy edge cases.
                return CommandResult(
                    success=False,
                    message=f"Layer node {self.node_id} not found in clone.",
                    command_name="MoveLayerCommand",
                )
            cloned_old_parent = self._find_parent(cloned_map.layers, cloned_node)
            if cloned_old_parent is None:
                return CommandResult(
                    success=False,
                    message="Cannot find current parent in clone.",
                    command_name="MoveLayerCommand",
                )

            # Remove from old parent in the clone
            cloned_old_parent.children.remove(cloned_node)

            # Find new parent and insert in the clone
            cloned_new_parent = _find_layer_node(cloned_map.layers, self.new_parent_id)
            if not cloned_new_parent:
                return CommandResult(
                    success=False,
                    message=f"New parent {self.new_parent_id} not found.",
                    command_name="MoveLayerCommand",
                )

            insert_row = min(self.new_row, len(cloned_new_parent.children))
            cloned_new_parent.children.insert(insert_row, cloned_node)

            # Persist the clone — original map_obj is untouched until this succeeds
            attrs = dict(cloned_map.attributes) if cloned_map.attributes else {}
            attrs["layers"] = cloned_map.layers.to_dict()
            cloned_map.attributes = attrs
            db_service.map_repo.insert_map(cloned_map)

            self._is_executed = True
            return CommandResult(
                success=True,
                message="Layer moved.",
                command_name="MoveLayerCommand",
            )
        except Exception as e:
            logger.error(f"MoveLayerCommand failed: {e}")
            return CommandResult(
                success=False,
                message=str(e),
                command_name="MoveLayerCommand",
            )

    def undo(self, db_service: DatabaseService) -> None:
        """Revert the move.

        Args:
            db_service: The database service.

        """
        if (
            self._is_executed
            and self._old_parent_id is not None
            and self._old_row is not None
        ):
            map_obj = db_service.map_repo.get_map(self.map_id)
            if map_obj and map_obj.layers:
                node = _find_layer_node(map_obj.layers, self.node_id)
                if node:
                    # Remove from current position
                    cur_parent = self._find_parent(map_obj.layers, node)
                    if cur_parent:
                        cur_parent.children.remove(node)
                    # Insert back at old position
                    old_parent = _find_layer_node(map_obj.layers, self._old_parent_id)
                    if old_parent:
                        row = min(self._old_row, len(old_parent.children))
                        old_parent.children.insert(row, node)

                    attrs = dict(map_obj.attributes) if map_obj.attributes else {}
                    attrs["layers"] = map_obj.layers.to_dict()
                    map_obj.attributes = attrs
                    db_service.map_repo.insert_map(map_obj)
            self._is_executed = False

    def to_dict(self) -> dict:
        """Serialize command to dictionary."""
        return {
            "map_id": self.map_id,
            "node_id": self.node_id,
            "new_parent_id": self.new_parent_id,
            "new_row": self.new_row,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MoveLayerCommand":
        """Deserialize command from dictionary."""
        return cls(
            data["map_id"],
            data["node_id"],
            data["new_parent_id"],
            data["new_row"],
        )

    @staticmethod
    def _find_parent(root: MapLayerNode, node: MapLayerNode) -> Optional[MapLayerNode]:
        """Walk the tree to find the parent of a node.

        Args:
            root: Root of the layer tree.
            node: Target child node.

        Returns:
            Optional[MapLayerNode]: The parent or ``None``.

        """
        for child in root.children:
            if child is node or child.id == node.id:
                return root
            found = MoveLayerCommand._find_parent(child, node)
            if found:
                return found
        return None


class SaveLayerTreeCommand(BaseCommand):
    """Command to persist the entire layer tree to the map's attributes.

    Used when the in-memory tree has been modified (e.g. by auto-registering
    new markers) and needs to be flushed to the database.
    """

    def __init__(self, map_id: str, layer_tree_dict: Dict[str, Any]) -> None:
        """Initialise the command.

        Args:
            map_id: The map to update.
            layer_tree_dict: Serialised layer tree (from ``MapLayerNode.to_dict()``).

        """
        super().__init__()
        self.map_id = map_id
        self.layer_tree_dict = layer_tree_dict
        self._previous_tree_dict: Optional[Dict[str, Any]] = None

    @property
    def has_history(self) -> bool:
        """Background sync — never tracked in the undo stack."""
        return False

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Persist the layer tree.

        Args:
            db_service: The database service.

        Returns:
            CommandResult: Result of the operation.

        """
        try:
            map_obj = db_service.map_repo.get_map(self.map_id)
            if not map_obj:
                return CommandResult(
                    success=False,
                    message="Map not found.",
                    command_name="SaveLayerTreeCommand",
                )

            attrs = dict(map_obj.attributes) if map_obj.attributes else {}
            self._previous_tree_dict = attrs.get("layers")
            attrs["layers"] = self.layer_tree_dict
            map_obj.attributes = attrs
            # Clear the in-memory MapLayerNode so insert_map uses our
            # layer_tree_dict snapshot rather than re-serializing the stale tree.
            map_obj.layers = None
            db_service.map_repo.insert_map(map_obj)

            self._is_executed = True
            return CommandResult(
                success=True,
                message="Layer tree saved.",
                command_name="SaveLayerTreeCommand",
            )
        except Exception as e:
            logger.error(f"SaveLayerTreeCommand failed: {e}")
            return CommandResult(
                success=False,
                message=str(e),
                command_name="SaveLayerTreeCommand",
            )

    def undo(self, db_service: DatabaseService) -> None:
        """Revert to the previous layer tree.

        Args:
            db_service: The database service.

        """
        if self._is_executed:
            map_obj = db_service.map_repo.get_map(self.map_id)
            if map_obj:
                attrs = dict(map_obj.attributes) if map_obj.attributes else {}
                if self._previous_tree_dict is not None:
                    attrs["layers"] = self._previous_tree_dict
                else:
                    attrs.pop("layers", None)
                map_obj.attributes = attrs
                db_service.map_repo.insert_map(map_obj)
            self._is_executed = False

    def to_dict(self) -> dict:
        """Serialize command to dictionary."""
        return {
            "map_id": self.map_id,
            "layer_tree_dict": self.layer_tree_dict,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SaveLayerTreeCommand":
        """Deserialize command from dictionary."""
        return cls(data["map_id"], data["layer_tree_dict"])


class SetLayerOpacityCommand(BaseCommand):
    """Command to change a layer node's opacity (undoable).

    Persists the layer tree to the map's attributes after the change.
    """

    def __init__(
        self,
        map_id: str,
        node_id: str,
        opacity: float,
        previous_opacity: Optional[float] = None,
        layer_tree_dict: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialise the command.

        Args:
            map_id: The map whose layer tree is being modified.
            node_id: ID of the layer node to change.
            opacity: New opacity (0.0–1.0).
            previous_opacity: The opacity before this change (for undo).
            layer_tree_dict: Optional pre-serialised tree snapshot.
                When provided, avoids stale DB reads.

        """
        super().__init__()
        self.map_id = map_id
        self.node_id = node_id
        self.opacity = opacity
        self.layer_tree_dict = layer_tree_dict
        self._previous_opacity = previous_opacity

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Execute the opacity change and persist.

        When ``layer_tree_dict`` is provided, uses the snapshot (which
        already reflects the user's change) as the source of truth and
        writes it directly — avoiding stale-DB-read races.

        Args:
            db_service: The database service.

        Returns:
            CommandResult: Result of the operation.

        """
        try:
            map_obj = db_service.map_repo.get_map(self.map_id)
            if not map_obj:
                return CommandResult(
                    success=False,
                    message="Map not found.",
                    command_name="SetLayerOpacityCommand",
                )

            attrs = dict(map_obj.attributes) if map_obj.attributes else {}

            if self.layer_tree_dict is not None:
                if self._previous_opacity is None and map_obj.layers:
                    db_node = _find_layer_node(map_obj.layers, self.node_id)
                    if db_node:
                        self._previous_opacity = db_node.opacity

                attrs["layers"] = self.layer_tree_dict
                map_obj.attributes = attrs
                map_obj.layers = None
                db_service.map_repo.insert_map(map_obj)
            else:
                if not map_obj.layers:
                    return CommandResult(
                        success=False,
                        message="Map layers not found.",
                        command_name="SetLayerOpacityCommand",
                    )

                node = _find_layer_node(map_obj.layers, self.node_id)
                if not node:
                    return CommandResult(
                        success=False,
                        message=f"Layer node {self.node_id} not found.",
                        command_name="SetLayerOpacityCommand",
                    )

                if self._previous_opacity is None:
                    self._previous_opacity = node.opacity

                node.opacity = max(0.0, min(1.0, self.opacity))

                attrs["layers"] = map_obj.layers.to_dict()
                map_obj.attributes = attrs
                db_service.map_repo.insert_map(map_obj)

            self._is_executed = True
            return CommandResult(
                success=True,
                message=f"Layer opacity set to {self.opacity:.0%}.",
                command_name="SetLayerOpacityCommand",
            )
        except Exception as e:
            logger.error(f"SetLayerOpacityCommand failed: {e}")
            return CommandResult(
                success=False,
                message=str(e),
                command_name="SetLayerOpacityCommand",
            )

    def undo(self, db_service: DatabaseService) -> None:
        """Revert the opacity change.

        Args:
            db_service: The database service.

        """
        if self._is_executed and self._previous_opacity is not None:
            map_obj = db_service.map_repo.get_map(self.map_id)
            if map_obj and map_obj.layers:
                node = _find_layer_node(map_obj.layers, self.node_id)
                if node:
                    node.opacity = self._previous_opacity
                    attrs = dict(map_obj.attributes) if map_obj.attributes else {}
                    attrs["layers"] = map_obj.layers.to_dict()
                    map_obj.attributes = attrs
                    db_service.map_repo.insert_map(map_obj)
            self._is_executed = False

    def to_dict(self) -> dict:
        """Serialize command to dictionary."""
        return {
            "map_id": self.map_id,
            "node_id": self.node_id,
            "opacity": self.opacity,
            "previous_opacity": self._previous_opacity,
            "layer_tree_dict": self.layer_tree_dict,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SetLayerOpacityCommand":
        """Deserialize command from dictionary."""
        return cls(
            data["map_id"],
            data["node_id"],
            data["opacity"],
            data.get("previous_opacity"),
            data.get("layer_tree_dict"),
        )


class RenameLayerCommand(BaseCommand):
    """Command to rename a layer node (undoable).

    Persists the layer tree to the map's attributes after the change.
    """

    def __init__(
        self,
        map_id: str,
        node_id: str,
        new_name: str,
        layer_tree_dict: Optional[Dict[str, Any]] = None,
        marker_id: Optional[str] = None,
    ) -> None:
        """Initialise the command.

        Args:
            map_id: The map whose layer tree is being modified.
            node_id: ID of the layer node to rename.  In the UI this
                equals the entity/event ``object_id``.
            new_name: New display name.
            layer_tree_dict: Optional pre-serialised tree snapshot
                (already containing the renamed node).  When provided
                the command writes this directly instead of re-reading
                from the database, avoiding stale-data races.
            marker_id: The actual ``MapFeature.id`` (DB primary key)
                for the linked marker.  When *None* the command falls
                back to querying by ``node_id`` (legacy behaviour).

        """
        super().__init__()
        self.map_id = map_id
        self.node_id = node_id
        self.new_name = new_name
        self._layer_tree_dict = layer_tree_dict
        self._marker_id = marker_id
        self._previous_name: Optional[str] = None
        # Undo state for the linked feature label
        self._prev_feature_label: Optional[str] = None
        # Undo state for the linked lore item name
        self._prev_lore_name: Optional[str] = None
        self._lore_object_id: Optional[str] = None
        self._lore_object_type: Optional[str] = None
        # Atomic-rollback state: the full attrs["layers"] dict as it was
        # *before* execute() wrote its change.  Used to revert the tree
        # write if any downstream sync (marker/lore) fails.
        self._prev_layers_attr: Optional[Dict[str, Any]] = None

    # ------------------------------------------------------------------
    # Private helpers — sync feature label & lore item name
    # ------------------------------------------------------------------

    def _sync_feature_label(self, db_service: DatabaseService) -> None:
        """Rename the MapFeature label linked to this node.

        Uses ``_marker_id`` (the actual DB primary key) when available,
        falling back to ``node_id`` for backwards compatibility.

        Args:
            db_service: Database service instance.

        """
        lookup_id = self._marker_id or self.node_id
        marker = db_service.map_repo.get_marker(lookup_id)
        if not marker:
            return
        self._prev_feature_label = marker.label
        self._lore_object_id = marker.object_id
        self._lore_object_type = marker.object_type
        marker.label = self.new_name
        import time as _time

        marker.modified_at = _time.time()
        db_service.map_repo.insert_marker(marker)

    def _sync_lore_item(self, db_service: DatabaseService) -> None:
        """Rename the underlying Entity or Event.

        Args:
            db_service: Database service instance.

        """
        if not self._lore_object_id or not self._lore_object_type:
            return

        if self._lore_object_type == "entity":
            entity = db_service.get_entity(self._lore_object_id)
            if entity:
                self._prev_lore_name = entity.name
                entity.name = self.new_name
                db_service.insert_entity(entity)
        elif self._lore_object_type == "event":
            event = db_service.get_event(self._lore_object_id)
            if event:
                self._prev_lore_name = event.name
                event.name = self.new_name
                db_service.insert_event(event)

    def _undo_feature_label(self, db_service: DatabaseService) -> None:
        """Revert the MapFeature label."""
        if self._prev_feature_label is None:
            return
        lookup_id = self._marker_id or self.node_id
        marker = db_service.map_repo.get_marker(lookup_id)
        if marker:
            marker.label = self._prev_feature_label
            db_service.map_repo.insert_marker(marker)

    def _undo_lore_item(self, db_service: DatabaseService) -> None:
        """Revert the Entity/Event name."""
        if self._prev_lore_name is None:
            return
        if not self._lore_object_id or not self._lore_object_type:
            return
        if self._lore_object_type == "entity":
            entity = db_service.get_entity(self._lore_object_id)
            if entity:
                entity.name = self._prev_lore_name
                db_service.insert_entity(entity)
        elif self._lore_object_type == "event":
            event = db_service.get_event(self._lore_object_id)
            if event:
                event.name = self._prev_lore_name
                db_service.insert_event(event)

    def _undo_layer_tree_write(self, db_service: DatabaseService) -> None:
        """Restore the map's ``attributes["layers"]`` to its pre-execute value.

        Called when a downstream sync (marker label or lore item) fails
        after the tree write succeeded, so that the three stores stay
        consistent.

        Args:
            db_service: Database service instance.

        """
        if self._prev_layers_attr is None:
            return
        map_obj = db_service.map_repo.get_map(self.map_id)
        if not map_obj:
            return
        attrs = dict(map_obj.attributes) if map_obj.attributes else {}
        attrs["layers"] = self._prev_layers_attr
        map_obj.attributes = attrs
        # Clear layers so insert_map writes the restored snapshot, not
        # the in-memory tree that was mutated above.
        map_obj.layers = None
        db_service.map_repo.insert_map(map_obj)

    # ------------------------------------------------------------------
    # Command interface
    # ------------------------------------------------------------------

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Execute the rename and persist.

        Performs a **triple-sync rename**:

        1. Rename the ``MapLayerNode`` in the hierarchy tree.
        2. Rename the ``MapFeature.label`` in the markers table.
        3. Rename the linked ``Entity.name`` or ``Event.name``.

        Args:
            db_service: The database service.

        Returns:
            CommandResult: Result of the operation.

        """
        try:
            map_obj = db_service.map_repo.get_map(self.map_id)
            if not map_obj:
                return CommandResult(
                    success=False,
                    message="Map not found.",
                    command_name="RenameLayerCommand",
                )

            attrs = dict(map_obj.attributes) if map_obj.attributes else {}

            # Capture the pre-execute layers snapshot so any sync failure
            # further down can roll the tree write back.
            self._prev_layers_attr = copy.deepcopy(attrs.get("layers"))

            if self._layer_tree_dict is not None:
                # -- Snapshot path (fast, avoids stale reads) --
                # Record previous name from DB tree for undo
                if map_obj.layers:
                    node = _find_layer_node(map_obj.layers, self.node_id)
                    if node:
                        self._previous_name = node.name

                attrs["layers"] = self._layer_tree_dict
                map_obj.attributes = attrs
                # Clear layers so insert_map won't re-serialize the
                # stale in-memory tree over our snapshot.
                map_obj.layers = None
                db_service.map_repo.insert_map(map_obj)
            else:
                # -- Fallback path (read from DB, find & rename) --
                if not map_obj.layers:
                    return CommandResult(
                        success=False,
                        message="Map layers not found.",
                        command_name="RenameLayerCommand",
                    )

                node = _find_layer_node(map_obj.layers, self.node_id)
                if not node:
                    return CommandResult(
                        success=False,
                        message=(f"Layer node {self.node_id} not found."),
                        command_name="RenameLayerCommand",
                    )

                self._previous_name = node.name
                node.name = self.new_name
                attrs["layers"] = map_obj.layers.to_dict()
                map_obj.attributes = attrs
                db_service.map_repo.insert_map(map_obj)

            # -- Sync feature label + lore item name --
            # Both syncs must succeed together; if either fails, roll
            # back every write that came before so all three stores
            # (layer tree, marker, lore item) stay consistent.
            try:
                self._sync_feature_label(db_service)
            except Exception as marker_exc:
                logger.error(
                    "RenameLayerCommand: _sync_feature_label failed (%s); "
                    "rolling back layer-tree write",
                    marker_exc,
                )
                self._undo_layer_tree_write(db_service)
                return CommandResult(
                    success=False,
                    message=str(marker_exc),
                    command_name="RenameLayerCommand",
                )

            try:
                self._sync_lore_item(db_service)
            except Exception as lore_exc:
                logger.error(
                    "RenameLayerCommand: _sync_lore_item failed (%s); "
                    "rolling back feature label and layer-tree write",
                    lore_exc,
                )
                self._undo_feature_label(db_service)
                self._undo_layer_tree_write(db_service)
                return CommandResult(
                    success=False,
                    message=str(lore_exc),
                    command_name="RenameLayerCommand",
                )

            self._is_executed = True
            return CommandResult(
                success=True,
                message=f"Renamed to '{self.new_name}'.",
                command_name="RenameLayerCommand",
            )
        except Exception as e:
            logger.error(f"RenameLayerCommand failed: {e}")
            return CommandResult(
                success=False,
                message=str(e),
                command_name="RenameLayerCommand",
            )

    def undo(self, db_service: DatabaseService) -> None:
        """Revert the rename across all three stores.

        Args:
            db_service: The database service.

        """
        if self._is_executed and self._previous_name is not None:
            map_obj = db_service.map_repo.get_map(self.map_id)
            if map_obj and map_obj.layers:
                node = _find_layer_node(map_obj.layers, self.node_id)
                if node:
                    node.name = self._previous_name
                    attrs = dict(map_obj.attributes) if map_obj.attributes else {}
                    attrs["layers"] = map_obj.layers.to_dict()
                    map_obj.attributes = attrs
                    db_service.map_repo.insert_map(map_obj)

            # Revert feature label and lore item name
            self._undo_feature_label(db_service)
            self._undo_lore_item(db_service)

            self._is_executed = False

    def to_dict(self) -> dict:
        """Serialize command to dictionary."""
        return {
            "map_id": self.map_id,
            "node_id": self.node_id,
            "new_name": self.new_name,
            "marker_id": self._marker_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RenameLayerCommand":
        """Deserialize command from dictionary."""
        return cls(
            data["map_id"],
            data["node_id"],
            data["new_name"],
            marker_id=data.get("marker_id"),
        )
