"""Composite Command Module.

Combines multiple commands into a single executable unit.
"""

import logging
from typing import Dict, List

from src.commands.base_command import BaseCommand, CommandResult
from src.services.db_service import DatabaseService

logger = logging.getLogger(__name__)


class CompositeCommand(BaseCommand):
    """Executes a list of commands in sequence.

    If any command fails, execution stops, and previously executed commands
    are undone (rollback).
    """

    def __init__(
        self,
        commands: List[BaseCommand] | None = None,
        description: str = "Composite Command",
    ) -> None:
        """Initializes the composite command.

        Args:
            commands: List of sub-commands to execute.
            description: Human-readable description.
        """
        super().__init__()
        self.commands = commands or []
        self._custom_description = description
        self._executed_commands: List[BaseCommand] = []

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Executes strict sequence of commands.

        Args:
            db_service: Database service to operate on.

        Returns:
            CommandResult: Combined result of operation.
        """
        self._executed_commands.clear()

        for cmd in self.commands:
            try:
                result = cmd.execute(db_service)

                # Check for boolean or CommandResult failure
                success: CommandResult | bool = result
                message = ""
                if isinstance(result, CommandResult):
                    success = result.success
                    message = result.message

                if not success:
                    # Rollback
                    self._rollback(db_service)
                    return CommandResult(
                        success=False,
                        message=f"Sub-command failed: {message}",
                        command_name="CompositeCommand",
                    )

                self._executed_commands.append(cmd)

            except Exception as e:
                self._rollback(db_service)
                return CommandResult(
                    success=False,
                    message=f"Exception in sub-command: {e}",
                    command_name="CompositeCommand",
                )

        self._is_executed = True
        index_requests: list[dict[str, str]] = []
        for command in self.commands:
            command_name = command.__class__.__name__
            if command_name in {"CreateEntityCommand", "UpdateEntityCommand"}:
                object_id = getattr(command, "entity_id", None)
                if object_id:
                    index_requests.append(
                        {"object_type": "entity", "object_id": str(object_id)}
                    )
            elif command_name in {"CreateEventCommand", "UpdateEventCommand"}:
                object_id = getattr(command, "event_id", None)
                if object_id:
                    index_requests.append(
                        {"object_type": "event", "object_id": str(object_id)}
                    )
        return CommandResult(
            success=True,
            message=f"{self.get_description()} completed.",
            command_name="CompositeCommand",
            data={"index_requests": index_requests[:1]},
        )

    def _rollback(self, db_service: DatabaseService) -> None:
        """Undoes all successfully executed commands in reverse order."""
        for cmd in reversed(self._executed_commands):
            try:
                cmd.undo(db_service)
            except Exception:
                # Log but continue rollback
                pass

    def undo(self, db_service: DatabaseService) -> None:
        """Undoes all commands in reverse order."""
        if not self._is_executed:
            return

        for cmd in reversed(self.commands):
            if hasattr(cmd, "is_executed") and not cmd.is_executed:
                continue

            try:
                cmd.undo(db_service)
            except Exception as e:
                logger.error(
                    f"CompositeCommand: Failed to undo sub-command "
                    f"{cmd.__class__.__name__}: {e}"
                )

        self._is_executed = False

    def get_description(self) -> str:
        return self._custom_description

    def to_dict(self) -> Dict:
        """Serialize command to dictionary."""
        return {
            "description": self._custom_description,
            "commands": [
                {
                    "type": cmd.__class__.__name__,
                    "data": cmd.to_dict(),
                    "base": cmd.base_state_dict(),
                }
                for cmd in self.commands
            ],
            "is_executed": self._is_executed,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "CompositeCommand":
        """Deserialize command from dictionary.

        Command types are resolved through the central command registry.
        """
        description = data.get("description", "Composite Command")
        cmd_dicts = data.get("commands", [])

        reconstructed_commands = []

        from src.commands.registry import get_command_types

        known_types = get_command_types()

        for cmd_info in cmd_dicts:
            cmd_type = cmd_info.get("type")
            cmd_data = cmd_info.get("data")

            cmd_class = known_types.get(cmd_type)
            if cmd_class and cmd_class is not cls:
                cmd = cmd_class.from_dict(cmd_data)
                base_state = cmd_info.get("base", {})
                if isinstance(base_state, dict):
                    cmd.restore_base_state(base_state)
                reconstructed_commands.append(cmd)

        command = cls(reconstructed_commands, description)
        command._is_executed = data.get("is_executed", False)
        return command
