"""Commands for manipulating Map and MapFeature (Marker) objects.

API Usage Note:
===============
These commands accept `db_service` in the `execute()` method parameter,
matching the project's standard command pattern used across other modules
(entity_commands, event_commands, etc.). This design allows commands to be
instantiated without database coupling and executed later with the appropriate
database service instance.
"""

import dataclasses
import json
import logging
from typing import Any, Dict, List, Optional

from src.commands.base_command import BaseCommand, CommandResult
from src.core.map import Map, MapLayerNode
from src.core.marker import MapFeature, Marker
from src.services.db_service import DatabaseService

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# Map Commands
# --------------------------------------------------------------------------


class CreateMapCommand(BaseCommand):
    """Command to create a new map."""

    def __init__(self, map_data: Optional[dict] = None) -> None:
        """Initializes the CreateMapCommand.

        Args:
            map_data (dict, optional): Dictionary containing map data.
                                       If None, default values are used.

        """
        super().__init__()
        if map_data:
            self._map = Map(**map_data)
        else:
            self._map = Map(name="New Map", image_path="")

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Executes the command to create the map.

        Args:
            db_service (DatabaseService): The database service to use.

        Returns:
            CommandResult: Result object indicating success or failure.

        """
        try:
            db_service.insert_map(self._map)
            self._is_executed = True
            logger.info(f"Created map: {self._map.name} ({self._map.id})")
            return CommandResult(
                success=True,
                message=f"Map '{self._map.name}' created.",
                command_name="CreateMapCommand",
                data={"id": self._map.id},
            )
        except Exception as e:
            logger.error(f"Failed to create map: {e}")
            return CommandResult(
                success=False,
                message=f"Failed to create map: {e}",
                command_name="CreateMapCommand",
            )

    def undo(self, db_service: DatabaseService) -> None:
        """Reverts the map creation by deleting it from the database.

        Args:
            db_service (DatabaseService): The database service to operate on.

        """
        if self._is_executed:
            db_service.delete_map(self._map.id)
            self._is_executed = False
            logger.info(f"Undid creation of map: {self._map.id}")

    def to_dict(self) -> dict:
        """Serialize command to dictionary.

        Returns:
            Dictionary representation of the command.
        """
        return {"map_data": self._map.to_dict()}

    @classmethod
    def from_dict(cls, data: dict) -> "CreateMapCommand":
        """Deserialize command from dictionary.

        Args:
            data: Dictionary containing serialized command data.

        Returns:
            CreateMapCommand instance.
        """
        return cls(data.get("map_data"))


class UpdateMapCommand(BaseCommand):
    """Command to update an existing map.

    Accepts a dictionary of changes.
    """

    def __init__(self, map_id: str, update_data: dict) -> None:
        """Initializes the UpdateMapCommand.

        Args:
            map_id (str): The ID of the map to update.
            update_data (dict): Dictionary of fields to update.

        """
        super().__init__()
        self.map_id = map_id
        self.update_data = update_data
        self._previous_map: Optional[Map] = None
        self._new_map: Optional[Map] = None

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Executes the update.

        Args:
            db_service (DatabaseService): The database service to use.

        Returns:
            CommandResult: Result object containing success status and messages.

        """
        try:
            # Fetch current state before update
            current = db_service.get_map(self.map_id)
            if not current:
                logger.error(f"Map not found for update: {self.map_id}")
                return CommandResult(
                    success=False,
                    message=f"Map not found: {self.map_id}",
                    command_name="UpdateMapCommand",
                )

            self._previous_map = current

            # Apply updates
            valid_fields = {f.name for f in dataclasses.fields(Map)}
            clean_data = {
                k: v for k, v in self.update_data.items() if k in valid_fields
            }

            # Safely merge attributes if present
            if "attributes" in clean_data and isinstance(
                clean_data["attributes"], dict
            ):
                current_attrs = current.attributes.copy() if current.attributes else {}
                current_attrs.update(clean_data["attributes"])
                clean_data["attributes"] = current_attrs

            self._new_map = dataclasses.replace(current, **clean_data)

            db_service.insert_map(self._new_map)
            self._is_executed = True
            logger.info(f"Updated map: {self._new_map.id}")
            return CommandResult(
                success=True,
                message="Map updated.",
                command_name="UpdateMapCommand",
            )
        except Exception as e:
            logger.error(f"Failed to update map: {e}")
            return CommandResult(
                success=False,
                message=f"Failed to update map: {e}",
                command_name="UpdateMapCommand",
            )

    def undo(self, db_service: DatabaseService) -> None:
        """Reverts the map update by restoring the previous state.

        Args:
            db_service (DatabaseService): The database service to operate on.

        """
        if self._is_executed and self._previous_map:
            db_service.insert_map(self._previous_map)
            self._is_executed = False
            logger.info(f"Undid update of map: {self.map_id}")

    def to_dict(self) -> dict:
        """Serialize command to dictionary.

        Returns:
            Dictionary representation of the command.
        """
        return {"map_id": self.map_id, "update_data": self.update_data}

    @classmethod
    def from_dict(cls, data: dict) -> "UpdateMapCommand":
        """Deserialize command from dictionary.

        Args:
            data: Dictionary containing serialized command data.

        Returns:
            UpdateMapCommand instance.
        """
        return cls(data["map_id"], data["update_data"])


class DeleteMapCommand(BaseCommand):
    """Command to delete a map and all its markers."""

    def __init__(self, map_id: str) -> None:
        """Initializes the DeleteMapCommand.

        Args:
            map_id (str): The ID of the map to delete.

        """
        super().__init__()
        self.map_id = map_id
        self._deleted_map: Optional[Map] = None
        self._deleted_markers: List[Marker] = []

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Executes the deletion.

        Args:
            db_service (DatabaseService): The database service to use.

        Returns:
            CommandResult: Result object containing success status and messages.

        """
        try:
            # Store map and markers for undo
            self._deleted_map = db_service.get_map(self.map_id)
            if not self._deleted_map:
                return CommandResult(
                    success=False,
                    message=f"Map not found: {self.map_id}",
                    command_name="DeleteMapCommand",
                )

            self._deleted_markers = db_service.get_markers_for_map(self.map_id)

            db_service.delete_map(self.map_id)
            self._is_executed = True
            logger.info(f"Deleted map: {self.map_id}")
            return CommandResult(
                success=True,
                message=f"Map '{self._deleted_map.name}' deleted.",
                command_name="DeleteMapCommand",
            )
        except Exception as e:
            logger.error(f"Failed to delete map: {e}")
            return CommandResult(
                success=False,
                message=f"Failed to delete map: {e}",
                command_name="DeleteMapCommand",
            )

    def undo(self, db_service: DatabaseService) -> None:
        """Reverts the deletion by restoring the map and its markers.

        Args:
            db_service (DatabaseService): The database service to operate on.

        """
        if self._is_executed and self._deleted_map:
            db_service.insert_map(self._deleted_map)
            for marker in self._deleted_markers:
                db_service.insert_marker(marker)
            self._is_executed = False
            logger.info(f"Undid deletion of map: {self.map_id}")

    def to_dict(self) -> dict:
        """Serialize command to dictionary.

        Returns:
            Dictionary representation of the command.
        """
        return {"map_id": self.map_id}

    @classmethod
    def from_dict(cls, data: dict) -> "DeleteMapCommand":
        """Deserialize command from dictionary.

        Args:
            data: Dictionary containing serialized command data.

        Returns:
            DeleteMapCommand instance.
        """
        return cls(data["map_id"])


# --------------------------------------------------------------------------
# Marker Commands
# --------------------------------------------------------------------------


class CreateMarkerCommand(BaseCommand):
    """Command to create a new marker on a map."""

    def __init__(self, marker_data: dict) -> None:
        """Initializes the CreateMarkerCommand.

        Args:
            marker_data (dict): Dictionary containing marker data.
                               Must include: map_id, object_id, object_type, x, y.

        """
        super().__init__()
        self._marker = Marker(**marker_data)
        self._actual_marker_id: Optional[str] = None

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Executes the command to create the marker.

        Due to upsert behavior on UNIQUE(map_id, object_id, object_type),
        the returned marker ID may differ from the one in marker_data if
        a marker for this object already exists on this map.

        Args:
            db_service (DatabaseService): The database service to use.

        Returns:
            CommandResult: Result object indicating success or failure.

        """
        try:
            # Insert may return different ID if upsert occurred
            self._actual_marker_id = db_service.insert_marker(self._marker)
            self._is_executed = True
            logger.info(
                f"Created/updated marker: {self._actual_marker_id} for "
                f"{self._marker.object_type} {self._marker.object_id}"
            )
            return CommandResult(
                success=True,
                message="Marker created/updated.",
                command_name="CreateMarkerCommand",
                data={"id": self._actual_marker_id},
            )
        except Exception as e:
            logger.error(f"Failed to create marker: {e}")
            return CommandResult(
                success=False,
                message=f"Failed to create marker: {e}",
                command_name="CreateMarkerCommand",
            )

    def undo(self, db_service: DatabaseService) -> None:
        """Reverts the marker creation by deleting it from the database.

        Args:
            db_service (DatabaseService): The database service to operate on.

        """
        if self._is_executed and self._actual_marker_id:
            db_service.delete_marker(self._actual_marker_id)
            self._is_executed = False
            logger.info(f"Undid creation of marker: {self._actual_marker_id}")

    def to_dict(self) -> dict:
        """Serialize command to dictionary.

        Returns:
            Dictionary representation of the command.
        """
        return {"marker_data": self._marker.to_dict()}

    @classmethod
    def from_dict(cls, data: dict) -> "CreateMarkerCommand":
        """Deserialize command from dictionary.

        Args:
            data: Dictionary containing serialized command data.

        Returns:
            CreateMarkerCommand instance.
        """
        return cls(data["marker_data"])


class UpdateMarkerCommand(BaseCommand):
    """Command to update a marker's position or other properties."""

    def __init__(self, marker_id: str, update_data: dict) -> None:
        """Initializes the UpdateMarkerCommand.

        Args:
            marker_id (str): The ID of the marker to update.
            update_data (dict): Dictionary of fields to update (e.g., x, y, label).

        """
        super().__init__()
        self.marker_id = marker_id
        self.update_data = update_data
        self._previous_marker: Optional[Marker] = None
        self._new_marker: Optional[Marker] = None

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Executes the update.

        Args:
            db_service (DatabaseService): The database service to use.

        Returns:
            CommandResult: Result object containing success status and messages.

        """
        try:
            # Fetch current state before update
            current = db_service.get_marker(self.marker_id)
            if not current:
                logger.error(f"Marker not found for update: {self.marker_id}")
                return CommandResult(
                    success=False,
                    message=f"Marker not found: {self.marker_id}",
                    command_name="UpdateMarkerCommand",
                )

            self._previous_marker = current

            # Apply updates
            valid_fields = {f.name for f in dataclasses.fields(Marker)}
            clean_data = {
                k: v for k, v in self.update_data.items() if k in valid_fields
            }

            self._new_marker = dataclasses.replace(current, **clean_data)

            db_service.insert_marker(self._new_marker)
            self._is_executed = True
            logger.info(f"Updated marker: {self._new_marker.id}")
            return CommandResult(
                success=True,
                message="Marker updated.",
                command_name="UpdateMarkerCommand",
            )
        except Exception as e:
            logger.error(f"Failed to update marker: {e}")
            return CommandResult(
                success=False,
                message=f"Failed to update marker: {e}",
                command_name="UpdateMarkerCommand",
            )

    def undo(self, db_service: DatabaseService) -> None:
        """Reverts the marker update by restoring the previous state.

        Args:
            db_service (DatabaseService): The database service to operate on.

        """
        if self._is_executed and self._previous_marker:
            db_service.insert_marker(self._previous_marker)
            self._is_executed = False
            logger.info(f"Undid update of marker: {self.marker_id}")

    def to_dict(self) -> dict:
        """Serialize command to dictionary.

        Returns:
            Dictionary representation of the command.
        """
        return {"marker_id": self.marker_id, "update_data": self.update_data}

    @classmethod
    def from_dict(cls, data: dict) -> "UpdateMarkerCommand":
        """Deserialize command from dictionary.

        Args:
            data: Dictionary containing serialized command data.

        Returns:
            UpdateMarkerCommand instance.
        """
        return cls(data["marker_id"], data["update_data"])


class DeleteMarkerCommand(BaseCommand):
    """Command to delete a marker from a map."""

    def __init__(self, marker_id: str) -> None:
        """Initializes the DeleteMarkerCommand.

        Args:
            marker_id (str): The ID of the marker to delete.

        """
        super().__init__()
        self.marker_id = marker_id
        self._deleted_marker: Optional[Marker] = None

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Executes the deletion.

        Args:
            db_service (DatabaseService): The database service to use.

        Returns:
            CommandResult: Result object containing success status and messages.

        """
        try:
            # Store marker for undo
            self._deleted_marker = db_service.get_marker(self.marker_id)
            if not self._deleted_marker:
                return CommandResult(
                    success=False,
                    message=f"Marker not found: {self.marker_id}",
                    command_name="DeleteMarkerCommand",
                )

            db_service.delete_marker(self.marker_id)
            self._is_executed = True
            logger.info(f"Deleted marker: {self.marker_id}")
            return CommandResult(
                success=True,
                message="Marker deleted.",
                command_name="DeleteMarkerCommand",
            )
        except Exception as e:
            logger.error(f"Failed to delete marker: {e}")
            return CommandResult(
                success=False,
                message=f"Failed to delete marker: {e}",
                command_name="DeleteMarkerCommand",
            )

    def undo(self, db_service: DatabaseService) -> None:
        """Reverts the deletion by restoring the marker.

        Args:
            db_service (DatabaseService): The database service to operate on.

        """
        if self._is_executed and self._deleted_marker:
            db_service.insert_marker(self._deleted_marker)
            self._is_executed = False
            logger.info(f"Undid deletion of marker: {self.marker_id}")

    def to_dict(self) -> dict:
        """Serialize command to dictionary.

        Returns:
            Dictionary representation of the command.
        """
        return {"marker_id": self.marker_id}

    @classmethod
    def from_dict(cls, data: dict) -> "DeleteMarkerCommand":
        """Deserialize command from dictionary.

        Args:
            data: Dictionary containing serialized command data.

        Returns:
            DeleteMarkerCommand instance.
        """
        return cls(data["marker_id"])


class UpdateMarkerIconCommand(BaseCommand):
    """Command to update a marker's icon.

    Stores the icon filename in the marker's attributes dict.
    """

    def __init__(self, marker_id: str, icon: str) -> None:
        """Initializes the UpdateMarkerIconCommand.

        Args:
            marker_id (str): The ID of the marker to update.
            icon (str): The new icon filename (e.g., 'castle.svg').

        """
        super().__init__()
        self.marker_id = marker_id
        self.icon = icon
        self._previous_icon: Optional[str] = None
        self._marker: Optional[Marker] = None

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Executes the icon update.

        Args:
            db_service (DatabaseService): The database service to use.

        Returns:
            CommandResult: Result object containing success status and messages.

        """
        try:
            # Fetch current marker
            current = db_service.get_marker(self.marker_id)
            if not current:
                logger.error(f"Marker not found for icon update: {self.marker_id}")
                return CommandResult(
                    success=False,
                    message=f"Marker not found: {self.marker_id}",
                    command_name="UpdateMarkerIconCommand",
                )

            self._marker = current
            self._previous_icon = current.attributes.get("icon")

            # Update the icon in attributes
            new_attributes = dict(current.attributes)
            new_attributes["icon"] = self.icon

            # Create updated marker
            updated_marker = dataclasses.replace(current, attributes=new_attributes)

            db_service.insert_marker(updated_marker)
            self._is_executed = True
            logger.info(f"Updated marker {self.marker_id} icon to: {self.icon}")
            return CommandResult(
                success=True,
                message=f"Marker icon updated to {self.icon}.",
                command_name="UpdateMarkerIconCommand",
            )
        except Exception as e:
            logger.error(f"Failed to update marker icon: {e}")
            return CommandResult(
                success=False,
                message=f"Failed to update marker icon: {e}",
                command_name="UpdateMarkerIconCommand",
            )

    def undo(self, db_service: DatabaseService) -> None:
        """Reverts the icon update by restoring the previous icon.

        Args:
            db_service (DatabaseService): The database service to operate on.

        """
        if self._is_executed and self._marker:
            # Restore previous icon
            new_attributes = dict(self._marker.attributes)
            if self._previous_icon:
                new_attributes["icon"] = self._previous_icon
            else:
                new_attributes.pop("icon", None)

            restored_marker = dataclasses.replace(
                self._marker, attributes=new_attributes
            )
            db_service.insert_marker(restored_marker)
            self._is_executed = False
            logger.info(f"Undid icon update of marker: {self.marker_id}")

    def to_dict(self) -> dict:
        """Serialize command to dictionary."""
        return {"marker_id": self.marker_id, "icon": self.icon}

    @classmethod
    def from_dict(cls, data: dict) -> "UpdateMarkerIconCommand":
        """Deserialize command from dictionary."""
        return cls(data["marker_id"], data["icon"])


class UpdateMarkerColorCommand(BaseCommand):
    """Command to update a marker's color.

    Stores the color hex code in the marker's attributes dict.
    """

    def __init__(self, marker_id: str, color: str) -> None:
        """Initializes the UpdateMarkerColorCommand.

        Args:
            marker_id (str): The ID of the marker to update.
            color (str): The new color hex code (e.g., '#FF5733').

        """
        super().__init__()
        self.marker_id = marker_id
        self.color = color
        self._previous_color: Optional[str] = None
        self._marker: Optional[Marker] = None

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Executes the color update.

        Args:
            db_service (DatabaseService): The database service to use.

        Returns:
            CommandResult: Result object containing success status and messages.

        """
        try:
            # Fetch current marker
            current = db_service.get_marker(self.marker_id)
            if not current:
                logger.error(f"Marker not found for color update: {self.marker_id}")
                return CommandResult(
                    success=False,
                    message=f"Marker not found: {self.marker_id}",
                    command_name="UpdateMarkerColorCommand",
                )

            self._marker = current
            self._previous_color = current.attributes.get("color")

            # Update the color in attributes
            new_attributes = dict(current.attributes)
            new_attributes["color"] = self.color

            # Create updated marker
            updated_marker = dataclasses.replace(current, attributes=new_attributes)

            db_service.insert_marker(updated_marker)
            self._is_executed = True
            logger.info(f"Updated marker {self.marker_id} color to: {self.color}")
            return CommandResult(
                success=True,
                message=f"Marker color updated to {self.color}.",
                command_name="UpdateMarkerColorCommand",
            )
        except Exception as e:
            logger.error(f"Failed to update marker color: {e}")
            return CommandResult(
                success=False,
                message=f"Failed to update marker color: {e}",
                command_name="UpdateMarkerColorCommand",
            )

    def undo(self, db_service: DatabaseService) -> None:
        """Reverts the color update by restoring the previous color.

        Args:
            db_service (DatabaseService): The database service to operate on.

        """
        if self._is_executed and self._marker:
            # Restore previous color
            new_attributes = dict(self._marker.attributes)
            if self._previous_color:
                new_attributes["color"] = self._previous_color
            else:
                new_attributes.pop("color", None)

            restored_marker = dataclasses.replace(
                self._marker, attributes=new_attributes
            )
            db_service.insert_marker(restored_marker)
            self._is_executed = False
            logger.info(f"Undid color update of marker: {self.marker_id}")

    def to_dict(self) -> dict:
        """Serialize command to dictionary."""
        return {"marker_id": self.marker_id, "color": self.color}

    @classmethod
    def from_dict(cls, data: dict) -> "UpdateMarkerColorCommand":
        """Deserialize command from dictionary."""
        return cls(data["marker_id"], data["color"])


class DeleteKeyframeCommand(BaseCommand):
    """Command to delete a keyframe from a marker's trajectory."""

    def __init__(self, map_id: str, marker_id: str, t: float) -> None:
        """Initializes the DeleteKeyframeCommand.

        Args:
            map_id: The ID of the map.
            marker_id: The object ID of the marker (entity/event ID).
            t: The timestamp of the keyframe to delete.

        """
        super().__init__()
        self.map_id = map_id
        self.marker_id = marker_id
        self.t = t
        self._deleted_keyframe: Optional[tuple] = None  # (t, x, y) for undo

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Executes the keyframe deletion.

        Args:
            db_service: The database service to use.

        Returns:
            CommandResult: Result object containing success status and messages.

        """
        try:
            # Store keyframe for undo (get it before deletion)
            from src.core.trajectory import KEYFRAME_TIME_EPSILON

            trajectories = db_service.trajectory_repo.get_by_map_id(self.map_id)
            for marker_id_db, traj_id, keyframes in trajectories:
                if marker_id_db == self.marker_id:
                    for kf in keyframes:
                        if abs(kf.t - self.t) < KEYFRAME_TIME_EPSILON:
                            self._deleted_keyframe = (kf.t, kf.x, kf.y)
                            break
                    break

            result = db_service.trajectory_repo.delete_keyframe(
                self.map_id, self.marker_id, self.t
            )
            self._is_executed = True

            if result is None:
                logger.info(
                    f"Deleted keyframe at t={self.t:.2f} for {self.marker_id} "
                    f"(trajectory removed - <2 keyframes remaining)"
                )
            else:
                logger.info(f"Deleted keyframe at t={self.t:.2f} for {self.marker_id}")

            return CommandResult(
                success=True,
                message="Keyframe deleted.",
                command_name="DeleteKeyframeCommand",
            )
        except ValueError as e:
            logger.warning(f"Keyframe delete failed: {e}")
            return CommandResult(
                success=False,
                message=str(e),
                command_name="DeleteKeyframeCommand",
            )
        except Exception as e:
            logger.error(f"Failed to delete keyframe: {e}")
            return CommandResult(
                success=False,
                message=f"Failed to delete keyframe: {e}",
                command_name="DeleteKeyframeCommand",
            )

    def undo(self, db_service: DatabaseService) -> None:
        """Reverts the keyframe deletion by restoring it.

        Args:
            db_service: The database service to operate on.

        """
        if self._is_executed and self._deleted_keyframe:
            from src.core.trajectory import Keyframe

            t, x, y = self._deleted_keyframe
            keyframe = Keyframe(t=t, x=x, y=y)
            db_service.trajectory_repo.add_keyframe(
                self.map_id, self.marker_id, keyframe
            )
            self._is_executed = False
            logger.info(f"Undid deletion of keyframe at t={t:.2f} for {self.marker_id}")

    def to_dict(self) -> dict:
        """Serialize command to dictionary."""
        return {"map_id": self.map_id, "marker_id": self.marker_id, "t": self.t}

    @classmethod
    def from_dict(cls, data: dict) -> "DeleteKeyframeCommand":
        """Deserialize command from dictionary."""
        return cls(data["map_id"], data["marker_id"], data["t"])


# --------------------------------------------------------------------------
# Layer Commands (undo/redo for layer operations)
# --------------------------------------------------------------------------


def _find_layer_node(
    root: MapLayerNode, node_id: str
) -> Optional[MapLayerNode]:
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
    ) -> None:
        """Initialise the command.

        Args:
            map_id: The map whose layer tree is being modified.
            node_id: ID of the layer node to toggle.
            visible: New visibility state.

        """
        super().__init__()
        self.map_id = map_id
        self.node_id = node_id
        self.visible = visible
        self._previous_visible: Optional[bool] = None

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Execute the visibility change and persist.

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

            # Persist
            attrs = dict(map_obj.attributes) if map_obj.attributes else {}
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
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SetLayerVisibilityCommand":
        """Deserialize command from dictionary."""
        return cls(data["map_id"], data["node_id"], data["visible"])


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

            node = _find_layer_node(
                map_obj.layers, self.node_id
            )
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

            # Remove from old parent
            old_parent.children.remove(node)

            # Find new parent and insert
            new_parent = _find_layer_node(
                map_obj.layers, self.new_parent_id
            )
            if not new_parent:
                # Rollback
                old_parent.children.insert(self._old_row, node)
                return CommandResult(
                    success=False,
                    message=f"New parent {self.new_parent_id} not found.",
                    command_name="MoveLayerCommand",
                )

            insert_row = min(self.new_row, len(new_parent.children))
            new_parent.children.insert(insert_row, node)

            # Persist
            attrs = dict(map_obj.attributes) if map_obj.attributes else {}
            attrs["layers"] = map_obj.layers.to_dict()
            map_obj.attributes = attrs
            db_service.map_repo.insert_map(map_obj)

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
                node = _find_layer_node(
                    map_obj.layers, self.node_id
                )
                if node:
                    # Remove from current position
                    cur_parent = self._find_parent(map_obj.layers, node)
                    if cur_parent:
                        cur_parent.children.remove(node)
                    # Insert back at old position
                    old_parent = _find_layer_node(
                        map_obj.layers, self._old_parent_id
                    )
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
            data["map_id"], data["node_id"],
            data["new_parent_id"], data["new_row"],
        )

    @staticmethod
    def _find_parent(
        root: MapLayerNode, node: MapLayerNode
    ) -> Optional[MapLayerNode]:
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
    ) -> None:
        """Initialise the command.

        Args:
            map_id: The map whose layer tree is being modified.
            node_id: ID of the layer node to change.
            opacity: New opacity (0.0–1.0).

        """
        super().__init__()
        self.map_id = map_id
        self.node_id = node_id
        self.opacity = opacity
        self._previous_opacity: Optional[float] = None

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Execute the opacity change and persist.

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
                    command_name="SetLayerOpacityCommand",
                )

            node = _find_layer_node(
                map_obj.layers, self.node_id
            )
            if not node:
                return CommandResult(
                    success=False,
                    message=f"Layer node {self.node_id} not found.",
                    command_name="SetLayerOpacityCommand",
                )

            self._previous_opacity = node.opacity
            node.opacity = max(0.0, min(1.0, self.opacity))

            # Persist
            attrs = dict(map_obj.attributes) if map_obj.attributes else {}
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
                node = _find_layer_node(
                    map_obj.layers, self.node_id
                )
                if node:
                    node.opacity = self._previous_opacity
                    attrs = (
                        dict(map_obj.attributes) if map_obj.attributes else {}
                    )
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
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SetLayerOpacityCommand":
        """Deserialize command from dictionary."""
        return cls(data["map_id"], data["node_id"], data["opacity"])


class RenameLayerCommand(BaseCommand):
    """Command to rename a layer node (undoable).

    Persists the layer tree to the map's attributes after the change.
    """

    def __init__(
        self,
        map_id: str,
        node_id: str,
        new_name: str,
    ) -> None:
        """Initialise the command.

        Args:
            map_id: The map whose layer tree is being modified.
            node_id: ID of the layer node to rename.
            new_name: New display name.

        """
        super().__init__()
        self.map_id = map_id
        self.node_id = node_id
        self.new_name = new_name
        self._previous_name: Optional[str] = None

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Execute the rename and persist.

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
                    command_name="RenameLayerCommand",
                )

            node = _find_layer_node(
                map_obj.layers, self.node_id
            )
            if not node:
                return CommandResult(
                    success=False,
                    message=f"Layer node {self.node_id} not found.",
                    command_name="RenameLayerCommand",
                )

            self._previous_name = node.name
            node.name = self.new_name

            # Persist
            attrs = dict(map_obj.attributes) if map_obj.attributes else {}
            attrs["layers"] = map_obj.layers.to_dict()
            map_obj.attributes = attrs
            db_service.map_repo.insert_map(map_obj)

            self._is_executed = True
            return CommandResult(
                success=True,
                message=f"Layer renamed to '{self.new_name}'.",
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
        """Revert the rename.

        Args:
            db_service: The database service.

        """
        if self._is_executed and self._previous_name is not None:
            map_obj = db_service.map_repo.get_map(self.map_id)
            if map_obj and map_obj.layers:
                node = _find_layer_node(
                    map_obj.layers, self.node_id
                )
                if node:
                    node.name = self._previous_name
                    attrs = (
                        dict(map_obj.attributes) if map_obj.attributes else {}
                    )
                    attrs["layers"] = map_obj.layers.to_dict()
                    map_obj.attributes = attrs
                    db_service.map_repo.insert_map(map_obj)
            self._is_executed = False

    def to_dict(self) -> dict:
        """Serialize command to dictionary."""
        return {
            "map_id": self.map_id,
            "node_id": self.node_id,
            "new_name": self.new_name,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RenameLayerCommand":
        """Deserialize command from dictionary."""
        return cls(data["map_id"], data["node_id"], data["new_name"])
