"""Real caller, import, persistence and cancellation boundaries for joint timing."""

from dataclasses import replace
from fractions import Fraction

import pytest

from src.cli.event_timing import execute_timing
from src.commands.event_commands import UpdateEventCommand
from src.commands.transfer_commands import ApplyTransferCommand
from src.core.event_timing.constraints import (
    ZERO,
    Constraint,
    ConstraintBranch,
    TimingCancelled,
)
from src.core.event_timing.definitions import EndpointDefinition, EventTimingDefinition
from src.core.event_timing.solver import resolve_world
from src.core.events import Event
from src.services.event_timing.planning import TimingChangeRequest, prepare_change
from src.services.event_timing.store import capture
from src.services.transfer_import import prepare_import

pytestmark = pytest.mark.ci_fast


def test_cli_requires_repeatable_explicit_cascade_fingerprint(db_service):
    root = Event("Treaty", 10, id="root")
    child = Event(
        "Aftermath",
        0,
        id="child",
        attributes=EventTimingDefinition(
            EndpointDefinition("event", anchor_id="event:root")
        ).apply({}),
    )
    db_service.insert_event(root)
    db_service.insert_event(child)
    result = execute_timing(UpdateEventCommand(root.id, {"lore_date": 20}), db_service)
    assert not result.success
    fingerprint = result.data["timing_review"]["fingerprint"]
    assert db_service.get_event(root.id).lore_date == 10
    assert not execute_timing(
        UpdateEventCommand(root.id, {"lore_date": 20}), db_service, "different"
    ).success
    assert execute_timing(
        UpdateEventCommand(root.id, {"lore_date": 20}), db_service, fingerprint
    ).success
    assert db_service.get_event(child.id).lore_date == 20


def test_scalar_date_and_tags_do_not_discard_authority(db_service):
    event = Event(
        "Manual",
        10,
        id="manual",
        attributes=EventTimingDefinition(EndpointDefinition(instant=10)).apply({}),
    )
    db_service.insert_event(event)
    attributes = {**event.attributes, "_tags": ["evidence"]}
    assert execute_timing(
        UpdateEventCommand(event.id, {"lore_date": 12, "attributes": attributes}),
        db_service,
    ).success
    saved = db_service.get_event(event.id)
    assert saved.lore_date == 12
    assert saved.tags == ["evidence"]
    assert EventTimingDefinition.from_event(saved).start.instant == 12


def test_import_retains_missing_endpoint_without_inventing_date(
    db_service, prepare_timing_command
):
    event = Event(
        "Broken imported Event",
        None,
        id="00000000-0000-4000-8000-000000000001",
        attributes=EventTimingDefinition(
            EndpointDefinition("event", anchor_id="event:missing", endpoint="end")
        ).apply({}),
    )
    review = prepare_import(
        db_service,
        {"events": [event.to_dict()], "entities": [], "relations": []},
        {"mode": "update"},
    )
    assert not review["errors"], review
    command = prepare_timing_command(ApplyTransferCommand(review))
    assert command.execute(db_service).success
    saved = db_service.get_event(event.id)
    assert saved.lore_date is None
    assert EventTimingDefinition.from_event(saved).start.source == "event:missing:end"
    command.undo(db_service)
    assert db_service.get_event(event.id) is None
    assert command.execute(db_service).success


def test_redo_refuses_changed_source_after_undo(db_service, prepare_timing_command):
    event = Event("Manual", 10, id="root")
    db_service.insert_event(event)
    command = prepare_timing_command(UpdateEventCommand(event.id, {"lore_date": 20}))
    assert command.execute(db_service).success
    command.undo(db_service)
    db_service.insert_event(replace(event, lore_date=11))
    assert not command.execute(db_service).success
    assert db_service.get_event(event.id).lore_date == 11


def test_feasible_placement_respects_strict_correlated_bounds():
    edges = [
        Constraint(ZERO, "a", Fraction(10)),
        Constraint("a", ZERO, Fraction(0)),
        Constraint("a", "b", Fraction(2)),
        Constraint("b", "a", Fraction(-1), True),
    ]
    branch = ConstraintBranch(("a", "b"), edges)
    placed = branch.placement()
    for edge in edges:
        delta = placed[edge.target] - placed[edge.source]
        assert delta < edge.limit if edge.strict else delta <= edge.limit


def test_cancelled_validation_never_produces_a_saveable_plan(db_service):
    event = Event("Manual", 10)
    db_service.insert_event(event)
    with pytest.raises(TimingCancelled):
        prepare_change(
            capture(db_service),
            TimingChangeRequest(updates={event.id: {"lore_date": 20}}),
            cancel=lambda: True,
        )
    assert db_service.get_event(event.id).lore_date == 10


def test_serialized_joint_result_keeps_the_selected_feasible_placement():
    from src.core.event_timing.resolution import TemporalWorldResolution

    result = resolve_world([Event("Exact", 10, id="a")])
    restored = TemporalWorldResolution.from_dict(result.to_dict())
    assert restored.endpoints["event:a"].coordinate == 10
    assert restored.to_dict() == result.to_dict()


def test_unplaced_appearance_remains_available_in_all_history_context(db_service):
    from src.core.authoring_context import EntityAuthoringContext
    from src.core.entities import Entity
    from src.services.authoring_context_builder import AuthoringContextBuilder

    entity = Entity("Witness", "Person", id="00000000-0000-4000-8000-000000000010")
    event = Event(
        "Unplaced testimony",
        None,
        id="00000000-0000-4000-8000-000000000011",
        attributes=EventTimingDefinition(
            EndpointDefinition("event", anchor_id="event:missing")
        ).apply({}),
    )
    db_service.insert_entity(entity)
    db_service.insert_event(event)
    db_service.insert_relation(event.id, entity.id, "involved")
    context = AuthoringContextBuilder(db_service).build_entity_context(entity.id)
    assert context.event_appearances[0].event.lore_date is None
    assert context.event_appearances[0].event.temporal_status == "indeterminate"
    assert EntityAuthoringContext.from_dict(context.to_dict()) == context


def test_legacy_independent_end_is_retained_by_scalar_moves(db_service):
    from src.core.calendar import CalendarConfig
    from src.core.date_parser import DateParser

    config = CalendarConfig.create_default()
    config.is_active = True
    db_service.insert_calendar_config(config)
    parser = DateParser(config)
    start, end = (
        parser.parse_expression("1 January 1"),
        parser.parse_expression("10 January 1"),
    )
    event = Event(
        "Legacy interval",
        0,
        id="legacy",
        lore_duration=9,
        attributes={
            "_temporal_v2": {
                "schema": 1,
                "expression": start.to_dict(),
                "end_expression": end.to_dict(),
            }
        },
    )
    db_service.insert_event(event)
    assert execute_timing(
        UpdateEventCommand(event.id, {"lore_date": 2}), db_service
    ).success
    saved = db_service.get_event(event.id)
    assert saved.attributes["_temporal_v2"]["end_expression"] == end.to_dict()
    assert saved.lore_duration is None  # Independent day-precision dates imply a range.


def test_world_validation_reports_collective_interval_impossibility(db_service):
    from src.core.calendar import CalendarConfig
    from src.core.temporal_expression import TemporalExpression
    from src.services.world_validator import WorldValidator

    config = CalendarConfig.create_default()
    config.is_active = True
    db_service.insert_calendar_config(config)
    uncertain = EndpointDefinition(
        expression=TemporalExpression(
            config.id, 1, 1, 1, explicit_outer_start=0, explicit_outer_end=10
        ).to_dict()
    )
    root = Event(
        "Uncertain root",
        5,
        id="root",
        attributes=EventTimingDefinition(uncertain).apply({}),
    )
    first = Event(
        "Upper restriction",
        0,
        id="upper",
        attributes=EventTimingDefinition(
            EndpointDefinition("event", anchor_id="event:root"),
            "independent",
            EndpointDefinition(instant=5),
        ).apply({}),
    )
    second = Event(
        "Lower restriction",
        6,
        id="lower",
        attributes=EventTimingDefinition(
            EndpointDefinition(instant=6),
            "independent",
            EndpointDefinition("event", anchor_id="event:root"),
        ).apply({}),
    )
    for event in (root, first, second):
        db_service.insert_event(event)
    report = WorldValidator(db_service, editorial_checks=False).validate()
    assert any(
        issue.fingerprint.startswith("event-timing:infeasible")
        for issue in report.issues
    )


def test_repository_range_query_uses_start_projection_without_writing(db_service):
    from src.services.repositories.event_repository import EventRepository

    root = Event("Source", 20, id="source", lore_duration=80)
    child = Event(
        "Uncached dependent",
        None,
        id="child",
        attributes=EventTimingDefinition(
            EndpointDefinition("event", anchor_id="event:source")
        ).apply({}),
    )
    broken = Event(
        "Unplaced",
        None,
        id="broken",
        attributes=EventTimingDefinition(
            EndpointDefinition("event", anchor_id="event:missing")
        ).apply({}),
    )
    for event in (root, child, broken):
        db_service.insert_event(event)
    repository = EventRepository(db_service.get_connection())
    assert {event.id for event in repository.get_by_date_range(19, 21)} == {
        root.id,
        child.id,
    }
    assert repository.get_by_date_range(90, 99) == []
    assert db_service.get_event(child.id).lore_date is None
