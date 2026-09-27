"""Acceptance examples for precision and shared validity semantics."""

import pytest

from src.core.calendar import CalendarConfig, CalendarConverter
from src.core.date_parser import DateParser
from src.core.entities import Entity
from src.core.graph_temporal import GraphTemporalMode, evaluate_graph_relation
from src.core.temporal_expression import TemporalExpression
from src.core.temporal_resolver import TemporalResolver
from src.core.temporal_window import TemporalValidity, resolve_temporal_window


def test_malformed_boundary_is_indeterminate():
    window = resolve_temporal_window({"temporal": {"schema": 1, "start": []}})
    assert window.status_at(0) == TemporalValidity.INDETERMINATE
    assert window.error


def test_adjacent_periods_cannot_be_same_transition(calendar):
    from src.core.temporal_constraints import (
        TemporalConstraint,
        TemporalConstraintKind,
        validate_constraints,
    )

    parser = DateParser(calendar._config)
    anchors = {
        year: parser.parse_expression(year).resolve_bounds(calendar)
        for year in ("961", "962")
    }
    assert validate_constraints(
        [TemporalConstraint("961", TemporalConstraintKind.SAME_AS, "962")], anchors
    )


@pytest.mark.parametrize("text", ["before 961", "after 961", "between 961 and 964"])
def test_drag_preserves_explicit_window_meaning(calendar, text):
    from src.core.temporal_expression import move_expression

    expression = DateParser(calendar._config).parse_expression(text)
    moved = move_expression(expression, calendar.start_of_year(970) + 20, calendar)
    assert moved.display_text(calendar).startswith(text.split()[0])
    assert "970" in moved.display_text(calendar)
    assert (
        moved.explicit_outer_start is not None or moved.explicit_outer_end is not None
    )


def test_exclusive_roles_distinguish_shared_and_independent_transitions(calendar):
    from src.core.events import Event
    from src.services.temporal_conflict_service import exclusive_role_conflicts

    event = Event(
        id="handover", name="Succession", lore_date=0, attributes=metadata(calendar)
    )

    def role(identity, source, side, boundary):
        return {
            "id": identity,
            "source_id": source,
            "target_id": "house",
            "rel_type": "Prima of",
            "attributes": {
                "exclusive": True,
                "temporal": {
                    "schema": 1,
                    "start": {"status": "open"},
                    "end": {"status": "open"},
                    side: boundary,
                },
            },
        }

    shared = {"anchor": {"anchor_id": "event:handover"}}
    first = role("a", "Tasgillia", "end", shared)
    second = role("b", "Kalliste", "start", shared)
    assert exclusive_role_conflicts([first, second], [event], calendar) == []
    second["attributes"]["temporal"]["start"] = {
        "expression": metadata(calendar)["_temporal_v2"]["expression"]
    }
    conflicts = exclusive_role_conflicts([first, second], [event], calendar)
    assert len(conflicts) == 1
    assert conflicts[0].severity.value == "warning"


@pytest.fixture
def calendar():
    return CalendarConverter(CalendarConfig.create_default())


def metadata(calendar, text="961"):
    expression = DateParser(calendar._config).parse_expression(text)
    return {"_temporal_v2": {"schema": 1, "expression": expression.to_dict()}}


def test_year_roundtrip_and_calendar_bounds(calendar):
    data = metadata(calendar)["_temporal_v2"]["expression"]
    expression = TemporalExpression.from_dict(data)
    assert expression.display_text(calendar) == "961"
    assert expression.month is None and expression.day is None
    bounds = expression.resolve_bounds(calendar)
    assert bounds.hard_start == calendar.start_of_year(961)
    assert bounds.hard_end == calendar.start_of_next_year(961)
    assert (
        bounds.hard_start < expression.representative_time(calendar) < bounds.hard_end
    )


@pytest.mark.parametrize("text", ["c. 961", "961?", "c. 961?"])
def test_qualifications_supply_no_invented_evidence(calendar, text):
    expression = DateParser(calendar._config).parse_expression(text)
    assert not expression.resolve_bounds(calendar).has_hard_bounds
    assert expression.display_text() == text


def test_sometime_is_asserted_year(calendar):
    expression = DateParser(calendar._config).parse_expression("sometime in 961")
    assert expression.precision.value == "year"
    assert expression.resolve_bounds(calendar).has_hard_bounds


def test_shared_succession_validity(calendar):
    kwargs = dict(
        source_event_attributes=metadata(calendar),
        source_event_id="execution",
        converter=calendar,
    )
    end = resolve_temporal_window({"valid_to_event": True}, 100, **kwargs)
    start = resolve_temporal_window({"valid_from_event": True}, 100, **kwargs)
    early = calendar.start_of_year(961)
    late = calendar.start_of_next_year(961)
    assert end.status_at(early - 1) == TemporalValidity.DEFINITE
    assert start.status_at(early - 1) == TemporalValidity.INACTIVE
    assert end.status_at((early + late) / 2) == TemporalValidity.POSSIBLE
    assert start.status_at((early + late) / 2) == TemporalValidity.POSSIBLE
    assert end.status_at(late) == TemporalValidity.INACTIVE
    assert start.status_at(late) == TemporalValidity.DEFINITE
    assert end.end_bounds.anchor_id == start.start_bounds.anchor_id


def test_unknown_is_not_open():
    unknown = resolve_temporal_window(
        {"temporal": {"start": {"status": "unknown"}, "end": {"status": "open"}}}
    )
    opened = resolve_temporal_window(
        {"temporal": {"start": {"status": "open"}, "end": {"status": "open"}}}
    )
    assert unknown.status_at(0) == TemporalValidity.INDETERMINATE
    assert opened.status_at(0) == TemporalValidity.DEFINITE


def test_possible_effect_survives_in_state(calendar):
    entity = Entity(name="Tasgillia", type="person", attributes={"office": "Prima"})
    relation = {
        "id": "r",
        "source_id": "execution",
        "source_event_date": 10,
        "source_event_attributes": metadata(calendar),
        "attributes": {
            "valid_from_event": True,
            "payload": {"attributes": {"office": "none"}},
        },
    }
    time = calendar.start_of_year(961) + 10
    state = TemporalResolver().resolve_entity_state(entity, [relation], time, calendar)
    assert state.attributes["office"] == "Prima"
    assert state.ambiguous_attributes["office"] == ["Prima", "none"]
    assert state.to_dict()["possible_effects"][0]["validity"] == "possible"


def test_graph_modes_share_evaluator(calendar):
    relation = {
        "id": "r",
        "source_id": "e",
        "target_id": "a",
        "attributes": {"valid_to_event": True},
        "source_event_date": 0,
        "source_event_attributes": metadata(calendar),
    }
    time = calendar.start_of_next_year(961)
    assert (
        evaluate_graph_relation(relation, time, calendar, GraphTemporalMode.AT_PLAYHEAD)
        is None
    )
    edge = evaluate_graph_relation(
        relation, time, calendar, GraphTemporalMode.ALL_RELATIONS
    )
    assert edge["validity_status"] == "inactive"


def test_legacy_exact_boundary_stays_exact():
    window = resolve_temporal_window({"valid_to_event": True}, 42)
    assert window.status_at(41.999) == TemporalValidity.DEFINITE
    assert window.status_at(42) == TemporalValidity.INACTIVE


def test_shared_anchor_excludes_false_overlap(calendar):
    from src.core.temporal_constraints import overlap_status

    context = dict(
        source_event_attributes=metadata(calendar),
        source_event_id="e",
        converter=calendar,
    )
    first = resolve_temporal_window({"valid_to_event": True}, 0, **context)
    second = resolve_temporal_window({"valid_from_event": True}, 0, **context)
    assert overlap_status(first, second) == TemporalValidity.INACTIVE
    independent = resolve_temporal_window(
        {"valid_from_event": True}, 0, **{**context, "source_event_id": "independent"}
    )
    assert overlap_status(first, independent) == TemporalValidity.POSSIBLE


def test_order_cycles_include_equal_anchor_contraction():
    from src.core.temporal_constraints import (
        TemporalConstraint,
        validate_constraints,
    )
    from src.core.temporal_constraints import (
        TemporalConstraintKind as Kind,
    )

    assert validate_constraints(
        [
            TemporalConstraint("a", Kind.BEFORE, "b"),
            TemporalConstraint("b", Kind.SAME_AS, "a"),
        ]
    )
    assert not validate_constraints([TemporalConstraint("a", Kind.BEFORE, "b")])


def test_unordered_coarse_effects_do_not_use_relation_id(calendar):
    relations = [
        {
            "id": identity,
            "source_id": identity,
            "source_event_date": 0,
            "source_event_attributes": metadata(calendar),
            "attributes": {
                "valid_from_event": True,
                "payload": {"attributes": {"office": identity}},
            },
        }
        for identity in ["a", "b"]
    ]
    entity = Entity(name="Person", type="person", attributes={"office": "baseline"})
    state = TemporalResolver().resolve_entity_state(
        entity, relations, calendar.start_of_year(962), calendar
    )
    assert state.attributes["office"] == "baseline"
    assert len(state.possible_effects) == 2
    assert set(state.ambiguous_attributes["office"]) == {"baseline", "a", "b"}


@pytest.mark.parametrize("year", [-10, -1, 0, 1, 4, 961])
def test_calendar_periods_meet_without_gaps(calendar, year):
    months = calendar._config.get_months_for_year(year)
    for month in range(1, len(months)):
        assert calendar.start_of_next_month(year, month) == calendar.start_of_month(
            year, month + 1
        )
    assert calendar.start_of_next_month(
        year, len(months)
    ) == calendar.start_of_next_year(year)


def test_unknown_anchor_and_bad_calendar_are_indeterminate(calendar):
    window = resolve_temporal_window(
        {
            "temporal": {
                "start": {"anchor": {"anchor_id": "event:deleted"}},
                "end": {"status": "open"},
            }
        },
        converter=calendar,
    )
    assert window.status_at(50) == TemporalValidity.INDETERMINATE
    assert window.error


def test_graph_projection_preserves_status():
    from src.gui.widgets.graph_view.graph_projection import GraphProjection

    edge = {
        "id": "r",
        "source_id": "a",
        "target_id": "b",
        "rel_type": "Prima",
        "validity_status": "possible",
        "temporal_summary": "Ends sometime in 961",
    }
    projected = GraphProjection.project_edges([edge])
    assert projected[0]["validity_status"] == "possible"
    assert projected[0]["temporal_summary"] == edge["temporal_summary"]
