"""Composite Command Module.

Combines multiple commands into a single executable unit.
"""

import logging
from typing import Dict, List

from src.commands.base_command import BaseCommand, CommandResult
from src.commands.entity_commands import CreateEntityCommand
from src.commands.event_commands import CreateEventCommand
from src.commands.marker_commands import CreateMarkerCommand
from src.commands.temporal_entity_edit_command import TemporalEntityEditCommand
from src.commands.wiki_commands import ProcessWikiLinksCommand
from src.core.command import LoreMutationEffect, parse_lore_mutation_effects
from src.services.db_service import DatabaseService
from src.services.temporal_entity_snapshot_service import TemporalEntitySnapshotService

logger = logging.getLogger(__name__)

_OBJECT_MARKER_COMMAND_COUNT = 2


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
        sub_results: list[CommandResult] = []

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
                if isinstance(result, CommandResult):
                    sub_results.append(result)

            except Exception as e:
                self._rollback(db_service)
                return CommandResult(
                    success=False,
                    message=f"Exception in sub-command: {e}",
                    command_name="CompositeCommand",
                )

        checkpoint_data = self._temporal_checkpoint_data(db_service)
        self._is_executed = True
        index_requests: list[dict[str, str]] = []
        marker_map_ids: list[str] = []
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
            if command_name == "CreateMarkerCommand":
                map_id = getattr(command, "map_id", None)
                if map_id and str(map_id) not in marker_map_ids:
                    marker_map_ids.append(str(map_id))
        data: dict[str, object] = {
            "index_requests": index_requests[:1],
            "marker_map_ids": marker_map_ids,
            "maps_changed": any(
                command.__class__.__name__ == "SetRasterMappingCommand"
                for command in self.commands
            ),
        }
        data.update(checkpoint_data)
        effects = self._aggregate_lore_effects(sub_results)
        if effects is not None:
            data["lore_effects"] = effects
            data["select_after_apply"] = self._creation_selection(sub_results)
        return CommandResult(
            success=True,
            message=f"{self.get_description()} completed.",
            command_name="CompositeCommand",
            data=data,
        )

    def _creation_selection(
        self, results: list[CommandResult]
    ) -> dict[str, str] | bool:
        """Carry the creating child's navigation intent into a safe composite."""
        for result in results:
            object_type = {
                "CreateEntityCommand": "entity",
                "CreateEventCommand": "event",
            }.get(result.command_name)
            if object_type and result.data.get("select_after_apply") is not False:
                return {
                    "object_type": object_type,
                    "object_id": str(result.data["id"]),
                }
        return False

    def _is_object_marker_creation(self) -> bool:
        """Recognize only atomic creation of one object and its own marker."""
        if len(self.commands) != _OBJECT_MARKER_COMMAND_COUNT:
            return False
        create, marker = self.commands
        if not isinstance(marker, CreateMarkerCommand):
            return False
        marker_data = marker.to_dict()["marker_data"]
        if isinstance(create, CreateEntityCommand):
            return (
                marker_data["object_type"] == "entity"
                and marker_data["object_id"] == create.entity_id
            )
        if isinstance(create, CreateEventCommand):
            return (
                marker_data["object_type"] == "event"
                and marker_data["object_id"] == create.event_id
            )
        return False

    def _temporal_checkpoint_command(self) -> TemporalEntityEditCommand | None:
        """Identify the source-aware save plus optional WikiLink reconciliation."""
        if not self.commands or not isinstance(
            self.commands[0], TemporalEntityEditCommand
        ):
            return None
        edit = self.commands[0]
        if any(
            not isinstance(command, ProcessWikiLinksCommand)
            or command.source_id != edit.entity_id
            for command in self.commands[1:]
        ):
            return None
        return edit

    def _temporal_checkpoint_data(
        self, db_service: DatabaseService
    ) -> dict[str, object]:
        """Resolve the final comparison only after the entire save has succeeded."""
        edit = self._temporal_checkpoint_command()
        if edit is None:
            return {}
        return {
            "temporal_entity_checkpoint": TemporalEntitySnapshotService(
                db_service
            ).build(edit.entity_id, edit.lore_time)
        }

    def _aggregate_lore_effects(
        self, sub_results: list[CommandResult]
    ) -> list[LoreMutationEffect] | None:
        """Return effects for safe CRUD/wiki saves or matched object-marker creation."""
        allowed = {
            "CreateEventCommand",
            "UpdateEventCommand",
            "DeleteEventCommand",
            "CreateEntityCommand",
            "UpdateEntityCommand",
            "DeleteEntityCommand",
            "ProcessWikiLinksCommand",
        }
        if self._is_object_marker_creation():
            allowed.add("CreateMarkerCommand")
        if not self.commands or any(
            command.__class__.__name__ not in allowed for command in self.commands
        ):
            return None

        effects: list[LoreMutationEffect] = []
        for result in sub_results:
            parsed = parse_lore_mutation_effects(result.data.get("lore_effects"))
            if parsed:
                effects.extend(parsed)
        if len(effects) != 1:
            return None

        wiki_sources = {
            str(getattr(command, "source_id"))
            for command in self.commands
            if command.__class__.__name__ == "ProcessWikiLinksCommand"
        }
        if wiki_sources and wiki_sources != {effects[0]["object_id"]}:
            return None
        if wiki_sources:
            effects[0]["relations_changed"] = True
        return effects

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
        """Return the user-facing description for the command group."""
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
