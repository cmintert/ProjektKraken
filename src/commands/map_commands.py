"""
Commands for manipulating Map and Marker objects.

API Usage Note:
===============
These commands accept `db_service` in the `execute()` method parameter,
matching the project's standard command pattern used across other modules
(entity_commands, event_commands, etc.). This design allows commands to be
instantiated without database coupling and executed later with the appropriate
database service instance.
"""

import dataclasses
import logging
from typing import Optional

from src.commands.base_command import BaseCommand, CommandResult
from src.core.map import Map
from src.core.marker import Marker
from src.services.db_service import DatabaseService

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# Map Commands
# --------------------------------------------------------------------------


class CreateMapCommand(BaseCommand):
    """
    Command to create a new map.
    """

    def __init__(self, map_data: Optional[dict] = None):
        """
        Initializes the CreateMapCommand.

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
        """
        Executes the command to create the map.

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
        """
        Reverts the map creation by deleting it from the database.

        Args:
            db_service (DatabaseService): The database service to operate on.
        """
        if self._is_executed:
            db_service.delete_map(self._map.id)
            self._is_executed = False
            logger.info(f"Undid creation of map: {self._map.id}")


class UpdateMapCommand(BaseCommand):
    """
    Command to update an existing map.
    Accepts a dictionary of changes.
    """

    def __init__(self, map_id: str, update_data: dict):
        """
        Initializes the UpdateMapCommand.

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
        """
        Executes the update.

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
        """
        Reverts the map update by restoring the previous state.

        Args:
            db_service (DatabaseService): The database service to operate on.
        """
        if self._is_executed and self._previous_map:
            db_service.insert_map(self._previous_map)
            self._is_executed = False
            logger.info(f"Undid update of map: {self.map_id}")


class DeleteMapCommand(BaseCommand):
    """
    Command to delete a map and all its markers.
    """

    def __init__(self, map_id: str):
        """
        Initializes the DeleteMapCommand.

        Args:
            map_id (str): The ID of the map to delete.
        """
        super().__init__()
        self.map_id = map_id
        self._deleted_map: Optional[Map] = None
        self._deleted_markers: list = []

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """
        Executes the deletion.

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
        """
        Reverts the deletion by restoring the map and its markers.

        Args:
            db_service (DatabaseService): The database service to operate on.
        """
        if self._is_executed and self._deleted_map:
            db_service.insert_map(self._deleted_map)
            for marker in self._deleted_markers:
                db_service.insert_marker(marker)
            self._is_executed = False
            logger.info(f"Undid deletion of map: {self.map_id}")


# --------------------------------------------------------------------------
# Marker Commands
# --------------------------------------------------------------------------


class CreateMarkerCommand(BaseCommand):
    """
    Command to create a new marker on a map.
    """

    def __init__(self, marker_data: dict):
        """
        Initializes the CreateMarkerCommand.

        Args:
            marker_data (dict): Dictionary containing marker data.
                               Must include: map_id, object_id, object_type, x, y.
        """
        super().__init__()
        self._marker = Marker(**marker_data)
        self._actual_marker_id: Optional[str] = None

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """
        Executes the command to create the marker.

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
        """
        Reverts the marker creation by deleting it from the database.

        Args:
            db_service (DatabaseService): The database service to operate on.
        """
        if self._is_executed and self._actual_marker_id:
            db_service.delete_marker(self._actual_marker_id)
            self._is_executed = False
            logger.info(f"Undid creation of marker: {self._actual_marker_id}")


class UpdateMarkerCommand(BaseCommand):
    """
    Command to update a marker's position or other properties.
    """

    def __init__(self, marker_id: str, update_data: dict):
        """
        Initializes the UpdateMarkerCommand.

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
        """
        Executes the update.

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
        """
        Reverts the marker update by restoring the previous state.

        Args:
            db_service (DatabaseService): The database service to operate on.
        """
        if self._is_executed and self._previous_marker:
            db_service.insert_marker(self._previous_marker)
            self._is_executed = False
            logger.info(f"Undid update of marker: {self.marker_id}")


class DeleteMarkerCommand(BaseCommand):
    """
    Command to delete a marker from a map.
    """

    def __init__(self, marker_id: str):
        """
        Initializes the DeleteMarkerCommand.

        Args:
            marker_id (str): The ID of the marker to delete.
        """
        super().__init__()
        self.marker_id = marker_id
        self._deleted_marker: Optional[Marker] = None

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """
        Executes the deletion.

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
        """
        Reverts the deletion by restoring the marker.

        Args:
            db_service (DatabaseService): The database service to operate on.
        """
        if self._is_executed and self._deleted_marker:
            db_service.insert_marker(self._deleted_marker)
            self._is_executed = False
            logger.info(f"Undid deletion of marker: {self.marker_id}")


class UpdateMarkerIconCommand(BaseCommand):
    """
    Command to update a marker's icon.

    Stores the icon filename in the marker's attributes dict.
    """

    def __init__(self, marker_id: str, icon: str):
        """
        Initializes the UpdateMarkerIconCommand.

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
        """
        Executes the icon update.

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
        """
        Reverts the icon update by restoring the previous icon.

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


class UpdateMarkerColorCommand(BaseCommand):
    """
    Command to update a marker's color.

    Stores the color hex code in the marker's attributes dict.
    """

    def __init__(self, marker_id: str, color: str):
        """
        Initializes the UpdateMarkerColorCommand.

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
        """
        Executes the color update.

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
        """
        Reverts the color update by restoring the previous color.

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
