"""Recorded legacy operations and new calendar cascades keep atomic history."""

from dataclasses import replace

import pytest

from src.commands.calendar_commands import (
    CreateCalendarConfigCommand,
    SetActiveCalendarCommand,
    UpdateCalendarConfigCommand,
)
from src.commands.chronology_commands import ApplyChronologyCommand
from src.commands.event_commands import DeleteEventCommand, UpdateEventCommand
from src.commands.event_timing_commands import ApplyEventTimingPlanCommand
from src.commands.transfer_commands import ApplyTransferCommand
from src.core.calendar import CalendarConfig
from src.core.event_timing.definitions import EndpointDefinition, EventTimingDefinition
from src.core.events import Event
from src.core.map import Map
from src.services.transfer_import import prepare_import

pytestmark = pytest.mark.ci_fast


def calculated_event(db):
    event = Event(
        "Manual authority",
        5,
        attributes=EventTimingDefinition(EndpointDefinition(instant=5)).apply({}),
    )
    db.insert_event(event)
    return event


def test_legacy_import_redo_restores_recorded_delta_in_calculated_world(db_service):
    source = Event("Historical import", 10)
    preview = prepare_import(
        db_service,
        {"events": [source.to_dict()], "entities": [], "relations": []},
        {"mode": "update"},
    )
    command = ApplyTransferCommand(preview)
    assert command.execute(db_service).success
    accepted = db_service.get_event(source.id).to_dict()
    calculated_event(db_service)
    assert command.undo(db_service).success
    restored = ApplyTransferCommand.from_dict(command.to_dict())
    assert restored.execute(db_service).success
    assert db_service.get_event(source.id).to_dict() == accepted
    assert restored.undo(db_service).success
    db_service.insert_event(replace(source, name="Concurrent replacement"))
    assert not restored.execute(db_service).success


def test_recorded_legacy_event_update_replays_with_observers_and_checks_state(
    db_service,
):
    before = Event("Source", 10)
    after = replace(before, lore_date=20)
    db_service.insert_event(after)
    db_service.insert_map(
        Map(
            name="Observer",
            image_path="map.png",
            attributes={
                "temporal": {
                    "schema": 2,
                    "start": {"anchor": {"anchor_id": f"event:{before.id}"}},
                    "end": {"status": "open"},
                }
            },
        )
    )
    legacy = UpdateEventCommand.from_dict(
        {
            "event_id": before.id,
            "update_data": {"lore_date": 20},
            "previous_event": before.to_dict(),
            "new_event": after.to_dict(),
            "is_executed": True,
        }
    )
    legacy.undo(db_service)
    assert db_service.get_event(before.id).lore_date == 10
    restored = UpdateEventCommand.from_dict(legacy.to_dict())
    assert restored.execute(db_service).success
    assert db_service.get_event(before.id).to_dict() == after.to_dict()
    restored.undo(db_service)
    db_service.insert_event(replace(before, lore_date=11))
    assert not restored.execute(db_service).success
    assert db_service.get_event(before.id).lore_date == 11


def test_active_calendar_creation_restores_previous_active_and_redoes(
    db_service, prepare_timing_command
):
    first = CalendarConfig.create_default()
    first.is_active = True
    db_service.insert_calendar_config(first)
    calculated_event(db_service)
    second = CalendarConfig.create_default()
    second.name = "New active calendar"
    second.is_active = True
    command = prepare_timing_command(CreateCalendarConfigCommand(second))
    assert command.execute(db_service).success
    assert db_service.get_active_calendar_config().id == second.id
    command.undo(db_service)
    assert db_service.get_calendar_config(second.id) is None
    assert db_service.get_active_calendar_config().id == first.id
    restored = ApplyEventTimingPlanCommand.from_dict(command.to_dict())
    assert restored.execute(db_service).success
    assert db_service.get_active_calendar_config().id == second.id


def test_calendar_update_activation_restores_other_active_calendar(
    db_service, prepare_timing_command
):
    first = CalendarConfig.create_default()
    first.is_active = True
    second = CalendarConfig.create_default()
    second.is_active = False
    db_service.insert_calendar_config(first)
    db_service.insert_calendar_config(second)
    calculated_event(db_service)
    command = prepare_timing_command(
        UpdateCalendarConfigCommand(replace(second, is_active=True))
    )
    assert command.execute(db_service).success
    assert db_service.get_active_calendar_config().id == second.id
    restored = ApplyEventTimingPlanCommand.from_dict(command.to_dict())
    restored.undo(db_service)
    assert db_service.get_active_calendar_config().id == first.id
    assert not db_service.get_calendar_config(second.id).is_active
    assert restored.execute(db_service).success
    assert db_service.get_active_calendar_config().id == second.id


def test_first_calendar_activation_undo_restores_no_active_calendar(
    db_service, prepare_timing_command
):
    config = CalendarConfig.create_default()
    config.is_active = False
    db_service.insert_calendar_config(config)
    calculated_event(db_service)
    command = prepare_timing_command(SetActiveCalendarCommand(config.id))
    assert command.execute(db_service).success
    command.undo(db_service)
    assert db_service.get_active_calendar_config() is None
    restored = ApplyEventTimingPlanCommand.from_dict(command.to_dict())
    assert restored.execute(db_service).success
    assert db_service.get_active_calendar_config().id == config.id


def test_recorded_calendar_update_replays_and_refuses_changed_before_state(db_service):
    old = CalendarConfig.create_default()
    old.is_active = True
    new = replace(old, name="Historical rename")
    db_service.insert_calendar_config(new)
    calculated_event(db_service)
    command = UpdateCalendarConfigCommand.from_dict(
        {"config": new.to_dict(), "original_config": old.to_dict(), "is_executed": True}
    )
    command.undo(db_service)
    assert command.execute(db_service).success
    assert db_service.get_calendar_config(old.id).name == new.name
    command.undo(db_service)
    db_service.insert_calendar_config(replace(old, name="Concurrent change"))
    assert not command.execute(db_service).success
    assert db_service.get_calendar_config(old.id).name == "Concurrent change"


def test_legacy_confirmed_deletion_replays_but_new_deletion_blocks(db_service):
    from src.services.temporal_dependency_service import event_temporal_dependencies

    source = Event("Historical source", 10)
    db_service.insert_event(source)
    observer = Map(
        name="Observer",
        image_path="map.png",
        attributes={
            "temporal": {
                "schema": 2,
                "start": {"anchor": {"anchor_id": f"event:{source.id}"}},
                "end": {"status": "open"},
            }
        },
    )
    db_service.insert_map(observer)
    dependencies = event_temporal_dependencies(db_service, source.id)
    assert not DeleteEventCommand(source.id, dependencies).execute(db_service).success
    legacy = DeleteEventCommand.from_dict(
        {
            "event_id": source.id,
            "backup_event": source.to_dict(),
            "backup_relations": [],
            "confirmed_dependencies": dependencies,
            "is_executed": True,
        }
    )
    # A historical deletion is already absent when loaded from executed history.
    db_service.delete_event(source.id)
    legacy.undo(db_service)
    restored = DeleteEventCommand.from_dict(legacy.to_dict())
    assert restored.execute(db_service).success
    assert db_service.get_event(source.id) is None
    restored.undo(db_service)
    db_service.insert_event(replace(source, name="Concurrent edit"))
    assert not restored.execute(db_service).success


def test_recorded_chronology_replays_without_forward_validation(db_service):
    source = calculated_event(db_service)
    metadata = source.attributes["_temporal_v2"] | {
        "constraints": [
            {
                "id": "historical-rule",
                "anchor_a": f"event:{source.id}",
                "relation": "before",
                "anchor_b": "event:missing",
                "min_offset_days": 0,
            }
        ]
    }
    after = replace(source, attributes={"_temporal_v2": metadata})
    db_service.insert_event(after)
    legacy = ApplyChronologyCommand.from_dict(
        {
            "operations": [],
            "previous": {source.id: source.to_dict()},
            "updated": {source.id: after.to_dict()},
            "is_executed": True,
        }
    )
    legacy.undo(db_service)
    restored = ApplyChronologyCommand.from_dict(legacy.to_dict())
    assert restored.execute(db_service).success
    assert db_service.get_event(source.id).to_dict() == after.to_dict()
    restored.undo(db_service)
    db_service.insert_event(replace(source, name="Concurrent edit"))
    assert not restored.execute(db_service).success
