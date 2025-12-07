from abc import ABC, abstractmethod
from src.services.db_service import DatabaseService


class BaseCommand(ABC):
    """
    Abstract base class for all user actions.
    Encapsulates logic to generic execution and undo/redo support.
    """

    def __init__(self, db_service: DatabaseService):
        """
        Initializes the command.

        Args:
            db_service (DatabaseService): The database service to operate on.
        """
        self.db = db_service
        self._is_executed = False

    @abstractmethod
    def execute(self) -> bool:
        """
        Performs the action.

        Returns:
            bool: True if execution was successful, False otherwise.
        """
        pass

    @abstractmethod
    def undo(self) -> None:
        """
        Reverts the action.
        MUST be implemented for every command to support Undo/Redo.
        """
        pass

    @property
    def is_executed(self) -> bool:
        return self._is_executed
