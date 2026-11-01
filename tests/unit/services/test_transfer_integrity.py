"""Regression evidence for KRT-121's reproduced import/export defects."""

import copy
import json
import uuid

import pytest

from src.commands.transfer_commands import ApplyTransferCommand
from src.core.calendar import CalendarConfig
from src.core.events import Event
from src.services.repositories.transfer_repository import snapshot
from src.services.transfer_exchange import csv_text, load_sources, parse_json
from src.services.transfer_import import prepare_import
from src.services.transfer_selection import select_lore

pytestmark = pytest.mark.ci_fast


def uid():
    return str(uuid.uuid4())


def batch(**rows):
    return {"entities": [], "events": [], "relations": [], **rows}


def active_calendar(db):
    config = CalendarConfig.create_default()
    config.is_active = True
    db.insert_calendar_config(config)
    return config


def apply_and_undo(db, data, options=None):
    before = snapshot(db.get_connection())
    original = copy.deepcopy(data)
    preview = prepare_import(db, data, options or {"mode": "skip"})
    assert not preview["errors"], preview
    assert data == original
    assert snapshot(db.get_connection()) == before
    command = ApplyTransferCommand(preview)
    assert command.execute(db).success
    after = snapshot(db.get_connection())
    restored = ApplyTransferCommand.from_dict(command.to_dict())
    assert restored.undo(db).success
    assert snapshot(db.get_connection()) == before
    assert restored.execute(db).success
    assert snapshot(db.get_connection()) == after
    return preview


@pytest.mark.parametrize("mode", ["update", "overwrite", "skip"])
def test_selected_event_match_wins_over_other_name(db_service, mode):
    a, b, incoming = uid(), uid(), uid()
    db_service.insert_event(Event(id=a, name="Alpha", lore_date=1))
    db_service.insert_event(Event(id=b, name="Beta", lore_date=2))
    apply_and_undo(
        db_service,
        batch(events=[{"id": incoming, "name": "Beta", "lore_date": 8}]),
        {"mode": mode, "matches": {"events:0": a}},
    )
    assert db_service.get_event(b).lore_date == 2
    assert db_service.get_event(a).lore_date == (1 if mode == "skip" else 8)


def test_same_uuid_rename_and_conflicting_uuid_requires_review(db_service):
    identity = uid()
    db_service.insert_event(Event(id=identity, name="Old", lore_date=1))
    apply_and_undo(
        db_service,
        batch(events=[{"id": identity, "name": "Renamed", "lore_date": 2}]),
        {"mode": "overwrite"},
    )
    preview = prepare_import(
        db_service,
        batch(events=[{"id": uid(), "name": "Renamed", "lore_date": 3}]),
        {"mode": "update"},
    )
    assert preview["errors"]
    assert db_service.get_event(identity).lore_date == 2


@pytest.mark.parametrize("mode", ["skip", "update", "overwrite"])
def test_distinct_temporal_relations_survive_and_repeat(db_service, mode):
    a, b, r1, r2 = uid(), uid(), uid(), uid()
    data = batch(
        entities=[{"id": a, "name": "A"}, {"id": b, "name": "B"}],
        relations=[
            {
                "id": identity,
                "source_id": a,
                "target_id": b,
                "rel_type": "allied",
                "attributes": {"valid_from": start, "valid_to": start + 2},
            }
            for identity, start in ((r1, 1), (r2, 7))
        ],
    )
    apply_and_undo(db_service, data, {"mode": mode})
    assert {row["id"] for row in db_service.get_all_relations()} == {r1, r2}
    again = prepare_import(db_service, data, {"mode": "skip"})
    assert not again["errors"]
    assert not again["delta"]


@pytest.mark.parametrize("attributes", [[], None, "wrong"])
def test_outer_attributes_are_diagnostics_not_crashes(db_service, attributes):
    preview = prepare_import(
        db_service,
        batch(events=[{"name": "Malformed", "lore_date": 2, "attributes": attributes}]),
        {},
    )
    assert "Attributes must be a JSON object" in " ".join(preview["errors"])
    assert not preview["delta"]


@pytest.mark.parametrize("duration", [-3, float("inf"), float("nan"), True])
def test_invalid_duration_is_not_hidden_by_projection(db_service, duration):
    preview = prepare_import(
        db_service,
        batch(events=[{"name": "Invalid", "lore_date": 1, "lore_duration": duration}]),
        {},
    )
    assert preview["errors"]


def test_private_state_payload_is_rejected(db_service):
    preview = prepare_import(
        db_service,
        batch(
            relations=[
                {
                    "id": uid(),
                    "source_id": uid(),
                    "target_id": uid(),
                    "rel_type": "changes_state",
                    "attributes": {"payload": {"attributes": {"_private": "no"}}},
                }
            ]
        ),
        {},
    )
    assert "internal" in " ".join(preview["errors"])


@pytest.mark.parametrize(
    "text,precision",
    [
        ("1214", "year"),
        ("AUG 1214", "month"),
        ("23 AUG 1214", "day"),
        ("circa 1214", "year"),
        ("1214?", "year"),
        ("estimated 1214", "year"),
        ("between 1214 and 1216", "year"),
    ],
)
def test_text_dates_retain_authored_precision(db_service, text, precision):
    active_calendar(db_service)
    identity = uid()
    apply_and_undo(
        db_service, batch(events=[{"id": identity, "name": text, "lore_date": text}])
    )
    stored = db_service.get_event(identity)
    expression = stored.attributes["_temporal_v2"]["expression"]
    assert expression["precision"] == precision
    assert expression["original_text"] == text
    assert stored.lore_date != 1214.0


def test_v1_v2_and_relation_only_json():
    for version in (1, 2):
        assert (
            parse_json(json.dumps({"exchange_version": version, "relations": []}))[
                "relations"
            ]
            == []
        )
    with pytest.raises(ValueError):
        parse_json('{"exchange_version":99,"entities":[]}')


def test_selection_one_hop_is_order_independent_and_closes_timing():
    data = batch(
        entities=[{"id": key} for key in ("a", "b", "c")],
        relations=[
            {"id": "ab", "source_id": "a", "target_id": "b"},
            {"id": "bc", "source_id": "b", "target_id": "c"},
        ],
    )
    one, _, _ = select_lore(data, {"a"}, True)
    data["relations"].reverse()
    two, _, _ = select_lore(data, {"a"}, True)
    assert one == two
    assert {row["id"] for row in one["entities"]} == {"a", "b"}
    data["events"] = [
        {
            "id": "child",
            "attributes": {
                "_temporal_v2": {
                    "schema": 2,
                    "timing": {"start": {"anchor_id": "event:root:end"}},
                }
            },
        },
        {
            "id": "root",
            "attributes": {
                "_temporal_v2": {
                    "schema": 2,
                    "timing": {"start": {"anchor_id": "event:child"}},
                }
            },
        },
    ]
    selected, warnings, added = select_lore(data, {"child"}, False)
    assert not warnings
    assert {row["id"] for row in selected["events"]} == {"child", "root"}
    assert added == ["root"]


def test_typed_csv_scalars_and_yaml_sensitive_values(db_service, tmp_path):
    active_calendar(db_service)
    rows = [
        {"id": uid(), "name": "Year", "lore_date": "1214"},
        {"id": uid(), "name": "Coordinate", "lore_date": 1214.0},
    ]
    path = tmp_path / "events.csv"
    path.write_text(csv_text("events", rows), encoding="utf-8")
    data = load_sources([{"path": str(path), "kind": "events"}])
    assert isinstance(data["events"][0]["lore_date"], str)
    assert isinstance(data["events"][1]["lore_date"], float)
    apply_and_undo(db_service, data)
    assert db_service.get_event(rows[0]["id"]).attributes["_temporal_v2"]
    assert db_service.get_event(rows[1]["id"]).lore_date == 1214.0


def test_create_separate_record_does_not_update_supplied_existing_uuid(db_service):
    identity = uid()
    db_service.insert_event(Event(id=identity, name="Same", lore_date=1))
    preview = apply_and_undo(
        db_service,
        batch(events=[{"id": identity, "name": "Same", "lore_date": 2}]),
        {"actions": {"events:0": "create"}},
    )
    assert db_service.get_event(identity).lore_date == 1
    assert len(db_service.get_all_events()) == 2
    assert preview["actions"][0]["id"] != identity


def test_source_cannot_supply_review_control_fields(db_service):
    identity = uid()
    db_service.insert_event(Event(id=identity, name="Target", lore_date=1))
    review = prepare_import(
        db_service,
        batch(
            events=[
                {
                    "name": "Other",
                    "lore_date": 2,
                    "_transfer_match": identity,
                    "_transfer_original_id": identity,
                }
            ]
        ),
        {"mode": "overwrite"},
    )
    assert not review["errors"]
    assert ApplyTransferCommand(review).execute(db_service).success
    assert db_service.get_event(identity).lore_date == 1


@pytest.mark.parametrize("shape", [None, {}, [None], ["bad"]])
def test_malformed_collections_have_friendly_errors(db_service, shape):
    review = prepare_import(db_service, {"events": shape}, {})
    assert review["errors"]
    assert not review["delta"]


def test_missing_anchor_requires_explicit_unresolved_acceptance(db_service):
    from src.core.event_timing.definitions import (
        EndpointDefinition,
        EventTimingDefinition,
    )

    identity, absent = uid(), uid()
    data = batch(
        events=[
            {
                "id": identity,
                "name": "Dependent",
                "lore_date": None,
                "attributes": EventTimingDefinition(
                    EndpointDefinition(kind="event", anchor_id=f"event:{absent}")
                ).apply({}),
            }
        ]
    )
    blocked = prepare_import(db_service, data, {})
    assert blocked["errors"]
    assert blocked["dependency_decisions"][0]["source_id"] == absent
    accepted = prepare_import(db_service, data, {"unresolved_events": [absent]})
    assert not accepted["errors"]
    assert accepted["warnings"]
    from src.cli.import_review import reviewed_command
    from src.commands.event_timing_intents import request_for_command
    from src.services.event_timing.planning import prepare_change
    from src.services.event_timing.store import capture

    command = ApplyTransferCommand(accepted)
    state = capture(db_service)
    plan = prepare_change(state, request_for_command(command, state))
    assert reviewed_command(db_service, accepted, plan).execute(db_service).success
    assert db_service.get_event(identity).lore_date is None


def test_new_timing_cycle_is_structurally_blocked(db_service):
    from src.core.event_timing.definitions import (
        EndpointDefinition,
        EventTimingDefinition,
    )

    a, b = uid(), uid()
    data = batch(
        events=[
            {
                "id": identity,
                "name": identity,
                "lore_date": None,
                "attributes": EventTimingDefinition(
                    EndpointDefinition(kind="event", anchor_id=f"event:{target}")
                ).apply({}),
            }
            for identity, target in ((a, b), (b, a))
        ]
    )
    preview = prepare_import(db_service, data, {})
    assert any("cycle" in error for error in preview["errors"])
    assert not db_service.get_all_events()


def test_opaque_future_event_metadata_is_preserved_with_warning(db_service):
    identity = uid()
    attributes = {"_temporal_v2": {"schema": 99, "future": {"value": "unchanged"}}}
    preview = apply_and_undo(
        db_service,
        batch(
            events=[
                {
                    "id": identity,
                    "name": "Future",
                    "lore_date": None,
                    "attributes": attributes,
                }
            ]
        ),
    )
    assert preview["warnings"]
    assert (
        db_service.get_event(identity).attributes["_temporal_v2"]
        == attributes["_temporal_v2"]
    )


def test_idless_relation_fallback_never_merges_different_payloads(db_service):
    a, b = uid(), uid()
    apply_and_undo(
        db_service,
        batch(
            entities=[{"id": a, "name": "A"}, {"id": b, "name": "B"}],
            relations=[
                {
                    "source_id": a,
                    "target_id": b,
                    "rel_type": "allied",
                    "attributes": {"valid_from": 1, "valid_to": 3},
                }
            ],
        ),
    )
    data = batch(
        relations=[
            {
                "source_id": a,
                "target_id": b,
                "rel_type": "allied",
                "attributes": {"valid_from": 1, "valid_to": 3},
            }
        ]
    )
    assert not prepare_import(db_service, data, {"mode": "skip"})["delta"]
    data["relations"][0]["attributes"]["valid_to"] = 5
    assert prepare_import(db_service, data, {"mode": "update"})["errors"]
    assert db_service.get_all_relations()[0]["attributes"]["valid_to"] == 3


def test_explicit_match_remaps_endpoints_and_chronology(db_service):
    from src.cli.import_review import reviewed_command
    from src.commands.event_timing_intents import request_for_command
    from src.core.event_timing.definitions import (
        EndpointDefinition,
        EventTimingDefinition,
    )
    from src.services.event_timing.planning import prepare_change
    from src.services.event_timing.store import capture

    source, target, child = uid(), uid(), uid()
    db_service.insert_event(
        Event(id=target, name="Existing root", lore_date=8, lore_duration=2)
    )
    attributes = EventTimingDefinition(
        EndpointDefinition(kind="event", anchor_id=f"event:{source}", endpoint="end")
    ).apply(
        {
            "_temporal_v2": {
                "constraints": [
                    {
                        "anchor_a": f"event:{source}:end",
                        "relation": "same_as",
                        "anchor_b": f"event:{child}",
                    }
                ]
            }
        }
    )
    data = batch(
        events=[
            {"id": source, "name": "Renamed root", "lore_date": 10, "lore_duration": 2},
            {"id": child, "name": "Child", "lore_date": None, "attributes": attributes},
        ]
    )
    preview = prepare_import(
        db_service, data, {"mode": "update", "matches": {"events:0": target}}
    )
    assert not preview["errors"]
    state = capture(db_service)
    plan = prepare_change(
        state, request_for_command(ApplyTransferCommand(preview), state)
    )
    assert reviewed_command(db_service, preview, plan).execute(db_service).success
    stored = db_service.get_event(child)
    assert stored.lore_date == 12
    native = stored.attributes["_temporal_v2"]
    assert native["timing"]["start"]["anchor_id"] == f"event:{target}"
    assert native["constraints"][0]["anchor_a"] == f"event:{target}:end"
    assert db_service.get_event(source) is None
