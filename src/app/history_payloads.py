"""Reconstruct detached command stacks without database access or UI mutation."""

from typing import Any

from src.commands.base_command import BaseCommand
from src.commands.registry import get_command_types


def restore_stacks(
    payload: object, limit: int
) -> tuple[list[BaseCommand], list[BaseCommand]]:
    """Reject the complete snapshot if an active command cannot be restored."""
    if isinstance(payload, list):
        payload = {"undo": payload, "redo": []}
    if not isinstance(payload, dict):
        raise ValueError("Invalid history snapshot")
    return (_restore(payload.get("undo"), limit), _restore(payload.get("redo"), limit))


def _restore(payloads: Any, limit: int) -> list[BaseCommand]:
    if not isinstance(payloads, list):
        raise ValueError("Invalid history stack")
    types = get_command_types()
    commands = []
    for payload in payloads[-limit:]:
        if not isinstance(payload, dict):
            raise ValueError("Invalid command snapshot")
        kind = types.get(str(payload.get("type", "")))
        data, base = payload.get("data"), payload.get("base")
        if kind is None or not isinstance(data, dict) or not isinstance(base, dict):
            raise ValueError("Cannot reconstruct active history command")
        command = kind.from_dict(data)
        command.restore_base_state(base)
        commands.append(command)
    return commands
