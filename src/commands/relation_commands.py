"""Relation Commands Module.

Provides command classes for managing relationships between events and entities:
- AddRelationCommand: Create directed relationships
- RemoveRelationCommand: Delete relationships
- UpdateRelationCommand: Modify existing relationships

All commands support undo/redo operations and return CommandResult objects.
"""

import logging
from typing import Any, Dict, Optional

from src.commands.base_command import BaseCommand, CommandResult
from src.services.db_service import DatabaseService

logger = logging.getLogger(__name__)


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

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Executes insertion of the relation(s).

        Returns:
            CommandResult: Result indicating success or failure.

        """
        try:
            logger.info(
                f"Add rel: {self.source_id}->{self.target_id} ({self.rel_type})"
            )

            # Forward
            fwd_id = db_service.insert_relation(
                self.source_id, self.target_id, self.rel_type, self.attributes
            )
            self._created_rel_ids.append(fwd_id)

            if self.bidirectional:
                logger.info(
                    f"Adding reverse relation: {self.target_id} -> {self.source_id}"
                )
                rev_id = db_service.insert_relation(
                    self.target_id, self.source_id, self.rel_type, self.attributes
                )
                self._created_rel_ids.append(rev_id)

            self._is_executed = True
            return CommandResult(
                success=True,
                message=f"Added relation {self.source_id}->{self.target_id}",
                command_name="AddRelationCommand",
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
            self._created_rel_ids.clear()
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
        self._backup_rel = None

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Executes the command to delete the relation.

        Returns:
            CommandResult: Result indicating success or failure.

        """
        # Backup logic would go here
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
            )

        self._previous_state = current

        try:
            logger.info(f"Updating relation {self.rel_id}")
            db_service.update_relation(
                self.rel_id, self.target_id, self.rel_type, self.attributes
            )
            self._is_executed = True
            return CommandResult(
                success=True,
                message=f"Updated relation {self.rel_id}",
                command_name="UpdateRelationCommand",
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
            db_service.update_relation(
                self.rel_id,
                self._previous_state["target_id"],
                self._previous_state["rel_type"],
                self._previous_state["attributes"],
            )
            self._is_executed = False

    def to_dict(self) -> Dict:
        """Serialize command to dictionary."""
        return {
            "rel_id": self.rel_id,
            "target_id": self.target_id,
            "rel_type": self.rel_type,
            "attributes": self.attributes,
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
        )
        cmd._previous_state = data.get("previous_state")
        cmd._is_executed = data.get("is_executed", False)
        return cmd
