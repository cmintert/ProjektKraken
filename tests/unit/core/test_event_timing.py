"""Joint timing regressions independent of Qt and persistence."""

from fractions import Fraction

import pytest

from src.core.event_timing.constraints import (
    ZERO,
    Constraint,
    ConstraintBranch,
    TimingCancelled,
)
from src.core.event_timing.definitions import EndpointDefinition, EventTimingDefinition
from src.core.event_timing.solver import resolve_world
from src.core.events import Event

pytestmark = pytest.mark.ci_fast


def manual(name, date):
    return Event(name=name, lore_date=date, id=name)


def followed(name, source, endpoint="start", offset=0, end=None, duration=None):
    definition = EventTimingDefinition(
        EndpointDefinition(
            "event",
            anchor_id=f"event:{source}",
            endpoint=endpoint,
            offset={"unit": "days", "value": offset},
        ),
        "independent" if end else "duration" if duration is not None else "none",
        end=end,
        duration_days=duration,
    )
    return Event(name=name, id=name, lore_date=0, attributes=definition.apply({}))


def uncertain(name, lower=1, upper=10):
    # Authored explicit ranges use the existing calendar expression adapter.
    from src.core.calendar import CalendarConfig, CalendarConverter
    from src.core.temporal_expression import TemporalExpression

    config = CalendarConfig.create_default()
    config.id = "test"
    converter = CalendarConverter(config)
    expression = TemporalExpression(
        calendar_id="test",
        year=1,
        month=1,
        day=1,
        explicit_outer_start=lower,
        explicit_outer_end=upper,
    )
    event = Event(
        name=name,
        id=name,
        lore_date=5,
        attributes={"_temporal_v2": {"schema": 1, "expression": expression.to_dict()}},
    )
    return event, converter


def test_strict_zero_cycle_is_infeasible_without_epsilon():
    branch = ConstraintBranch(
        ["x", "y"],
        [Constraint("x", "y", Fraction(0), True), Constraint("y", "x", Fraction(0))],
    )
    assert not branch.feasible


def test_all_endpoint_combinations_and_explicit_zero_end():
    source = followed("source", "root", duration=0)
    events = [manual("root", 10), source]
    for source_endpoint in ("start", "end"):
        end = EndpointDefinition(
            "event",
            anchor_id="event:source",
            endpoint=source_endpoint,
            offset={"unit": "days", "value": 3},
        )
        event = followed("child", "source", source_endpoint, 2, end=end)
        result = resolve_world([*events, event])
        assert not result.issues
        assert result.endpoints["event:child"].coordinate == 12
        assert result.exact_duration("child") == 1
    assert resolve_world(events).endpoints["event:source:end"].coordinate == 10


def test_same_uncertain_root_proves_exact_duration():
    root, converter = uncertain("root")
    end = EndpointDefinition(
        "event", anchor_id="event:root", offset={"unit": "days", "value": 5}
    )
    result = resolve_world(
        [root, followed("child", "root", offset=2, end=end)], converter
    )
    assert not result.issues
    assert result.exact_duration("child") == 3
    assert result.endpoints["event:child"].bounds().hard_start == 3


def test_collectively_impossible_intervals_are_rejected():
    x, converter = uncertain("x")
    y, _ = uncertain("y")
    a = followed("a", "x", end=EndpointDefinition("event", anchor_id="event:y"))
    b = followed(
        "b", "y", offset=1, end=EndpointDefinition("event", anchor_id="event:x")
    )
    assert not resolve_world([x, y, a], converter).issues
    assert not resolve_world([x, y, b], converter).issues
    assert any(
        issue.code == "infeasible"
        for issue in resolve_world([x, y, a, b], converter).issues
    )


def test_inferred_bounds_preserve_evidence_and_open_upper_bound():
    root, converter = uncertain("root")
    child = followed("child", "root", end=EndpointDefinition(instant=5))
    result = resolve_world([root, child], converter)
    endpoint = result.endpoints["event:root"]
    assert endpoint.authored.hard_end == 10
    assert endpoint.bounds().hard_end == 5
    assert endpoint.bounds().upper_inclusive
    assert root.attributes["_temporal_v2"]["expression"]["explicit_outer_end"] == 10


def test_joint_queries_do_not_combine_incompatible_marginals():
    root, converter = uncertain("root")
    child = followed("child", "root", offset=3)
    result = resolve_world([root, child], converter)
    query = (
        Constraint("event:root", ZERO, Fraction(-5)),
        Constraint(ZERO, "event:child", Fraction(6)),
    )
    assert result.possible((query[0],)) is True
    assert result.possible((query[1],)) is True
    assert result.possible(query) is False


def test_self_reference_cannot_impersonate_duration():
    event = manual("root", 3)
    definition = EventTimingDefinition(
        EndpointDefinition(instant=3),
        "independent",
        EndpointDefinition("event", anchor_id="event:root"),
    )
    event.attributes = definition.apply({})
    assert any(
        issue.code == "self_reference" for issue in resolve_world([event]).issues
    )


def test_mutual_event_references_can_be_endpoint_acyclic():
    a = followed("a", "b", end=EndpointDefinition(instant=10))
    b = manual("b", 1)
    b.attributes = EventTimingDefinition(
        EndpointDefinition(instant=1),
        "independent",
        EndpointDefinition("event", anchor_id="event:a", endpoint="end"),
    ).apply({})
    assert not resolve_world([a, b]).issues


def test_cycles_missing_end_and_cancellation_are_explicit():
    result = resolve_world([followed("a", "b"), followed("b", "a")])
    assert any(issue.code == "dependency_cycle" for issue in result.issues)
    result = resolve_world([manual("root", 2), followed("child", "root", "end")])
    assert any(issue.code == "missing_endpoint" for issue in result.issues)
    assert result.endpoints["event:child"].coordinate is None
    with pytest.raises(TimingCancelled):
        resolve_world([manual("root", 2)], cancel=lambda: True)


def test_unsupported_metadata_never_uses_cached_numeric_date():
    event = manual("root", 123)
    event.attributes = {"_temporal_v2": {"schema": 99, "future": "preserve"}}
    result = resolve_world([event])
    assert result.endpoints["event:root"].coordinate is None
    assert event.attributes["_temporal_v2"]["future"] == "preserve"


def test_difference_solver_matches_small_exhaustive_integer_oracle():
    from itertools import product

    nodes = ("x", "y", "z")
    bounds = [
        edge
        for node in nodes
        for edge in (
            Constraint(ZERO, node, Fraction(2)),
            Constraint(node, ZERO, Fraction(0)),
        )
    ]
    for limits in product((-1, 0, 1), repeat=3):
        edges = [
            Constraint(source, target, Fraction(limit))
            for (source, target), limit in zip(
                (("x", "y"), ("y", "z"), ("z", "x")), limits, strict=True
            )
        ]
        expected = any(
            all(
                values[nodes.index(edge.target)] - values[nodes.index(edge.source)]
                <= edge.limit
                for edge in edges
            )
            for values in product(range(3), repeat=3)
        )
        assert ConstraintBranch(nodes, (*bounds, *edges)).feasible == expected


def test_large_affine_chain_uses_exact_aliases():
    events = [manual("root", 10)]
    source = "root"
    for index in range(1000):
        name = f"e{index:04d}"
        events.append(followed(name, source, offset=1))
        source = name
    result = resolve_world(events)
    assert not result.issues
    assert result.endpoints[f"event:{source}"].coordinate == 1010
    assert len(next(iter(result.branches.values()))[0]._nodes) == 1


def test_calendar_offset_rejects_only_otherwise_possible_invalid_dates():
    from src.core.calendar import CalendarConfig, CalendarConverter, CalendarDate
    from src.core.temporal_expression import TemporalExpression

    config = CalendarConfig.create_default()
    converter = CalendarConverter(config)
    lower = converter.to_float(CalendarDate(1, 1, 27))
    upper = converter.to_float(CalendarDate(1, 1, 31))
    expression = TemporalExpression(
        config.id, 1, 1, 27, explicit_outer_start=lower, explicit_outer_end=upper
    )
    root = manual("root", lower)
    root.attributes = EventTimingDefinition(
        EndpointDefinition(expression=expression.to_dict())
    ).apply({})
    offset = EndpointDefinition(
        "event",
        anchor_id="event:root",
        offset={"unit": "months", "value": 1, "calendar_id": config.id},
    )
    child = manual("child", lower)
    child.attributes = EventTimingDefinition(offset).apply({})
    assert any(
        issue.code == "calendar_offset"
        for issue in resolve_world([root, child], converter).issues
    )
    cutoff = converter.to_float(CalendarDate(1, 1, 28))
    narrowing = followed("narrowing", "root", end=EndpointDefinition(instant=cutoff))
    result = resolve_world([root, child, narrowing], converter)
    assert not result.issues
    assert result.endpoints["event:root"].bounds().hard_end == cutoff
    assert result.endpoints["event:child"].bounds().error is None


def test_calendar_expansion_cooperatively_cancels():
    from src.core.calendar import CalendarConfig, CalendarConverter
    from src.core.event_timing.calendar_domains import calendar_pieces
    from src.core.event_timing.constraints import Interval

    config = CalendarConfig.create_default()
    converter = CalendarConverter(config)
    endpoint = EndpointDefinition(
        "event",
        anchor_id="event:root",
        offset={"unit": "years", "value": 1, "calendar_id": config.id},
    )
    checks = 0

    def cancelled():
        nonlocal checks
        checks += 1
        return checks >= 8

    with pytest.raises(TimingCancelled):
        list(
            calendar_pieces(
                "event:child",
                endpoint,
                (Interval(Fraction(0), Fraction(10**10)),),
                converter,
                cancelled,
            )
        )
    assert checks == 8


def test_sparse_variants_use_periodic_calendar_regions():
    import copy

    from src.core.calendar import CalendarConfig, CalendarConverter, YearVariant
    from src.core.event_timing.calendar_domains import calendar_pieces
    from src.core.event_timing.constraints import Interval

    config = CalendarConfig.create_default()
    config.year_variants.append(
        YearVariant(year=20, months=copy.deepcopy(config.months))
    )
    converter = CalendarConverter(config)
    endpoint = EndpointDefinition(
        "event",
        anchor_id="event:root",
        offset={"unit": "years", "value": 400, "calendar_id": config.id},
    )
    pieces = list(
        calendar_pieces(
            "event:child",
            endpoint,
            (Interval(Fraction(0), Fraction(10**10)),),
            converter,
            None,
        )
    )
    assert len(pieces) < 40
    assert not any(piece.invalid for piece in pieces)


def test_unbounded_approximation_keeps_its_nominal_layout_preference():
    from src.core.calendar import CalendarConfig, CalendarConverter
    from src.core.date_parser import DateParser

    config = CalendarConfig.create_default()
    converter = CalendarConverter(config)
    expression = DateParser(config).parse_expression("c. 961")
    event = Event(
        "Approximate",
        expression.representative_time(converter),
        id="approximate",
        attributes=EventTimingDefinition(
            EndpointDefinition(expression=expression.to_dict())
        ).apply({}),
    )
    result = resolve_world([event], converter)
    endpoint = result.endpoints["event:approximate"]
    assert endpoint.coordinate == expression.representative_time(converter)
    assert endpoint.ranges[0].lower is None
    assert endpoint.ranges[0].upper is None


def test_large_invalid_calendar_domain_stops_after_a_proven_counterexample(monkeypatch):
    from src.core.calendar import CalendarConfig, CalendarConverter
    from src.core.temporal_expression import TemporalExpression

    config = CalendarConfig.create_default()
    converter = CalendarConverter(config)
    root = Event(
        "Root",
        0,
        id="root",
        attributes=EventTimingDefinition(
            EndpointDefinition(
                expression=TemporalExpression(
                    config.id,
                    1,
                    1,
                    1,
                    explicit_outer_start=0,
                    explicit_outer_end=10**10,
                ).to_dict()
            )
        ).apply({}),
    )
    child = Event(
        "Child",
        0,
        id="child",
        attributes=EventTimingDefinition(
            EndpointDefinition(
                "event",
                anchor_id="event:root",
                offset={"unit": "months", "value": 1, "calendar_id": config.id},
            )
        ).apply({}),
    )
    original = converter.from_float
    visits = 0

    def counted(value):
        nonlocal visits
        visits += 1
        assert visits < 1000, "Calendar validation eagerly enumerated the whole domain"
        return original(value)

    monkeypatch.setattr(converter, "from_float", counted)
    result = resolve_world([root, child], converter)
    assert any(issue.code == "calendar_offset" for issue in result.issues)
    assert result.endpoints["event:root"].verified


def test_calendar_chains_and_observers_preserve_excluded_gaps():
    from src.core.calendar import CalendarConfig, CalendarConverter, CalendarDate
    from src.core.temporal_expression import TemporalExpression
    from src.core.temporal_window import resolve_temporal_window

    config = CalendarConfig.create_default()
    converter = CalendarConverter(config)
    lower = converter.to_float(CalendarDate(1, 2, 1))
    upper = converter.to_float(CalendarDate(1, 3, 31))
    root = Event(
        "Root",
        lower,
        id="root",
        attributes=EventTimingDefinition(
            EndpointDefinition(
                expression=TemporalExpression(
                    config.id,
                    1,
                    2,
                    1,
                    explicit_outer_start=lower,
                    explicit_outer_end=upper,
                ).to_dict()
            )
        ).apply({}),
    )
    offset = {"unit": "months", "value": 1, "calendar_id": config.id}
    middle = Event(
        "Middle",
        0,
        id="middle",
        attributes=EventTimingDefinition(
            EndpointDefinition("event", anchor_id="event:root", offset=offset)
        ).apply({}),
    )
    last = Event(
        "Last",
        0,
        id="last",
        attributes=EventTimingDefinition(
            EndpointDefinition("event", anchor_id="event:middle", offset=offset)
        ).apply({}),
    )
    result = resolve_world([root, middle, last], converter)
    assert not result.issues
    assert len(result.endpoints["event:middle"].ranges) == 2
    assert len(result.endpoints["event:last"].ranges) == 2
    window = resolve_temporal_window(
        {
            "temporal": {
                "schema": 2,
                "start": {"anchor": {"anchor_id": "event:middle", "offset": offset}},
                "end": {"status": "open"},
            }
        },
        converter=converter,
        anchors=result.anchors(),
    )
    assert window.is_valid, window.error


def test_fractional_reference_projections_never_become_evidence():
    root = manual("root", 0.1)
    child = followed("child", "root", offset=0.2, duration=0.1)
    result = resolve_world([root, child])
    assert not result.issues
    exact = Fraction(0.1) + Fraction(0.2)
    assert result.endpoints["event:child"].ranges[0].lower == exact
    assert result.endpoints["event:child"].coordinate == float(exact)
    assert result.exact_duration(child.id) == 0.1
