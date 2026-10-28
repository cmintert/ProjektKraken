"""Prepared timing plans exercise worker-owned persistence and exact undo."""

from dataclasses import replace

import pytest

from src.commands.event_commands import DeleteEventCommand, UpdateEventCommand
from src.commands.event_timing_commands import ApplyEventTimingPlanCommand
from src.core.event_timing.definitions import EndpointDefinition, EventTimingDefinition
from src.core.events import Event
from src.services.event_timing.planning import TimingChangeRequest, prepare_change
from src.services.event_timing.store import capture, register

pytestmark = pytest.mark.ci_fast


def world(db):
    root = Event(name="Treaty", lore_date=10, id="root")
    child = Event(name="War", lore_date=2, id="child")
    definition = EventTimingDefinition(
        EndpointDefinition(instant=2),
        "independent",
        EndpointDefinition("event", anchor_id="event:root"),
    )
    child.attributes = definition.apply({})
    db.insert_event(root)
    db.insert_event(child)
    return root, child


def prepare(db, root, patch):
    request = TimingChangeRequest(updates={root.id: patch}, world_id=db.db_path)
    plan = prepare_change(capture(db), request)
    assert not plan.errors
    register(db, plan)
    command = ApplyEventTimingPlanCommand(
        UpdateEventCommand(root.id, patch), plan.identity, plan.fingerprint
    )
    return command, plan


def test_reference_reschedule_cascades_atomically_and_undo_redo(db_service):
    root, child = world(db_service)
    previous = {event.id: event.to_dict() for event in db_service.get_all_events()}
    command, plan = prepare(db_service, root, {"lore_date": 20})
    assert plan.needs_review
    assert command.execute(db_service).success
    assert db_service.get_event("child").lore_duration == 18
    assert db_service.get_event("child").modified_at == child.modified_at
    command.undo(db_service)
    assert {
        event.id: event.to_dict() for event in db_service.get_all_events()
    } == previous
    restored = ApplyEventTimingPlanCommand.from_dict(command.to_dict())
    assert restored.execute(db_service).success
    assert db_service.get_event("child").lore_duration == 18


def test_unregistered_stale_and_unconfirmed_changes_write_nothing(db_service):
    root, child = world(db_service)
    assert (
        not UpdateEventCommand(root.id, {"lore_date": 20}).execute(db_service).success
    )
    command, plan = prepare(db_service, root, {"lore_date": 20})
    db_service.insert_event(replace(root, name="Changed source label"))
    result = command.execute(db_service)
    assert not result.success
    assert db_service.get_event(root.id).lore_date == 10
    assert db_service.get_event(child.id).lore_date == 2


def test_all_references_block_deletion_even_old_confirmation(db_service):
    root, _ = world(db_service)
    rejected = DeleteEventCommand(root.id, ["old confirmation"]).execute(db_service)
    assert not rejected.success
    assert rejected.data["blocked_temporal_dependencies"]
    assert db_service.get_event(root.id) is not None


def test_calendar_or_interval_conflict_blocks_plan(db_service):
    root, _ = world(db_service)
    plan = prepare_change(
        capture(db_service), TimingChangeRequest(updates={root.id: {"lore_date": 1}})
    )
    assert plan.errors
    with pytest.raises(ValueError):
        register(db_service, plan)


def test_unrelated_content_edit_preserves_broken_reference(db_service):
    event = Event(
        name="Broken import",
        lore_date=None,
        id="broken",
        attributes=EventTimingDefinition(
            EndpointDefinition("event", anchor_id="event:missing")
        ).apply({}),
    )
    db_service.insert_event(event)
    plan = prepare_change(
        capture(db_service),
        TimingChangeRequest(updates={event.id: {"description": "Still editable"}}),
    )
    assert not plan.errors
    register(db_service, plan)
    command = ApplyEventTimingPlanCommand(
        UpdateEventCommand(event.id, {"description": "Still editable"}),
        plan.identity,
        plan.fingerprint,
    )
    assert command.execute(db_service).success
    assert db_service.get_event(event.id).lore_date is None


def test_plan_confirmation_is_bound_to_its_actual_command(db_service):
    root, _ = world(db_service)
    _, plan = prepare(db_service, root, {"lore_date": 20})
    forged = ApplyEventTimingPlanCommand(
        UpdateEventCommand(root.id, {"lore_date": 100}), plan.identity, plan.fingerprint
    )
    assert not forged.execute(db_service).success
    assert db_service.get_event(root.id).lore_date == 10


def test_undo_preserves_unrelated_content_changed_during_review(db_service):
    root, child = world(db_service)
    command, _ = prepare(db_service, root, {"lore_date": 20})
    db_service.insert_event(
        replace(child, description="Written while the preview was open")
    )
    assert command.execute(db_service).success
    command.undo(db_service)
    assert (
        db_service.get_event(child.id).description
        == "Written while the preview was open"
    )
