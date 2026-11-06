"""Richer MCP reads preserve facts, evidence, privacy and bounded continuation."""

import copy
import json

import pytest

from src.core.calendar import CalendarConfig
from src.core.entities import Entity
from src.core.event_timing.definitions import EndpointDefinition, EventTimingDefinition
from src.core.events import Event
from src.core.mcp_access import McpFailure
from src.core.temporal_expression import TemporalExpression, TemporalQualifier
from src.services.mcp_compact import compact_data
from src.services.mcp_read_service import McpReadService

pytestmark = pytest.mark.ci_fast


def call(db, tool, service=None, **arguments):
    return (service or McpReadService()).execute(
        db,
        {
            "tool": tool,
            "arguments": arguments,
            "world_id": "world-a",
            "world_name": "World A",
            "generation": "session-a",
        },
        lambda: False,
    )


def expand(value, references):
    """Client-side expansion keeps authored attribute dictionaries literal."""
    if isinstance(value, list):
        return [expand(item, references) for item in value]
    if not isinstance(value, dict):
        return value
    if set(value) == {"$ref"}:
        return copy.deepcopy(references[value["$ref"]])
    return {
        key: copy.deepcopy(item)
        if key in {"value", "attributes"}
        else expand(item, references)
        for key, item in value.items()
    }


@pytest.fixture
def calendar(db_service):
    config = CalendarConfig.create_default()
    config.name = "Test calendar"
    config.months[0].name = "Frostmoon"
    config.is_active = True
    db_service.insert_calendar_config(config)
    return config


def test_saved_fields_public_attributes_tags_and_provenance(db_service):
    entity = Entity(
        "Northwatch",
        "place",
        "Full prose " * 200,
        attributes={
            "population": 1200,
            "nested": {"safe": [None, 2], "password": "hidden"},
            "_private": "hidden",
            "api_key": "hidden",
            "image_path": "C:/hidden",
            "_tags": ["Old tag", "old TAG"],
        },
    )
    db_service.insert_entity(entity)
    db_service.assign_tag_to_entity(entity.id, "New tag")
    tag_id = db_service.get_tags_for_entity(entity.id)[0]["id"]
    data = call(db_service, "get_object", kind="entity", id=entity.id)["data"]
    assert data["description"] == entity.description
    assert data["attributes"] == {"population": 1200, "nested": {"safe": [None, 2]}}
    assert data["tags"] == [
        {"id": tag_id, "name": "New tag"},
        {"id": "", "name": "Old tag"},
    ]
    assert data["provenance"] == {
        "kind": "saved",
        "object_kind": "entity",
        "id": entity.id,
    }
    assert "hidden" not in json.dumps(data)


def test_batch_order_missing_duplicates_and_compact_round_trip(db_service):
    entity = Entity(
        "Northwatch",
        "place",
        "Long complete description " * 30,
        attributes={"literal": {"$ref": "r1"}},
    )
    event = Event("Siege", 42.5)
    db_service.insert_entity(entity)
    db_service.insert_event(event)
    objects = [
        {"kind": "entity", "id": entity.id},
        {"kind": "event", "id": event.id},
        {"kind": "entity", "id": "missing"},
        {"kind": "entity", "id": entity.id},
    ]
    full = call(db_service, "get_objects", objects=objects)
    compact = call(db_service, "get_objects", objects=objects, detail="compact")
    assert [row["id"] for row in full["data"]["results"]] == [
        row["id"] for row in objects
    ]
    assert full["data"]["results"][2]["status"] == "NOT_FOUND"
    assert full["data"]["results"][2]["data"] is None
    assert (
        expand(compact["data"]["content"], compact["data"]["references"])
        == full["data"]
    )
    assert len(json.dumps(compact["data"])) < len(json.dumps(full["data"]))
    assert full["data"]["results"][0]["data"]["attributes"]["literal"] == {"$ref": "r1"}


@pytest.mark.parametrize(
    "objects",
    [
        [],
        [{}],
        [{"kind": "map", "id": "x"}],
        [{"kind": [], "id": "x"}],
        [{"kind": "entity", "id": 1}],
        [None],
        [{"kind": "event", "id": "x"}] * 26,
    ],
)
def test_batch_validates_entire_request(db_service, objects):
    with pytest.raises(McpFailure, match="INVALID_INPUT"):
        call(db_service, "get_objects", objects=objects)


def test_whole_batch_size_failure_and_invalid_detail(db_service):
    entity = Entity("Big", "place", "x" * 66000)
    db_service.insert_entity(entity)
    with pytest.raises(McpFailure, match="RESULT_TOO_LARGE"):
        call(db_service, "get_objects", objects=[{"kind": "entity", "id": entity.id}])
    with pytest.raises(McpFailure, match="INVALID_INPUT"):
        call(db_service, "get_object", kind="entity", id=entity.id, detail="short")


def test_overview_counts_and_standard_calendar(db_service, calendar):
    db_service.insert_entity(Entity("City", "place"))
    db_service.insert_entity(Entity("Person", "person"))
    db_service.insert_event(Event("Siege", 3))
    data = call(db_service, "get_world_overview")["data"]
    assert data["counts"]["entity"] == {
        "total": 2,
        "by_type": [{"type": "person", "count": 1}, {"type": "place", "count": 1}],
    }
    assert data["counts"]["event"]["total"] == 1
    assert data["calendar"]["id"] == calendar.id
    assert data["calendar"]["months"][0]["name"] == "Frostmoon"
    assert data["calendar"]["week"] == calendar.week.to_dict()


def test_empty_overview_and_missing_calendar(db_service):
    data = call(db_service, "get_world_overview")["data"]
    assert data["counts"]["event"]["total"] == 0
    assert data["calendar"] is None
    event = Event("Noon", 0.5)
    db_service.insert_event(event)
    data = call(db_service, "get_object", kind="event", id=event.id)["data"]
    assert data["lore_date"] == 0.5
    assert not data["temporal"]["calendar_available"]
    assert data["temporal"]["start"]["possible_start"] == 0.5


def test_custom_calendar_independent_end_and_uncertainty(db_service, calendar):
    expression = TemporalExpression(
        calendar.id,
        1,
        1,
        2,
        qualifier=TemporalQualifier.UNCERTAIN,
        explicit_outer_start=1,
        explicit_outer_end=4,
    )
    end = TemporalExpression(calendar.id, 1, 1, 10)
    event = Event(
        "Siege",
        2.5,
        attributes={
            "_temporal_v2": {
                "schema": 1,
                "expression": expression.to_dict(),
                "end_expression": end.to_dict(),
            }
        },
    )
    db_service.insert_event(event)
    data = call(db_service, "get_object", kind="event", id=event.id)["data"]
    temporal = data["temporal"]
    assert "Frostmoon" in temporal["start"]["caption"]
    assert temporal["start"]["qualifier"] == "uncertain"
    assert temporal["start"]["possible_end"] == 4
    assert temporal["end"]["possible_start"] == 9
    assert temporal["authored_duration"] is None
    assert "anchor" not in temporal["start"]


def test_browse_possible_overlap_open_bounds_and_unresolved(db_service, calendar):
    expression = TemporalExpression(
        calendar.id,
        1,
        1,
        2,
        qualifier=TemporalQualifier.UNCERTAIN,
        explicit_outer_start=1,
        explicit_outer_end=20,
    )
    events = [
        Event(
            "Broad",
            2,
            attributes={
                "_temporal_v2": {"schema": 1, "expression": expression.to_dict()}
            },
        ),
        Event("Exact", 15.5),
        Event("Unresolved", None),
        Event("Outside", 40),
    ]
    for event in events:
        db_service.insert_event(event)
    data = call(db_service, "browse_world", kinds=["event"], date_from=15, date_to=16)[
        "data"
    ]
    matches = {row["name"]: row["date_match"] for row in data["rows"]}
    assert matches == {"Broad": "possible", "Exact": "definite"}
    assert data["omitted_counts"] == {"unresolved": 1, "excluded": 1}
    broad = events[0]
    broad.attributes["_temporal_v2"]["expression"]["explicit_outer_end"] = None
    db_service.insert_event(broad)
    data = call(db_service, "browse_world", kinds=["event"], date_from=100)["data"]
    assert [row["name"] for row in data["rows"]] == ["Broad"]


def test_browse_combines_types_and_all_tags(db_service):
    for name, kind, tags in [
        ("Match", "place", ["A", "B"]),
        ("One tag", "place", ["A"]),
        ("Other type", "person", ["A", "B"]),
    ]:
        db_service.insert_entity(Entity(name, kind, attributes={"_tags": tags}))
    data = call(
        db_service, "browse_world", kinds=["entity"], types=["place"], tags=["a", "B"]
    )["data"]
    assert [row["name"] for row in data["rows"]] == ["Match"]


def test_browse_empty_batch_continuation_and_cursor_bindings(db_service):
    for index in range(101):
        db_service.insert_entity(Entity("Candidate", "place", id=f"e{index:03}"))
    service = McpReadService()
    args = {"kinds": ["entity"], "tags": ["absent"]}
    first = call(db_service, "browse_world", service, **args)["data"]
    assert first["rows"] == [] and not first["done"]
    assert first["evaluated_count"] == 100
    cursor = first["next_cursor"]
    second = call(db_service, "browse_world", service, **args, cursor=cursor)["data"]
    assert second["done"] and second["evaluated_count"] == 1
    with pytest.raises(McpFailure, match="STALE_CURSOR"):
        call(db_service, "browse_world", service, kinds=["entity"], cursor=cursor)
    with pytest.raises(McpFailure, match="STALE_CURSOR"):
        call(db_service, "search_world", service, query="Candidate", cursor=cursor)
    db_service.insert_entity(Entity("New", "place"))
    with pytest.raises(McpFailure, match="STALE_CURSOR"):
        call(db_service, "browse_world", service, **args, cursor=cursor)


@pytest.mark.parametrize(
    "args",
    [
        {"date_from": 1},
        {"kinds": ["event"], "date_to": float("nan")},
        {"kinds": ["event"], "date_from": 2, "date_to": 1},
        {"limit": True},
        {"types": "place"},
    ],
)
def test_invalid_browse_filters(db_service, args):
    with pytest.raises(McpFailure, match="INVALID"):
        call(db_service, "browse_world", **args)


def test_compact_distinct_projections_and_literal_attribute_values():
    item = {"id": "same", "object_type": "entity", "name": "Long name " * 20}
    variant = {**item, "name": "Different projection"}
    data = {
        "participants": [item, item, variant],
        "attributes": {
            "literal": {"$ref": "r1"},
            "source": item,
            "target": item,
        },
    }
    before = copy.deepcopy(data)
    compact = compact_data(data)
    assert expand(compact["content"], compact["references"]) == data
    assert compact["content"]["attributes"] == data["attributes"]
    assert compact["content"]["participants"][2] == variant
    assert data == before


def test_context_connections_compact_parity_and_activity_ids(db_service):
    from src.app.coordinators.mcp_coordinator import McpCoordinator

    source = Entity("Northwatch " * 20, "place")
    db_service.insert_entity(source)
    for index in range(3):
        target = Entity(f"Target {index}", "person")
        db_service.insert_entity(target)
        db_service.insert_relation(source.id, target.id, "knows")
    for tool, args in [
        ("get_context", {"kind": "entity", "id": source.id}),
        ("list_connections", {"entity_id": source.id}),
    ]:
        full = call(db_service, tool, mode="all_history", **args)["data"]
        compact = call(db_service, tool, mode="all_history", detail="compact", **args)[
            "data"
        ]
        assert expand(compact["content"], compact["references"]) == full
        assert set(McpCoordinator._record_ids(full)) == set(
            McpCoordinator._record_ids(compact)
        )


def test_dependent_timing_uses_canonical_sources_not_saved_coordinate(db_service):
    source = Event("Source", 10)
    definition = EventTimingDefinition(
        EndpointDefinition(
            kind="event",
            anchor_id=f"event:{source.id}",
            offset={"unit": "days", "value": 5},
        )
    )
    child = Event("Child", 999, attributes=definition.apply({}))
    db_service.insert_event(source)
    db_service.insert_event(child)
    data = call(db_service, "get_object", kind="event", id=child.id)["data"]
    assert data["lore_date"] == 999
    assert data["temporal"]["start"]["possible_start"] == 15
    assert data["temporal"]["start"]["qualifier"] == "calculated"
    assert data["authored_timing"]["start"]["anchor_id"] == f"event:{source.id}"
    rows = call(db_service, "browse_world", kinds=["event"], date_from=15, date_to=15)[
        "data"
    ]["rows"]
    assert [row["id"] for row in rows] == [child.id]
    assert rows[0]["date_match"] == "definite"


def test_timing_limit_keeps_saved_fields_and_marks_unresolved(db_service, monkeypatch):
    from src.services import mcp_temporal

    monkeypatch.setattr(mcp_temporal, "MAX_TIMING_EVENTS", 1)
    source = Event("Source", 10)
    child = Event(
        "Child",
        15,
        attributes=EventTimingDefinition(
            EndpointDefinition(kind="event", anchor_id=f"event:{source.id}")
        ).apply({}),
    )
    db_service.insert_event(source)
    db_service.insert_event(child)
    data = call(db_service, "get_object", kind="event", id=child.id)["data"]
    assert data["name"] == "Child"
    assert data["temporal"]["start"]["unresolved"]
    assert data["temporal"]["start"]["caption"] == "TIMING_LIMIT"


def test_historical_attribute_sources_survive_full_and_compact(db_service):
    entity = Entity("Ilyra", "person", attributes={"rank": "citizen"})
    event = Event("Coronation", 120)
    db_service.insert_entity(entity)
    db_service.insert_event(event)
    relation = db_service.insert_relation(
        event.id,
        entity.id,
        "changes",
        {
            "valid_from": 120,
            "payload": {
                "description": "Crowned ruler",
                "attributes": {"rank": "queen"},
            },
        },
    )
    full = call(
        db_service,
        "get_context",
        kind="entity",
        id=entity.id,
        mode="at_playhead",
        lore_day=135,
    )["data"]
    rank = next(item for item in full["attributes"] if item["name"] == "rank")
    assert rank["value"] == "queen"
    assert rank["source"]["event_id"] == event.id
    assert rank["source"]["relation_id"] == relation
    assert full["effective_description"]["source"] == rank["source"]
    compact = call(
        db_service,
        "get_context",
        kind="entity",
        id=entity.id,
        mode="at_playhead",
        lore_day=135,
        detail="compact",
    )["data"]
    # This context is small enough that its source records need not be pooled.
    restored = expand(compact["content"], compact["references"])
    # Attribute values stay literal, but their typed source positions can be refs.
    for attribute in restored["attributes"]:
        if set(attribute.get("source", {})) == {"$ref"}:
            attribute["source"] = compact["references"][attribute["source"]["$ref"]]
    assert restored == full


def test_cursor_rejects_other_world_session_and_tool_even_with_same_args(db_service):
    for index in range(26):
        db_service.insert_entity(Entity("City", "place"))
    service = McpReadService()
    cursor = call(db_service, "browse_world", service)["data"]["next_cursor"]
    for changed in (
        {"world_id": "world-b"},
        {"generation": "session-b"},
        {"tool": "search_world"},
    ):
        request = {
            "tool": "browse_world",
            "world_id": "world-a",
            "generation": "session-a",
            **changed,
        }
        with pytest.raises(McpFailure, match="STALE_CURSOR"):
            service._continue({"cursor": cursor}, request, service.revision(db_service))


def test_date_range_keeps_strict_bounds_and_disjoint_alternatives():
    from src.core.temporal_display import TemporalDisplay
    from src.services.mcp_browse import overlap

    display = TemporalDisplay(1, 8, explicit_window=True)
    ranges = [
        {"from": 1, "until": 3, "from_inclusive": True, "until_inclusive": False},
        {"from": 5, "until": 8, "from_inclusive": False, "until_inclusive": True},
    ]
    assert overlap(display, 3, 5, ranges) == "excluded"
    assert overlap(display, 2, 2, ranges) == "possible"
    assert overlap(display, 8, 8, ranges) == "possible"
    assert overlap(TemporalDisplay(42.5, 42.5), 42.5, 42.5) == "definite"


def test_activity_records_only_factual_ids_not_authored_values_or_missing_ids(
    db_service,
):
    from src.services.mcp_compact import record_ids

    entity = Entity(
        "City",
        "place",
        attributes={"id": "authored prose", "source": {"id": "private prose"}},
    )
    db_service.insert_entity(entity)
    objects = [{"kind": "entity", "id": entity.id}] * 2 + [
        {"kind": "entity", "id": "missing"}
    ]
    for detail in ("full", "compact"):
        result = call(db_service, "get_objects", objects=objects, detail=detail)
        assert record_ids(result["data"]) == [entity.id]


@pytest.mark.parametrize("failure", ["WORLD_CHANGED", "TIMEOUT"])
def test_batch_never_publishes_results_after_revision_change_or_timeout(
    db_service, monkeypatch, failure
):
    entity = Entity("City", "place")
    db_service.insert_entity(entity)
    service = McpReadService()
    revisions = iter(["first", "changed" if failure == "WORLD_CHANGED" else "first"])
    monkeypatch.setattr(service, "revision", lambda db: next(revisions))
    expirations = iter([False, False, failure == "TIMEOUT"])
    with pytest.raises(McpFailure, match=failure):
        service.execute(
            db_service,
            {
                "tool": "get_objects",
                "world_id": "a",
                "world_name": "World",
                "generation": "session",
                "arguments": {
                    "objects": [{"kind": "entity", "id": entity.id}],
                    "detail": "compact",
                },
            },
            lambda: next(expirations),
        )
