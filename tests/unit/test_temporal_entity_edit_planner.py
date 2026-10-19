"""Mutation planning preserves source ownership without persistence dependencies."""

from copy import deepcopy
from dataclasses import FrozenInstanceError

import pytest

from src.services.temporal_entity_edit_planner import (
    TemporalEditPlanError,
    TemporalEntityEditPlanner,
)

pytestmark = pytest.mark.ci_fast


@pytest.fixture
def snapshots():
    entity = {
        "id": "entity",
        "name": "Harbor",
        "type": "Location",
        "description": "Baseline",
        "attributes": {
            "owner": "Guild",
            "nested": {"items": [1]},
            "_tags": ["coast"],
            "_sheet_layout": [["owner"]],
            "_summary_data": {"text": "old"},
        },
    }
    state = {
        "description_source": {"kind": "relation", "relation_id": "relation"},
        "attribute_sources": {
            "owner": {"kind": "relation", "relation_id": "relation"},
            "nested": {"kind": "baseline"},
        },
    }
    relations = {
        "relation": {
            "id": "relation",
            "source_id": "event",
            "target_id": "entity",
            "rel_type": "involved",
            "attributes": {
                "payload": {
                    "description": "Dated",
                    "attributes": {"owner": "Army", "other": [1]},
                    "unset_attributes": ["hidden"],
                },
                "note": {"items": [2]},
            },
        }
    }
    return entity, state, relations


def _prepare(snapshots, patches=(), metadata=None):
    entity, state, relations = snapshots
    return TemporalEntityEditPlanner.prepare(
        entity, state, list(patches), metadata or {}, relations
    )


def test_mixed_plan_preserves_unrelated_values_and_detaches_all_nested_inputs(
    snapshots,
):
    entity, state, relations = snapshots
    patches = [
        {"field": "description", "action": "set", "value": ""},
        {"field": "attribute", "key": "owner", "action": "set", "value": ["Navy"]},
        {
            "field": "attribute",
            "key": "nested",
            "action": "set",
            "value": {"items": [3]},
        },
        {
            "field": "attribute",
            "key": "new",
            "action": "set",
            "scope": "dated",
            "event_name": " Rebuilding ",
            "value": {"items": [4]},
        },
    ]
    metadata = {"hidden_attributes": {"_summary_data": {"text": ["new"]}}}
    before = deepcopy((snapshots, patches, metadata))
    plan = _prepare(snapshots, patches, metadata)
    assert (snapshots, patches, metadata) == before
    assert plan.baseline_changed and not plan.sync_tags
    after = plan.relation_updates["relation"]
    assert after["attributes"]["payload"] == {
        "description": "",
        "attributes": {"owner": ["Navy"], "other": [1]},
        "unset_attributes": ["hidden"],
    }
    assert after["attributes"]["note"] == {"items": [2]}
    assert plan.before_relations == relations
    plan.baseline["attributes"]["nested"]["items"].append(9)
    plan.baseline["attributes"]["_summary_data"]["text"].append("later")
    plan.before_relations["relation"]["attributes"]["note"]["items"].append(9)
    after["attributes"]["payload"]["attributes"]["owner"].append("later")
    plan.dated_updates[("", " Rebuilding ")]["attributes"]["new"]["items"].append(9)
    assert after["attributes"]["note"] == {"items": [2]}
    assert (snapshots, patches, metadata) == before
    entity["attributes"]["_tags"].append("later")
    relations["relation"]["attributes"]["payload"]["attributes"]["other"].append(9)
    state["description_source"]["relation_id"] = "changed"
    assert plan.baseline["attributes"]["_tags"] == ["coast"]
    assert after["attributes"]["payload"]["attributes"]["other"] == [1]
    with pytest.raises(FrozenInstanceError):
        plan.baseline_changed = False


@pytest.mark.parametrize(
    "actions,initial,expected",
    [
        (["unset"], {}, {"attributes": {}, "unset_attributes": ["owner"]}),
        (["remove_override"], {}, {"attributes": {}, "unset_attributes": []}),
        (
            ["unset", "set"],
            {},
            {"attributes": {"owner": "new"}, "unset_attributes": []},
        ),
        (
            ["set", "remove_override"],
            {},
            {"attributes": {}, "unset_attributes": []},
        ),
        (
            ["remove_override"],
            {"unset_attributes": ["owner"]},
            {"attributes": {}, "unset_attributes": ["owner"]},
        ),
    ],
)
def test_attribute_action_sequences_retain_existing_mask_semantics(
    snapshots, actions, initial, expected
):
    snapshots[2]["relation"]["attributes"]["payload"] = initial
    patches = [
        {"field": "attribute", "key": "owner", "action": action, "value": "new"}
        for action in actions
    ]
    plan = _prepare(snapshots, patches)
    assert plan.relation_updates["relation"]["attributes"]["payload"] == expected


def test_description_override_removal_and_empty_baseline(snapshots):
    plan = _prepare(
        snapshots,
        [
            {"field": "description", "action": "remove_override"},
            {"field": "description", "scope": "baseline", "action": "set", "value": ""},
        ],
    )
    assert plan.baseline["description"] == ""
    assert (
        "description" not in plan.relation_updates["relation"]["attributes"]["payload"]
    )


@pytest.mark.parametrize("action", ["unset", "remove_override"])
def test_baseline_removals_delete_the_key(snapshots, action):
    plan = _prepare(
        snapshots, [{"field": "attribute", "key": "nested", "action": action}]
    )
    assert "nested" not in plan.baseline["attributes"]


def test_dated_groups_keep_first_use_order_untrimmed_names_and_last_patch(snapshots):
    patches = [
        {"field": "description", "scope": "dated", "action": "set", **destination}
        for destination in [
            {"event_name": " First ", "value": "one"},
            {"event_id": "existing", "value": "two"},
            {"event_name": " First ", "value": "replacement"},
            {"event_name": "First", "value": "three"},
        ]
    ]
    plan = _prepare(snapshots, patches)
    assert list(plan.dated_updates) == [
        ("", " First "),
        ("existing", ""),
        ("", "First"),
    ]
    assert plan.dated_updates[("", " First ")]["description"] == "replacement"
    assert not plan.baseline_changed


@pytest.mark.parametrize("key", ["_tags", "_sheet_layout", "_summary_data"])
def test_hidden_metadata_removal_and_noop(snapshots, key):
    noop = _prepare(
        snapshots,
        metadata={"hidden_attributes": {key: snapshots[0]["attributes"][key]}},
    )
    assert not noop.baseline_changed and not noop.sync_tags
    removed = _prepare(snapshots, metadata={"hidden_attributes": {key: None}})
    assert key not in removed.baseline["attributes"]
    assert removed.baseline_changed
    assert removed.sync_tags == (key == "_tags")


def test_metadata_only_name_type_and_tags(snapshots):
    plan = _prepare(
        snapshots,
        metadata={
            "name": "New",
            "type": "Place",
            "hidden_attributes": {"_tags": ["new"]},
        },
    )
    assert (plan.baseline["name"], plan.baseline["type"]) == ("New", "Place")
    assert plan.baseline["description"] == snapshots[0]["description"]
    assert plan.sync_tags
    assert not plan.relation_updates and not plan.dated_updates


@pytest.mark.parametrize(
    "patch,metadata,message",
    [
        (
            {"field": "attribute", "key": "new", "action": "set", "value": 1},
            {},
            "A new field needs a baseline or dated scope",
        ),
        (
            {"field": "description", "scope": "unknown", "action": "set", "value": "x"},
            {},
            "Unknown edit scope: unknown",
        ),
        (
            {
                "field": "description",
                "scope": "dated",
                "action": "set",
                "value": "x",
                "event_name": "  ",
            },
            {},
            "Choose an event or enter a new event name",
        ),
        (
            {"field": "description", "action": "set", "value": "x"},
            {"hidden_attributes": {"_private": 1}},
            "Unsupported baseline metadata: _private",
        ),
    ],
)
def test_planning_rejections_preserve_messages_and_inputs(
    snapshots, patch, metadata, message
):
    before = deepcopy(snapshots)
    with pytest.raises(TemporalEditPlanError) as error:
        _prepare(snapshots, [patch], metadata)
    assert str(error.value) == message
    assert snapshots == before


@pytest.mark.parametrize("record", [None, {"target_id": "other"}])
def test_missing_or_wrong_target_relation_rejects(snapshots, record):
    snapshots[2]["relation"] = record
    with pytest.raises(
        TemporalEditPlanError, match="The source relation no longer exists"
    ):
        _prepare(snapshots, [{"field": "description", "action": "set", "value": "x"}])


def test_relation_snapshot_collection_is_distinct_and_excludes_explicit_destinations(
    snapshots,
):
    patches = [
        {"field": "description"},
        {"field": "attribute", "key": "owner"},
        {"field": "attribute", "key": "nested"},
        {"field": "description", "scope": "baseline"},
        {"field": "description", "scope": "dated"},
    ]
    assert TemporalEntityEditPlanner.source_relation_ids(snapshots[1], patches) == (
        "relation",
    )
