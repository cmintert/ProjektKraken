"""Commands for creating, updating, and deleting Map objects.

These commands handle map-level CRUD operations — they do not touch
individual markers or the layer hierarchy.
"""

import dataclasses
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.commands.base_command import BaseCommand, CommandResult
from src.core.map import Map
from src.core.map_constants import MAP_ROLE_DETAIL, MAP_ROLE_MASTER
from src.core.map_state import MapAggregateSnapshot
from src.core.marker import Marker
from src.services.command_artifact_store import CommandArtifactStore
from src.services.db_service import DatabaseService
from src.services.map_aggregate_service import MapAggregateService
from src.services.map_nesting_service import (
    MapNestingService,
    NestingValidationError,
)
from src.services.raster_asset_service import RasterAssetService
from src.services.repositories.map_repository import MapRepository

logger = logging.getLogger(__name__)


class CreateMapCommand(BaseCommand):
    """Command to create a new map."""

    def __init__(
        self,
        map_data: Optional[dict] = None,
        source_image_path: str = "",
    ) -> None:
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
        self.source_image_path = source_image_path
        self._artifact_manifest: dict[str, str] = {}
        self._owns_image = bool(source_image_path and self._map.image_path)

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Executes the command to create the map.

        Args:
            db_service (DatabaseService): The database service to use.

        Returns:
            CommandResult: Result object indicating success or failure.

        """
        try:
            world_root = Path(db_service.get_db_file_path()).parent
            artifacts = CommandArtifactStore(world_root)
            image_created = False
            image_restored = False
            if self._owns_image:
                if self._artifact_manifest:
                    artifacts.restore(self._artifact_manifest)
                    image_restored = True
                else:
                    source = Path(self.source_image_path).resolve()
                    RasterAssetService(world_root).atomic_write_bytes(
                        self._map.image_path,
                        source.read_bytes(),
                    )
                    image_created = True
            try:
                with db_service.transaction():
                    db_service.insert_map(self._map)
            except Exception:
                if image_restored:
                    self._artifact_manifest = artifacts.stash(
                        self.command_id,
                        [self._map.image_path],
                    )
                elif image_created:
                    target = (world_root / self._map.image_path).resolve()
                    if target.exists() and target.is_relative_to(
                        world_root.resolve()
                    ):
                        target.unlink()
                raise
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
            world_root = Path(db_service.get_db_file_path()).parent
            artifacts = CommandArtifactStore(world_root)
            if self._owns_image:
                self._artifact_manifest = artifacts.stash(
                    self.command_id,
                    [self._map.image_path],
                )
            try:
                with db_service.transaction():
                    db_service.delete_map(self._map.id)
            except Exception:
                if self._artifact_manifest:
                    artifacts.restore(self._artifact_manifest)
                raise
            self._is_executed = False
            logger.info(f"Undid creation of map: {self._map.id}")

    def to_dict(self) -> dict:
        """Serialize command to dictionary.

        Returns:
            Dictionary representation of the command.
        """
        return {
            "map_data": self._map.to_dict(),
            "source_image_path": self.source_image_path,
            "artifact_manifest": self._artifact_manifest,
            "owns_image": self._owns_image,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CreateMapCommand":
        """Deserialize command from dictionary.

        Args:
            data: Dictionary containing serialized command data.

        Returns:
            CreateMapCommand instance.
        """
        command = cls(
            data.get("map_data"),
            source_image_path=str(data.get("source_image_path", "")),
        )
        command._artifact_manifest = dict(data.get("artifact_manifest", {}))
        command._owns_image = bool(data.get("owns_image", command._owns_image))
        return command


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
        self._aggregate_snapshot: Optional[MapAggregateSnapshot] = None
        self._artifact_manifest: dict[str, str] = {}

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

            # Block deletion if any descendant detail maps are registered
            # under this map.  Cascade-clearing would silently destroy the
            # user's nested-map layout, so the design forbids it: list the
            # affected maps and let the user re-register or delete them
            # explicitly first.
            all_maps = db_service.get_all_maps()
            descendants = list(
                MapRepository.iter_descendants(self.map_id, all_maps)
            )
            if descendants:
                names = ", ".join(d.name for d in descendants)
                return CommandResult(
                    success=False,
                    message=(
                        f"Cannot delete '{self._deleted_map.name}': "
                        f"{len(descendants)} detail map(s) are registered "
                        f"under it ({names}). Re-register or delete them "
                        f"first."
                    ),
                    command_name="DeleteMapCommand",
                )

            self._aggregate_snapshot = MapAggregateService(db_service).snapshot(
                self.map_id
            )
            self._deleted_markers = db_service.get_markers_for_map(self.map_id)
            world_root = Path(db_service.get_db_file_path()).parent
            artifact_store = CommandArtifactStore(world_root)
            self._artifact_manifest = artifact_store.stash(
                self.command_id,
                self._aggregate_snapshot.raster_files,
            )
            try:
                db_service.delete_map(self.map_id)
            except Exception:
                artifact_store.restore(self._artifact_manifest)
                self._artifact_manifest = {}
                raise
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
        if not self._is_executed or self._aggregate_snapshot is None:
            return

        snapshot = self._aggregate_snapshot
        map_obj = Map.from_dict(snapshot.map_data)
        world_root = Path(db_service.get_db_file_path()).parent
        artifacts = CommandArtifactStore(world_root)
        artifacts.restore(self._artifact_manifest)
        try:
            with db_service.transaction():
                db_service.insert_map(map_obj)
                for marker_data in snapshot.markers:
                    db_service.insert_marker(Marker.from_dict(marker_data))
                for trajectory in snapshot.trajectories:
                    db_service.trajectory_repo.restore_snapshot(trajectory)
        except Exception:
            self._artifact_manifest = artifacts.stash(
                self.command_id, snapshot.raster_files
            )
            raise
        self._is_executed = False
        logger.info(f"Undid deletion of map: {self.map_id}")

    def to_dict(self) -> dict:
        """Serialize command to dictionary.

        Returns:
            Dictionary representation of the command.
        """
        return {
            "map_id": self.map_id,
            "aggregate_snapshot": (
                self._aggregate_snapshot.to_dict()
                if self._aggregate_snapshot
                else None
            ),
            "artifact_manifest": self._artifact_manifest,
            "is_executed": self._is_executed,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DeleteMapCommand":
        """Deserialize command from dictionary.

        Args:
            data: Dictionary containing serialized command data.

        Returns:
            DeleteMapCommand instance.
        """
        command = cls(data["map_id"])
        snapshot_data = data.get("aggregate_snapshot")
        if snapshot_data:
            command._aggregate_snapshot = MapAggregateSnapshot.from_dict(
                snapshot_data
            )
            command._deleted_map = Map.from_dict(
                command._aggregate_snapshot.map_data
            )
            command._deleted_markers = [
                Marker.from_dict(marker)
                for marker in command._aggregate_snapshot.markers
            ]
        command._artifact_manifest = dict(data.get("artifact_manifest", {}))
        command._is_executed = bool(data.get("is_executed", snapshot_data))
        return command


# ---------------------------------------------------------------------------
# Map nesting commands
# ---------------------------------------------------------------------------


def _merge_attributes(current: Map, updates: Dict[str, Any]) -> Map:
    """Return a copy of ``current`` whose attributes are merged with ``updates``.

    Mirrors the attribute-merge semantics in ``UpdateMapCommand.execute``
    (shallow merge — top-level keys from ``updates`` win).  Used by the
    nesting commands so they share a single, audited write path.

    Args:
        current: Map whose attributes to merge into.
        updates: Mapping of top-level attribute keys to new values.  A
            value of ``None`` removes the key entirely.

    Returns:
        A new ``Map`` dataclass with the merged attributes applied.

    """
    merged = dict(current.attributes) if current.attributes else {}
    for key, value in updates.items():
        if value is None:
            merged.pop(key, None)
        else:
            merged[key] = value
    return dataclasses.replace(current, attributes=merged)


class SetMasterMapCommand(BaseCommand):
    """Designate a map as the world's master.

    The previous master (if any) is **state**, not input — it is
    discovered at execute time so undo remains correct even if the world
    state changed between submission and execution.
    """

    def __init__(self, map_id: str) -> None:
        """Initializes the SetMasterMapCommand.

        Args:
            map_id: ID of the map to mark as master.

        """
        super().__init__()
        self.map_id = map_id
        self._previous_master_id: Optional[str] = None

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Promote the target map to master, demoting any prior master.

        Args:
            db_service: The database service to use.

        Returns:
            CommandResult indicating success or failure.

        """
        try:
            target = db_service.get_map(self.map_id)
            if not target:
                return CommandResult(
                    success=False,
                    message=f"Map not found: {self.map_id}",
                    command_name="SetMasterMapCommand",
                )

            if (target.attributes or {}).get("map_role") == MAP_ROLE_MASTER:
                # Already master — no-op, but mark executed so undo is a no-op.
                self._is_executed = True
                return CommandResult(
                    success=True,
                    message=f"Map '{target.name}' is already the master.",
                    command_name="SetMasterMapCommand",
                )

            all_maps = db_service.get_all_maps()
            previous = MapRepository.get_master_map(all_maps)
            if previous and previous.id != self.map_id:
                self._previous_master_id = previous.id
                # A master being demoted to a plain map clears its role,
                # but it has no parent, so we drop ``parent_map_id`` and
                # ``registration`` defensively in case stale values exist.
                demoted = _merge_attributes(
                    previous,
                    {
                        "map_role": None,
                        "parent_map_id": None,
                        "registration": None,
                    },
                )
                db_service.insert_map(demoted)

            # Promoting a detail map to master strips its parent linkage —
            # a master cannot have a parent.
            promoted = _merge_attributes(
                target,
                {
                    "map_role": MAP_ROLE_MASTER,
                    "parent_map_id": None,
                    "registration": None,
                },
            )
            db_service.insert_map(promoted)
            self._is_executed = True
            logger.info(
                f"Set master map: {target.name} ({self.map_id}); "
                f"previous master: {self._previous_master_id}"
            )
            return CommandResult(
                success=True,
                message=f"'{target.name}' is now the master map.",
                command_name="SetMasterMapCommand",
            )
        except Exception as e:
            logger.error(f"Failed to set master map: {e}")
            return CommandResult(
                success=False,
                message=f"Failed to set master map: {e}",
                command_name="SetMasterMapCommand",
            )

    def undo(self, db_service: DatabaseService) -> None:
        """Restore the previous master assignment.

        Args:
            db_service: The database service to operate on.

        """
        if not self._is_executed:
            return
        try:
            target = db_service.get_map(self.map_id)
            if target:
                cleared = _merge_attributes(target, {"map_role": None})
                db_service.insert_map(cleared)
            if self._previous_master_id:
                previous = db_service.get_map(self._previous_master_id)
                if previous:
                    restored = _merge_attributes(
                        previous, {"map_role": MAP_ROLE_MASTER}
                    )
                    db_service.insert_map(restored)
            self._is_executed = False
            logger.info(f"Undid set master: {self.map_id}")
        except Exception as e:
            logger.error(f"Failed to undo SetMasterMapCommand: {e}")

    def to_dict(self) -> dict:
        """Serialize command to dictionary."""
        return {"map_id": self.map_id}

    @classmethod
    def from_dict(cls, data: dict) -> "SetMasterMapCommand":
        """Deserialize command from dictionary."""
        return cls(data["map_id"])


class RegisterDetailMapCommand(BaseCommand):
    """Register a map as a detail child of another map.

    Replacement-safe: re-running this on an already-registered detail
    map captures the prior parent and registration before overwriting,
    so a single undo restores the previous placement atomically.

    Validation against cycles, depth caps, and malformed payloads is
    delegated to :class:`MapNestingService.validate_registration` which
    is called before any mutation.  Phase 1 ships with a minimal
    inline-validation fallback; Phase 2 swaps it for the real service.
    """

    def __init__(
        self,
        detail_map_id: str,
        parent_map_id: str,
        registration: Dict[str, Any],
    ) -> None:
        """Initializes the RegisterDetailMapCommand.

        Args:
            detail_map_id: ID of the map being registered as a detail.
            parent_map_id: ID of the parent (master or detail) map.
            registration: Aspect-locked-affine registration payload as
                described in the master-map nesting design doc.

        """
        super().__init__()
        self.detail_map_id = detail_map_id
        self.parent_map_id = parent_map_id
        self.registration = registration
        self._previous_attrs: Optional[Dict[str, Any]] = None

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Persist the registration after validating it.

        Args:
            db_service: The database service to use.

        Returns:
            CommandResult indicating success or failure.

        """
        try:
            detail = db_service.get_map(self.detail_map_id)
            if not detail:
                return CommandResult(
                    success=False,
                    message=f"Detail map not found: {self.detail_map_id}",
                    command_name="RegisterDetailMapCommand",
                )

            all_maps = db_service.get_all_maps()
            try:
                MapNestingService.validate_registration(
                    self.detail_map_id,
                    self.parent_map_id,
                    self.registration,
                    all_maps,
                )
            except NestingValidationError as ve:
                return CommandResult(
                    success=False,
                    message=f"Invalid registration: {ve}",
                    command_name="RegisterDetailMapCommand",
                )

            self._previous_attrs = (
                dict(detail.attributes) if detail.attributes else {}
            )

            updated = _merge_attributes(
                detail,
                {
                    "map_role": MAP_ROLE_DETAIL,
                    "parent_map_id": self.parent_map_id,
                    "registration": self.registration,
                },
            )
            db_service.insert_map(updated)
            self._is_executed = True
            logger.info(
                f"Registered detail map {self.detail_map_id} under "
                f"{self.parent_map_id}"
            )
            return CommandResult(
                success=True,
                message=f"'{detail.name}' registered as a detail map.",
                command_name="RegisterDetailMapCommand",
            )
        except Exception as e:
            logger.error(f"Failed to register detail map: {e}")
            return CommandResult(
                success=False,
                message=f"Failed to register detail map: {e}",
                command_name="RegisterDetailMapCommand",
            )

    def undo(self, db_service: DatabaseService) -> None:
        """Restore the detail map's attributes to their pre-execute snapshot.

        Args:
            db_service: The database service to operate on.

        """
        if not self._is_executed or self._previous_attrs is None:
            return
        try:
            detail = db_service.get_map(self.detail_map_id)
            if detail:
                restored = dataclasses.replace(
                    detail, attributes=dict(self._previous_attrs)
                )
                db_service.insert_map(restored)
            self._is_executed = False
            logger.info(f"Undid detail-map registration: {self.detail_map_id}")
        except Exception as e:
            logger.error(f"Failed to undo RegisterDetailMapCommand: {e}")

    def to_dict(self) -> dict:
        """Serialize command to dictionary."""
        return {
            "detail_map_id": self.detail_map_id,
            "parent_map_id": self.parent_map_id,
            "registration": self.registration,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RegisterDetailMapCommand":
        """Deserialize command from dictionary."""
        return cls(
            data["detail_map_id"],
            data["parent_map_id"],
            data["registration"],
        )


# ---------------------------------------------------------------------------
# Phase-1 validation fallback
#
# A minimal validator lives here so Phase 1 can ship without depending on
# Phase 2's MapNestingService.  Phase 2 will replace this with calls to
# the service while keeping the same exception type.
# ---------------------------------------------------------------------------


# NestingValidationError is defined in map_nesting_service and imported above.
# Re-exported here so that callers that import it from this module
# (including the Phase-1 tests) continue to work unchanged.
__all__ = [
    "NestingValidationError",
]

# _validate_registration is kept as a thin shim used by the Phase-1 tests
# that import it directly.  Phase 2+ code should call
# MapNestingService.validate_registration instead.
def _validate_registration(
    detail_id: str,
    parent_id: str,
    registration: Dict[str, Any],
    all_maps: List[Map],
) -> None:
    """Shim — delegates to :meth:`MapNestingService.validate_registration`.

    Kept for backwards compatibility with Phase-1 tests that import this
    symbol directly.

    Raises:
        NestingValidationError: On any validation failure.

    """
    MapNestingService.validate_registration(
        detail_id, parent_id, registration, all_maps
    )
