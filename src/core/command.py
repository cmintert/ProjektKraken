"""Layer-neutral command contracts shared by commands and services."""

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, TypedDict, cast


class LoreMutationEffect(TypedDict):
    """Serializable description of one persisted lore-object mutation."""

    object_type: Literal["event", "entity"]
    operation: Literal["upsert", "delete"]
    object_id: str
    snapshot: dict[str, Any] | None
    relations_changed: bool


def parse_lore_mutation_effects(value: object) -> list[LoreMutationEffect] | None:
    """Validate an optional command-result lore mutation payload."""
    if not isinstance(value, list) or not value:
        return None
    validated: list[LoreMutationEffect] = []
    for raw in value:
        if not isinstance(raw, dict):
            return None
        object_type = raw.get("object_type")
        operation = raw.get("operation")
        object_id = raw.get("object_id")
        snapshot = raw.get("snapshot")
        relations_changed = raw.get("relations_changed")
        if object_type not in {"event", "entity"}:
            return None
        if operation not in {"upsert", "delete"}:
            return None
        if not isinstance(object_id, str) or not object_id:
            return None
        if operation == "upsert" and not isinstance(snapshot, dict):
            return None
        if operation == "delete" and snapshot is not None:
            return None
        if not isinstance(relations_changed, bool):
            return None
        if isinstance(snapshot, dict):
            if snapshot.get("id") != object_id:
                return None
            try:
                if object_type == "event":
                    from src.core.events import Event

                    Event.from_dict(snapshot)
                else:
                    from src.core.entities import Entity

                    Entity.from_dict(snapshot)
            except (TypeError, ValueError, KeyError):
                return None
        validated.append(cast(LoreMutationEffect, dict(raw)))
    return validated


@dataclass
class CommandResult:
    """Standardized result returned by command execution and undo."""

    success: bool
    message: str = ""
    errors: dict[str, str] = field(default_factory=dict)
    data: dict[str, object] = field(default_factory=dict)
    command_name: str = ""


class CommandProtocol(Protocol):
    """Structural command interface required by persistence and workers."""

    command_id: str
    persist_to_history: bool

    def execute(self, db_service: Any) -> CommandResult:
        """Execute this command against the worker-owned database service."""
        ...

    def undo(self, db_service: Any) -> CommandResult | None:
        """Undo this command against the worker-owned database service."""
        ...

    def to_dict(self) -> dict[str, Any]:
        """Return the command-specific serializable payload."""
        ...

    def base_state_dict(self) -> dict[str, Any]:
        """Return common serializable command state."""
        ...

    def restore_base_state(self, state: dict[str, Any]) -> None:
        """Restore common state after deserialization."""
        ...

    def get_description(self) -> str:
        """Return a user-facing description of the command."""
        ...
