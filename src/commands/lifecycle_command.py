"""Atomic Event creation and historical association."""

from typing import TYPE_CHECKING
from uuid import uuid4

from src.commands.base_command import BaseCommand
from src.commands.composite_command import CompositeCommand
from src.commands.event_commands import CreateEventCommand
from src.commands.relation_commands import AddRelationCommand
from src.core.command import CommandResult
from src.core.lifecycle import allowed_lifecycle_key
from src.services.authored_relation_service import AuthoredRelationService
from src.services.temporal_edit_validation import validate_temporal_edit

if TYPE_CHECKING:
    from src.services.db_service import DatabaseService


class CreateLifecycleEventCommand(CompositeCommand):
    """Expose the Event timing intent while enforcing strict transactional undo."""

    def execute(self, db_service: "DatabaseService") -> CommandResult:
        """Validate the Entity and publish a relation-aware Event mutation."""
        event, relation = self.commands
        assert isinstance(event, CreateEventCommand)
        assert isinstance(relation, AddRelationCommand)
        entity = db_service.get_entity(relation.target_id)
        if entity is None:
            return CommandResult(False, "The Entity no longer exists.")
        if (
            relation.source_id != event.event.id
            or relation.bidirectional
            or not allowed_lifecycle_key(entity.type, relation.rel_type)
        ):
            return CommandResult(
                False, "The Event association is no longer applicable."
            )
        if db_service.get_event(event.event.id) is not None:
            return CommandResult(False, "The Event identity is already in use.")
        result = super().execute(db_service)
        if result.success:
            result.command_name = type(self).__name__
            result.data["refresh_editor_relations"] = True
            result.data["lore_effects"] = [
                {
                    "object_type": "event",
                    "operation": "upsert",
                    "object_id": event.event.id,
                    "snapshot": event.event.to_dict(),
                    "relations_changed": True,
                }
            ]
        return result

    def undo(self, db_service: "DatabaseService") -> CommandResult | None:
        """Roll back the whole operation if a child cannot be undone."""
        if not self.is_executed:
            return None
        event = self.commands[0]
        assert isinstance(event, CreateEventCommand)
        states = [command.base_state_dict() for command in self.commands]
        try:
            for command in reversed(self.commands):
                command.undo(db_service)
        except Exception:
            for command, state in zip(self.commands, states, strict=True):
                command.restore_base_state(state)
            raise
        self._is_executed = False
        return CommandResult(
            True,
            "Historical Event creation undone.",
            data={
                "refresh_editor_relations": True,
                "lore_effects": [
                    {
                        "object_type": "event",
                        "operation": "delete",
                        "object_id": event.event.id,
                        "relations_changed": True,
                    }
                ],
            },
        )


class ChangeLifecycleAssociationCommand(BaseCommand):
    """Link, replace or unlink an Event without editing either endpoint."""

    def __init__(self, intent: dict) -> None:
        """Capture a detached association intent and allocate its history ID."""
        super().__init__()
        self.intent = intent
        self.relation_id = intent.get("relation_id") or str(uuid4())
        self.previous: dict | None = None

    def execute(self, db_service: "DatabaseService") -> CommandResult:
        """Validate the selected relation snapshot before applying the change."""
        entity_id = self.intent["entity_id"]
        event_id = self.intent.get("event_id")
        key = self.intent["key"]
        expected = self.intent.get("expected")
        current = db_service.get_relation(self.relation_id)
        if expected != current:
            return CommandResult(
                False, "The association changed. Refresh and try again."
            )
        entity = db_service.get_entity(entity_id)
        if entity is None:
            return CommandResult(False, "The Entity no longer exists.")
        if current is None and not allowed_lifecycle_key(entity.type, key):
            return CommandResult(
                False, "That lifecycle meaning is unavailable for this Entity."
            )
        if current is not None and (
            entity_id not in (current["source_id"], current["target_id"])
            or key != current["rel_type"]
        ):
            return CommandResult(
                False, "The association does not belong to this Entity."
            )
        if event_id is not None:
            if db_service.get_event(event_id) is None:
                return CommandResult(False, "The Event no longer exists.")
            if self._already_linked(db_service, entity_id, event_id, key):
                return CommandResult(False, "That Event already has this association.")
        service = AuthoredRelationService.from_connection(
            db_service.require_connection()
        )
        self._apply(db_service, service, current, event_id, entity_id, key)
        self.previous = current
        self._is_executed = True
        return self._result(db_service, "Historical association updated.")

    def _already_linked(
        self, db_service: "DatabaseService", entity_id: str, event_id: str, key: str
    ) -> bool:
        normalized = key.strip().casefold()
        for row in (
            *db_service.get_relations(entity_id),
            *db_service.get_incoming_relations(entity_id),
        ):
            if row["rel_type"].strip().casefold() != normalized:
                continue
            endpoints = {row["source_id"], row["target_id"]}
            if endpoints == {entity_id, event_id}:
                return True
            attributes = row.get("attributes") or {}
            if (
                normalized in {"birth", "death"}
                and attributes.get("event_id") == event_id
            ):
                other = next(iter(endpoints - {entity_id}), None)
                if other is not None and db_service.get_event(other) is None:
                    return True
        return False

    def _apply(
        self,
        db_service: "DatabaseService",
        service: AuthoredRelationService,
        current: dict | None,
        event_id: str | None,
        entity_id: str,
        key: str,
    ) -> None:
        if event_id is None:
            service.require_authored_type(key)
            db_service.delete_relation(self.relation_id)
        elif current is None:
            service.create(
                event_id,
                entity_id,
                key,
                relation_id=self.relation_id,
                created_at=self.timestamp,
            )
        else:
            validate_temporal_edit(db_service, current["attributes"], event_id)
            entity_is_source = current["source_id"] == entity_id
            service.update(
                self.relation_id,
                event_id if entity_is_source else entity_id,
                key,
                current["attributes"],
                source_id=entity_id if entity_is_source else event_id,
            )

    def undo(self, db_service: "DatabaseService") -> CommandResult | None:
        """Restore the original association and its identity exactly."""
        if not self.is_executed:
            return None
        service = AuthoredRelationService.from_connection(
            db_service.require_connection()
        )
        if self.previous is None:
            db_service.delete_relation(self.relation_id)
        elif self.intent.get("event_id") is None:
            row = self.previous
            service.create(
                row["source_id"],
                row["target_id"],
                row["rel_type"],
                row["attributes"],
                relation_id=row["id"],
                created_at=row["created_at"],
            )
        else:
            service.restore_snapshot(self.relation_id, self.previous)
        self._is_executed = False
        return self._result(db_service, "Historical association restored.")

    def _result(self, db_service: "DatabaseService", message: str) -> CommandResult:
        identities = {self.intent.get("event_id")}
        if self.previous is not None:
            identities.update((self.previous["source_id"], self.previous["target_id"]))
        identities.discard(self.intent["entity_id"])
        effects = []
        for identity in sorted(value for value in identities if value):
            event = db_service.get_event(identity)
            if event is not None:
                effects.append(
                    {
                        "object_type": "event",
                        "operation": "upsert",
                        "object_id": identity,
                        "snapshot": event.to_dict(),
                        "relations_changed": True,
                    }
                )
        return CommandResult(
            True,
            message,
            command_name=type(self).__name__,
            data={"refresh_editor_relations": True, "lore_effects": effects},
        )

    def get_description(self) -> str:
        """Describe the history item."""
        return "Change historical association"

    def to_dict(self) -> dict:
        """Persist the exact previous association for undo across restarts."""
        return {
            "intent": self.intent,
            "relation_id": self.relation_id,
            "previous": self.previous,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ChangeLifecycleAssociationCommand":
        """Restore detached command history."""
        command = cls(data["intent"])
        command.relation_id = data["relation_id"]
        command.previous = data["previous"]
        return command
