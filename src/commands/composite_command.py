"""Composite Command Module.

Combines multiple commands into a single executable unit.
"""

from typing import Dict, List

from src.commands.base_command import BaseCommand, CommandResult
from src.services.db_service import DatabaseService


class CompositeCommand(BaseCommand):
    """Executes a list of commands in sequence.

    If any command fails, execution stops, and previously executed commands
    are undone (rollback).
    """

    def __init__(
        self, commands: List[BaseCommand] = None, description: str = "Composite Command"
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
                success = result
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
        return CommandResult(
            success=True,
            message=f"{self.get_description()} completed.",
            command_name="CompositeCommand",
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
        for cmd in reversed(self.commands):
            cmd.undo(db_service)

    def get_description(self) -> str:
        return self._custom_description

    def to_dict(self) -> Dict:
        """Serialize command to dictionary."""
        return {
            "description": self._custom_description,
            "commands": [
                {"type": cmd.__class__.__name__, "data": cmd.to_dict()}
                for cmd in self.commands
            ],
            "is_executed": self._is_executed,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "CompositeCommand":
        """Deserialize command from dictionary.

        NOTE: This requires knowledge of supported sub-command types.
        """
        description = data.get("description", "Composite Command")
        cmd_dicts = data.get("commands", [])

        reconstructed_commands = []

        # Pragmatic registry import for deserialization
        from src.commands.entity_commands import (
            CreateEntityCommand,
            UpdateEntityCommand,
        )
        from src.commands.event_commands import CreateEventCommand, UpdateEventCommand
        from src.commands.relation_commands import AddRelationCommand
        from src.commands.wiki_commands import ProcessWikiLinksCommand

        known_types = {
            "UpdateEventCommand": UpdateEventCommand,
            "CreateEventCommand": CreateEventCommand,
            "UpdateEntityCommand": UpdateEntityCommand,
            "CreateEntityCommand": CreateEntityCommand,
            "ProcessWikiLinksCommand": ProcessWikiLinksCommand,
            "AddRelationCommand": AddRelationCommand,
        }

        for cmd_info in cmd_dicts:
            cmd_type = cmd_info.get("type")
            cmd_data = cmd_info.get("data")

            if cmd_type == "MockCommand":
                # Special case for testing
                # In real app logic, this branch wouldn't exist or we'd use registration
                continue

            cmd_class = known_types.get(cmd_type)
            if cmd_class:
                cmd = cmd_class.from_dict(cmd_data)
                reconstructed_commands.append(cmd)

        command = cls(reconstructed_commands, description)
        command._is_executed = data.get("is_executed", False)
        return command
