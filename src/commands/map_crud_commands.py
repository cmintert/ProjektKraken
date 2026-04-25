"""Commands for creating, updating, and deleting Map objects.

These commands handle map-level CRUD operations — they do not touch
individual markers or the layer hierarchy.
"""

import dataclasses
import logging
from typing import Any, Dict, List, Optional

from src.app.constants import MAP_ROLE_DETAIL, MAP_ROLE_MASTER
from src.commands.base_command import BaseCommand, CommandResult
from src.core.map import Map
from src.core.marker import Marker
from src.services.db_service import DatabaseService
from src.services.repositories.map_repository import MapRepository

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
                _validate_registration(
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


class NestingValidationError(ValueError):
    """Raised when a detail-map registration is rejected.

    Phase 2 will move this exception to ``map_nesting_service`` and
    re-export it here for backwards compatibility.
    """


def _validate_registration_payload(registration: Dict[str, Any]) -> None:
    """Validate the structural shape of a registration dict.

    Checks the keys, types, and finite-numeric values required by the
    aspect-locked-affine registration mode.  Pulled out of
    :func:`_validate_registration` to keep complexity bounded.

    Raises:
        NestingValidationError: When the payload is malformed.

    """
    from math import isfinite

    if not isinstance(registration, dict):
        raise NestingValidationError("Registration payload must be a dict.")
    if registration.get("mode") != "aspect_locked_affine":
        raise NestingValidationError(
            "Registration mode must be 'aspect_locked_affine'."
        )
    center = registration.get("master_center_norm") or {}
    fields = {
        "master_center_norm.x": center.get("x"),
        "master_center_norm.y": center.get("y"),
        "scale_norm": registration.get("scale_norm"),
        "aspect_ratio": registration.get("aspect_ratio"),
        "rotation_deg": registration.get("rotation_deg", 0.0),
    }
    for name, value in fields.items():
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise NestingValidationError(
                f"Registration field '{name}' must be a finite number."
            )
        if not isfinite(float(value)):
            raise NestingValidationError(
                f"Registration field '{name}' must be a finite number."
            )
    if float(fields["scale_norm"]) <= 0:
        raise NestingValidationError("scale_norm must be > 0.")
    if float(fields["aspect_ratio"]) <= 0:
        raise NestingValidationError("aspect_ratio must be > 0.")


def _validate_registration(
    detail_id: str,
    parent_id: str,
    registration: Dict[str, Any],
    all_maps: List[Map],
) -> None:
    """Phase-1 minimal validator.

    Catches the structural failures that would corrupt the data store
    even before the full transform service is available.  See Phase 2 of
    the master-map-nesting design doc for the full contract.

    Raises:
        NestingValidationError: On any of the documented failure modes.

    """
    # Constants referenced as integers to avoid an import cycle in tests
    # that stub the constants module.
    depth_cap = 5

    if detail_id == parent_id:
        raise NestingValidationError("A map cannot be its own parent.")

    by_id = {m.id: m for m in all_maps}
    parent = by_id.get(parent_id)
    if parent is None:
        raise NestingValidationError(f"Parent map not found: {parent_id}")

    parent_role = (parent.attributes or {}).get("map_role")
    if parent_role not in (MAP_ROLE_MASTER, MAP_ROLE_DETAIL):
        raise NestingValidationError(
            "Parent map must already be designated as a master or detail map."
        )

    # Cycle detection — walk the parent's chain looking for ``detail_id``.
    visited = {parent_id}
    cursor: Optional[Map] = parent
    depth = 1  # parent is depth 1 in the resulting chain (parent -> detail)
    while cursor is not None:
        cursor_attrs = cursor.attributes or {}
        next_id = cursor_attrs.get("parent_map_id")
        if not next_id:
            break
        if next_id == detail_id:
            raise NestingValidationError(
                "Registration would create a cycle in the nesting chain."
            )
        if next_id in visited:
            raise NestingValidationError(
                "Existing nesting chain already contains a cycle."
            )
        visited.add(next_id)
        cursor = by_id.get(next_id)
        if cursor is None:
            break
        depth += 1

    if depth + 1 > depth_cap:
        raise NestingValidationError(
            f"Nesting depth would exceed cap of {depth_cap} levels."
        )

    _validate_registration_payload(registration)
