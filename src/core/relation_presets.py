"""Versioned portable copies and exact-key import decisions."""

import json
from typing import Any

from src.core.relation_dictionary import (
    may_define,
    merge_definition,
    validate_definition,
)
from src.core.relation_vocabulary import load_document

PRESET_FORMAT = "kraken-relation-preset"
PRESET_VERSION = 1


def validate_definitions(entries: Any) -> dict[str, dict[str, Any]]:
    """Validate every definition before presenting a review."""
    if not isinstance(entries, list) or not entries:
        raise ValueError("A preset must contain at least one definition.")
    definitions: dict[str, dict[str, Any]] = {}
    for index, entry in enumerate(entries, start=1):
        name = entry.get("key") if isinstance(entry, dict) else None
        try:
            validate_definition(entry)
        except ValueError as exc:
            raise ValueError(f"{name or f'Definition {index}'}: {exc}") from exc
        key = entry["key"]
        if key in definitions:
            raise ValueError(f"Duplicate preset key: {key}")
        definitions[key] = entry
    return definitions


def read_preset(raw: str) -> list[dict[str, Any]]:
    """Decode only the supported portable preset envelope."""
    try:
        document = json.loads(raw)
        json.dumps(document, allow_nan=False)
    except (ValueError, RecursionError) as exc:
        raise ValueError("The preset is not valid JSON.") from exc
    if not isinstance(document, dict) or document.get("format") != PRESET_FORMAT:
        raise ValueError("Choose a Kraken relation preset file.")
    version = document.get("version")
    if type(version) is not int or version != PRESET_VERSION:
        raise ValueError("This relation preset version is unsupported.")
    return list(validate_definitions(document.get("definitions")).values())


def write_preset(definitions: list[dict[str, Any]]) -> str:
    """Serialize saved definitions without normalizing their keys."""
    validate_definitions(definitions)
    return (
        json.dumps(
            {
                "format": PRESET_FORMAT,
                "version": PRESET_VERSION,
                "definitions": definitions,
            },
            ensure_ascii=True,
            allow_nan=False,
            indent=2,
        )
        + "\n"
    )


def candidate(
    key: str, current: dict[str, Any] | None, incoming: dict[str, Any], count: int
) -> tuple[str, dict[str, Any] | None]:
    """Classify one destination key and build its explicit replacement."""
    known = current is not None or count > 0
    if not may_define(key, existing_key=known) or (not known and key != key.strip()):
        return "unavailable", None
    if current is None:
        return "addition", incoming
    merged = merge_definition(current, incoming)
    defaults = {"enabled": True, "symmetric": False}
    return ("match" if defaults | current == defaults | merged else "conflict"), merged


def apply_preset(
    raw: str | None,
    incoming: list[dict[str, Any]],
    choices: dict[str, str],
    counts: dict[str, int],
) -> str:
    """Apply a complete set of reviewed choices to detached metadata."""
    document = load_document(raw)
    existing = {entry["key"]: entry for entry in document["definitions"]}
    definitions = validate_definitions(incoming)
    if choices.keys() - definitions.keys():
        raise ValueError("The review contains a key absent from the preset.")
    for key, definition in definitions.items():
        status, proposed = candidate(key, existing.get(key), definition, counts[key])
        choice = choices.get(key)
        if choice == "keep" or (choice is None and status in {"match", "unavailable"}):
            continue
        if proposed is None or (status, choice) not in {
            ("addition", "import"),
            ("conflict", "replace"),
        }:
            raise ValueError(f"Review the import decision for {key}.")
        existing[key] = proposed
    document["definitions"] = list(existing.values())
    return json.dumps(document, ensure_ascii=True)
