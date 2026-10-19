"""Read-only compatibility assessments for inline relation editing."""

from collections.abc import Mapping
from typing import Any


def has_direction_sensitive_attributes(attributes: Mapping[str, Any]) -> bool:
    """Retain the inline editor's existing source-direction assessment exactly.

    Truthiness and the temporal string check are intentional compatibility rules,
    not structural validation. Command-level enforcement and improved temporal
    interpretation belong to KRT-70; undo restoration must remain independent.
    """
    return bool(
        attributes.get("payload")
        or any(
            attributes.get(key)
            for key in ("valid_from_event", "valid_to_event", "valid_at_event")
        )
        or "source_event" in str(attributes.get("temporal", {}))
    )
