"""
Map Commands Module.

Provides command classes for managing maps and markers:
- CreateMapCommand: Create new maps with calibration data
- UpdateMapCommand: Modify existing maps
- DeleteMapCommand: Remove maps (cascades to markers)
- AddMarkerCommand: Place entities/events on maps
- UpdateMarkerCommand: Move markers or update attributes
- DeleteMarkerCommand: Remove markers from maps

All commands support undo/redo operations and return CommandResult objects.
"""

from src.commands.base_command import BaseCommand, CommandResult
from src.core.maps import GameMap, MapMarker
from src.services.db_service import DatabaseService
import logging
import dataclasses
import time
from typing import Optional, List

logger = logging.getLogger(__name__)


class CreateMapCommand(BaseCommand):
    """
    Command to create a new map.
    """

    def __init__(self, map_data: dict = None):
        """
        Initializes the CreateMapCommand.

        Args:
            map_data (dict, optional): Dictionary containing map data.
                                       If None, default values are used.
        """
        super().__init__()
        if map_data:
            self.game_map = GameMap(**map_data)
        else:
            # Default Map
            self.game_map = GameMap(
                name="New Map",
                image_filename="",
                real_width=100.0,
                distance_unit="m",
                reference_width=1000,
                reference_height=1000,
            )

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """
        Executes the command to insert the map into the database.

        Args:
            db_service (DatabaseService): The database service to use.

        Returns:
            CommandResult: Result object indicating success or failure.
        """
        try:
            logger.info(f"Executing CreateMap: {self.game_map.name}")
            db_service.insert_map(self.game_map)
            self._is_executed = True
            return CommandResult(
                success=True,
                message=f"Map '{self.game_map.name}' created.",
                command_name="CreateMapCommand",
                data={"id": self.game_map.id},
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
        if not self._is_executed:
            return

        logger.info(f"Undoing CreateMap: {self.game_map.name}")
        db_service.delete_map(self.game_map.id)
        self._is_executed = False


class UpdateMapCommand(BaseCommand):
    """
    Command to update an existing map.
    Accepts a dictionary of changes to apply to the existing map.
    Snapshots the clean state before update for undo.
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
        self._previous_map: Optional[GameMap] = None
        self._new_map: Optional[GameMap] = None

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """
        Executes the update.

        Args:
            db_service (DatabaseService): The database service to use.

        Returns:
            CommandResult: Result object containing success status and messages.
        """
        # 1. Snapshot current state from DB
        current = db_service.get_map(self.map_id)
        if not current:
            return CommandResult(
                success=False,
                message=f"Cannot update map {self.map_id}: Not found",
                command_name="UpdateMapCommand",
            )

        self._previous_map = current

        # 2. Apply Updates
        try:
            # Validation
            if "name" in self.update_data:
                new_name = self.update_data["name"]
                if not new_name or not new_name.strip():
                    return CommandResult(
                        success=False,
                        message="Map name cannot be empty.",
                        command_name="UpdateMapCommand",
                    )

            valid_fields = {f.name for f in dataclasses.fields(GameMap)}
            clean_data = {
                k: v for k, v in self.update_data.items() if k in valid_fields
            }

            self._new_map = dataclasses.replace(current, **clean_data)
            self._new_map.modified_at = time.time()

            logger.info(f"Executing UpdateMap: {self._new_map.name}")
            db_service.insert_map(self._new_map)
            self._is_executed = True

            return CommandResult(
                success=True,
                message="Map updated successfully.",
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
        Reverts the update by restoring the previous state of the map.
        """
        if self._is_executed and self._previous_map:
            logger.info(f"Undoing UpdateMap: Reverting to {self._previous_map.name}")
            db_service.insert_map(self._previous_map)
            self._is_executed = False


class DeleteMapCommand(BaseCommand):
    """
    Command to delete a map, storing its state for undo.
    Note: This will cascade delete all markers on this map.
    """

    def __init__(self, map_id: str):
        """
        Initializes the DeleteMapCommand.

        Args:
            map_id (str): The ID of the map to delete.
        """
        super().__init__()
        self.map_id = map_id
        self._backup_map: Optional[GameMap] = None
        self._backup_markers: List[MapMarker] = []

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """
        Executes the command to delete the map.

        Args:
            db_service (DatabaseService): The database service to use.

        Returns:
            CommandResult: Result object indicating success or failure.
        """
        # Backup before delete
        self._backup_map = db_service.get_map(self.map_id)
        if not self._backup_map:
            logger.warning(f"Cannot delete map {self.map_id}: Not found")
            return CommandResult(
                success=False,
                message=f"Cannot delete map {self.map_id}: Not found",
                command_name="DeleteMapCommand",
            )

        # Backup markers for undo
        self._backup_markers = db_service.get_markers_for_map(self.map_id)

        try:
            db_service.delete_map(self.map_id)
            self._is_executed = True
            return CommandResult(
                success=True,
                message="Map deleted.",
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
        Reverts the map deletion by restoring it and its markers to the database.

        Args:
            db_service (DatabaseService): The database service to operate on.
        """
        if self._is_executed and self._backup_map:
            logger.info(f"Undoing DeleteMap: Restoring {self._backup_map.name}")
            db_service.insert_map(self._backup_map)
            # Restore markers
            for marker in self._backup_markers:
                db_service.insert_marker(marker)
            self._is_executed = False


class AddMarkerCommand(BaseCommand):
    """
    Command to add a marker to a map.
    """

    def __init__(self, marker_data: dict = None):
        """
        Initializes the AddMarkerCommand.

        Args:
            marker_data (dict, optional): Dictionary containing marker data.
        """
        super().__init__()
        if marker_data:
            self.marker = MapMarker(**marker_data)
        else:
            raise ValueError("marker_data is required for AddMarkerCommand")

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """
        Executes the command to insert the marker into the database.

        Args:
            db_service (DatabaseService): The database service to use.

        Returns:
            CommandResult: Result object indicating success or failure.
        """
        try:
            # Validate that the map exists
            if not db_service.get_map(self.marker.map_id):
                return CommandResult(
                    success=False,
                    message=f"Cannot add marker: Map {self.marker.map_id} not found",
                    command_name="AddMarkerCommand",
                )

            logger.info(
                f"Executing AddMarker: {self.marker.object_type} "
                f"{self.marker.object_id} on map {self.marker.map_id}"
            )
            db_service.insert_marker(self.marker)
            self._is_executed = True
            return CommandResult(
                success=True,
                message="Marker added to map.",
                command_name="AddMarkerCommand",
                data={"id": self.marker.id},
            )
        except Exception as e:
            logger.error(f"Failed to add marker: {e}")
            return CommandResult(
                success=False,
                message=f"Failed to add marker: {e}",
                command_name="AddMarkerCommand",
            )

    def undo(self, db_service: DatabaseService) -> None:
        """
        Reverts the marker addition by deleting it from the database.

        Args:
            db_service (DatabaseService): The database service to operate on.
        """
        if not self._is_executed:
            return

        logger.info(f"Undoing AddMarker: {self.marker.id}")
        db_service.delete_marker(self.marker.id)
        self._is_executed = False


class UpdateMarkerCommand(BaseCommand):
    """
    Command to update an existing marker (position or attributes).
    """

    def __init__(self, marker_id: str, update_data: dict):
        """
        Initializes the UpdateMarkerCommand.

        Args:
            marker_id (str): The ID of the marker to update.
            update_data (dict): Dictionary of fields to update.
        """
        super().__init__()
        self.marker_id = marker_id
        self.update_data = update_data
        self._previous_marker: Optional[MapMarker] = None
        self._new_marker: Optional[MapMarker] = None

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """
        Executes the update.

        Args:
            db_service (DatabaseService): The database service to use.

        Returns:
            CommandResult: Result object containing success status and messages.
        """
        # 1. Snapshot current state from DB
        current = db_service.get_marker(self.marker_id)
        if not current:
            return CommandResult(
                success=False,
                message=f"Cannot update marker {self.marker_id}: Not found",
                command_name="UpdateMarkerCommand",
            )

        self._previous_marker = current

        # 2. Apply Updates
        try:
            valid_fields = {f.name for f in dataclasses.fields(MapMarker)}
            clean_data = {
                k: v for k, v in self.update_data.items() if k in valid_fields
            }

            self._new_marker = dataclasses.replace(current, **clean_data)

            logger.info(f"Executing UpdateMarker: {self.marker_id}")
            db_service.insert_marker(self._new_marker)
            self._is_executed = True

            return CommandResult(
                success=True,
                message="Marker updated successfully.",
                command_name="UpdateMarkerCommand",
            )
        except ValueError as e:
            # Coordinate validation errors
            logger.error(f"Failed to update marker: {e}")
            return CommandResult(
                success=False,
                message=f"Invalid marker data: {e}",
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
        Reverts the update by restoring the previous state of the marker.
        """
        if self._is_executed and self._previous_marker:
            logger.info(f"Undoing UpdateMarker: {self.marker_id}")
            db_service.insert_marker(self._previous_marker)
            self._is_executed = False


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
        self._backup_marker: Optional[MapMarker] = None

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """
        Executes the command to delete the marker.

        Args:
            db_service (DatabaseService): The database service to use.

        Returns:
            CommandResult: Result object indicating success or failure.
        """
        # Backup before delete
        self._backup_marker = db_service.get_marker(self.marker_id)
        if not self._backup_marker:
            logger.warning(f"Cannot delete marker {self.marker_id}: Not found")
            return CommandResult(
                success=False,
                message=f"Cannot delete marker {self.marker_id}: Not found",
                command_name="DeleteMarkerCommand",
            )

        try:
            db_service.delete_marker(self.marker_id)
            self._is_executed = True
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
        Reverts the marker deletion by restoring it to the database.

        Args:
            db_service (DatabaseService): The database service to operate on.
        """
        if self._is_executed and self._backup_marker:
            logger.info(f"Undoing DeleteMarker: {self.marker_id}")
            db_service.insert_marker(self._backup_marker)
            self._is_executed = False
