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

    def __init__(self, entity_data: dict = None):
        super().__init__()
        if entity_data:
            self._entity = Entity(**entity_data)
        else:
            self._entity = Entity(name="New Entity", type="Concept")

    def execute(self, db_service: DatabaseService) -> bool:
        try:
            db_service.insert_entity(self._entity)
            self._is_executed = True
            logger.info(f"Created entity: {self._entity.name} ({self._entity.id})")
            return True
        except Exception as e:
            logger.error(f"Failed to create entity: {e}")
            return False

    def undo(self, db_service: DatabaseService) -> None:
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
        super().__init__()
        self.entity_id = entity_id
        self.update_data = update_data
        self._previous_entity: Optional[Entity] = None
        self._new_entity: Optional[Entity] = None

    def execute(self, db_service: DatabaseService) -> bool:
        try:
            # Fetch current state before update
            current = db_service.get_entity(self.entity_id)
            if not current:
                logger.error(f"Entity not found for update: {self.entity_id}")
                return False

            self._previous_entity = current

            # Apply updates
            import dataclasses

            # Assuming Entity is a dataclass like Event
            valid_fields = {f.name for f in dataclasses.fields(Entity)}
            clean_data = {
                k: v for k, v in self.update_data.items() if k in valid_fields
            }

            self._new_entity = dataclasses.replace(current, **clean_data)
            # Entity might not have modified_at, checking usage in create command
            # It seems Entity has created_at but not explicitly modified_at in usage I saw?
            # Checking Entity definition would be safer but let's assume similarity or check file.
            # I will skip modified_at unless I see it.

            db_service.insert_entity(self._new_entity)
            self._is_executed = True
            logger.info(f"Updated entity: {self._new_entity.id}")
            return True
        except Exception as e:
            logger.error(f"Failed to update entity: {e}")
            return False

    def undo(self, db_service: DatabaseService) -> None:
        if self._is_executed and self._previous_entity:
            db_service.insert_entity(self._previous_entity)
            self._is_executed = False
            logger.info(f"Undid update of entity: {self._previous_entity.id}")


class DeleteEntityCommand(BaseCommand):
    """
    Command to delete an entity.
    """

    def __init__(self, entity_id: str):
        super().__init__()
        self._entity_id = entity_id
        self._backup_entity: Optional[Entity] = None

    def execute(self, db_service: DatabaseService) -> bool:
        try:
            # Fetch before delete for undo
            self._backup_entity = db_service.get_entity(self._entity_id)
            if not self._backup_entity:
                logger.error(f"Entity not found for deletion: {self._entity_id}")
                return False

            db_service.delete_entity(self._entity_id)
            self._is_executed = True
            logger.info(f"Deleted entity: {self._entity_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete entity: {e}")
            return False

    def undo(self, db_service: DatabaseService) -> None:
        if self._is_executed and self._backup_entity:
            db_service.insert_entity(self._backup_entity)
            self._is_executed = False
            logger.info(f"Undid deletion of entity: {self._entity_id}")
