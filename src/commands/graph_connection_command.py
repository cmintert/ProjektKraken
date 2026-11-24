"""Undoable graph connection with an optional newly created endpoint."""

from src.commands.composite_command import CompositeCommand
from src.commands.entity_commands import CreateEntityCommand
from src.commands.event_commands import CreateEventCommand
from src.commands.relation_commands import AddRelationCommand, UpdateRelationCommand
from src.core.command import CommandResult, parse_lore_mutation_effects
from src.services.db_service import DatabaseService

_WITH_NEW_ENDPOINT = 2


class GraphConnectionCommand(CompositeCommand):
    """Publish one strict unit of authoring through command and history transactions."""

    recovery: dict | None = None

    def _created_identity(self) -> tuple[str, str] | None:
        creation = self.commands[0]
        if isinstance(creation, CreateEntityCommand):
            return "entity", creation.entity_id
        if isinstance(creation, CreateEventCommand):
            return "event", creation.event_id
        return None

    def _relation(self) -> AddRelationCommand | UpdateRelationCommand:
        if len(self.commands) not in (1, _WITH_NEW_ENDPOINT):
            raise ValueError("A graph connection requires one relation command.")
        relation = self.commands[-1]
        if not isinstance(relation, (AddRelationCommand, UpdateRelationCommand)):
            raise ValueError("Invalid graph relation command.")
        if len(self.commands) == _WITH_NEW_ENDPOINT:
            identity = self._created_identity()
            if (
                identity is None
                or not isinstance(relation, AddRelationCommand)
                or identity[1] not in (relation.source_id, relation.target_id)
            ):
                raise ValueError("The new item must be an endpoint of this relation.")
        return relation

    @staticmethod
    def _rejected(result: CommandResult) -> CommandResult:
        return CommandResult(
            False, result.message, data={**result.data, "graph_error": "rejected"}
        )

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Check identity, execute children, and publish only committed changes."""
        relation = self._relation()
        identity = self._created_identity()
        effects = None
        if identity is not None:
            kind, object_id = identity
            if db_service.get_entity(object_id) or db_service.get_event(object_id):
                return self._rejected(
                    CommandResult(False, "The item ID is already in use.")
                )
            creation = self.commands[0].execute(db_service)
            if not creation.success:
                return self._rejected(creation)
            effects = parse_lore_mutation_effects(creation.data.get("lore_effects"))
            if effects is None or effects[0]["object_type"] != kind:
                raise ValueError("Missing creation effect for a new graph endpoint.")
            effects[0]["relations_changed"] = True

        linked = relation.execute(db_service)
        if not linked.success:
            return self._rejected(linked)
        self._is_executed = True
        result = CommandResult(
            True,
            "Connection saved.",
            data={
                "refresh_editor_relations": True,
                "graph_relation_ids": linked.data.get(
                    "relation_ids", [linked.data["relation_id"]]
                ),
                "select_after_apply": False,
            },
        )
        if effects is not None:
            result.data["lore_effects"] = effects
        if self.recovery is not None:
            result.data["graph_context_tags"] = self.recovery
        return result

    def undo(self, db_service: DatabaseService) -> CommandResult | None:
        """Undo the complete change or fail the enclosing transaction."""
        if not self.is_executed:
            return None
        self._relation()
        for command in reversed(self.commands):
            result = command.undo(db_service)
            if result is not None and not result.success:
                return result
        self._is_executed = False
        data: dict[str, object] = {"refresh_editor_relations": True}
        identity = self._created_identity()
        if identity is not None:
            kind, object_id = identity
            data["lore_effects"] = [
                {
                    "object_type": kind,
                    "operation": "delete",
                    "object_id": object_id,
                    "snapshot": None,
                    "relations_changed": True,
                }
            ]
        if self.recovery is not None:
            data["graph_context_tags"] = {**self.recovery, "status": "unavailable"}
        return CommandResult(True, "Connection undone.", data=data)

    def to_dict(self) -> dict:
        """Keep child IDs and recovery metadata in the same history record."""
        return {**super().to_dict(), "graph_context_tags": self.recovery}

    @classmethod
    def from_dict(cls, data: dict) -> "GraphConnectionCommand":
        """Restore child command state for persistent undo and redo."""
        command = super().from_dict(data)
        if not isinstance(command, cls):
            raise TypeError("Invalid graph command state.")
        command.recovery = data.get("graph_context_tags")
        return command
