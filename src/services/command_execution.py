"""Atomic command effects and persistent history, behind worker entry points."""

from typing import Literal

from src.core.command import CommandProtocol, CommandResult
from src.services.command_transactions import command_transaction
from src.services.db_service import DatabaseService
from src.services.history_service import HistoryService

Action = Literal["execute", "undo", "redo"]


class _FailedResult(Exception):
    silent_transaction_rollback = True

    def __init__(self, result: CommandResult) -> None:
        self.result = result


def execute_with_history(
    database: DatabaseService,
    history: HistoryService | None,
    command: CommandProtocol,
    action: Action,
) -> CommandResult:
    """Publish success only after both authoring and history have committed."""
    try:
        with command_transaction(database, restore_retry_state=True):
            raw = (
                command.undo(database)
                if action == "undo"
                else command.execute(database)
            )
            result = _normalize(raw, action)
            if not result.success:
                raise _FailedResult(result)
            if history is not None and getattr(command, "is_undoable", True):
                history.record_transition(command, action)
        return result
    except _FailedResult as failure:
        return failure.result


def _normalize(raw: object, action: Action) -> CommandResult:
    if isinstance(raw, CommandResult):
        return raw
    if raw is None and action == "undo":
        return CommandResult(success=True)
    if isinstance(raw, bool):
        return CommandResult(success=raw)
    return CommandResult(success=False, message="Invalid command result.")
