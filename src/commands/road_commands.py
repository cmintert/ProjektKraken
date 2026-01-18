"""Commands for manipulating road networks on maps.

These commands handle creating, updating, and deleting road network data
stored in map.attributes["_roads"].
"""

import json
import logging
import time
from typing import Optional

from src.commands.base_command import BaseCommand, CommandResult
from src.core.road import RoadNetwork
from src.services.db_service import DatabaseService

logger = logging.getLogger(__name__)


class UpdateMapRoadsCommand(BaseCommand):
    """Command to update the road network for a map.

    Stores road network in map.attributes["_roads"] as JSON.
    """

    def __init__(self, map_id: str, road_network: RoadNetwork) -> None:
        """Initializes the UpdateMapRoadsCommand.

        Args:
            map_id: ID of the map to update.
            road_network: RoadNetwork instance with road data.
        """
        super().__init__()
        self.map_id = map_id
        self.road_network = road_network
        self._previous_roads: Optional[dict] = None

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Executes the command to update map roads.

        Args:
            db_service: The database service to use.

        Returns:
            CommandResult: Result object indicating success or failure.
        """
        try:
            # Get the map
            map_obj = db_service.get_map(self.map_id)
            if not map_obj:
                return CommandResult(
                    success=False,
                    message=f"Map with ID {self.map_id} not found.",
                    command_name="UpdateMapRoadsCommand",
                )

            # Store previous roads for undo
            self._previous_roads = map_obj.attributes.get("_roads")

            # Update roads in attributes
            self.road_network.meta["modified_at"] = time.time()
            map_obj.attributes["_roads"] = self.road_network.to_dict()
            map_obj.modified_at = time.time()

            # Save to database
            db_service.insert_map(map_obj)

            self._is_executed = True
            logger.info(
                f"Updated roads for map {self.map_id}: "
                f"{len(self.road_network.nodes)} nodes, "
                f"{len(self.road_network.segments)} segments"
            )

            return CommandResult(
                success=True,
                message=f"Roads updated for map '{map_obj.name}'.",
                command_name="UpdateMapRoadsCommand",
                data={"map_id": self.map_id},
            )

        except Exception as e:
            logger.error(f"Failed to update map roads: {e}")
            return CommandResult(
                success=False,
                message=f"Failed to update roads: {e}",
                command_name="UpdateMapRoadsCommand",
            )

    def undo(self, db_service: DatabaseService) -> None:
        """Reverts the road network update.

        Args:
            db_service: The database service to operate on.
        """
        if not self._is_executed:
            return

        try:
            map_obj = db_service.get_map(self.map_id)
            if map_obj:
                # Restore previous roads (may be None)
                if self._previous_roads is None:
                    if "_roads" in map_obj.attributes:
                        del map_obj.attributes["_roads"]
                else:
                    map_obj.attributes["_roads"] = self._previous_roads

                map_obj.modified_at = time.time()
                db_service.insert_map(map_obj)

            self._is_executed = False
            logger.info(f"Undid road update for map: {self.map_id}")

        except Exception as e:
            logger.error(f"Failed to undo road update: {e}")


class ClearMapRoadsCommand(BaseCommand):
    """Command to clear all roads from a map."""

    def __init__(self, map_id: str) -> None:
        """Initializes the ClearMapRoadsCommand.

        Args:
            map_id: ID of the map to clear roads from.
        """
        super().__init__()
        self.map_id = map_id
        self._previous_roads: Optional[dict] = None

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Executes the command to clear map roads.

        Args:
            db_service: The database service to use.

        Returns:
            CommandResult: Result object indicating success or failure.
        """
        try:
            # Get the map
            map_obj = db_service.get_map(self.map_id)
            if not map_obj:
                return CommandResult(
                    success=False,
                    message=f"Map with ID {self.map_id} not found.",
                    command_name="ClearMapRoadsCommand",
                )

            # Store previous roads for undo
            self._previous_roads = map_obj.attributes.get("_roads")

            # Clear roads
            if "_roads" in map_obj.attributes:
                del map_obj.attributes["_roads"]
                map_obj.modified_at = time.time()
                db_service.insert_map(map_obj)

            self._is_executed = True
            logger.info(f"Cleared roads for map {self.map_id}")

            return CommandResult(
                success=True,
                message=f"Roads cleared for map '{map_obj.name}'.",
                command_name="ClearMapRoadsCommand",
                data={"map_id": self.map_id},
            )

        except Exception as e:
            logger.error(f"Failed to clear map roads: {e}")
            return CommandResult(
                success=False,
                message=f"Failed to clear roads: {e}",
                command_name="ClearMapRoadsCommand",
            )

    def undo(self, db_service: DatabaseService) -> None:
        """Reverts the road clearing.

        Args:
            db_service: The database service to operate on.
        """
        if not self._is_executed:
            return

        try:
            map_obj = db_service.get_map(self.map_id)
            if map_obj and self._previous_roads is not None:
                map_obj.attributes["_roads"] = self._previous_roads
                map_obj.modified_at = time.time()
                db_service.insert_map(map_obj)

            self._is_executed = False
            logger.info(f"Undid road clearing for map: {self.map_id}")

        except Exception as e:
            logger.error(f"Failed to undo road clearing: {e}")
