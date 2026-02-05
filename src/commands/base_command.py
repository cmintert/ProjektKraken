"""Base Command Module.

Defines the abstract base class and result type for all commands in the application.

Classes:
    CommandResult: Standardized result object for command execution.
    BaseCommand: Abstract base class implementing command pattern with undo/redo.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Union

from src.services.db_service import DatabaseService


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
        self._is_executed = False

    @abstractmethod
    def execute(self, db_service: DatabaseService) -> Union[bool, CommandResult]:
        """Performs the action.

        Args:
            db_service (DatabaseService): The database service to operate on.

        Returns:
            Union[bool, CommandResult]: Result object or success boolean.

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
        result = re.sub(r'([A-Z])', r' \1', class_name).strip()
        return result

    @property
    def is_executed(self) -> bool:
        """Checks if the command has been executed.

        Returns:
            bool: True if the command has been executed, False otherwise.

        """
        return self._is_executed
