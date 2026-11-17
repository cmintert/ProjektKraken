"""Snapshot-safe worker command for keeping placement while changing parents."""

from copy import deepcopy
from typing import Any

from src.commands.base_command import CommandResult
from src.commands.map_hierarchy_commands import ChangeMapParentCommand
from src.core.map_hierarchy import hierarchy_attributes
from src.services.db_service import DatabaseService
from src.services.map_reparenting import plan_preserved_reparent


class PreserveMapPlacementCommand(ChangeMapParentCommand):
    """Recompute on the worker, guard both ancestry chains, and replay snapshots."""

    def __init__(
        self,
        map_id: str,
        new_parent_id: str,
        expected_context: dict[str, dict[str, Any]],
    ) -> None:
        """Copy proposal dependencies without retaining a service or live maps."""
        super().__init__(
            map_id, new_parent_id, None, expected_hierarchy=expected_context.get(map_id)
        )
        self.expected_context = deepcopy(expected_context)

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Reject changed ancestry before calculating or replaying exact placement."""
        records = db_service.get_all_maps()
        current = {
            record.id: hierarchy_attributes(record.attributes) for record in records
        }
        if not self.expected_context or any(
            current.get(key) != value for key, value in self.expected_context.items()
        ):
            return CommandResult(
                False, "The map hierarchy changed. Choose the parent again."
            )
        try:
            plan = plan_preserved_reparent(
                records, self.map_id, str(self.new_parent_id)
            )
        except (ValueError, TypeError, KeyError) as exc:
            return CommandResult(False, str(exc))
        if plan.expected_context != self.expected_context:
            return CommandResult(
                False, "The map hierarchy changed. Choose the parent again."
            )
        if self._after is None:
            self.registration = deepcopy(plan.registration)
        return super().execute(db_service)

    def to_dict(self) -> dict[str, Any]:
        """Serialize dependency guards and the inherited exact undo/redo state."""
        return {
            **super().to_dict(),
            "expected_context": deepcopy(self.expected_context),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PreserveMapPlacementCommand":
        """Restore a proposal or executed history entry without querying storage."""
        command = cls(data["map_id"], data["new_parent_id"], data["expected_context"])
        command.registration = deepcopy(data.get("registration"))
        command._before = deepcopy(data.get("before"))
        command._after = deepcopy(data.get("after"))
        command._is_executed = bool(data.get("is_executed", False))
        return command

    def get_description(self) -> str:
        """Name the creator's one reversible structural operation."""
        return "Change map parent (keep geographic placement)"
