from src.commands.base_command import BaseCommand
from src.services.db_service import DatabaseService
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class AddRelationCommand(BaseCommand):
    """
    Command to add a directed relationship between two events/entities.
    """

    def __init__(
        self,
        db_service: DatabaseService,
        source_id: str,
        target_id: str,
        rel_type: str,
        attributes: Dict[str, Any] = None,
    ):
        """
        Initializes the AddRelation command.

        Args:
            db_service (DatabaseService): The database service.
            source_id (str): The ID of the source object.
            target_id (str): The ID of the target object.
            rel_type (str): The type of relationship (e.g. "caused").
            attributes (Dict[str, Any]): Optional metadata for the relationship.
        """
        super().__init__(db_service)
        self.source_id = source_id
        self.target_id = target_id
        self.rel_type = rel_type
        self.attributes = attributes or {}

        self._created_rel_id: str = None  # Store for Undo

    def execute(self) -> bool:
        """
        Executes insertion of the relation.

        Returns:
            bool: True if successful.
        """
        try:
            logger.info(
                f"Adding relation: {self.source_id} -> {self.target_id} ({self.rel_type})"
            )
            # Now insert_relation returns the ID string
            self._created_rel_id = self.db.insert_relation(
                self.source_id, self.target_id, self.rel_type, self.attributes
            )
            self._is_executed = True
            return True
        except Exception as e:
            logger.error(f"Failed to add relation: {e}")
            return False

    def undo(self) -> None:
        """
        Reverts the action by deleting the created relation.
        """
        if self._is_executed and self._created_rel_id:
            logger.info(f"Undoing AddRelation: Deleting {self._created_rel_id}")
            self.db.delete_relation(self._created_rel_id)
            self._is_executed = False


class RemoveRelationCommand(BaseCommand):
    """
    Command to remove a relationship.
    """

    def __init__(self, db_service: DatabaseService, rel_id: str):
        """
        Initializes the RemoveRelation command.

        Args:
            db_service (DatabaseService): The database service.
            rel_id (str): The ID of the relationship to remove.
        """
        super().__init__(db_service)
        self.rel_id = rel_id
        self._backup_rel = None

    def execute(self) -> bool:
        """
        Executes the command to delete the relation.

        Returns:
            bool: True if successful, False if error.
        """
        # Backup logic would go here
        try:
            self.db.delete_relation(self.rel_id)
            self._is_executed = True
            return True
        except Exception as e:
            logger.error(f"Failed to delete relation: {e}")
            return False

    def undo(self) -> None:
        """
        Reverts the deletion (Not fully implemented yet, needs backup logic).
        """
        pass
