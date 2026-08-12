"""Layer-neutral command contracts shared by commands and services."""

from dataclasses import dataclass, field
from typing import Any, Protocol


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
