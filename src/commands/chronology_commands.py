"""Undoable edits to chronology rules across event owners."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from typing import Any
from uuid import uuid4

from src.commands.base_command import BaseCommand
from src.core.calendar import CalendarConverter
from src.core.command import CommandResult
from src.core.events import Event
from src.services.chronology_service import collect_chronology, new_issues, world_issues
from src.services.db_service import DatabaseService


class ApplyChronologyCommand(BaseCommand):
    """Apply a small set of rule edits as one atomic, undoable action."""

    def __init__(self, operations: list[dict[str, Any]]) -> None:
        """Keep detached edit intents until worker-side execution."""
        super().__init__()
        self.operations = deepcopy(operations)
        self._previous: dict[str, dict[str, Any]] = {}
        self._updated: dict[str, dict[str, Any]] = {}

    def get_description(self) -> str:
        """Describe the history entry."""
        return "Edit event chronology"

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Re-read, validate, and update all touched owners in one transaction."""
        events = db_service.get_all_events()
        by_id = {event.id: event for event in events}
        converter_config = db_service.get_active_calendar_config()
        converter = CalendarConverter(converter_config) if converter_config else None
        before = world_issues(events, converter)
        records = {record.reference: record for record in collect_chronology(events)}
        revised = {event.id: deepcopy(event) for event in events}
        removals: dict[str, set[int]] = {}
        additions: dict[str, list[dict[str, Any]]] = {}
        for operation in self.operations:
            kind = operation["kind"]
            if kind in {"update", "delete"}:
                reference = str(operation["reference"])
                record = records.get(reference)
                if record is None or record.data != operation["old_data"]:
                    return CommandResult(
                        success=False,
                        message="Chronology changed since this dialog opened. Reopen it and retry.",
                        command_name="ApplyChronologyCommand",
                    )
                removals.setdefault(record.owner_id, set()).add(record.position)
            if kind in {"create", "update"}:
                data = deepcopy(operation["data"])
                owner_id = str(data["anchor_a"]).removeprefix("event:")
                if owner_id not in by_id:
                    return CommandResult(
                        success=False,
                        message="The chronology event is unavailable.",
                        command_name="ApplyChronologyCommand",
                    )
                data["id"] = data.get("id") or str(uuid4())
                operation["data"]["id"] = data["id"]
                additions.setdefault(owner_id, []).append(data)
        touched = set(removals) | set(additions)
        for owner_id in touched:
            event = revised[owner_id]
            attributes = deepcopy(event.attributes)
            metadata = deepcopy(attributes.get("_temporal_v2", {}))
            original = metadata.get("constraints", [])
            metadata.update(schema=1)
            metadata["constraints"] = [
                item
                for index, item in enumerate(original)
                if index not in removals.get(owner_id, set())
            ] + additions.get(owner_id, [])
            attributes["_temporal_v2"] = metadata
            revised[owner_id] = replace(event, attributes=attributes)
        after = world_issues(list(revised.values()), converter)
        introduced = new_issues(before, after)
        if introduced:
            return CommandResult(
                success=False,
                message=introduced[0].message,
                command_name="ApplyChronologyCommand",
            )
        self._previous = {owner: by_id[owner].to_dict() for owner in touched}
        self._updated = {owner: revised[owner].to_dict() for owner in touched}
        for owner in touched:
            db_service.insert_event(revised[owner])
        self._is_executed = True
        return CommandResult(
            success=True,
            message="Chronology updated.",
            command_name="ApplyChronologyCommand",
            data={
                "lore_effects": [
                    {
                        "object_type": "event",
                        "operation": "upsert",
                        "object_id": owner,
                        "snapshot": self._updated[owner],
                        "relations_changed": False,
                    }
                    for owner in touched
                ]
            },
        )

    def undo(self, db_service: DatabaseService) -> None:
        """Restore every affected event's previous metadata."""
        if not self._is_executed:
            return
        for snapshot in self._previous.values():
            db_service.insert_event(Event.from_dict(snapshot))
        self._is_executed = False

    def to_dict(self) -> dict[str, Any]:
        """Serialize the intent and undo snapshots."""
        return {
            "operations": self.operations,
            "previous": self._previous,
            "updated": self._updated,
            "is_executed": self._is_executed,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ApplyChronologyCommand:
        """Restore a command from history."""
        command = cls(data["operations"])
        command._previous = data.get("previous", {})
        command._updated = data.get("updated", {})
        command._is_executed = data.get("is_executed", False)
        return command
