"""Validation and presentation for world-local relation definition edits."""

import json
from collections.abc import Mapping
from typing import Any

from src.core.lifecycle import CHARACTER_TRANSITIONS
from src.core.relation_guidance import relation_hint
from src.core.relation_vocabulary import (
    ENDPOINTS,
    FLAGS,
    OPTIONAL_TEXT,
    REQUIRED_TEXT,
    load_document,
    parse_vocabulary,
    resolve_wording,
    valid_template,
    validate_structure,
)

CATALOG_VERSION = 1
_FIXED_KEYS = {"mentions", "related"}
_BUILTIN_KEYS = CHARACTER_TRANSITIONS | {"member_of", "involved", "participated_in"}


def kraken_defaults() -> dict[str, dict[str, Any]]:
    """Build independent copies of the curated version 1 definitions."""
    return {
        key: {
            "key": key,
            "forward_label": forward,
            "reverse_label": reverse,
            "description": description,
            "category": category,
            "preferred_source_kind": source,
            "preferred_target_kind": target,
        }
        for key, forward, reverse, description, category, source, target in (
            (
                "member_of",
                "Member of",
                "Members",
                "Membership in a group.",
                "Membership",
                "entity",
                "entity",
            ),
            (
                "participated_in",
                "Participated in",
                "Participants",
                "An entity participated in an event.",
                "Participation",
                "entity",
                "event",
            ),
            (
                "involved",
                "Involves",
                "Involved in",
                "An event involves an entity.",
                "Participation",
                "event",
                "entity",
            ),
            (
                "birth",
                "Birth of",
                "Born at",
                "Birth of a character.",
                "Lifecycle",
                "event",
                "entity",
            ),
            (
                "death",
                "Death of",
                "Died at",
                "Death of a character.",
                "Lifecycle",
                "event",
                "entity",
            ),
            (
                "revival",
                "Revival of",
                "Revived at",
                "Return to life of a character.",
                "Lifecycle",
                "event",
                "entity",
            ),
        )
    }


def may_define(key: str, *, existing_key: bool = False) -> bool:
    """Protect fixed keys and variants recognized by normalized system consumers."""
    normalized = key.strip().casefold()
    return (
        bool(normalized)
        and normalized not in _FIXED_KEYS
        and (existing_key or normalized not in _BUILTIN_KEYS or key == normalized)
    )


def edit_document(
    raw: str | None, definition: dict[str, Any], original_key: str | None
) -> str:
    """Validate a single edit, retaining unrelated entries and extension fields."""
    document = load_document(raw)
    validate_structure(definition, editing=True)
    key = definition["key"]
    if original_key is not None and original_key != key:
        raise ValueError("A saved relation key cannot be edited here.")
    if original_key is None and key != key.strip():
        raise ValueError("Remove leading and trailing spaces from the new key.")
    if not may_define(key, existing_key=original_key is not None):
        raise ValueError("This key is reserved by Kraken.")
    for field, label in (
        ("forward_template", "Forward template"),
        ("reverse_template", "Reverse template"),
    ):
        if field in definition and (
            not isinstance(definition[field], str)
            or not valid_template(definition[field])
        ):
            raise ValueError(f"{label} may use only {{source}} and {{target}}.")
    entries: list[dict[str, Any]] = document["definitions"]
    for index, entry in enumerate(entries):
        if entry["key"] == key:
            if original_key is None:
                raise ValueError(
                    "This key already has a definition. Select it to edit."
                )
            known_fields = {"key", *REQUIRED_TEXT, *OPTIONAL_TEXT, *ENDPOINTS, *FLAGS}
            entries[index] = {
                name: value for name, value in entry.items() if name not in known_fields
            } | definition
            break
    else:
        entries.append(definition)
    return json.dumps(document, ensure_ascii=True)


def wording_examples(
    raw: str | None, key: str, example: Mapping[str, str] | None
) -> tuple[str, str, str]:
    """Render two perspectives and advisory guidance using the saved read path."""
    vocabulary = parse_vocabulary(raw)
    sample = example or {
        "source_id": "Source",
        "target_id": "Target",
        "source_kind": "",
        "target_kind": "",
    }
    assertion = {**sample, "rel_type": key}
    forward = resolve_wording(assertion, vocabulary)
    reverse = resolve_wording(assertion, vocabulary, incoming=True)
    guidance = relation_hint(
        key, vocabulary, sample["source_kind"], sample["target_kind"]
    )
    return (
        f"{forward.label} · {forward.sentence}"
        if forward.sentence
        else forward.assertion,
        f"{reverse.label} · {reverse.sentence}"
        if reverse.sentence
        else reverse.assertion,
        guidance,
    )
