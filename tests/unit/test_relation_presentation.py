"""Compatibility behavior for relation wording without Qt or a database."""

from copy import deepcopy
from dataclasses import FrozenInstanceError
from types import MappingProxyType

import pytest

from src.core.relation_policy import has_direction_sensitive_attributes
from src.core.relation_presentation import (
    authoring_caption,
    authoring_choices,
    form_type_choices,
    inline_relation_preview,
    overview_caption,
)

pytestmark = pytest.mark.ci_fast


@pytest.mark.parametrize(
    "key,overview,authoring",
    [
        ("related", "Connected — kind not specified", "Connected — kind not specified"),
        ("involved", "Participation", "Participant in"),
        ("participated_in", "Participation", "participated_in"),
        ("mentions", "Reference (read-only)", "mentions"),
        ("member_of", "Member of", "Member of"),
        ("guards Ælf's gate", "guards Ælf's gate", "guards Ælf's gate"),
        ("Member of", "Member of", "Member of"),
        ("", "", ""),
    ],
)
def test_captions_preserve_surface_meaning_and_exact_unknown_keys(
    key, overview, authoring
):
    assert overview_caption(key) == overview
    assert authoring_caption(key) == authoring


def test_authoring_choices_keep_order_identity_and_caption_collisions():
    known = ["custom oath", "member_of", "mentions", "Member of", "custom oath"]
    before = known.copy()
    choices = authoring_choices(known, "current only")
    assert choices == (
        ("related", "Connected — kind not specified"),
        ("member_of", "Member of"),
        ("involved", "Participant in"),
        ("located_at", "Located at"),
        ("owns", "Owns"),
        ("parent_of", "Parent of"),
        ("caused", "Caused"),
        ("custom oath", "custom oath"),
        ("Member of", "Member of"),
        ("current only", "current only"),
    )
    assert known == before
    assert authoring_choices() == authoring_choices([]) == choices[:7]
    assert authoring_choices(["mentions"], "mentions") == choices[:7]


@pytest.mark.parametrize("known", [None, []])
def test_full_form_defaults_and_returned_choices_are_independent(known):
    expected = [
        "birth",
        "caused",
        "death",
        "involved",
        "located_at",
        "member_of",
        "owns",
        "parent_of",
        "related",
    ]
    choices = form_type_choices(known)
    assert choices == expected
    choices.append("local edit")
    assert form_type_choices(known) == expected


def test_full_form_observed_types_are_sorted_without_normalizing_keys():
    known = ["Ω oath", "member_of", "mentions", "Member of", "Ω oath"]
    before = known.copy()
    assert form_type_choices(known) == [
        "Member of",
        "birth",
        "caused",
        "death",
        "involved",
        "located_at",
        "member_of",
        "owns",
        "parent_of",
        "related",
        "Ω oath",
    ]
    assert known == before


@pytest.mark.parametrize(
    "key,is_event,reversed_direction,text,assertion",
    [
        (
            "related",
            False,
            False,
            "A is connected to B; kind not specified.",
            "A → Connected — kind not specified → B",
        ),
        (
            "related",
            True,
            True,
            "B is connected to A; kind not specified.",
            "B → Connected — kind not specified → A",
        ),
        ("involved", True, False, "B participates in A.", "A → Participation → B"),
        ("involved", False, False, "A participates in B.", "A → Participation → B"),
        ("involved", True, True, "B participates in A.", "B → Participation → A"),
        ("member_of", True, False, "A → B: Member of", "A → Member of → B"),
        ("custom oath", False, True, "B → A: custom oath", "B → custom oath → A"),
    ],
)
def test_previews_preserve_original_direction_rules(
    key, is_event, reversed_direction, text, assertion
):
    result = inline_relation_preview(
        "A", "B", key, source_is_event=is_event, reversed_direction=reversed_direction
    )
    assert (result.text, result.assertion) == (text, assertion)
    with pytest.raises(FrozenInstanceError):
        result.text = "changed"


@pytest.mark.parametrize(
    "attributes,expected",
    [
        ({}, False),
        ({"notes": "source_event", "custom": [1]}, False),
        ({"payload": {}, "valid_from_event": 0, "temporal": {}}, False),
        ({"payload": {"attributes": {"rank": "Lord"}}}, True),
        ({"payload": {"unrecognized": True}}, True),
        ({"valid_from_event": "anchor"}, True),
        ({"valid_to_event": "anchor"}, True),
        ({"valid_at_event": "anchor"}, True),
        ({"temporal": {"schema": 1, "start": {"binding": "source_event"}}}, True),
        ({"temporal": {"note": "legacy source_event text"}}, True),
        ({"temporal": {"start": {"exact": 0.0}}}, False),
    ],
)
def test_reversal_assessment_preserves_truthiness_and_string_compatibility(
    attributes, expected
):
    before = deepcopy(attributes)
    assert has_direction_sensitive_attributes(MappingProxyType(attributes)) is expected
    assert attributes == before
