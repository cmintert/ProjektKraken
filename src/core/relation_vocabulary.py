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
        document = json.loads(raw) if raw is not None else None
    except (ValueError, RecursionError):
        return {}
    if not isinstance(document, dict) or type(document.get("version")) is not int:
        return {}
    if document["version"] != 1 or not isinstance(document.get("definitions"), list):
        return {}
    return _definitions(document["definitions"])


def _definitions(entries: list[Any]) -> dict[str, dict[str, str]]:
    result = {}
    seen = set()
    for entry in entries:
        required = ("key", "forward_label", "reverse_label", "description")
        if not isinstance(entry, dict) or any(
            not isinstance(entry.get(field), str) or not entry[field].strip()
            for field in required
        ):
            return {}
        key = entry["key"]
        enabled = entry.get("enabled", True)
        if key in seen or not isinstance(enabled, bool):
            return {}
        seen.add(key)
        if enabled and key not in _FIXED_LABELS:
            result[key] = {
                field: entry[field]
                for field in (*required[1:], "forward_template", "reverse_template")
                if isinstance(entry.get(field), str)
            }
    return result


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
    if not template or not template.strip():
        return None
    literal = _PLACEHOLDER.sub("", template)
    if "{" in literal or "}" in literal:
        return None
    names = {"source": source, "target": target}
    return _PLACEHOLDER.sub(lambda match: names[match[1]], template)
