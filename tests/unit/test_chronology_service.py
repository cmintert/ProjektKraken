"""Worker-side chronology editing, projection, and date-save guards."""

import pytest

from src.commands.chronology_commands import ApplyChronologyCommand
from src.commands.event_commands import UpdateEventCommand
from src.core.calendar import CalendarConfig
from src.core.date_parser import DateParser
from src.core.events import Event
from src.services.chronology_service import collect_chronology, direct_chronology

pytestmark = pytest.mark.ci_fast


def before(a: Event, b: Event) -> dict:
    return {
        "anchor_a": f"event:{a.id}",
        "relation": "before",
        "anchor_b": f"event:{b.id}",
        "min_offset_days": 0,
    }


def test_incoming_rule_can_be_removed_and_undone(db_service) -> None:
    a = Event(name="Discovery", lore_date=1)
    b = Event(name="Execution", lore_date=2)
    for event in (a, b):
        db_service.insert_event(event)
    create = ApplyChronologyCommand([{"kind": "create", "data": before(a, b)}])
    assert create.execute(db_service).success
    events = db_service.get_all_events()
    rows = direct_chronology(b.id, collect_chronology(events))
    assert len(rows) == 1
    record, other, relation = rows[0]
    assert other == f"event:{a.id}"
    assert relation.value == "after"
    assert record.constraint.id
    delete = ApplyChronologyCommand(
        [{"kind": "delete", "reference": record.reference, "old_data": record.data}]
    )
    assert delete.execute(db_service).success
    assert not collect_chronology(db_service.get_all_events())
    delete.undo(db_service)
    assert (
        collect_chronology(db_service.get_all_events())[0].reference == record.reference
    )


def test_date_move_rejects_new_chronology_conflict(db_service) -> None:
    a = Event(name="A", lore_date=1)
    b = Event(name="B", lore_date=2)
    db_service.insert_event(a)
    db_service.insert_event(b)
    assert (
        ApplyChronologyCommand([{"kind": "create", "data": before(a, b)}])
        .execute(db_service)
        .success
    )
    result = UpdateEventCommand(a.id, {"lore_date": 3}).execute(db_service)
    assert not result.success
    assert db_service.get_event(a.id).lore_date == 1


def test_legacy_rule_moves_only_when_edited(db_service) -> None:
    a = Event(name="A", lore_date=1)
    b = Event(name="B", lore_date=2)
    c = Event(name="Legacy owner", lore_date=0)
    old = before(a, b)
    c.attributes = {"_temporal_v2": {"schema": 1, "constraints": [old]}}
    for event in (a, b, c):
        db_service.insert_event(event)
    record = collect_chronology(db_service.get_all_events())[0]
    assert record.reference.startswith("legacy:")
    revised = {
        "anchor_a": f"event:{b.id}",
        "relation": "after",
        "anchor_b": f"event:{a.id}",
        "min_offset_days": 0,
    }
    result = ApplyChronologyCommand(
        [
            {
                "kind": "update",
                "reference": record.reference,
                "old_data": record.data,
                "data": revised,
            }
        ]
    ).execute(db_service)
    assert result.success
    rows = collect_chronology(db_service.get_all_events())
    assert len(rows) == 1
    assert rows[0].owner_id == b.id
    assert rows[0].constraint.id


def test_cycle_across_storage_owners_is_rejected(db_service) -> None:
    a = Event(name="A", lore_date=1)
    b = Event(name="B", lore_date=2)
    c = Event(name="C", lore_date=3)
    for event in (a, b, c):
        db_service.insert_event(event)
    assert (
        ApplyChronologyCommand([{"kind": "create", "data": before(a, b)}])
        .execute(db_service)
        .success
    )
    assert (
        ApplyChronologyCommand([{"kind": "create", "data": before(b, c)}])
        .execute(db_service)
        .success
    )
    rejected = ApplyChronologyCommand(
        [{"kind": "create", "data": before(c, a)}]
    ).execute(db_service)
    assert not rejected.success
    assert len(collect_chronology(db_service.get_all_events())) == 2


def test_unrelated_save_preserves_rule_and_existing_problem(db_service) -> None:
    a = Event(name="A", lore_date=1)
    b = Event(name="B", lore_date=2)
    rule = before(a, b)
    a.attributes = {"_temporal_v2": {"schema": 1, "constraints": [rule]}}
    b.attributes = {"_temporal_v2": {"schema": 1, "constraints": [before(b, a)]}}
    for event in (a, b):
        db_service.insert_event(event)
    # This stale editor snapshot omits the current chronology metadata.
    result = UpdateEventCommand(
        a.id, {"name": "Renamed", "attributes": {"custom": "value"}}
    ).execute(db_service)
    assert result.success
    assert rule in [
        record.data for record in collect_chronology(db_service.get_all_events())
    ]


def test_redo_keeps_rule_identity_and_stale_edit_is_rejected(db_service) -> None:
    a = Event(name="A", lore_date=1)
    b = Event(name="B", lore_date=2)
    db_service.insert_event(a)
    db_service.insert_event(b)
    create = ApplyChronologyCommand([{"kind": "create", "data": before(a, b)}])
    assert create.execute(db_service).success
    record = collect_chronology(db_service.get_all_events())[0]
    first_id = record.constraint.id
    create.undo(db_service)
    assert create.execute(db_service).success
    assert collect_chronology(db_service.get_all_events())[0].constraint.id == first_id
    delete = ApplyChronologyCommand(
        [{"kind": "delete", "reference": record.reference, "old_data": record.data}]
    )
    assert delete.execute(db_service).success
    stale = ApplyChronologyCommand(
        [
            {
                "kind": "update",
                "reference": record.reference,
                "old_data": record.data,
                "data": {
                    "anchor_a": f"event:{a.id}",
                    "relation": "after",
                    "anchor_b": f"event:{b.id}",
                },
            }
        ]
    )
    assert not stale.execute(db_service).success


def test_existing_conflict_does_not_block_unrelated_ordering(db_service) -> None:
    a = Event(name="A", lore_date=1)
    b = Event(name="B", lore_date=2)
    c = Event(name="C", lore_date=3)
    d = Event(name="D", lore_date=4)
    a.attributes = {"_temporal_v2": {"schema": 1, "constraints": [before(a, b)]}}
    b.attributes = {"_temporal_v2": {"schema": 1, "constraints": [before(b, a)]}}
    for event in (a, b, c, d):
        db_service.insert_event(event)
    result = ApplyChronologyCommand([{"kind": "create", "data": before(c, d)}]).execute(
        db_service
    )
    assert result.success


def test_preferred_source_and_timeline_move_revalidate_dates(db_service) -> None:
    config = CalendarConfig.create_default()
    config.is_active = True
    db_service.insert_calendar_config(config)
    parser = DateParser(config)
    first = parser.parse_expression("961")
    later = parser.parse_expression("963")
    a = Event(
        name="A",
        lore_date=first.representative_time(parser.converter),
        attributes={"_temporal_v2": {"schema": 1, "expression": first.to_dict()}},
    )
    b_date = parser.parse_expression("962")
    b = Event(
        name="B",
        lore_date=b_date.representative_time(parser.converter),
        attributes={"_temporal_v2": {"schema": 1, "expression": b_date.to_dict()}},
    )
    db_service.insert_event(a)
    db_service.insert_event(b)
    assert (
        ApplyChronologyCommand([{"kind": "create", "data": before(a, b)}])
        .execute(db_service)
        .success
    )
    preferred = {
        "schema": 1,
        "expression": later.to_dict(),
        "claims": [
            {"id": "source-1", "source": "Chronicle", "expression": later.to_dict()}
        ],
        "preferred_claim_id": "source-1",
    }
    result = UpdateEventCommand(
        a.id,
        {
            "lore_date": later.representative_time(parser.converter),
            "attributes": {"_temporal_v2": preferred},
        },
    ).execute(db_service)
    assert not result.success
    moved = UpdateEventCommand(
        a.id, {"lore_date": later.representative_time(parser.converter)}
    ).execute(db_service)
    assert not moved.success
    assert (
        db_service.get_event(a.id).attributes["_temporal_v2"]["expression"]
        == first.to_dict()
    )
