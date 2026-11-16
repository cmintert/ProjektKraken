"""Snapshot-safe structural map changes, independent of map UI workflows."""

from copy import deepcopy
from dataclasses import replace
from typing import Any

from src.commands.base_command import BaseCommand, CommandResult
from src.core.map_hierarchy import (
    HierarchyError,
    MapHierarchy,
    hierarchy_attributes,
    restore_hierarchy_attributes,
)
from src.services.db_service import DatabaseService
from src.services.map_nesting_service import validate_registration_payload


class ChangeMapParentCommand(BaseCommand):
    """Change only hierarchy keys; replay exact snapshots across serialization."""

    def __init__(
        self,
        map_id: str,
        new_parent_id: str | None,
        registration: dict[str, Any] | None,
        *,
        expected_hierarchy: dict[str, Any] | None = None,
    ) -> None:
        """Capture intent without accessing services or retaining mutable inputs."""
        super().__init__()
        self.map_id = map_id
        self.new_parent_id = new_parent_id
        self.registration = deepcopy(registration)
        self.expected_hierarchy = deepcopy(expected_hierarchy)
        self._before: dict[str, Any] | None = None
        self._after: dict[str, Any] | None = None

    def _validate(self, db_service: DatabaseService, state: dict[str, Any]) -> None:
        parent = state.get("parent_map_id")
        if parent:
            registration = state.get("registration")
            if not isinstance(registration, dict):
                raise HierarchyError("A child map requires a registration payload.")
            validate_registration_payload(registration)
        records = db_service.get_all_maps()
        hierarchy = MapHierarchy(records)
        hierarchy.validate_change_parent(self.map_id, parent)
        related = hierarchy.descendants(self.map_id)
        if parent:
            related += hierarchy.ancestors(parent)
            related += [record for record in records if record.id == parent]
        for record in related:
            if record.id != self.map_id and (record.attributes or {}).get(
                "parent_map_id"
            ):
                payload = (record.attributes or {}).get("registration")
                if not isinstance(payload, dict):
                    raise HierarchyError(f"Map {record.id} lacks a registration.")
                validate_registration_payload(payload)

    def _write(self, db_service: DatabaseService, state: dict[str, Any]) -> None:
        current = db_service.get_map(self.map_id)
        if current is None:
            raise HierarchyError(f"Map not found: {self.map_id}")
        attributes = restore_hierarchy_attributes(current.attributes, state)
        db_service.insert_map(replace(current, attributes=attributes))

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Validate current data and apply the original proposed hierarchy state."""
        current = db_service.get_map(self.map_id)
        if current is None:
            return CommandResult(success=False, message="Map not found.")
        expected = self._before if self._before is not None else self.expected_hierarchy
        if (
            expected is not None
            and hierarchy_attributes(current.attributes) != expected
        ):
            return CommandResult(
                success=False, message="Map hierarchy changed; refresh the proposal."
            )
        if self.new_parent_id is None and self.registration is not None:
            return CommandResult(
                success=False, message="Independent maps need no registration."
            )
        state = self._after
        if state is None:
            state = (
                {}
                if self.new_parent_id is None
                else {
                    "map_role": "detail",
                    "parent_map_id": self.new_parent_id,
                    "registration": deepcopy(self.registration),
                }
            )
        try:
            self._validate(db_service, state)
        except (ValueError, TypeError, AttributeError) as exc:
            return CommandResult(success=False, message=str(exc))
        if self._before is None:
            self._before = hierarchy_attributes(current.attributes)
            self._after = deepcopy(state)
        self._write(db_service, state)
        self._is_executed = True
        return CommandResult(success=True, message="Map hierarchy updated.")

    def undo(self, db_service: DatabaseService) -> CommandResult:
        """Restore hierarchy keys without overwriting unrelated map attributes."""
        if not self._is_executed or self._before is None:
            return CommandResult(
                success=False, message="No hierarchy snapshot to restore."
            )
        current = db_service.get_map(self.map_id)
        if current is None or hierarchy_attributes(current.attributes) != self._after:
            return CommandResult(
                success=False, message="Map hierarchy changed; undo was not applied."
            )
        # Exact restoration includes legacy role mismatches and explicit nulls.
        self._write(db_service, self._before)
        self._is_executed = False
        return CommandResult(success=True, message="Map hierarchy restored.")

    def to_dict(self) -> dict[str, Any]:
        """Serialize independently owned intent and both history snapshots."""
        return deepcopy(
            {
                "map_id": self.map_id,
                "new_parent_id": self.new_parent_id,
                "registration": self.registration,
                "expected_hierarchy": self.expected_hierarchy,
                "before": self._before,
                "after": self._after,
                "is_executed": self._is_executed,
            }
        )

    @classmethod
    def from_dict(cls, data: dict) -> "ChangeMapParentCommand":
        """Restore snapshots without needing a database or reconstructing state."""
        command = cls(
            data["map_id"],
            data["new_parent_id"],
            data["registration"],
            expected_hierarchy=data.get("expected_hierarchy"),
        )
        command._before = deepcopy(data.get("before"))
        command._after = deepcopy(data.get("after"))
        command._is_executed = bool(data.get("is_executed", False))
        return command
