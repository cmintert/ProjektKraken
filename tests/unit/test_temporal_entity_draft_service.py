"""Source-aware preparation preserves authored intent without UI or storage."""

from copy import deepcopy
from dataclasses import replace

import pytest

from src.services.temporal_entity_draft_service import (
    ChoiceRequired,
    NoChanges,
    PendingTemporalSubmission,
    PreparedSave,
    TemporalEntityDraftService,
    TemporalEntityDraftSnapshot,
)

pytestmark = pytest.mark.ci_fast


@pytest.fixture
def draft():
    return TemporalEntityDraftSnapshot(
        entity_id="harbor",
        lore_time=-12.0,
        generation=3,
        revision=4,
        state={
            "description": "Old harbor",
            "attributes": {"owner": "Guild", "_private": "preserve"},
            "attribute_sources": {"owner": {"kind": "baseline"}},
        },
        baseline_metadata={
            "name": "Harbor",
            "type": "Location",
            "_tags": None,
            "_sheet_layout": None,
            "_summary_data": None,
        },
        name="Harbor",
        entity_type="Location",
        description="Old harbor",
        attributes={"owner": "Guild", "_private": "ignored"},
        tags=[],
        sheet_layout={"rows": ["owner"]},
        displayed_sheet_layout={"rows": ["owner"]},
        description_event=None,
        summary_changed=False,
        summary_data=None,
    )


def test_unchanged_draft_ignores_hidden_values_and_displayed_layout(draft):
    assert isinstance(TemporalEntityDraftService.prepare(draft, {}), NoChanges)


@pytest.mark.parametrize("source", [{"kind": "baseline"}, {"kind": "relation"}])
def test_source_corrections_do_not_choose_new_ownership(draft, source):
    draft.state["description_source"] = source
    draft.state["attribute_sources"]["owner"] = source
    changed = replace(draft, description="", attributes={"owner": ["Council"]})
    result = TemporalEntityDraftService.prepare(changed, {})
    assert result == PreparedSave(
        [
            {"field": "description", "action": "set", "value": ""},
            {
                "field": "attribute",
                "key": "owner",
                "action": "set",
                "value": ["Council"],
            },
        ],
        {},
    )


def test_same_description_can_start_a_new_dated_owner(draft):
    result = TemporalEntityDraftService.prepare(
        replace(draft, description_event={"event_name": "Rebuilding"}), {}
    )
    assert result == PreparedSave(
        [
            {
                "field": "description",
                "action": "set",
                "value": "Old harbor",
                "scope": "dated",
                "event_name": "Rebuilding",
            }
        ],
        {},
    )


@pytest.mark.parametrize(
    "destination",
    [
        {"scope": "baseline"},
        {"scope": "dated", "event_id": "existing-event"},
        {"scope": "dated", "event_name": "New event"},
    ],
)
def test_addition_requires_explicit_destination(draft, destination):
    changed = replace(draft, attributes={"owner": "Guild", "rank": 2})
    assert TemporalEntityDraftService.prepare(changed, {}) == ChoiceRequired(
        "rank", "addition"
    )
    assert TemporalEntityDraftService.prepare(changed, {"rank": destination}) == (
        PreparedSave(
            [
                {
                    "field": "attribute",
                    "key": "rank",
                    "action": "set",
                    "value": 2,
                    **destination,
                }
            ],
            {},
        )
    )


@pytest.mark.parametrize(
    "removal",
    [
        {"field": "attribute", "key": "owner", "action": "unset"},
        {"field": "attribute", "key": "owner", "action": "remove_override"},
        {
            "field": "attribute",
            "key": "owner",
            "action": "unset",
            "scope": "dated",
            "event_name": "Abandonment",
        },
    ],
)
def test_removal_preserves_the_selected_meaning(draft, removal):
    changed = replace(draft, attributes={})
    assert TemporalEntityDraftService.prepare(changed, {}) == ChoiceRequired(
        "owner", "removal"
    )
    assert TemporalEntityDraftService.prepare(changed, {"owner": removal}) == (
        PreparedSave([removal], {})
    )


@pytest.mark.parametrize("summary", [None, {}, {"text": "A harbor"}])
def test_metadata_only_preserves_empty_and_deleted_summary_intent(draft, summary):
    changed = replace(
        draft,
        name="Port",
        entity_type="Place",
        tags=["coast"],
        summary_changed=True,
        summary_data=summary,
    )
    assert TemporalEntityDraftService.prepare(changed, {}) == PreparedSave(
        [],
        {
            "name": "Port",
            "type": "Place",
            "hidden_attributes": {"_tags": ["coast"], "_summary_data": summary},
        },
    )


def test_sheet_reordering_is_saved_only_with_unchanged_visible_keys(draft):
    changed = replace(draft, sheet_layout={"rows": []})
    assert TemporalEntityDraftService.prepare(changed, {}) == PreparedSave(
        [],
        {
            "hidden_attributes": {"_sheet_layout": {"rows": []}},
        },
    )
    changed = replace(changed, attributes={"owner": "Guild", "rank": 2})
    result = TemporalEntityDraftService.prepare(
        changed, {"rank": {"scope": "baseline"}}
    )
    assert isinstance(result, PreparedSave)
    assert result.metadata == {}


def test_preparation_and_pending_intent_own_nested_copies(draft):
    changed = replace(
        draft,
        attributes={"owner": ["Council"]},
        summary_changed=True,
        summary_data={"parts": ["first"]},
        description_event={"event_name": "Rebuilding"},
    )
    before = deepcopy(changed)
    result = TemporalEntityDraftService.prepare(changed, {})
    assert isinstance(result, PreparedSave)
    pending = PendingTemporalSubmission(result.metadata, changed.description_event)
    assert changed == before
    changed.attributes["owner"].append("newer")
    changed.summary_data["parts"].append("newer")
    changed.description_event["event_name"] = "Newer event"
    assert result.patches[-1]["value"] == ["Council"]
    assert result.metadata["hidden_attributes"]["_summary_data"] == {"parts": ["first"]}
    result.metadata["hidden_attributes"]["_summary_data"]["parts"].append("transport")
    assert pending.metadata["hidden_attributes"]["_summary_data"] == {
        "parts": ["first"]
    }
    assert pending.description_event == {"event_name": "Rebuilding"}


def test_choices_are_copied_and_no_partial_payload_escapes(draft):
    changed = replace(draft, attributes={"new": [1], "other": 2}, description="New")
    choices = {"new": {"scope": "dated", "event_name": "Rebuilding"}}
    assert TemporalEntityDraftService.prepare(changed, choices) == ChoiceRequired(
        "other", "addition"
    )
    choices["other"] = {"scope": "baseline"}
    result = TemporalEntityDraftService.prepare(changed, choices)
    assert result == ChoiceRequired("owner", "removal")
    choices["owner"] = {"field": "attribute", "key": "owner", "action": "unset"}
    result = TemporalEntityDraftService.prepare(changed, choices)
    assert isinstance(result, PreparedSave)
    choices["owner"]["action"] = "remove_override"
    assert result.patches[-1]["action"] == "unset"
