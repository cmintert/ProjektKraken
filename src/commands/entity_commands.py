"""
Commands for manipulating Entity objects.
"""

import logging
from typing import Optional
from src.commands.base_command import BaseCommand
from src.services.db_service import DatabaseService
from src.core.entities import Entity

logger = logging.getLogger(__name__)


class CreateEntityCommand(BaseCommand):
    """
    Command to create a new entity.
    """

    def __init__(self, db_service: DatabaseService, entity: Entity):
        self._db_service = db_service
        self._entity = entity
        self._is_executed = False

    def execute(self) -> bool:
        try:
            self._db_service.insert_entity(self._entity)
            self._is_executed = True
            logger.info(f"Created entity: {self._entity.name} ({self._entity.id})")
            return True
        except Exception as e:
            logger.error(f"Failed to create entity: {e}")
            return False

    def undo(self) -> None:
        if self._is_executed:
            self._db_service.delete_entity(self._entity.id)
            self._is_executed = False
            logger.info(f"Undid creation of entity: {self._entity.id}")


class UpdateEntityCommand(BaseCommand):
    """
    Command to update an existing entity.
    """

    def __init__(self, db_service: DatabaseService, entity: Entity):
        self._db_service = db_service
        self._new_entity = entity
        self._previous_entity: Optional[Entity] = None
        self._is_executed = False

    def execute(self) -> bool:
        try:
            # Fetch current state before update
            current = self._db_service.get_entity(self._new_entity.id)
            if not current:
                logger.error(f"Entity not found for update: {self._new_entity.id}")
                return False

            self._previous_entity = current
            self._db_service.insert_entity(self._new_entity)
            self._is_executed = True
            logger.info(f"Updated entity: {self._new_entity.id}")
            return True
        except Exception as e:
            logger.error(f"Failed to update entity: {e}")
            return False

    def undo(self) -> None:
        if self._is_executed and self._previous_entity:
            self._db_service.insert_entity(self._previous_entity)
            self._is_executed = False
            logger.info(f"Undid update of entity: {self._new_entity.id}")


class DeleteEntityCommand(BaseCommand):
    """
    Command to delete an entity.
    """

    def __init__(self, db_service: DatabaseService, entity_id: str):
        self._db_service = db_service
        self._entity_id = entity_id
        self._backup_entity: Optional[Entity] = None
        self._is_executed = False

    def execute(self) -> bool:
        try:
            # Fetch before delete for undo
            self._backup_entity = self._db_service.get_entity(self._entity_id)
            if not self._backup_entity:
                logger.error(f"Entity not found for deletion: {self._entity_id}")
                return False

            self._db_service.delete_entity(self._entity_id)
            self._is_executed = True
            logger.info(f"Deleted entity: {self._entity_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete entity: {e}")
            return False

    def undo(self) -> None:
        if self._is_executed and self._backup_entity:
            self._db_service.insert_entity(self._backup_entity)
            self._is_executed = False
            logger.info(f"Undid deletion of entity: {self._entity_id}")
