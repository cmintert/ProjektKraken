"""Tests for the canonical Payload v2 contract."""

from copy import deepcopy

import pytest

from src.core.temporal_state import (
    ResolvedEntityState,
    apply_payload,
    validate_payload,
)


@pytest.mark.parametrize(
    "payload, message",
    [
        ([], "dictionary"),
        ({"status": "Wounded"}, "unsupported keys"),
        ({"attributes": []}, "attributes must be a dictionary"),
        ({"unset_attributes": "status"}, "must be a list"),
        ({"unset_attributes": [1]}, "keys must be strings"),
        ({"description": None}, "description must be a string"),
        ({"attributes": {"_tags": []}}, "internal"),
        ({"unset_attributes": ["_summary_data"]}, "internal"),
        ({"attributes": {"name": "Alias"}}, "reserved"),
        ({"unset_attributes": ["modified_at"]}, "reserved"),
        (
            {"attributes": {"status": "Wounded"}, "unset_attributes": ["status"]},
            "set and unset",
        ),
    ],
)
def test_validate_payload_rejects_invalid_contract(payload, message):
    with pytest.raises(ValueError, match=message):
        validate_payload(payload)


def test_apply_payload_is_immutable_and_obeys_operation_order():
    state = ResolvedEntityState(
        entity_id="entity-1",
        description="Original",
        attributes={"status": "Healthy", "garrison": 600, "ruler": "Crown"},
    )
    original = deepcopy(state)

    resolved = apply_payload(
        state,
        {
            "unset_attributes": ["garrison", "absent"],
            "attributes": {"status": "Ruined", "ruler": None},
            "description": "",
        },
    )

    assert resolved.description == ""
    assert resolved.attributes == {"status": "Ruined", "ruler": None}
    assert state == original
    assert resolved is not state


def test_to_dict_returns_detached_serializable_snapshot():
    state = ResolvedEntityState("entity-1", "Desc", {"nested": {"value": 1}})

    snapshot = state.to_dict()
    snapshot["attributes"]["nested"]["value"] = 2

    assert state.attributes["nested"]["value"] == 1
