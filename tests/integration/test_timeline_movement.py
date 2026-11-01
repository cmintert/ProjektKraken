"""Explicit graphical moves retain timing authorities and atomic history."""

from copy import deepcopy
from dataclasses import replace

import pytest

from src.commands.event_timing_commands import ApplyEventTimingPlanCommand
from src.commands.event_timing_intents import request_for_command
from src.commands.timeline_move_command import TimelineMoveCommand
from src.core.calendar import CalendarConfig, CalendarConverter, CalendarDate
from src.core.event_timing.definitions import EndpointDefinition, EventTimingDefinition
from src.core.event_timing.solver import resolve_world
from src.core.events import Event
from src.core.temporal_expression import TemporalExpression, TemporalPrecision
from src.services.event_timing.planning import prepare_change
from src.services.event_timing.store import capture, register

pytestmark = pytest.mark.ci_fast


def follower(name, source, value=5.25, unit="days", calendar_id=None, endpoint="start"):
    offset = {"unit": unit, "value": value}
    if calendar_id:
        offset["calendar_id"] = calendar_id
    timing = EventTimingDefinition(
        EndpointDefinition(
            "event",
            anchor_id=f"event:{source.id}",
            endpoint=endpoint,
            offset=offset,
        )
    )
    return Event(name, 0, id=name, attributes=timing.apply({"custom": "retained"}))


def setup_world(db):
    root = Event("Root", 10.125, id="root", lore_duration=2.5)
    child = follower("child", root)
    sibling = follower("sibling", root, -3)
    grandchild = follower("grandchild", child, 1)
    for event in (root, child, sibling, grandchild):
        db.insert_event(event)
    return root, child, sibling, grandchild


def proposal(db, event, target, mode="offset", generation=None):
    snapshot = capture(db)
    converter = (
        CalendarConverter(CalendarConfig.from_json(snapshot["calendar"]))
        if snapshot["calendar"]
        else None
    )
    resolution = resolve_world(
        [Event.from_dict(row) for row in snapshot["events"]], converter
    )
    command = TimelineMoveCommand(
        {
            "event_id": event.id,
            "target": target,
            "mode": mode,
            "generation": generation or resolution.fingerprint,
        }
    )
    return command, prepare_change(snapshot, request_for_command(command, snapshot))


def apply(db, command, plan):
    assert not plan.errors
    register(db, plan)
    wrapped = ApplyEventTimingPlanCommand(command, plan.identity, plan.fingerprint)
    assert wrapped.execute(db).success
    return wrapped


def test_offset_move_preserves_source_units_and_transitive_followers(db_service):
    root, child, sibling, grandchild = setup_world(db_service)
    before = capture(db_service)
    command, plan = proposal(db_service, child, 20.875)
    assert plan.needs_review
    wrapped = apply(db_service, command, plan)
    saved = db_service.get_event(child.id)
    timing = EventTimingDefinition.from_event(saved)
    assert timing.start.anchor_id == "event:root"
    assert timing.start.offset == {"unit": "days", "value": 10.75}
    assert saved.lore_date == 20.875
    assert db_service.get_event(root.id).lore_date == root.lore_date
    assert db_service.get_event(sibling.id).lore_date == 7.125
    assert db_service.get_event(grandchild.id).lore_date == 21.875
    assert saved.attributes["custom"] == "retained"
    wrapped.undo(db_service)
    assert capture(db_service) == before
    restored = ApplyEventTimingPlanCommand.from_dict(wrapped.to_dict())
    assert restored.execute(db_service).success
    assert db_service.get_event(child.id).lore_date == 20.875


def test_chain_from_child_moves_branches_and_preserves_authored_offsets(db_service):
    root, child, sibling, grandchild = setup_world(db_service)
    original = {
        event.id: EventTimingDefinition.from_event(event)
        for event in (child, sibling, grandchild)
    }
    command, plan = proposal(db_service, child, 18.375, "chain")
    apply(db_service, command, plan)
    assert db_service.get_event(root.id).lore_date == 13.125
    assert db_service.get_event(root.id).lore_duration == 2.5
    for key, definition in original.items():
        assert EventTimingDefinition.from_event(db_service.get_event(key)) == definition
    assert db_service.get_event(sibling.id).lore_date == 10.125


@pytest.mark.parametrize("unit,amount", [("months", 1), ("years", 1)])
def test_calendar_offset_snaps_without_converting_or_losing_time(
    db_service, unit, amount
):
    config = CalendarConfig.create_default()
    config.is_active = True
    db_service.insert_calendar_config(config)
    converter = CalendarConverter(config)
    date = converter.to_float(CalendarDate(2024, 1, 31, 0.125))
    root = Event("Root", date, id="root")
    child = follower("child", root, amount, unit, config.id)
    # January 31 + one month is invalid; use a valid original offset.
    if unit == "months":
        child = follower("child", root, 2, unit, config.id)
    db_service.insert_event(root)
    db_service.insert_event(child)
    target = converter.to_float(CalendarDate(2024 if unit == "months" else 2026, 4, 2))
    command, plan = proposal(db_service, child, target)
    apply(db_service, command, plan)
    start = EventTimingDefinition.from_event(db_service.get_event(child.id)).start
    assert start.offset["unit"] == unit
    assert start.offset["calendar_id"] == config.id
    assert float(start.offset["value"]).is_integer()
    assert (
        converter.from_float(db_service.get_event(child.id).lore_date).time_fraction
        == 0.125
    )


def test_calendar_chain_retains_offset_with_changed_spacing(db_service):
    config = CalendarConfig.create_default()
    config.is_active = True
    db_service.insert_calendar_config(config)
    converter = CalendarConverter(config)
    root = Event("Root", converter.to_float(CalendarDate(2024, 1, 1)), id="root")
    child = follower("child", root, 1, "months", config.id)
    db_service.insert_event(root)
    db_service.insert_event(child)
    command, plan = proposal(
        db_service, root, converter.to_float(CalendarDate(2024, 2, 1)), "chain"
    )
    apply(db_service, command, plan)
    assert db_service.get_event(child.id).lore_date == converter.to_float(
        CalendarDate(2024, 3, 1)
    )
    assert EventTimingDefinition.from_event(
        db_service.get_event(child.id)
    ) == EventTimingDefinition.from_event(child)


def test_stale_drag_and_unreviewed_command_write_nothing(db_service):
    root, child, *_ = setup_world(db_service)
    before = capture(db_service)
    with pytest.raises(ValueError, match="Timing changed"):
        proposal(db_service, child, 50, generation="obsolete")
    command, plan = proposal(db_service, child, 50)
    assert not command.execute(db_service).success
    assert capture(db_service) == before
    register(db_service, plan)
    db_service.insert_event(replace(root, lore_date=11))
    wrapped = ApplyEventTimingPlanCommand(command, plan.identity, plan.fingerprint)
    assert not wrapped.execute(db_service).success
    assert db_service.get_event(child.id).to_dict() == child.to_dict()


@pytest.mark.parametrize("target", [float("inf"), float("nan"), 1e13])
def test_invalid_targets_do_not_write(db_service, target):
    _, child, *_ = setup_world(db_service)
    before = capture(db_service)
    with pytest.raises(ValueError):
        proposal(db_service, child, target)
    assert capture(db_service) == before


def test_uncertain_day_dependency_translates_range_without_inventing_date(db_service):
    config = CalendarConfig.create_default()
    config.is_active = True
    db_service.insert_calendar_config(config)
    expression = TemporalExpression(
        config.id, 2024, 1, 1, explicit_outer_start=10, explicit_outer_end=20
    )
    root = Event(
        "Root",
        15,
        id="root",
        attributes=EventTimingDefinition(
            EndpointDefinition(expression=expression.to_dict())
        ).apply({}),
    )
    child = follower("child", root, 5)
    db_service.insert_event(root)
    db_service.insert_event(child)
    command, plan = proposal(db_service, child, 23)
    apply(db_service, command, plan)
    source = EventTimingDefinition.from_event(db_service.get_event(root.id))
    assert source.start.expression == expression.to_dict()
    ranges = plan.after.endpoints["event:child"].ranges
    assert float(ranges[0].upper - ranges[0].lower) == 10


def test_uncertain_calendar_source_is_rejected(db_service):
    config = CalendarConfig.create_default()
    config.is_active = True
    db_service.insert_calendar_config(config)
    expression = TemporalExpression(config.id, 2024, precision=TemporalPrecision.YEAR)
    root = Event(
        "Root",
        0,
        id="root",
        attributes=EventTimingDefinition(
            EndpointDefinition(expression=expression.to_dict())
        ).apply({}),
    )
    child = follower("child", root, 1, "years", config.id)
    db_service.insert_event(root)
    db_service.insert_event(child)
    before = deepcopy(capture(db_service))
    with pytest.raises(ValueError, match="uncertain source|unresolved"):
        proposal(db_service, child, 1)
    assert capture(db_service) == before


def test_chain_translates_explicit_window_and_nominal_date_together(db_service):
    config = CalendarConfig.create_default()
    config.is_active = True
    db_service.insert_calendar_config(config)
    expression = TemporalExpression(
        config.id, 2024, 1, 1, explicit_outer_start=10, explicit_outer_end=20
    )
    root = Event(
        "Root",
        15,
        id="root",
        attributes=EventTimingDefinition(
            EndpointDefinition(expression=expression.to_dict())
        ).apply({}),
    )
    child = follower("child", root, 5)
    db_service.insert_event(root)
    db_service.insert_event(child)
    command, plan = proposal(db_service, child, 23, "chain")
    apply(db_service, command, plan)
    moved = EventTimingDefinition.from_event(
        db_service.get_event(root.id)
    ).start.expression
    assert moved["year"] == 2024
    assert moved["day"] == 4
    assert moved["explicit_outer_start"] == 13
    assert moved["explicit_outer_end"] == 23


def test_wrong_world_move_cannot_apply_to_identical_facts(db_service):
    _, child, *_ = setup_world(db_service)
    command, _ = proposal(db_service, child, 30)
    command.intent["world_id"] = "another-world.kraken"
    snapshot = capture(db_service)
    with pytest.raises(ValueError, match="active world changed"):
        prepare_change(snapshot, request_for_command(command, snapshot))
    assert capture(db_service) == snapshot


def test_chain_moves_independent_manual_end_and_explicit_zero_duration(db_service):
    root, child, *_ = setup_world(db_service)
    timing = EventTimingDefinition(
        EndpointDefinition(instant=10.125),
        "independent",
        end=EndpointDefinition(instant=12.625),
    )
    db_service.insert_event(replace(root, attributes=timing.apply({})))
    zero = Event(
        "Zero",
        0,
        id="zero",
        attributes=EventTimingDefinition(
            EndpointDefinition("event", anchor_id="event:child"),
            "duration",
            duration_days=0,
        ).apply({}),
    )
    db_service.insert_event(zero)
    command, plan = proposal(db_service, child, 18.375, "chain")
    apply(db_service, command, plan)
    moved = EventTimingDefinition.from_event(db_service.get_event(root.id))
    assert moved.start.instant == 13.125
    assert moved.end.instant == 15.625
    assert (
        EventTimingDefinition.from_event(db_service.get_event(zero.id)).duration_days
        == 0
    )


@pytest.mark.parametrize("precision", list(TemporalPrecision))
def test_manual_precision_and_components_survive_whole_day_chain_move(
    db_service, precision
):
    config = CalendarConfig.create_default()
    config.is_active = True
    db_service.insert_calendar_config(config)
    converter = CalendarConverter(config)
    order = list(TemporalPrecision)
    expression = TemporalExpression(
        config.id,
        2023,
        month=3
        if order.index(precision) >= order.index(TemporalPrecision.MONTH)
        else None,
        day=2 if order.index(precision) >= order.index(TemporalPrecision.DAY) else None,
        hour=11
        if order.index(precision) >= order.index(TemporalPrecision.HOUR)
        else None,
        minute=12
        if order.index(precision) >= order.index(TemporalPrecision.MINUTE)
        else None,
        second=13 if precision == TemporalPrecision.SECOND else None,
        precision=precision,
    )
    root = Event(
        "Root",
        0,
        id="root",
        attributes=EventTimingDefinition(
            EndpointDefinition(expression=expression.to_dict())
        ).apply({}),
    )
    db_service.insert_event(root)
    target = expression.representative_time(converter) + 1
    if precision in {TemporalPrecision.YEAR, TemporalPrecision.MONTH}:
        with pytest.raises(ValueError, match="authored precision"):
            proposal(db_service, root, target, "chain")
        return
    command, plan = proposal(db_service, root, target, "chain")
    apply(db_service, command, plan)
    moved = EventTimingDefinition.from_event(
        db_service.get_event(root.id)
    ).start.expression
    for field in ("precision", "hour", "minute", "second", "qualifier", "calendar_id"):
        assert moved[field] == expression.to_dict()[field]


def test_invalid_independent_end_and_cycle_are_rejected_without_writes(db_service):
    root, child, *_ = setup_world(db_service)
    timing = EventTimingDefinition.from_event(child)
    db_service.insert_event(
        replace(
            child,
            attributes=replace(
                timing, end_mode="independent", end=EndpointDefinition(instant=18)
            ).apply(child.attributes),
        )
    )
    before = capture(db_service)
    command, plan = proposal(db_service, child, 30)
    assert plan.errors
    with pytest.raises(ValueError):
        register(db_service, plan)
    assert capture(db_service) == before
    db_service.insert_event(
        replace(
            root,
            attributes=EventTimingDefinition(
                EndpointDefinition("event", anchor_id="event:child")
            ).apply(root.attributes),
        )
    )
    before = capture(db_service)
    with pytest.raises(ValueError, match="cyclic|unresolved"):
        proposal(db_service, child, 20, "chain")
    assert capture(db_service) == before


def test_map_consumer_is_reviewed_and_not_part_of_chain(db_service):
    from src.core.map import Map

    root, child, *_ = setup_world(db_service)
    observer = Map(
        name="Historical map",
        image_path="map.png",
        attributes={
            "temporal": {
                "schema": 2,
                "start": {"anchor": {"anchor_id": "event:child"}},
                "end": {"status": "open"},
            }
        },
    )
    db_service.insert_map(observer)
    command, plan = proposal(db_service, child, 30, "chain")
    assert any(
        row["kind"] == "map" and row["id"] == observer.id for row in plan.consequences
    )
    apply(db_service, command, plan)
    assert db_service.get_map(observer.id).attributes == observer.attributes


def test_chain_rejects_redo_after_authority_changes(db_service):
    root, child, *_ = setup_world(db_service)
    command, plan = proposal(db_service, child, 30, "chain")
    wrapped = apply(db_service, command, plan)
    wrapped.undo(db_service)
    db_service.insert_event(replace(root, lore_date=9))
    before = capture(db_service)
    assert not wrapped.execute(db_service).success
    assert capture(db_service) == before


def test_chronology_is_a_constraint_not_a_chain_membership_edge(db_service):
    from src.core.temporal_constraints import TemporalConstraint, TemporalConstraintKind

    root, child, *_ = setup_world(db_service)
    boundary = Event("Boundary", 25, id="boundary")
    db_service.insert_event(boundary)
    timing = EventTimingDefinition.from_event(child)
    attributes = timing.apply(child.attributes)
    rule = TemporalConstraint(
        "event:child",
        TemporalConstraintKind.BEFORE,
        "event:boundary",
        id="before-boundary",
    ).to_dict()
    attributes["_temporal_v2"]["constraints"] = [rule]
    db_service.insert_event(replace(child, attributes=attributes))
    original = capture(db_service)
    _, rejected = proposal(db_service, child, 30, "chain")
    assert rejected.errors
    with pytest.raises(ValueError):
        register(db_service, rejected)
    assert capture(db_service) == original
    command, plan = proposal(db_service, child, 20, "chain")
    apply(db_service, command, plan)
    assert db_service.get_event(boundary.id).to_dict() == boundary.to_dict()
    assert db_service.get_event(child.id).attributes["_temporal_v2"]["constraints"] == [
        rule
    ]


def test_custom_calendar_month_count_variants_and_negative_years(db_service):
    from src.core.calendar import MonthDefinition, YearVariant

    config = CalendarConfig.create_default()
    config.months = [
        MonthDefinition("Frost", "Fro", 20),
        MonthDefinition("Sun", "Sun", 40),
    ]
    config.year_variants = [
        YearVariant(-1, [*config.months, MonthDefinition("Feast", "Fea", 10)])
    ]
    config.leap_year_rules = []
    config.is_active = True
    db_service.insert_calendar_config(config)
    converter = CalendarConverter(config)
    root = Event("Root", converter.to_float(CalendarDate(-2, 2, 5, 0.375)), id="root")
    child = follower("child", root, 1, "months", config.id)
    db_service.insert_event(root)
    db_service.insert_event(child)
    target = converter.to_float(CalendarDate(1, 1, 5, 0.375))
    command, plan = proposal(db_service, child, target)
    apply(db_service, command, plan)
    assert db_service.get_event(child.id).lore_date == target
    offset = EventTimingDefinition.from_event(
        db_service.get_event(child.id)
    ).start.offset
    assert offset == {"unit": "months", "value": 6.0, "calendar_id": config.id}


def test_marginal_widths_do_not_authorize_changed_uncertainty_correlations(db_service):
    from src.core.temporal_constraints import TemporalConstraint, TemporalConstraintKind

    config = CalendarConfig.create_default()
    config.is_active = True
    db_service.insert_calendar_config(config)
    events = []
    for name, lower, upper in (("first", 0, 100), ("second", 50, 150)):
        expression = TemporalExpression(
            config.id, 2024, 1, 1, explicit_outer_start=lower, explicit_outer_end=upper
        )
        events.append(
            Event(
                name,
                (lower + upper) / 2,
                id=name,
                attributes=EventTimingDefinition(
                    EndpointDefinition(expression=expression.to_dict())
                ).apply({}),
            )
        )
    events[0].attributes["_temporal_v2"]["constraints"] = [
        TemporalConstraint(
            "event:first", TemporalConstraintKind.BEFORE, "event:second", id="ordering"
        ).to_dict()
    ]
    for event in events:
        db_service.insert_event(event)
    before = capture(db_service)
    _, plan = proposal(db_service, events[0], 51)
    assert any("correlated" in error for error in plan.errors)
    with pytest.raises(ValueError):
        register(db_service, plan)
    assert capture(db_service) == before


def test_known_start_with_unresolved_required_end_cannot_move(db_service):
    root, child, *_ = setup_world(db_service)
    timing = EventTimingDefinition.from_event(child)
    broken = replace(
        timing,
        end_mode="independent",
        end=EndpointDefinition("event", anchor_id="event:missing"),
    )
    db_service.insert_event(replace(child, attributes=broken.apply(child.attributes)))
    before = capture(db_service)
    with pytest.raises(ValueError, match="unresolved"):
        proposal(db_service, root, 20)
    assert capture(db_service) == before
