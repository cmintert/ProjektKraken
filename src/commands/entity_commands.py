"""
Commands for manipulating Entity objects.
"""

import logging
from typing import Optional

from src.commands.base_command import BaseCommand, CommandResult
from src.core.entities import Entity
from src.services.db_service import DatabaseService

logger = logging.getLogger(__name__)


class CreateEntityCommand(BaseCommand):
    """
    Command to create a new entity.
    """

    def __init__(self, entity_data: dict = None):
        """
        Initializes the CreateEntityCommand.

        Args:
            entity_data (dict, optional): Dictionary containing entity data.
                                          If None, default values are used.
        """
        super().__init__()
        if entity_data:
            self._entity = Entity(**entity_data)
        else:
            self._entity = Entity(name="New Entity", type="Concept")

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """
        Executes the command to create the entity.

        Args:
            db_service (DatabaseService): The database service to use.

        Returns:
            CommandResult: Result object indicating success or failure.
        """
        try:
            db_service.insert_entity(self._entity)
            self._is_executed = True
            logger.info(f"Created entity: {self._entity.name} ({self._entity.id})")
            return CommandResult(
                success=True,
                message=f"Entity '{self._entity.name}' created.",
                command_name="CreateEntityCommand",
                data={"id": self._entity.id},
            )
        except Exception as e:
            logger.error(f"Failed to create entity: {e}")
            return CommandResult(
                success=False,
                message=f"Failed to create entity: {e}",
                command_name="CreateEntityCommand",
            )

    def undo(self, db_service: DatabaseService) -> None:
        """
        Reverts the entity creation by deleting it from the database.

        Args:
            db_service (DatabaseService): The database service to operate on.
        """
        if self._is_executed:
            db_service.delete_entity(self._entity.id)
            self._is_executed = False
            logger.info(f"Undid creation of entity: {self._entity.id}")


class UpdateEntityCommand(BaseCommand):
    """
    Command to update an existing entity.
    Accepts a dictionary of changes.
    """

    def __init__(self, entity_id: str, update_data: dict):
        """
        Initializes the UpdateEntityCommand.

        Args:
            entity_id (str): The ID of the entity to update.
            update_data (dict): Dictionary of fields to update.
        """
        super().__init__()
        self.entity_id = entity_id
        self.update_data = update_data
        self._previous_entity: Optional[Entity] = None
        self._new_entity: Optional[Entity] = None

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """
        Executes the update.

        Args:
            db_service (DatabaseService): The database service to use.

        Returns:
            CommandResult: Result object containing success status and messages.
        """
        try:
            # Fetch current state before update
            current = db_service.get_entity(self.entity_id)
            if not current:
                logger.error(f"Entity not found for update: {self.entity_id}")
                return CommandResult(
                    success=False,
                    message=f"Entity not found: {self.entity_id}",
                    command_name="UpdateEntityCommand",
                )

            self._previous_entity = current

            # Apply updates
            import dataclasses

            valid_fields = {f.name for f in dataclasses.fields(Entity)}
            clean_data = {
                k: v for k, v in self.update_data.items() if k in valid_fields
            }

            self._new_entity = dataclasses.replace(current, **clean_data)

            db_service.insert_entity(self._new_entity)
            self._is_executed = True
            logger.info(f"Updated entity: {self._new_entity.id}")
            return CommandResult(
                success=True,
                message="Entity updated.",
                command_name="UpdateEntityCommand",
            )
        except Exception as e:
            logger.error(f"Failed to update entity: {e}")
            return CommandResult(
                success=False,
                message=f"Failed to update entity: {e}",
                command_name="UpdateEntityCommand",
            )

    def undo(self, db_service: DatabaseService) -> None:
        """
        Reverts the entity update by restoring the previous state.

        Args:
            db_service (DatabaseService): The database service to operate on.
        """
        if self._is_executed and self._previous_entity:
            db_service.insert_entity(self._previous_entity)
            self._is_executed = False
            logger.info(f"Undid update of entity: {self._previous_entity.id}")


class DeleteEntityCommand(BaseCommand):
    """
    Command to delete an entity.
    """

    def __init__(self, entity_id: str):
        """
        Initializes the DeleteEntityCommand.

        Args:
            entity_id (str): The ID of the entity to delete.
        """
        super().__init__()
        self._entity_id = entity_id
        self._backup_entity: Optional[Entity] = None

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """
        Executes the command to delete the entity.

        Args:
            db_service (DatabaseService): The database service to use.

        Returns:
            CommandResult: Result object indicating success or fail (e.g. not found).
        """
        try:
            # Fetch before delete for undo
            self._backup_entity = db_service.get_entity(self._entity_id)
            if not self._backup_entity:
                logger.error(f"Entity not found for deletion: {self._entity_id}")
                return CommandResult(
                    success=False,
                    message=f"Entity not found: {self._entity_id}",
                    command_name="DeleteEntityCommand",
                )

            db_service.delete_entity(self._entity_id)
            self._is_executed = True
            logger.info(f"Deleted entity: {self._entity_id}")
            return CommandResult(
                success=True,
                message="Entity deleted.",
                command_name="DeleteEntityCommand",
            )
        except Exception as e:
            logger.error(f"Failed to delete entity: {e}")
            return CommandResult(
                success=False,
                message=f"Failed to delete entity: {e}",
                command_name="DeleteEntityCommand",
            )

    def undo(self, db_service: DatabaseService) -> None:
        """
        Reverts the entity deletion by restoring it to the database.

        Args:
            db_service (DatabaseService): The database service to operate on.
        """
        if self._is_executed and self._backup_entity:
            db_service.insert_entity(self._backup_entity)
            self._is_executed = False
            logger.info(f"Undid deletion of entity: {self._entity_id}")
