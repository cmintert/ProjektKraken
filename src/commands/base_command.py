from abc import ABC, abstractmethod
from src.services.db_service import DatabaseService


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
    def execute(self, db_service: DatabaseService) -> bool:
        """
        Performs the action.

        Args:
            db_service (DatabaseService): The database service to operate on.

        Returns:
            bool: True if execution was successful, False otherwise.
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
        return self._is_executed
