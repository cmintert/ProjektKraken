"""
Base Command Module.

Defines the abstract base class and result type for all commands in the application.

Classes:
    CommandResult: Standardized result object for command execution.
    BaseCommand: Abstract base class implementing command pattern with undo/redo.
"""
from abc import ABC, abstractmethod
from src.services.db_service import DatabaseService


from dataclasses import dataclass, field
from typing import Dict, Union


@dataclass
class CommandResult:
    """
    Standardized result object for command execution.

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
    command_name: str = ""


class BaseCommand(ABC):
    """
    Abstract base class for all user actions.
    Encapsulates logic to generic execution and undo/redo support.
    """

    def __init__(self):
        """
        Initializes the command.
        """
        self._is_executed = False

    @abstractmethod
    def execute(self, db_service: DatabaseService) -> Union[bool, CommandResult]:
        """
        Performs the action.

        Args:
            db_service (DatabaseService): The database service to operate on.

        Returns:
            Union[bool, CommandResult]: Result object or success boolean.
        """
        pass

    @abstractmethod
    def undo(self, db_service: DatabaseService) -> None:
        """
        Reverts the action.

        Args:
            db_service (DatabaseService): The database service to operate on.
        """
        pass

    @property
    def is_executed(self) -> bool:
        """
        Checks if the command has been executed.

        Returns:
            bool: True if the command has been executed, False otherwise.
        """
        return self._is_executed
