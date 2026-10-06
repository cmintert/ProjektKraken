"""Relation Commands Module.

Provides command classes for managing relationships between events and entities:
- AddRelationCommand: Create directed relationships
- RemoveRelationCommand: Delete relationships
- UpdateRelationCommand: Modify existing relationships

All commands support undo/redo operations and return CommandResult objects.
"""

import logging
import time
import uuid
from typing import Any, Dict, Optional

from src.commands.base_command import BaseCommand, CommandResult
from src.services.db_service import DatabaseService
from src.services.repositories.relation_repository import RelationRepository

logger = logging.getLogger(__name__)


def _relation_repository(db_service: DatabaseService) -> RelationRepository:
    """Use the worker-owned connection for identity-preserving mutations."""
    repository = RelationRepository()
    repository.set_connection(db_service.require_connection())
    return repository


def _validate_endpoint(db_service: DatabaseService, endpoint: str) -> None:
    """Reject missing endpoints before a relation is inserted or reversed."""
    if (
        db_service.get_entity(endpoint) is None
        and db_service.get_event(endpoint) is None
    ):
        raise ValueError(f"Relation endpoint does not exist: {endpoint}")


class AddRelationCommand(BaseCommand):
    """Command to add a directed relationship between two events/entities."""

    def __init__(
        self,
        source_id: str,
        target_id: str,
        rel_type: str,
        attributes: Optional[Dict[str, Any]] = None,
        bidirectional: bool = False,
    ) -> None:
        """Initializes the AddRelation command.

        Args:
            source_id (str): The ID of the source object.
            target_id (str): The ID of the target object.
            rel_type (str): The type of relationship (e.g. "caused").
            attributes (Dict[str, Any]): Optional metadata for the relationship.
            bidirectional (bool): If True, also creates target->source relation.

        """
        super().__init__()
        self.source_id = source_id
        self.target_id = target_id
        self.rel_type = rel_type
        self.attributes = attributes or {}
        self.bidirectional = bidirectional

        self._created_rel_ids: list[str] = []  # Store for Undo (list of IDs)
        self._created_at = time.time()

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Executes insertion of the relation(s).

        Returns:
            CommandResult: Result indicating success or failure.

        """
        try:
            logger.info(
                f"Add rel: {self.source_id}->{self.target_id} ({self.rel_type})"
            )

            if self.rel_type == "mentions":
                raise ValueError("Mentions are managed from description wikilinks")
            _validate_endpoint(db_service, self.source_id)
            _validate_endpoint(db_service, self.target_id)
            count = 2 if self.bidirectional else 1
            if not self._created_rel_ids:
                self._created_rel_ids = [str(uuid.uuid4()) for _ in range(count)]
            if len(self._created_rel_ids) != count:
                raise ValueError("Relation history has inconsistent identities")
            repository = _relation_repository(db_service)
            endpoints = [(self.source_id, self.target_id)]
            if self.bidirectional:
                endpoints.append((self.target_id, self.source_id))
            for rel_id, (source, target) in zip(self._created_rel_ids, endpoints):
                repository.insert(
                    rel_id,
                    source,
                    target,
                    self.rel_type,
                    self.attributes,
                    self._created_at,
                )

            self._is_executed = True
            return CommandResult(
                success=True,
                message=f"Added relation {self.source_id}->{self.target_id}",
                command_name="AddRelationCommand",
                data={"relation_id": self._created_rel_ids[0]},
            )
        except Exception as e:
            logger.error(f"Failed to add relation: {e}")
            return CommandResult(
                success=False,
                message=str(e),
                command_name="AddRelationCommand",
            )

    def undo(self, db_service: DatabaseService) -> None:
        """Reverts the action by deleting the created relation(s)."""
        if self._is_executed and self._created_rel_ids:
            for rel_id in self._created_rel_ids:
                logger.info(f"Undoing AddRelation: Deleting {rel_id}")
                db_service.delete_relation(rel_id)
            self._is_executed = False

    def to_dict(self) -> Dict:
        """Serialize command to dictionary."""
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "rel_type": self.rel_type,
            "attributes": self.attributes,
            "bidirectional": self.bidirectional,
            "created_rel_ids": self._created_rel_ids,
            "created_at": self._created_at,
            "is_executed": self._is_executed,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "AddRelationCommand":
        """Deserialize command from dictionary."""
        cmd = cls(
            source_id=data["source_id"],
            target_id=data["target_id"],
            rel_type=data["rel_type"],
            attributes=data.get("attributes"),
            bidirectional=data.get("bidirectional", False),
        )
        cmd._created_rel_ids = data.get("created_rel_ids", [])
        cmd._created_at = data.get("created_at", cmd._created_at)
        cmd._is_executed = data.get("is_executed", False)
        return cmd


class RemoveRelationCommand(BaseCommand):
    """Command to remove a relationship."""

    def __init__(self, rel_id: str) -> None:
        """Initializes the RemoveRelation command.

        Args:
            rel_id (str): The ID of the relationship to remove.

        """
        super().__init__()
        self.rel_id = rel_id
        self._backup_rel: Optional[Dict[str, Any]] = None

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Executes the command to delete the relation.

        Returns:
            CommandResult: Result indicating success or failure.

        """
        relation = db_service.get_relation(self.rel_id)
        if not relation:
            return CommandResult(
                success=False,
                message=f"Relation {self.rel_id} not found",
                command_name="RemoveRelationCommand",
            )
        if relation["rel_type"] == "mentions":
            return CommandResult(
                success=False,
                message="Automatic mentions are managed from description wikilinks",
                command_name="RemoveRelationCommand",
            )

        self._backup_rel = relation
        try:
            db_service.delete_relation(self.rel_id)
            self._is_executed = True
            return CommandResult(
                success=True,
                message=f"Removed relation {self.rel_id}",
                command_name="RemoveRelationCommand",
            )
        except Exception as e:
            logger.error(f"Failed to delete relation: {e}")
            return CommandResult(
                success=False,
                message=str(e),
                command_name="RemoveRelationCommand",
            )

    def undo(self, db_service: DatabaseService) -> None:
        """Reverts the deletion (Not fully implemented yet, needs backup logic)."""

    def to_dict(self) -> Dict:
        """Serialize command to dictionary."""
        return {
            "rel_id": self.rel_id,
            "is_executed": self._is_executed,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "RemoveRelationCommand":
        """Deserialize command from dictionary."""
        cmd = cls(rel_id=data["rel_id"])
        cmd._is_executed = data.get("is_executed", False)
        return cmd


class UpdateRelationCommand(BaseCommand):
    """Command to update a relationship."""

    def __init__(
        self,
        rel_id: str,
        target_id: str,
        rel_type: str,
        attributes: Optional[Dict[str, Any]] = None,
        source_id: str | None = None,
        expected: dict[str, Any] | None = None,
    ) -> None:
        """Initializes the UpdateRelation command.

        Args:
            rel_id (str): The ID of the relationship.
            target_id (str): The new target ID.
            rel_type (str): The new relationship type.
            attributes (Dict[str, Any]): The new attributes.

        """
        super().__init__()
        self.rel_id = rel_id
        self.target_id = target_id
        self.rel_type = rel_type
        self.attributes = attributes or {}
        self.source_id = source_id
        self.expected = expected

        self._previous_state: Optional[Dict[str, Any]] = None

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Executes the update, snapshotting the old state.

        Returns:
            CommandResult: Result indicating success or failure.

        """
        # Snapshot
        current = db_service.get_relation(self.rel_id)
        if not current:
            logger.warning(f"Cannot update relation {self.rel_id}: Not found")
            return CommandResult(
                success=False,
                message=f"Relation {self.rel_id} not found",
                command_name="UpdateRelationCommand",
                data={"relation_id": self.rel_id},
            )
        if current["rel_type"] == "mentions" or self.rel_type == "mentions":
            return CommandResult(
                success=False,
                message="Automatic mentions are managed from description wikilinks",
                command_name="UpdateRelationCommand",
            )

        if self.expected is not None and self._previous_state is None:
            keys = ("source_id", "target_id", "rel_type", "attributes")
            if any(current.get(key) != self.expected.get(key) for key in keys):
                return CommandResult(
                    success=False,
                    message="The relation changed while you were editing. Reopen it.",
                    command_name="UpdateRelationCommand",
                )

        try:
            logger.info(f"Updating relation {self.rel_id}")
            if self.source_id is None:
                db_service.update_relation(
                    self.rel_id, self.target_id, self.rel_type, self.attributes
                )
            else:
                _validate_endpoint(db_service, self.source_id)
                _validate_endpoint(db_service, self.target_id)
                _relation_repository(db_service).update(
                    self.rel_id,
                    self.rel_type,
                    self.attributes,
                    target_id=self.target_id,
                    source_id=self.source_id,
                )
            self._previous_state = current
            self._is_executed = True
            return CommandResult(
                success=True,
                message=f"Updated relation {self.rel_id}",
                command_name="UpdateRelationCommand",
                data={"relation_id": self.rel_id},
            )
        except Exception as e:
            logger.error(f"Failed to update relation: {e}")
            return CommandResult(
                success=False,
                message=str(e),
                command_name="UpdateRelationCommand",
            )

    def undo(self, db_service: DatabaseService) -> None:
        """Reverts the update."""
        if self._is_executed and self._previous_state:
            logger.info(f"Undoing UpdateRelation: {self.rel_id}")
            _relation_repository(db_service).update(
                self.rel_id,
                self._previous_state["rel_type"],
                self._previous_state["attributes"],
                target_id=self._previous_state["target_id"],
                source_id=self._previous_state["source_id"],
            )
            self._is_executed = False

    def to_dict(self) -> Dict:
        """Serialize command to dictionary."""
        return {
            "rel_id": self.rel_id,
            "target_id": self.target_id,
            "rel_type": self.rel_type,
            "attributes": self.attributes,
            "source_id": self.source_id,
            "expected": self.expected,
            "previous_state": self._previous_state,
            "is_executed": self._is_executed,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "UpdateRelationCommand":
        """Deserialize command from dictionary."""
        cmd = cls(
            rel_id=data["rel_id"],
            target_id=data["target_id"],
            rel_type=data["rel_type"],
            attributes=data.get("attributes"),
            source_id=data.get("source_id"),
            expected=data.get("expected"),
        )
        cmd._previous_state = data.get("previous_state")
        cmd._is_executed = data.get("is_executed", False)
        return cmd
