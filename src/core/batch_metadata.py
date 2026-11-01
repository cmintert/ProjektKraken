"""Detached intent and value rules for editing saved lore metadata."""

import json
import math
from dataclasses import dataclass, field, fields
from typing import Any, Literal

from src.core.entities import Entity
from src.core.events import Event

ObjectKind = Literal["entity", "event"]
Target = tuple[ObjectKind, str]
ACTIONS = ("add_tags", "remove_tags", "set", "set_missing", "remove")
CORE_KEYS = frozenset(item.name for model in (Entity, Event) for item in fields(model))


def values_equal(left: Any, right: Any) -> bool:
    """Compare JSON values without equating booleans with numeric values."""
    if type(left) in (int, float) and type(right) in (int, float):
        return bool(left == right)
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(
            values_equal(value, right[key]) for key, value in left.items()
        )
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(
            values_equal(a, b) for a, b in zip(left, right, strict=True)
        )
    return json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(
        right, sort_keys=True, allow_nan=False
    )


def normalize_targets(targets: list[Any]) -> list[Target]:
    """Validate and sort typed identities, retaining same-ID distinct kinds."""
    result: set[Target] = set()
    for kind, object_id in targets:
        if kind not in ("entity", "event") or not isinstance(object_id, str):
            raise ValueError("Invalid checked object identity.")
        if not object_id:
            raise ValueError("An object ID is required.")
        result.add((kind, object_id))
    if not result:
        raise ValueError("Check at least one Entity or Event first.")
    return sorted(result)


@dataclass
class MetadataOperation:
    """One validated metadata operation applied to every checked record."""

    action: str
    key: str = ""
    value_type: str = "String"
    value: Any = ""
    tags: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Reject protected keys and invalid typed values at every boundary."""
        if self.action not in ACTIONS:
            raise ValueError("Unknown batch operation.")
        if self.action in ("add_tags", "remove_tags"):
            if not isinstance(self.tags, list) or any(
                not isinstance(tag, str) for tag in self.tags
            ):
                raise ValueError("Tags must be names.")
            self.tags = sorted({tag.strip() for tag in self.tags if tag.strip()})
            if not self.tags:
                raise ValueError("Add at least one tag to the operation.")
            return
        self.key = self.key.strip()
        if not self.key or self.key.startswith("_") or self.key in CORE_KEYS:
            raise ValueError(
                "Choose a custom attribute, not an internal or core field."
            )
        if self.action != "remove":
            self._validate_value()

    def _validate_value(self) -> None:
        valid = {
            "String": isinstance(self.value, str),
            "Boolean": type(self.value) is bool,
            "Number": type(self.value) in (int, float),
        }
        if not valid.get(self.value_type, False):
            raise ValueError("The value does not match its selected type.")
        if self.value_type == "Number" and not math.isfinite(self.value):
            raise ValueError("Enter a finite number.")

    @property
    def affected_key(self) -> str:
        """Return the only attribute key this operation may modify."""
        return "_tags" if self.action in ("add_tags", "remove_tags") else self.key

    def to_dict(self) -> dict[str, Any]:
        """Return detached JSON-safe intent."""
        return {
            "action": self.action,
            "key": self.key,
            "value_type": self.value_type,
            "value": self.value,
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MetadataOperation":
        """Validate serialized intent."""
        return cls(**data)

    def patch(self, attributes: dict[str, Any]) -> tuple[dict, dict, bool]:
        """Return presence-aware before/after states and overwrite classification."""
        key = self.affected_key
        before = {"present": key in attributes, "value": attributes.get(key)}
        after = dict(before)
        if self.action in ("add_tags", "remove_tags"):
            after = self._tag_patch(before)
        elif self.action == "remove":
            after = {"present": False, "value": None}
        elif self.action == "set" or not before["present"]:
            after = {"present": True, "value": self.value}
        overwritten = (
            self.action == "set"
            and bool(before["present"])
            and not values_equal(before, after)
        )
        return before, after, overwritten

    def _tag_patch(self, before: dict) -> dict:
        tags = before["value"] if before["present"] else []
        if not isinstance(tags, list) or any(not isinstance(t, str) for t in tags):
            raise ValueError("Saved tags are malformed; repair this object first.")
        if self.action == "add_tags":
            updated = list(dict.fromkeys([*tags, *self.tags]))
        else:
            updated = [tag for tag in tags if tag not in self.tags]
        if updated == tags:
            return dict(before)
        return {"present": True, "value": updated}
