"""Apply an internally registered timing plan as one reversible mutation."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from typing import Any

from src.commands.base_command import BaseCommand, CommandResult
from src.core.events import Event
from src.services.db_service import DatabaseService
from src.services.event_timing.guards import applying_timing_plan
from src.services.event_timing.planning import snapshot_fingerprint
from src.services.event_timing.store import capture, consume


class ApplyEventTimingPlanCommand(BaseCommand):
    """Retain root authoring behavior and all automatic projections in one history item."""

    def __init__(self, command: BaseCommand, plan_id: str, confirmation: str) -> None:
        """Keep a detached root command; services are supplied only at execution."""
        super().__init__()
        self.command = command
        self.plan_id = plan_id
        self.confirmation = confirmation
        self._previous: dict[str, dict[str, Any]] = {}
        self._updated: dict[str, dict[str, Any]] = {}
        self._redo = False
        self._base_fingerprint = ""

    def get_description(self) -> str:
        """Describe the actual authored operation, including its cascade."""
        return self.command.get_description()

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Check confirmation before any write, then apply the root and projections."""
        try:
            if self._redo:
                return self._restore_redo(db_service)
            plan = consume(db_service, self.plan_id, self.confirmation)
            self._base_fingerprint = plan.base_fingerprint
            from src.commands.event_timing_intents import request_for_command
            from src.services.event_timing.planning import digest

            intended = request_for_command(self.command, capture(db_service))
            if digest(intended.to_dict()) != digest(plan.request.to_dict()):
                raise ValueError("The command differs from its reviewed timing plan")
            self._previous = {
                identity: current.to_dict()
                for identity in plan.previous
                if (current := db_service.get_event(identity)) is not None
            }
            token = applying_timing_plan.set(True)
            try:
                result = self.command.execute(db_service)
            finally:
                applying_timing_plan.reset(token)
            if not result.success:
                return result
            for identity, projected in plan.updated.items():
                current = db_service.get_event(identity)
                if current is None:
                    raise ValueError("An affected Event disappeared during application")
                # Preserve unrelated current content and authored modification time.
                attributes = deepcopy(current.attributes)
                projection = (
                    projected["attributes"].get("_temporal_v2", {}).get("projection")
                )
                if projection is not None:
                    attributes.setdefault("_temporal_v2", {})["projection"] = projection
                updated = replace(
                    current,
                    lore_date=projected["lore_date"],
                    lore_duration=projected["lore_duration"],
                    attributes=attributes,
                )
                db_service.insert_event(updated)
                self._updated[identity] = updated.to_dict()
            self._is_executed = True
            return self._result(result)
        except (ValueError, KeyError) as exc:
            return CommandResult(
                success=False, message=str(exc), command_name=type(self).__name__
            )

    def _result(self, result: CommandResult | None = None) -> CommandResult:
        from src.core.command import LoreMutationEffect, parse_lore_mutation_effects

        effects: list[LoreMutationEffect] = (
            (parse_lore_mutation_effects(result.data.get("lore_effects")) or [])
            if result
            else []
        )
        effects.extend(
            {
                "object_type": "event",
                "operation": "upsert",
                "object_id": identity,
                "snapshot": row,
                "relations_changed": False,
            }
            for identity, row in self._updated.items()
        )
        return CommandResult(
            success=True,
            message="Timing changes applied.",
            command_name=type(self).__name__,
            data={
                **(result.data if result else {}),
                "lore_effects": effects,
                "temporal_generation_changed": True,
            },
        )

    def undo(self, db_service: DatabaseService) -> None:
        """Restore exact recorded state, including pre-existing defects."""
        self.command.undo(db_service)
        for row in self._previous.values():
            db_service.insert_event(Event.from_dict(deepcopy(row)))
        self._is_executed = False
        self._redo = True

    def _restore_redo(self, db: DatabaseService) -> CommandResult:
        if (
            self._base_fingerprint
            and snapshot_fingerprint(capture(db)) != self._base_fingerprint
        ):
            raise ValueError(
                "Timing inputs changed since undo; redo cannot safely apply"
            )
        for identity in self._updated.keys() - self._previous.keys():
            if db.get_event(identity) is not None:
                raise ValueError("A created Event identity was reused since undo")
        for identity, expected in self._previous.items():
            current = db.get_event(identity)
            if current is None or current.to_dict() != expected:
                raise ValueError(
                    "Timing changed since undo; redo cannot safely replace it"
                )
        token = applying_timing_plan.set(True)
        try:
            result = self.command.execute(db)
        finally:
            applying_timing_plan.reset(token)
        if not result.success:
            return result
        for row in self._updated.values():
            db.insert_event(Event.from_dict(deepcopy(row)))
        self._is_executed = True
        return self._result(result)

    def to_dict(self) -> dict[str, Any]:
        """Persist intent and exact snapshots, never a process-local solver."""
        return {
            "command_type": type(self.command).__name__,
            "command": self.command.to_dict(),
            "command_base": self.command.base_state_dict(),
            "plan_id": self.plan_id,
            "confirmation": self.confirmation,
            "previous": deepcopy(self._previous),
            "updated": deepcopy(self._updated),
            "redo": self._redo,
            "base_fingerprint": self._base_fingerprint,
            "is_executed": self._is_executed,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ApplyEventTimingPlanCommand:
        """Restore persisted history independently of prepared-plan registration."""
        from src.commands.registry import get_command_types

        command = get_command_types()[data["command_type"]].from_dict(data["command"])
        command.restore_base_state(data.get("command_base", {}))
        result = cls(command, data["plan_id"], data["confirmation"])
        result._previous = deepcopy(data.get("previous", {}))
        result._updated = deepcopy(data.get("updated", {}))
        result._redo = data.get("redo", False)
        result._base_fingerprint = data.get("base_fingerprint", "")
        result._is_executed = data.get("is_executed", False)
        return result
