"""Commands for creating, updating, and deleting Map objects.

These commands handle map-level CRUD operations — they do not touch
individual markers or the layer hierarchy.
"""

import dataclasses
import logging
from typing import List, Optional

from src.commands.base_command import BaseCommand, CommandResult
from src.core.map import Map
from src.core.marker import Marker
from src.services.db_service import DatabaseService

logger = logging.getLogger(__name__)


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
