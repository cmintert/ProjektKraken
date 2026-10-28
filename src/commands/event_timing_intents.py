"""Translate existing command intents into detached timing candidates."""

from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import uuid4

from src.commands.base_command import BaseCommand
from src.commands.calendar_commands import (
    CreateCalendarConfigCommand,
    DeleteCalendarConfigCommand,
    SetActiveCalendarCommand,
    UpdateCalendarConfigCommand,
)
from src.commands.chronology_commands import ApplyChronologyCommand
from src.commands.composite_command import CompositeCommand
from src.commands.event_commands import CreateEventCommand, UpdateEventCommand
from src.commands.transfer_commands import ApplyTransferCommand
from src.core.events import Event
from src.services.event_temporal_service import move_temporal_event
from src.services.event_timing.guards import preserve_chronology
from src.services.event_timing.planning import (
    TimingChangeRequest,
    converter_from_snapshot,
)


def children(command: BaseCommand) -> list[BaseCommand]:
    """Walk composites without changing their ordering or root identity."""
    if isinstance(command, CompositeCommand):
        return [child for item in command.commands for child in children(item)]
    return [command]


def timing_intent(command: BaseCommand) -> bool:
    """Identify existing timing mutators for asynchronous preparation."""
    return any(
        isinstance(item, (CreateEventCommand, ApplyChronologyCommand))
        or (isinstance(item, UpdateEventCommand) and _updates_timing(item))
        or isinstance(
            item,
            (
                CreateCalendarConfigCommand,
                DeleteCalendarConfigCommand,
                SetActiveCalendarCommand,
                UpdateCalendarConfigCommand,
            ),
        )
        or (
            isinstance(item, ApplyTransferCommand)
            and any(
                change["table"] == "events" for change in item.preview.get("delta", [])
            )
        )
        for item in children(command)
    )


def _updates_timing(command: UpdateEventCommand) -> bool:
    fields = command.update_data
    if fields.get("__preserve_timing") is True:
        # The command enforces this scope against the authoritative record.
        return False
    if not ({"lore_date", "lore_duration", "attributes"} & fields.keys()):
        return False
    expected = fields.get("__expected_timing")
    if expected is not None:
        from src.core.event_timing.definitions import EventTimingDefinition

        try:
            event = Event(
                name=str(fields.get("name", "")),
                lore_date=fields.get("lore_date"),
                lore_duration=fields.get("lore_duration"),
                attributes=fields.get("attributes", {}),
            )
            return EventTimingDefinition.from_event(event).to_dict() != expected
        except (ValueError, TypeError, KeyError):
            return True
    return True


def _event_patch(
    command: UpdateEventCommand, snapshot: dict[str, Any]
) -> dict[str, Any]:
    current = next(
        Event.from_dict(row)
        for row in snapshot["events"]
        if row["id"] == command.event_id
    )
    patch = {
        key: deepcopy(value)
        for key, value in command.update_data.items()
        if key in current.to_dict() and key != "id"
    }
    from src.services.event_timing.patches import normalize_scalar_patch

    patch = normalize_scalar_patch(
        current,
        patch,
        converter_from_snapshot(snapshot),
        preserve_timing=command.update_data.get("__preserve_timing") is True,
    )
    if "attributes" in patch:
        patch["attributes"] = preserve_chronology(patch["attributes"], current)
    elif "lore_date" in patch:
        converter = converter_from_snapshot(snapshot)
        if converter is not None:
            moved = move_temporal_event(current, patch["lore_date"], converter)
            patch["attributes"] = moved.attributes
    return patch


def _chronology_patches(
    command: ApplyChronologyCommand, snapshot: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    from src.services.chronology_service import collect_chronology

    events = {row["id"]: Event.from_dict(deepcopy(row)) for row in snapshot["events"]}
    records = {
        record.reference: record for record in collect_chronology(list(events.values()))
    }
    for operation in command.operations:
        if operation["kind"] in {"update", "delete"}:
            record = records[operation["reference"]]
            if record.data != operation["old_data"]:
                raise ValueError("Chronology changed since this draft opened")
            events[record.owner_id].attributes["_temporal_v2"]["constraints"].remove(
                record.data
            )
        if operation["kind"] in {"create", "update"}:
            data = deepcopy(operation["data"])
            data["id"] = data.get("id") or str(uuid4())
            operation["data"]["id"] = data["id"]
            owner = data["anchor_a"].removeprefix("event:").removesuffix(":end")
            metadata = events[owner].attributes.setdefault(
                "_temporal_v2", {"schema": 1}
            )
            metadata.setdefault("constraints", []).append(data)
    original = {row["id"]: row["attributes"] for row in snapshot["events"]}
    return {
        identity: {"attributes": event.attributes}
        for identity, event in events.items()
        if original[identity] != event.attributes
    }


def request_for_command(
    command: BaseCommand, snapshot: dict[str, Any]
) -> TimingChangeRequest:
    """Preserve root command behavior while preparing its temporal consequences."""
    updates: dict[str, dict[str, Any]] = {}
    creates = []
    expected = {}
    calendar = None
    calendar_changed = False
    imported = False
    consumers = None
    deletes: tuple[str, ...] = ()
    for item in children(command):
        if isinstance(item, UpdateEventCommand):
            updates[item.event_id] = _event_patch(item, snapshot)
            if item.update_data.get("__expected_timing") is not None:
                expected[item.event_id] = item.update_data["__expected_timing"]
        elif isinstance(item, CreateEventCommand):
            creates.append(item.event.to_dict())
        elif isinstance(item, ApplyChronologyCommand):
            updates.update(_chronology_patches(item, snapshot))
        elif isinstance(
            item, (UpdateCalendarConfigCommand, CreateCalendarConfigCommand)
        ):
            active = converter_from_snapshot(snapshot)
            if item._config.is_active or (
                active is not None and active._config.id == item._config.id
            ):
                calendar = item._config.to_json() if item._config.is_active else None
                calendar_changed = True
        elif isinstance(item, SetActiveCalendarCommand):
            config = next(
                (
                    row
                    for row in snapshot.get("calendars", [])
                    if row["id"] == item._config_id
                ),
                None,
            )
            if config is None:
                raise ValueError("The selected calendar is unavailable")
            from src.core.calendar import CalendarConfig

            selected = CalendarConfig.from_dict(config)
            selected.is_active = True
            calendar = selected.to_json()
            calendar_changed = True
        elif isinstance(item, DeleteCalendarConfigCommand):
            active = converter_from_snapshot(snapshot)
            calendar_changed = (
                active is not None and active._config.id == item._config_id
            )
        elif isinstance(item, ApplyTransferCommand):
            from src.services.event_timing.transfer import request_from_delta

            incoming = request_from_delta(snapshot, item.preview["delta"])
            updates.update(incoming.updates)
            creates.extend(incoming.creates)
            deletes = incoming.deletes
            consumers = incoming.consumers
            imported = True
    return TimingChangeRequest(
        updates=updates,
        creates=tuple(creates),
        deletes=deletes,
        expected=expected,
        calendar=calendar,
        calendar_changed=calendar_changed,
        imported=imported,
        consumers=consumers,
        world_id=snapshot["world_id"],
    )
