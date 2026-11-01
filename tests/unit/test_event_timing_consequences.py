"""Review descriptions identify world effects without changing solver behavior."""

from copy import deepcopy

import pytest

from src.core.event_timing.definitions import EndpointDefinition, EventTimingDefinition
from src.core.events import Event
from src.services.event_timing.planning import TimingChangeRequest, prepare_change
from src.services.event_timing.store import relation_consumer
from src.services.event_timing.transfer import request_from_delta

pytestmark = pytest.mark.ci_fast


def snapshot(attributes, *, predicate="rules"):
    root = Event("Succession", 10, id="root", lore_duration=2)
    consumer = relation_consumer(
        {
            "id": "relation",
            "source_id": "root",
            "target_id": "realm",
            "rel_type": predicate,
            "attributes": attributes,
        }
    )
    return {
        "world_id": "review",
        "events": [root.to_dict()],
        "objects": {
            "root": {"name": root.name, "kind": "event"},
            "realm": {"name": "Ashford", "kind": "entity"},
        },
        "consumers": [consumer],
    }


def review(data):
    plan = prepare_change(
        data, TimingChangeRequest(updates={"root": {"lore_date": 20}})
    )
    assert not plan.errors
    return next(row["review"] for row in plan.consequences if row["kind"] != "event")


@pytest.mark.parametrize(
    "side, phrase",
    [("start", "Reign begins"), ("end", "Reign ends"), ("at", "Reign recorded")],
)
def test_named_boundary_and_source_endpoint(side, phrase):
    result = review(
        snapshot(
            {
                "temporal": {
                    "schema": 1,
                    side: {
                        "anchor": {"anchor_id": "event:root", "endpoint": "end"},
                    },
                }
            }
        )
    )
    assert result["heading"] == "Succession → Ashford — rules"
    assert phrase in result["explanation"]
    assert "end of “Succession”" in result["explanation"]
    assert result["before_text"] == "12 days"
    assert result["after_text"] == "22 days"


def test_strict_offset_boundaries_keep_multiple_meanings():
    result = review(
        snapshot(
            {
                "temporal": {
                    "schema": 2,
                    "start": {
                        "anchor": {
                            "anchor_id": "event:root",
                            "relation": "after",
                            "offset_days": 3,
                        }
                    },
                    "end": {
                        "anchor": {
                            "anchor_id": "event:root",
                            "endpoint": "end",
                            "relation": "before",
                        }
                    },
                }
            }
        )
    )
    assert "Reign begins: after 13 days" in result["before_text"]
    assert "Reign ends: before 12 days" in result["before_text"]
    assert "offset +3 days" in result["explanation"]
    assert result["boundaries"] == ["start", "end"]


def test_payload_summary_and_full_values_are_separate():
    description = "Long description " * 100
    value = "Long value " * 100
    result = review(
        snapshot(
            {
                "valid_from_event": True,
                "payload": {
                    "attributes": {"Ruler": "Ilyra", "Notes": value},
                    "unset_attributes": ["Old office"],
                    "description": description,
                },
            },
            predicate="changes_state",
        )
    )
    assert result["section"] == "Changes taking effect"
    assert result["heading"] == "Ashford"
    assert "Ruler becomes Ilyra" in result["explanation"]
    assert "Remove Old office" in result["explanation"]
    assert "Description changes" in result["explanation"]
    assert description not in result["explanation"]
    assert value not in result["explanation"]
    assert description in result["details"] and value in result["details"]


def test_custom_predicate_missing_endpoint_and_ordinary_connection():
    data = snapshot({"valid_from_event": True}, predicate="swears_oath_to")
    del data["objects"]["realm"]
    result = review(data)
    assert result["heading"].endswith("Missing object (realm) — swears_oath_to")
    assert "Relationship starts" in result["explanation"]
    data["consumers"][0]["attributes"] = {}
    plan = prepare_change(
        data, TimingChangeRequest(updates={"root": {"lore_date": 20}})
    )
    assert [row["kind"] for row in plan.consequences] == ["event"]


def test_maps_and_features_keep_owner_and_boundary():
    data = snapshot({})
    data["consumers"] = [
        {
            "kind": "map feature",
            "id": "feature",
            "name": "Eastern border",
            "map_name": "Northwatch",
            "attributes": {
                "temporal": {
                    "start": {
                        "anchor": {"anchor_id": "event:root"},
                    }
                }
            },
        }
    ]
    result = review(data)
    assert result["section"] == "Maps and features"
    assert result["heading"] == "Eastern border — Map: Northwatch"
    assert "Availability starts" in result["explanation"]


def test_followed_event_explains_endpoint_and_calendar_offset():
    data = snapshot({})
    child = Event(
        "Coronation",
        0,
        id="child",
        attributes=EventTimingDefinition(
            EndpointDefinition(
                "event",
                anchor_id="event:root",
                endpoint="end",
                offset={"unit": "days", "value": -2},
            ),
        ).apply({}),
    )
    data["events"].append(child.to_dict())
    plan = prepare_change(
        data, TimingChangeRequest(updates={"root": {"lore_date": 20}})
    )
    rows = {row["id"]: row["review"] for row in plan.consequences}
    assert rows["root"]["section"] == "Edited events"
    assert rows["child"]["section"] == "Other events moving"
    assert "end of “Succession”" in rows["child"]["explanation"]
    assert "offset -2 days" in rows["child"]["explanation"]


def test_imported_names_apply_to_existing_and_new_relations():
    data = snapshot({"valid_from_event": True})
    root = deepcopy(data["events"][0])
    root.update(name="Revised succession", lore_date=20)
    request = request_from_delta(
        data,
        [
            {
                "table": "entities",
                "before": {"id": "realm", "name": "Ashford"},
                "after": {"id": "realm", "name": "New Ashford"},
            },
            {"table": "events", "before": data["events"][0], "after": root},
            {
                "table": "relations",
                "before": None,
                "after": {
                    "id": "new",
                    "source_id": "root",
                    "target_id": "realm",
                    "rel_type": "custom",
                    "attributes": {"valid_from_event": True},
                },
            },
        ],
    )
    plan = prepare_change(data, request)
    assert not plan.errors
    relations = [
        row["review"] for row in plan.consequences if row["kind"] == "relation"
    ]
    assert len(relations) == 2
    assert all(
        "Revised succession → New Ashford" in row["heading"] for row in relations
    )

    from src.commands.event_timing_intents import request_for_command
    from src.commands.transfer_commands import ApplyTransferCommand

    command_request = request_for_command(
        ApplyTransferCommand(
            {
                "delta": [
                    {
                        "table": "entities",
                        "before": {"id": "realm", "name": "Ashford"},
                        "after": {"id": "realm", "name": "New Ashford"},
                    },
                ]
            }
        ),
        data,
    )
    assert command_request.review_objects["realm"]["name"] == "New Ashford"


def test_uncertain_reference_keeps_disjoint_ranges():
    from src.core.temporal_expression import ResolvedTemporalBounds
    from src.services.event_timing.review import _bounds_caption

    bounds = ResolvedTemporalBounds(
        hard_start=1,
        hard_end=8,
        possible_ranges=((1, 3), (5, 8)),
        possible_inclusivity=((False, True), (True, False)),
    )
    assert _bounds_caption(bounds, None) == (
        "after 1 days; through 3 days or from 5 days; before 8 days"
    )
