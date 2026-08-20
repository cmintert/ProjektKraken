"""Commands for creating, updating, and deleting map markers and features.

These commands handle marker-level CRUD operations including position
updates, icon/color changes, and keyframe deletions.
"""

import dataclasses
import logging
from typing import Optional

from src.commands.base_command import BaseCommand, CommandResult
from src.core.marker import Marker
from src.services.db_service import DatabaseService

logger = logging.getLogger(__name__)


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
        self.map_id = self._marker.map_id
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
            existing = db_service.get_marker_by_composite(
                self._marker.map_id,
                self._marker.object_id,
                self._marker.object_type,
            )
            if existing is not None:
                return CommandResult(
                    success=False,
                    message=(
                        "This object is already placed on the selected map. "
                        "Move the existing marker instead."
                    ),
                    command_name="CreateMarkerCommand",
                    data={"existing_marker_id": existing.id},
                )
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
                data={
                    "id": self._actual_marker_id,
                    "map_id": self.map_id,
                },
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
        return {
            "marker_data": self._marker.to_dict(),
            "actual_marker_id": self._actual_marker_id,
            "is_executed": self._is_executed,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CreateMarkerCommand":
        """Deserialize command from dictionary.

        Args:
            data: Dictionary containing serialized command data.

        Returns:
            CreateMarkerCommand instance.
        """
        instance = cls(data["marker_data"])
        instance._actual_marker_id = data.get("actual_marker_id")
        instance._is_executed = bool(
            data.get("is_executed", instance._actual_marker_id)
        )
        return instance


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
        self._deleted_trajectories: list[dict] = []
        self._deleted_geometry_states: list[dict] = []

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

            self._deleted_trajectories = (
                db_service.trajectory_repo.snapshot_by_marker(self.marker_id)
            )
            self._deleted_geometry_states = (
                db_service.feature_geometry_repo.snapshot_by_marker(self.marker_id)
            )
            rows_deleted = db_service.delete_marker(self.marker_id)
            if rows_deleted == 0:
                return CommandResult(
                    success=False,
                    message=f"Marker delete confirmed 0 rows: {self.marker_id}",
                    command_name="DeleteMarkerCommand",
                )
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
            with db_service.transaction():
                db_service.insert_marker(self._deleted_marker)
                for trajectory in self._deleted_trajectories:
                    db_service.trajectory_repo.restore_snapshot(trajectory)
                for state in self._deleted_geometry_states:
                    db_service.feature_geometry_repo.restore_snapshot(state)
            self._is_executed = False
            logger.info(f"Undid deletion of marker: {self.marker_id}")

    def to_dict(self) -> dict:
        """Serialize command to dictionary.

        Returns:
            Dictionary representation of the command.
        """
        return {
            "marker_id": self.marker_id,
            "deleted_marker": (
                self._deleted_marker.to_dict() if self._deleted_marker else None
            ),
            "deleted_trajectories": self._deleted_trajectories,
            "deleted_geometry_states": self._deleted_geometry_states,
            "is_executed": self._is_executed,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DeleteMarkerCommand":
        """Deserialize command from dictionary.

        Args:
            data: Dictionary containing serialized command data.

        Returns:
            DeleteMarkerCommand instance.
        """
        command = cls(data["marker_id"])
        marker_data = data.get("deleted_marker")
        if marker_data:
            command._deleted_marker = Marker.from_dict(marker_data)
        command._deleted_trajectories = list(
            data.get("deleted_trajectories", [])
        )
        command._deleted_geometry_states = list(
            data.get("deleted_geometry_states", [])
        )
        command._is_executed = bool(data.get("is_executed", marker_data))
        return command


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


class UpdateMarkerAttributeCommand(BaseCommand):
    """Command to update visual-style keys in a marker's attributes dict.

    Merges the provided key/value pairs into the marker's ``attributes``
    and supports full undo by restoring the previous attribute snapshot.
    """

    def __init__(self, marker_id: str, updates: dict) -> None:
        """Initializes the UpdateMarkerAttributeCommand.

        Args:
            marker_id: The ID of the marker to update.
            updates: Dictionary of attribute keys/values to merge
                (e.g. ``{"_v_size_scale": 1.5, "_v_border_width": 4}``).
        """
        super().__init__()
        self.marker_id = marker_id
        self.updates = updates
        self._previous_attributes: Optional[dict] = None
        self._marker: Optional[Marker] = None

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Executes the attribute update.

        Args:
            db_service: The database service to use.

        Returns:
            CommandResult: Result object containing success status.
        """
        try:
            current = db_service.get_marker(self.marker_id)
            if not current:
                return CommandResult(
                    success=False,
                    message=f"Marker not found: {self.marker_id}",
                    command_name="UpdateMarkerAttributeCommand",
                )

            self._marker = current
            self._previous_attributes = dict(current.attributes)

            new_attributes = dict(current.attributes)
            new_attributes.update(self.updates)

            updated = dataclasses.replace(current, attributes=new_attributes)
            db_service.insert_marker(updated)
            self._is_executed = True
            logger.info(
                f"Updated marker {self.marker_id} attributes: "
                f"{list(self.updates.keys())}"
            )
            return CommandResult(
                success=True,
                message="Marker attributes updated.",
                command_name="UpdateMarkerAttributeCommand",
            )
        except Exception as e:
            logger.error(f"Failed to update marker attributes: {e}")
            return CommandResult(
                success=False,
                message=f"Failed to update marker attributes: {e}",
                command_name="UpdateMarkerAttributeCommand",
            )

    def undo(self, db_service: DatabaseService) -> None:
        """Reverts the attribute update by restoring previous attributes.

        Args:
            db_service: The database service to operate on.
        """
        if self._is_executed and self._marker and self._previous_attributes is not None:
            restored = dataclasses.replace(
                self._marker, attributes=self._previous_attributes
            )
            db_service.insert_marker(restored)
            self._is_executed = False
            logger.info(f"Undid attribute update of marker: {self.marker_id}")

    def to_dict(self) -> dict:
        """Serialize command to dictionary."""
        return {"marker_id": self.marker_id, "updates": self.updates}

    @classmethod
    def from_dict(cls, data: dict) -> "UpdateMarkerAttributeCommand":
        """Deserialize command from dictionary."""
        return cls(data["marker_id"], data["updates"])


class ApplyMarkerAppearanceCommand(BaseCommand):
    """Replace one marker's complete copyable appearance atomically."""

    def __init__(self, marker_id: str, appearance: dict) -> None:
        """Initialize an exact marker appearance replacement."""
        super().__init__()
        from src.core.marker_appearance import MarkerAppearance

        self.marker_id = marker_id
        self.appearance = MarkerAppearance.from_dict(appearance).to_dict()
        self._previous_attributes: Optional[dict] = None
        self._marker: Optional[Marker] = None

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Replace appearance keys while preserving semantic attributes."""
        from src.core.marker_appearance import MarkerAppearance

        try:
            current = db_service.get_marker(self.marker_id)
            if current is None:
                return CommandResult(
                    success=False,
                    message=f"Marker not found: {self.marker_id}",
                    command_name="ApplyMarkerAppearanceCommand",
                )
            self._marker = current
            self._previous_attributes = dict(current.attributes)
            appearance = MarkerAppearance.from_dict(self.appearance)
            updated = dataclasses.replace(
                current,
                attributes=appearance.apply_to_attributes(current.attributes),
            )
            db_service.insert_marker(updated)
            self._is_executed = True
            logger.info("Applied marker appearance: %s", self.marker_id)
            return CommandResult(
                success=True,
                message="Marker appearance applied.",
                command_name="ApplyMarkerAppearanceCommand",
            )
        except Exception as exc:
            logger.error("Failed to apply marker appearance: %s", exc)
            return CommandResult(
                success=False,
                message=f"Failed to apply marker appearance: {exc}",
                command_name="ApplyMarkerAppearanceCommand",
            )

    def undo(self, db_service: DatabaseService) -> None:
        """Restore the exact attribute snapshot from before the change."""
        if self._is_executed and self._marker and self._previous_attributes is not None:
            restored = dataclasses.replace(
                self._marker,
                attributes=self._previous_attributes,
            )
            db_service.insert_marker(restored)
            self._is_executed = False
            logger.info("Undid marker appearance change: %s", self.marker_id)

    def to_dict(self) -> dict:
        """Serialize the command."""
        return {"marker_id": self.marker_id, "appearance": self.appearance}

    @classmethod
    def from_dict(cls, data: dict) -> "ApplyMarkerAppearanceCommand":
        """Deserialize the command."""
        return cls(data["marker_id"], data["appearance"])
