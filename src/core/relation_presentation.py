"""Existing relation wording, independent of widgets and vocabulary storage.

These compatibility rules deliberately retain different captions for different
surfaces. They do not define inverse predicates or a world vocabulary schema.
"""

from collections.abc import Iterable
from dataclasses import dataclass

_OVERVIEW_CAPTIONS = {
    "related": "Connected — kind not specified",
    "member_of": "Member of",
    "parent_of": "Parent of",
    "owns": "Owns",
    "located_at": "Located at",
    "involved": "Participation",
    "participated_in": "Participation",
    "caused": "Caused",
    "mentions": "Reference (read-only)",
}
_AUTHORING_CAPTIONS = {
    "related": "Connected — kind not specified",
    "member_of": "Member of",
    "involved": "Participant in",
    "located_at": "Located at",
    "owns": "Owns",
    "parent_of": "Parent of",
    "caused": "Caused",
}
_FORM_DEFAULTS = (
    "birth",
    "caused",
    "death",
    "involved",
    "located_at",
    "member_of",
    "owns",
    "parent_of",
    "related",
)


def overview_caption(rel_type: str) -> str:
    """Return the existing compact overview caption, or the exact unknown key."""
    return _OVERVIEW_CAPTIONS.get(rel_type, rel_type)


def authoring_caption(rel_type: str) -> str:
    """Return the existing authoring caption without interpreting unknown keys."""
    return _AUTHORING_CAPTIONS.get(rel_type, rel_type)


def authoring_choices(
    known_types: Iterable[str] = (), current_type: str | None = None
) -> tuple[tuple[str, str], ...]:
    """Return ordered (stored key, caption) pairs, excluding generated mentions.

    Built-ins precede observed types and the current key; exact duplicates retain
    their first position. Caption collisions do not merge different stored keys.
    """
    keys = dict.fromkeys([*_AUTHORING_CAPTIONS, *known_types])
    if current_type is not None:
        keys.setdefault(current_type, None)
    return tuple((key, authoring_caption(key)) for key in keys if key != "mentions")


def form_type_choices(known_types: list[str] | None) -> list[str]:
    """Retain the full form's defaults and sorted observed-type merge."""
    if not known_types:
        return list(_FORM_DEFAULTS)
    return sorted(
        value for value in set([*_FORM_DEFAULTS, *known_types]) if value != "mentions"
    )


@dataclass(frozen=True)
class RelationPreview:
    """Display-only preview and heading; neither field is a stored predicate."""

    text: str
    assertion: str


def inline_relation_preview(
    source_name: str,
    target_name: str,
    rel_type: str,
    *,
    source_is_event: bool,
    reversed_direction: bool,
) -> RelationPreview:
    """Render existing inline wording from the original stored endpoint names.

    ``source_is_event`` means a source-event date is available, including zero.
    Reversal swaps the displayed endpoints, not the caller's stored assertion.
    """
    if reversed_direction:
        source_name, target_name = target_name, source_name
    if rel_type == "related":
        text = f"{source_name} is connected to {target_name}; kind not specified."
    elif rel_type == "involved":
        text = (
            f"{target_name} participates in {source_name}."
            if source_is_event and not reversed_direction
            else f"{source_name} participates in {target_name}."
        )
    else:
        text = f"{source_name} → {target_name}: {authoring_caption(rel_type)}"
    return RelationPreview(
        text=text,
        assertion=f"{source_name} → {overview_caption(rel_type)} → {target_name}",
    )
