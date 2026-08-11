"""Commands for managing the hierarchical layer system.

These commands handle layer-tree operations: visibility toggling,
reordering, opacity changes, renaming, and bulk persistence.
All commands persist the layer tree to the map's ``attributes["layers"]``
JSON column.
"""

import copy
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from src.commands.base_command import BaseCommand, CommandResult
from src.core.map import MapLayerNode
from src.core.map_state import LayerSubtreeSnapshot
from src.core.marker import Marker
from src.services.command_artifact_store import CommandArtifactStore
from src.services.db_service import DatabaseService
from src.services.raster_asset_service import RasterAssetService

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

        The worker-owned database tree is always authoritative. A serialized
        UI snapshot may be retained for command compatibility, but must not
        overwrite newer persisted layer state.

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
            cloned_layers = cloned_map.layers
            if cloned_layers is None:
                return CommandResult(
                    success=False,
                    message="Layer tree missing from cloned map.",
                    command_name="MoveLayerCommand",
                )

            cloned_node = _find_layer_node(cloned_layers, self.node_id)
            if cloned_node is None:
                # Should never happen since we already found the node above,
                # but guard against deepcopy edge cases.
                return CommandResult(
                    success=False,
                    message=f"Layer node {self.node_id} not found in clone.",
                    command_name="MoveLayerCommand",
                )
            cloned_old_parent = self._find_parent(cloned_layers, cloned_node)
            if cloned_old_parent is None:
                return CommandResult(
                    success=False,
                    message="Cannot find current parent in clone.",
                    command_name="MoveLayerCommand",
                )

            # Remove from old parent in the clone
            cloned_old_parent.children.remove(cloned_node)

            # Find new parent and insert in the clone
            cloned_new_parent = _find_layer_node(cloned_layers, self.new_parent_id)
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
            attrs["layers"] = cloned_layers.to_dict()
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
    def is_undoable(self) -> bool:
        """Background sync — never tracked in the undo stack."""
        return False

    @property
    def persist_to_history(self) -> bool:
        """Background synchronization is never persisted."""
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


class UpdateLayerTreeCommand(SaveLayerTreeCommand):
    """Undoable user-initiated replacement of the canonical layer tree."""

    @property
    def is_undoable(self) -> bool:
        """User tree edits belong in the current undo stack."""
        return True

    @property
    def persist_to_history(self) -> bool:
        """Structural tree edits remain undoable after restart."""
        return True

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Persist the tree while retaining the exact previous snapshot."""
        result = super().execute(db_service)
        result.command_name = self.__class__.__name__
        return result

    def to_dict(self) -> dict:
        """Serialize both sides of the structural edit."""
        return {
            "map_id": self.map_id,
            "layer_tree_dict": self.layer_tree_dict,
            "previous_tree_dict": self._previous_tree_dict,
            "is_executed": self._is_executed,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "UpdateLayerTreeCommand":
        """Deserialize a persistent structural edit."""
        command = cls(data["map_id"], data["layer_tree_dict"])
        command._previous_tree_dict = data.get("previous_tree_dict")
        command._is_executed = bool(data.get("is_executed", True))
        return command


class DeleteLayerSubtreeCommand(BaseCommand):
    """Delete one canonical layer subtree as a single reversible action."""

    def __init__(
        self,
        map_id: str,
        node_id: str,
        world_root: str = "",
    ) -> None:
        super().__init__()
        self.map_id = map_id
        self.node_id = node_id
        self.world_root = world_root
        self._snapshot: Optional[LayerSubtreeSnapshot] = None
        self._artifact_manifest: dict[str, str] = {}

    @staticmethod
    def _find_parent(
        root: MapLayerNode, node_id: str
    ) -> Optional[tuple[MapLayerNode, int, MapLayerNode]]:
        for row, child in enumerate(root.children):
            if child.id == node_id:
                return root, row, child
            found = DeleteLayerSubtreeCommand._find_parent(child, node_id)
            if found is not None:
                return found
        return None

    @staticmethod
    def _find_node(
        root: MapLayerNode, node_id: str
    ) -> Optional[MapLayerNode]:
        if root.id == node_id:
            return root
        for child in root.children:
            found = DeleteLayerSubtreeCommand._find_node(child, node_id)
            if found is not None:
                return found
        return None

    @staticmethod
    def _collect_nodes(node: MapLayerNode) -> list[MapLayerNode]:
        nodes = [node]
        for child in node.children:
            nodes.extend(DeleteLayerSubtreeCommand._collect_nodes(child))
        return nodes

    @staticmethod
    def _persist_tree(
        db_service: DatabaseService,
        map_obj: Any,
        raster_layers: list[dict[str, Any]],
    ) -> None:
        attributes = dict(map_obj.attributes or {})
        attributes["layers"] = map_obj.layers.to_dict()
        attributes["raster_layers"] = raster_layers
        map_obj.attributes = attributes
        db_service.map_repo.insert_map(map_obj)

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Delete tree state, descendant features, and owned raster files."""
        map_obj = db_service.map_repo.get_map(self.map_id)
        if map_obj is None or map_obj.layers is None:
            return CommandResult(
                success=False,
                message="Map or layer tree not found.",
                command_name=self.__class__.__name__,
            )
        found = self._find_parent(map_obj.layers, self.node_id)
        if found is None:
            return CommandResult(
                success=False,
                message="Layer not found.",
                command_name=self.__class__.__name__,
            )
        parent, row, node = found
        nodes = self._collect_nodes(node)
        node_ids = {item.id for item in nodes}
        raster_ids = {
            item.id for item in nodes if item.layer_type == "raster"
        }
        markers = [
            marker
            for marker in db_service.get_markers_for_map(self.map_id)
            if marker.id in node_ids
        ]
        trajectories: list[dict[str, Any]] = []
        geometry_states: list[dict[str, Any]] = []
        for marker in markers:
            trajectories.extend(
                db_service.trajectory_repo.snapshot_by_marker(marker.id)
            )
            geometry_states.extend(
                db_service.feature_geometry_repo.snapshot_by_marker(marker.id)
            )

        all_rasters = list(
            (map_obj.attributes or {}).get("raster_layers", [])
        )
        deleted_rasters = [
            dict(item)
            for item in all_rasters
            if item.get("node_id") in raster_ids
        ]
        kept_rasters = [
            dict(item)
            for item in all_rasters
            if item.get("node_id") not in raster_ids
        ]
        raster_files = RasterAssetService.owned_files_from_metadata(
            deleted_rasters
        )
        self._snapshot = LayerSubtreeSnapshot(
            parent_id=parent.id,
            row=row,
            node=node.to_dict(),
            markers=[marker.to_dict() for marker in markers],
            trajectories=trajectories,
            geometry_states=geometry_states,
            raster_layers=deleted_rasters,
            raster_files=raster_files,
        )

        world_root = (
            Path(self.world_root)
            if self.world_root
            else Path(db_service.get_db_file_path()).parent
        )
        artifacts = CommandArtifactStore(world_root)
        self._artifact_manifest = artifacts.stash(
            self.command_id, raster_files
        )
        try:
            with db_service.transaction():
                for marker in markers:
                    db_service.delete_marker(marker.id)
                parent.children.pop(row)
                self._persist_tree(db_service, map_obj, kept_rasters)
        except Exception:
            artifacts.restore(self._artifact_manifest)
            raise

        self._is_executed = True
        return CommandResult(
            success=True,
            message=f"Deleted layer '{node.name}'.",
            command_name=self.__class__.__name__,
            data={
                "effects": [
                    {"kind": "map_state_changed", "map_id": self.map_id}
                ]
            },
        )

    def undo(self, db_service: DatabaseService) -> None:
        """Restore the exact hierarchy, database rows, and raster assets."""
        if not self._is_executed or self._snapshot is None:
            return
        map_obj = db_service.map_repo.get_map(self.map_id)
        if map_obj is None or map_obj.layers is None:
            raise ValueError("Map or layer tree not found during undo")
        parent = self._find_node(map_obj.layers, self._snapshot.parent_id)
        if parent is None:
            raise ValueError("Original layer parent no longer exists")

        node = MapLayerNode.from_dict(self._snapshot.node)
        row = min(self._snapshot.row, len(parent.children))
        parent.children.insert(row, node)
        current_rasters = list(
            (map_obj.attributes or {}).get("raster_layers", [])
        )
        current_rasters.extend(copy.deepcopy(self._snapshot.raster_layers))
        world_root = (
            Path(self.world_root)
            if self.world_root
            else Path(db_service.get_db_file_path()).parent
        )
        artifacts = CommandArtifactStore(world_root)
        artifacts.restore(self._artifact_manifest)
        try:
            with db_service.transaction():
                self._persist_tree(db_service, map_obj, current_rasters)
                for marker_data in self._snapshot.markers:
                    db_service.insert_marker(Marker.from_dict(marker_data))
                for trajectory in self._snapshot.trajectories:
                    db_service.trajectory_repo.restore_snapshot(trajectory)
                for state in self._snapshot.geometry_states:
                    db_service.feature_geometry_repo.restore_snapshot(state)
        except Exception:
            self._artifact_manifest = artifacts.stash(
                self.command_id, self._snapshot.raster_files
            )
            raise
        self._is_executed = False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize persistent undo state."""
        return {
            "map_id": self.map_id,
            "node_id": self.node_id,
            "world_root": self.world_root,
            "snapshot": self._snapshot.to_dict() if self._snapshot else None,
            "artifact_manifest": self._artifact_manifest,
            "is_executed": self._is_executed,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DeleteLayerSubtreeCommand":
        """Restore a command from persistent history."""
        command = cls(
            str(data["map_id"]),
            str(data["node_id"]),
            str(data.get("world_root", "")),
        )
        if data.get("snapshot"):
            command._snapshot = LayerSubtreeSnapshot.from_dict(data["snapshot"])
        command._artifact_manifest = dict(data.get("artifact_manifest", {}))
        command._is_executed = bool(data.get("is_executed", command._snapshot))
        return command

    def get_description(self) -> str:
        """Return the history-panel description."""
        return "Delete layer subtree"


class UpdateLayerPropertiesCommand(BaseCommand):
    """Update common, temporal, and zoom properties for one layer."""

    def __init__(
        self, map_id: str, node_id: str, properties: dict[str, Any]
    ) -> None:
        super().__init__()
        self.map_id = map_id
        self.node_id = node_id
        self.properties = dict(properties)
        self._previous: dict[str, Any] = {}

    @staticmethod
    def _state(node: MapLayerNode) -> dict[str, Any]:
        return {
            "name": node.name,
            "visible": node.visible,
            "opacity": node.opacity,
            "notes": node.attributes.get("notes", ""),
            "mutually_exclusive": node.mutually_exclusive,
            "start_date": node.start_date,
            "end_date": node.end_date,
            "min_zoom": node.min_zoom,
            "max_zoom": node.max_zoom,
            "zoom_basis": node.attributes.get("zoom_basis"),
        }

    @staticmethod
    def _apply(node: MapLayerNode, properties: dict[str, Any]) -> None:
        start_date = properties.get("start_date", node.start_date)
        end_date = properties.get("end_date", node.end_date)
        if (
            start_date is not None
            and end_date is not None
            and float(end_date) <= float(start_date)
        ):
            raise ValueError("Layer end date must be after its start date")
        min_zoom = float(properties.get("min_zoom", node.min_zoom))
        max_zoom = float(properties.get("max_zoom", node.max_zoom))
        if min_zoom > max_zoom:
            raise ValueError("Minimum zoom must not exceed maximum zoom")

        node.name = str(properties.get("name", node.name)).strip() or node.name
        node.visible = bool(properties.get("visible", node.visible))
        node.opacity = max(
            0.0, min(1.0, float(properties.get("opacity", node.opacity)))
        )
        node.mutually_exclusive = bool(
            properties.get("mutually_exclusive", node.mutually_exclusive)
        )
        node.start_date = float(start_date) if start_date is not None else None
        node.end_date = float(end_date) if end_date is not None else None
        node.min_zoom = min_zoom
        node.max_zoom = max_zoom
        attributes = dict(node.attributes)
        if "notes" in properties:
            attributes["notes"] = str(properties["notes"])
        if "zoom_basis" in properties:
            zoom_basis = properties["zoom_basis"]
            if zoom_basis:
                attributes["zoom_basis"] = str(zoom_basis)
            else:
                attributes.pop("zoom_basis", None)
        node.attributes = attributes

    def _persist(
        self, db_service: DatabaseService, properties: dict[str, Any]
    ) -> None:
        map_obj = db_service.map_repo.get_map(self.map_id)
        if map_obj is None or map_obj.layers is None:
            raise ValueError("Map or layer tree not found")
        node = DeleteLayerSubtreeCommand._find_node(
            map_obj.layers, self.node_id
        )
        if node is None:
            raise ValueError("Layer not found")
        self._apply(node, properties)
        attrs = dict(map_obj.attributes or {})
        attrs["layers"] = map_obj.layers.to_dict()
        map_obj.attributes = attrs
        db_service.map_repo.insert_map(map_obj)

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Apply and persist layer properties."""
        map_obj = db_service.map_repo.get_map(self.map_id)
        if map_obj is None or map_obj.layers is None:
            return CommandResult(
                False,
                "Map or layer tree not found.",
                command_name=self.__class__.__name__,
            )
        node = DeleteLayerSubtreeCommand._find_node(
            map_obj.layers, self.node_id
        )
        if node is None:
            return CommandResult(
                False,
                "Layer not found.",
                command_name=self.__class__.__name__,
            )
        if not self._previous:
            self._previous = self._state(node)
        try:
            self._persist(db_service, self.properties)
        except ValueError as exc:
            return CommandResult(
                False, str(exc), command_name=self.__class__.__name__
            )
        self._is_executed = True
        return CommandResult(
            True,
            "Layer properties updated.",
            command_name=self.__class__.__name__,
        )

    def undo(self, db_service: DatabaseService) -> None:
        """Restore the preceding property values."""
        if self._is_executed:
            self._persist(db_service, self._previous)
            self._is_executed = False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the property edit."""
        return {
            "map_id": self.map_id,
            "node_id": self.node_id,
            "properties": self.properties,
            "previous": self._previous,
            "is_executed": self._is_executed,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UpdateLayerPropertiesCommand":
        """Deserialize the property edit."""
        command = cls(
            str(data["map_id"]),
            str(data["node_id"]),
            dict(data.get("properties", {})),
        )
        command._previous = dict(data.get("previous", {}))
        command._is_executed = bool(data.get("is_executed", True))
        return command


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

        The worker-owned database tree is always authoritative. A serialized
        UI snapshot may be retained for command compatibility, but must not
        overwrite newer persisted layer state.

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
