"""Component previews agree with full-world plans without per-target world work."""

import json
from dataclasses import replace

import pytest

from src.core.calendar import CalendarConfig, CalendarConverter, CalendarDate
from src.core.event_timing.definitions import EndpointDefinition, EventTimingDefinition
from src.core.event_timing.solver import resolve_world
from src.core.events import Event
from src.core.temporal_expression import TemporalExpression
from src.services.event_timing.planning import TimingChangeRequest, prepare_change
from src.services.event_timing.preview import MovementPreviewSession, component_events

pytestmark = pytest.mark.ci_fast


def followed(identity, source, offset=None, end=None):
    return Event(
        identity,
        0,
        id=identity,
        attributes=EventTimingDefinition(
            EndpointDefinition(
                "event",
                anchor_id=f"event:{source}",
                offset=offset or {"unit": "days", "value": 5},
            ),
            "independent" if end else "none",
            end=end,
        ).apply({}),
    )


def inputs(events, identity="child", converter=None):
    generation = resolve_world(events, converter).fingerprint
    snapshot = {
        "world_id": "probe",
        "events": [event.to_dict() for event in events],
        "calendar": converter._config.to_json() if converter else None,
        "consumers": [],
    }
    payload = {
        "session": 1,
        "generation": generation,
        "world_id": "probe",
        "event_id": identity,
        "events_json": json.dumps(snapshot["events"]),
        "calendar": snapshot["calendar"],
    }
    return snapshot, payload


@pytest.mark.parametrize("mode", ["offset", "chain"])
@pytest.mark.parametrize("kind", ["days", "months", "years", "uncertain", "end"])
def test_preview_matches_full_plan(mode, kind):
    config = CalendarConfig.create_default()
    converter = CalendarConverter(config)
    root = Event("root", converter.to_float(CalendarDate(2024, 1, 1, 0.125)), id="root")
    if kind == "uncertain":
        expression = TemporalExpression(
            config.id, 2024, 1, 1, explicit_outer_start=10, explicit_outer_end=20
        )
        root = replace(
            root,
            attributes=EventTimingDefinition(
                EndpointDefinition(expression=expression.to_dict())
            ).apply({}),
        )
    offset = (
        {"unit": kind, "value": 1, "calendar_id": config.id}
        if kind in {"months", "years"}
        else None
    )
    end = EndpointDefinition(instant=root.lore_date + 100) if kind == "end" else None
    child = followed("child", "root", offset, end)
    events = [
        root,
        child,
        followed("grandchild", "child"),
        Event("Unrelated", 100, id="other"),
    ]
    snapshot, payload = inputs(events, converter=converter)
    session = MovementPreviewSession(payload)
    baseline = resolve_world(events, converter).endpoints["event:child"].coordinate
    request = {**payload, "sequence": 1, "mode": mode, "target": baseline + 40}
    result = session.calculate(request)
    plan = prepare_change(
        snapshot,
        TimingChangeRequest(
            movement={
                key: request[key]
                for key in ("event_id", "generation", "mode", "target")
            }
        ),
    )
    assert not plan.errors
    assert result["component_size"] == 3
    for identity, delta in result["updated"].items():
        expected = plan.updated[identity]
        assert delta["lore_date"] == expected["lore_date"]
        assert delta["lore_duration"] == expected["lore_duration"]
        # Projections have different component fingerprints; authored definitions agree.
        assert delta["temporal"].get("timing") == expected["attributes"][
            "_temporal_v2"
        ].get("timing")
        projection = delta["temporal"].get("projection")
        if projection:
            for side in ("start", "end"):
                actual = projection.get(side)
                wanted = expected["attributes"]["_temporal_v2"]["projection"].get(side)
                if actual is not None and wanted is not None:
                    assert "root" not in actual and "network" not in actual
                    for key in ("ranges", "coordinate", "verified", "error"):
                        assert actual[key] == wanted[key]
    assert "other" not in result["updated"]


def test_component_includes_chronology_endpoints_and_third_party_rule_owner():
    root = Event("root", 10, id="root")
    child = followed("child", "root")
    boundary = Event("boundary", 30, id="boundary")
    owner = Event(
        "owner",
        100,
        id="owner",
        attributes={
            "_temporal_v2": {
                "schema": 1,
                "constraints": [
                    {
                        "id": "rule",
                        "anchor_a": "event:child",
                        "anchor_b": "event:boundary",
                        "relation": "before",
                        "min_offset_days": 0,
                    }
                ],
            }
        },
    )
    events = [root, child, boundary, owner]
    assert {event.id for event in component_events(events, "child")} == {
        event.id for event in events
    }
    _, payload = inputs(events)
    session = MovementPreviewSession(payload)
    with pytest.raises(ValueError):
        session.calculate({**payload, "mode": "offset", "target": 40, "sequence": 1})


def test_unrelated_event_count_does_not_increase_per_target_solver_scope(monkeypatch):
    import src.services.event_timing.preview as module

    events = [Event("root", 10, id="root"), followed("child", "root")]
    events += [Event(str(i), i, id=str(i)) for i in range(2000)]
    _, payload = inputs(events)
    calls = []
    solve = module.resolve_world

    def measured(rows, converter, cancel=None):
        calls.append(len(rows))
        return solve(rows, converter, cancel)

    monkeypatch.setattr(module, "resolve_world", measured)
    session = MovementPreviewSession(payload)
    index = session.index
    for sequence in range(1, 4):
        result = session.calculate(
            {**payload, "mode": "offset", "target": 20 + sequence, "sequence": sequence}
        )
        assert result["component_size"] == 2
        assert session.index is index
    assert calls == [2]  # Exact affine trees reuse the solved baseline itself.


def test_cancelled_or_stale_session_cannot_produce_preview():
    from src.core.event_timing.constraints import TimingCancelled

    events = [Event("root", 10, id="root"), followed("child", "root")]
    _, payload = inputs(events)
    session = MovementPreviewSession(payload)
    request = {**payload, "mode": "offset", "target": 20, "sequence": 1}
    with pytest.raises(ValueError, match="Obsolete"):
        session.calculate({**request, "session": 2})
    with pytest.raises(TimingCancelled):
        session.calculate(request, lambda: True)


@pytest.mark.parametrize("mode", ["offset", "chain"])
@pytest.mark.parametrize("root_date", [0.1, -5.125, 1e8 + 0.1])
def test_certified_tree_retains_exact_fractional_ranges_and_duration(mode, root_date):
    root = Event("root", root_date, id="root", lore_duration=2.375)
    events = [root]
    for i in range(12):
        parent = "root" if i < 3 else f"n{i - 3}"
        event = followed(f"n{i}", parent, {"unit": "days", "value": 0.1 * (i - 4)})
        timing = EventTimingDefinition.from_event(event)
        event.attributes = replace(
            timing, end_mode="duration", duration_days=0.125
        ).apply(event.attributes)
        events.append(event)
    snapshot, payload = inputs(events, identity="n2")
    session = MovementPreviewSession(payload)
    assert session.affine
    request = {
        **payload,
        "sequence": 1,
        "mode": mode,
        "target": session.before.endpoints["event:n2"].coordinate + 0.125,
    }
    result = session.calculate(request)
    plan = prepare_change(snapshot, TimingChangeRequest(movement=request))
    assert not plan.errors
    for identity, delta in result["updated"].items():
        expected = plan.updated[identity]
        assert delta["lore_date"] == expected["lore_date"]
        assert delta["lore_duration"] == expected["lore_duration"]
        projection = (delta["temporal"] or {}).get("projection")
        if projection:
            for side in ("start", "end"):
                assert (
                    projection[side]["ranges"]
                    == expected["attributes"]["_temporal_v2"]["projection"][side][
                        "ranges"
                    ]
                )


def test_certified_legacy_duration_cannot_cross_supported_date_limit():
    root = Event("root", 10, id="root", lore_duration=5)
    _, payload = inputs([root], identity="root")
    session = MovementPreviewSession(payload)
    with pytest.raises(ValueError, match="range"):
        session.calculate(
            {**payload, "sequence": 1, "mode": "chain", "target": 1e12 - 1}
        )
