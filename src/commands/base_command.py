"""Base Command Module.

Defines the abstract base class and result type for all commands in the application.

Classes:
    CommandResult: Standardized result object for command execution.
    BaseCommand: Abstract base class implementing command pattern with undo/redo.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Set

from src.services.db_service import DatabaseService

logger = logging.getLogger(__name__)


@dataclass
class CommandResult:
    """Standardized result object for command execution.

    Attributes:
        success (bool): True if the command executed successfully,
                        False otherwise.
        message (str): A human-readable message describing the result.
        errors (Dict[str, str]): A dictionary of validation errors
                                 (field -> error content).
        command_name (str): The name of the command that generated
                            this result.

    """

    success: bool
    message: str = ""
    errors: Dict[str, str] = field(default_factory=dict)
    data: Dict = field(default_factory=dict)
    command_name: str = ""


class BaseCommand(ABC):
    """Abstract base class for all user actions.

    Encapsulates logic to generic execution and undo/redo support.
    """

    def __init__(self) -> None:
        """Initializes the command."""
        import time

        self._is_executed = False
        self.timestamp: float = time.time()

    @abstractmethod
    def execute(self, db_service: DatabaseService) -> "CommandResult":
        """Performs the action.

        Args:
            db_service (DatabaseService): The database service to operate on.

        Returns:
            CommandResult: Standardized result object indicating success or failure.

        """
        pass

    @abstractmethod
    def undo(self, db_service: DatabaseService) -> None:
        """Reverts the action.

        Args:
            db_service (DatabaseService): The database service to operate on.

        """
        pass

    @abstractmethod
    def to_dict(self) -> Dict:
        """Serialize command to dictionary for persistence.

        Returns:
            Dict: Dictionary containing all command data needed for reconstruction.

        """
        pass

    @classmethod
    @abstractmethod
    def from_dict(cls, data: Dict) -> "BaseCommand":
        """Deserialize command from dictionary.

        Args:
            data (Dict): Dictionary containing command data.

        Returns:
            BaseCommand: Reconstructed command instance.

        """
        pass

    def get_description(self) -> str:
        """Get a human-readable description of this command.

        Returns:
            str: A brief description of what this command does (e.g., "Create Event").

        """
        # Default implementation: use class name without "Command" suffix
        class_name = self.__class__.__name__
        if class_name.endswith("Command"):
            class_name = class_name[:-7]  # Remove "Command"
        # Convert CamelCase to Title Case with spaces
        import re

        result = re.sub(r"([A-Z])", r" \1", class_name).strip()
        return result

    @property
    def is_executed(self) -> bool:
        """Checks if the command has been executed.

        Returns:
            bool: True if the command has been executed, False otherwise.

        """
        return self._is_executed

    @property
    def has_history(self) -> bool:
        """Whether this command should be added to the undo/redo stack.

        Override and return ``False`` for background synchronisation
        commands that should execute silently.

        Returns:
            bool: True if the command should be tracked in the undo stack.

        """
        return True

    @staticmethod
    def _assign_tags(
        db_service: DatabaseService,
        object_id: str,
        tags: List[str],
        object_type: str,
    ) -> None:
        """Assigns a list of tags to an entity or event.

        Args:
            db_service: The database service to use.
            object_id: The ID of the entity or event.
            tags: List of tag names to assign.
            object_type: Either ``"entity"`` or ``"event"``.

        """
        assign_fn = (
            db_service.assign_tag_to_entity
            if object_type == "entity"
            else db_service.assign_tag_to_event
        )
        for tag_name in tags:
            try:
                assign_fn(object_id, tag_name)
            except Exception as e:
                logger.warning(f"Failed to assign tag '{tag_name}': {e}")

    @staticmethod
    def _sync_tags(
        db_service: DatabaseService,
        object_id: str,
        new_tags: Set[str],
        object_type: str,
    ) -> None:
        """Synchronises normalised tag rows for an entity or event.

        Computes the diff between the currently stored tags and the desired
        set, then removes stale tags and adds new ones.

        Args:
            db_service: The database service to use.
            object_id: The ID of the entity or event.
            new_tags: The desired set of tag names after the update.
            object_type: Either ``"entity"`` or ``"event"``.

        """
        if object_type == "entity":
            get_fn = db_service.get_tags_for_entity
            remove_fn = db_service.remove_tag_from_entity
            assign_fn = db_service.assign_tag_to_entity
        else:
            get_fn = db_service.get_tags_for_event
            remove_fn = db_service.remove_tag_from_event
            assign_fn = db_service.assign_tag_to_event

        current_tags: Set[str] = {t["name"] for t in get_fn(object_id)}

        for tag_name in current_tags - new_tags:
            try:
                remove_fn(object_id, tag_name)
            except Exception as e:
                logger.warning(f"Failed to remove tag '{tag_name}': {e}")

        for tag_name in new_tags - current_tags:
            try:
                assign_fn(object_id, tag_name)
            except Exception as e:
                logger.warning(f"Failed to assign tag '{tag_name}': {e}")
