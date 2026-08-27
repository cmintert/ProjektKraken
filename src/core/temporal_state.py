"""Resolved temporal entity state and Payload v2 operations."""

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

_PAYLOAD_KEYS = {"attributes", "unset_attributes", "description"}
_RESERVED_ATTRIBUTE_KEYS = {
    "id",
    "name",
    "type",
    "created_at",
    "modified_at",
}


@dataclass
class ResolvedEntityState:
    """Calculated mutable entity state at a specific lore time."""

    entity_id: str
    description: str
    attributes: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Return a serializable snapshot suitable for queued Qt delivery."""
        return {
            "entity_id": self.entity_id,
            "description": self.description,
            "attributes": deepcopy(self.attributes),
        }


def _validate_attribute_key(key: object, section: str) -> str:
    """Validate and return a user-mutable attribute key."""
    if not isinstance(key, str):
        raise ValueError(f"{section} keys must be strings")
    if key.startswith("_"):
        raise ValueError(f"attribute key {key!r} is internal and cannot be mutated")
    if key in _RESERVED_ATTRIBUTE_KEYS:
        raise ValueError(f"attribute key {key!r} is reserved and cannot be mutated")
    return key


def validate_payload(payload: object) -> None:
    """Validate the canonical Payload v2 mutation object.

    Raises:
        ValueError: If the payload does not satisfy the v2 contract.
    """
    if not isinstance(payload, dict):
        raise ValueError("payload must be a dictionary")

    unknown_keys = set(payload) - _PAYLOAD_KEYS
    if unknown_keys:
        unknown = ", ".join(sorted(str(key) for key in unknown_keys))
        raise ValueError(f"payload contains unsupported keys: {unknown}")

    attributes = payload.get("attributes", {})
    if not isinstance(attributes, dict):
        raise ValueError("payload.attributes must be a dictionary")
    set_keys = {
        _validate_attribute_key(key, "payload.attributes") for key in attributes
    }

    unset_attributes = payload.get("unset_attributes", [])
    if not isinstance(unset_attributes, list):
        raise ValueError("payload.unset_attributes must be a list of strings")
    unset_keys = {
        _validate_attribute_key(key, "payload.unset_attributes")
        for key in unset_attributes
    }

    overlap = set_keys & unset_keys
    if overlap:
        keys = ", ".join(sorted(overlap))
        raise ValueError(f"attributes cannot be set and unset together: {keys}")

    if "description" in payload and not isinstance(payload["description"], str):
        raise ValueError("payload.description must be a string")


def apply_payload(
    state: ResolvedEntityState,
    payload: object,
) -> ResolvedEntityState:
    """Return a new resolved state with one validated Payload v2 mutation applied."""
    validate_payload(payload)
    assert isinstance(payload, dict)

    attributes = dict(state.attributes)
    for key in payload.get("unset_attributes", []):
        attributes.pop(key, None)
    attributes.update(payload.get("attributes", {}))

    description = payload.get("description", state.description)
    return ResolvedEntityState(
        entity_id=state.entity_id,
        description=description,
        attributes=attributes,
    )
