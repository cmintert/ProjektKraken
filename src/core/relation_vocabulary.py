"""Read-only relation wording over canonical saved assertions."""

import json
import re
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

VOCABULARY_KEY = "relation_vocabulary"
_PLACEHOLDER = re.compile(r"\{(source|target)\}")
_FIXED_LABELS = {
    "mentions": "Reference (read-only)",
    "related": "Connected — kind not specified",
}
REQUIRED_TEXT = ("forward_label", "reverse_label", "description")
OPTIONAL_TEXT = ("category", "forward_template", "reverse_template")
ENDPOINTS = ("preferred_source_kind", "preferred_target_kind")
FLAGS = ("enabled", "symmetric")


@dataclass(frozen=True)
class RelationWording:
    """Presentation of one assertion with its original identity."""

    relation_id: str
    key: str
    source_id: str
    target_id: str
    label: str
    assertion: str
    sentence: str | None


def parse_vocabulary(raw: str | None) -> dict[str, dict[str, str]]:
    """Decode supported world metadata into a detached wording snapshot."""
    try:
        entries = load_document(raw)["definitions"]
    except ValueError:
        return {}
    return _definitions(entries)


def load_document(raw: str | None) -> dict[str, Any]:
    """Read editable metadata while protecting unreadable or newer documents."""
    if raw is None:
        return {"version": 1, "definitions": []}
    try:
        document = json.loads(raw)
    except (ValueError, RecursionError) as exc:
        raise ValueError("This world's relation dictionary could not be read.") from exc
    if (
        not isinstance(document, dict)
        or type(document.get("version")) is not int
        or document["version"] != 1
        or not isinstance(document.get("definitions"), list)
    ):
        raise ValueError("This world's relation dictionary has an unsupported format.")
    seen: set[str] = set()
    for definition in document["definitions"]:
        validate_structure(definition)
        if definition["key"] in seen:
            raise ValueError(
                "This world's relation dictionary contains duplicate keys."
            )
        seen.add(definition["key"])
    return document


def validate_structure(definition: Any, *, editing: bool = False) -> None:
    """Validate version 1 fields while allowing recovery of invalid templates."""
    if not isinstance(definition, dict) or any(
        not isinstance(definition.get(field), str) or not definition[field].strip()
        for field in ("key", *REQUIRED_TEXT)
    ):
        raise ValueError("Each definition needs a key, both labels, and a description.")
    for field in FLAGS if editing else ("enabled",):
        if field in definition and type(definition[field]) is not bool:
            raise ValueError(f"Invalid definition field {field}.")
    if not editing:
        # Older readers ignored unrecognized optional hints and metadata.
        return
    for field in ENDPOINTS:
        if field in definition and definition[field] not in ("entity", "event"):
            raise ValueError(f"Invalid definition field {field}.")
    if "category" in definition and (
        not isinstance(definition["category"], str)
        or not definition["category"].strip()
    ):
        raise ValueError("Category must contain text when provided.")


def _definitions(entries: list[Any]) -> dict[str, dict[str, str]]:
    result = {}
    for entry in entries:
        key = entry["key"]
        if entry.get("enabled", True) and key not in _FIXED_LABELS:
            result[key] = {
                field: entry[field]
                for field in (
                    *REQUIRED_TEXT,
                    "forward_template",
                    "reverse_template",
                )
                if isinstance(entry.get(field), str)
            }
            for field in ENDPOINTS:
                if entry.get(field) in ("entity", "event"):
                    result[key][field] = entry[field]
    return result


def valid_template(template: str) -> bool:
    """Accept plain text with only the two literal endpoint placeholders."""
    literal = _PLACEHOLDER.sub("", template)
    return bool(template.strip()) and "{" not in literal and "}" not in literal


Vocabulary = Mapping[str, Mapping[str, str]]


def relation_label(key: str, vocabulary: Vocabulary) -> str:
    """Return the forward compact label for a stored key."""
    if key in _FIXED_LABELS:
        return _FIXED_LABELS[key]
    return vocabulary.get(key, {}).get("forward_label") or key


def filter_labels(keys: Iterable[str], vocabulary: Vocabulary) -> dict[str, str]:
    """Qualify ambiguous captions without replacing the filter value."""
    labels = {key: relation_label(key, vocabulary) for key in keys}
    counts = Counter(label.casefold() for label in labels.values())
    return {
        key: f"{label} ({key})" if counts[label.casefold()] > 1 else label
        for key, label in labels.items()
    }


def resolve_wording(
    relation: Mapping[str, Any],
    vocabulary: Vocabulary,
    *,
    incoming: bool = False,
) -> RelationWording:
    """Resolve plain text while retaining the canonical source and target."""
    key = relation["rel_type"]
    source_id, target_id = relation["source_id"], relation["target_id"]
    source = relation.get("source_name") or source_id
    target = relation.get("target_name") or target_id
    definition = vocabulary.get(key, {}) if key not in _FIXED_LABELS else {}
    reverse_label = definition.get("reverse_label") if incoming else None
    label = reverse_label or relation_label(key, vocabulary)
    template = definition.get("reverse_template" if incoming else "forward_template")
    if incoming and not reverse_label:
        template = None
    sentence = _render_sentence(template, source, target)
    assertion = (
        f"{label} {source}" if reverse_label else f"{source} → {label} → {target}"
    )
    return RelationWording(
        relation.get("id", ""), key, source_id, target_id, label, assertion, sentence
    )


def _render_sentence(template: str | None, source: str, target: str) -> str | None:
    if not template or not valid_template(template):
        return None
    names = {"source": source, "target": target}
    return _PLACEHOLDER.sub(lambda match: names[match[1]], template)
