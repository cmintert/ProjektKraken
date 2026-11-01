"""An explicit timeline movement intent, applied only through a reviewed plan."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from typing import Any

from src.commands.base_command import BaseCommand, CommandResult
from src.services.db_service import DatabaseService
from src.services.event_timing.guards import applying_timing_plan


class TimelineMoveCommand(BaseCommand):
    """Keep user gesture intent separate from generic scalar date updates."""

    def __init__(self, intent: dict[str, Any]) -> None:
        """Capture the target, mode and original timing generation."""
        super().__init__()
        self.intent = deepcopy(intent)
        self.updated: dict[str, dict[str, Any]] = {}

    def get_description(self) -> str:
        """Name the operation in history."""
        return "Move Event chain" if self.intent["mode"] == "chain" else "Move Event"

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Apply only worker-registered timing; the wrapper owns exact undo state."""
        if not applying_timing_plan.get():
            return CommandResult(success=False, message="Review this movement first.")
        for identity, row in self.updated.items():
            current = db_service.get_event(identity)
            if current is None:
                return CommandResult(
                    success=False, message="An affected Event disappeared."
                )
            attributes = deepcopy(current.attributes)
            if "_temporal_v2" in row["attributes"]:
                attributes["_temporal_v2"] = deepcopy(row["attributes"]["_temporal_v2"])
            db_service.insert_event(
                replace(
                    current,
                    attributes=attributes,
                    lore_date=row["lore_date"],
                    lore_duration=row["lore_duration"],
                )
            )
        self._is_executed = True
        return CommandResult(success=True, message="Timeline movement applied.")

    def undo(self, db_service: DatabaseService) -> None:
        """The reviewed-plan wrapper restores complete original records."""
        self._is_executed = False

    def to_dict(self) -> dict[str, Any]:
        """Persist intent and prepared updates for validated history replay."""
        return {"intent": deepcopy(self.intent), "updated": deepcopy(self.updated)}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TimelineMoveCommand:
        """Restore without recalculating from display coordinates."""
        command = cls(data["intent"])
        command.updated = deepcopy(data.get("updated", {}))
        return command
