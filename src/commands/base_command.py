"""Base Command Module.

Defines the abstract base class and result type for all commands in the application.

Classes:
    CommandResult: Standardized result object for command execution.
    BaseCommand: Abstract base class implementing command pattern with undo/redo.
"""

import logging
import re
import time
import uuid
from abc import ABC, abstractmethod
from collections.abc import Callable
from functools import wraps
from typing import Any, Literal

from src.core.command import CommandResult
from src.services.db_service import DatabaseService

logger = logging.getLogger(__name__)


class _RollbackCommandResult(Exception):
    """Internal control flow used to roll back a failed command result."""

    def __init__(self, result: CommandResult) -> None:
        super().__init__(result.message)
        self.result = result
        self.silent_transaction_rollback = True


class BaseCommand(ABC):
    """Abstract base class for all user actions.

    Encapsulates logic for generic execution and undo/redo support.
    Concrete subclasses must implement :meth:`execute`, :meth:`undo`,
    :meth:`to_dict`, and :meth:`from_dict`.

    Attributes:
        timestamp (float): Unix timestamp recorded when the command was
                           instantiated.
        _is_executed (bool): Internal flag set to ``True`` after the command
                             has been executed; exposed via the
                             :attr:`is_executed` property.

    """

    def __init_subclass__(cls, **kwargs: object) -> None:
        """Wrap concrete execute/undo methods in a database transaction.

        Commands historically caught exceptions and returned a failed
        :class:`CommandResult`, which allowed repository-level transactions to
        commit earlier writes. Wrapping every concrete command at class creation
        keeps the public API unchanged while guaranteeing one transaction for
        direct GUI, CLI, composite, and test execution paths.
        """
        super().__init_subclass__()
        cls._wrap_transactional_method("execute")
        cls._wrap_transactional_method("undo")

    @classmethod
    def _wrap_transactional_method(cls, method_name: str) -> None:
        """Install an atomic wrapper around a concrete command method."""
        method = cls.__dict__.get(method_name)
        if method is None or getattr(method, "_kraken_atomic", False):
            return

        @wraps(method)
        def atomic_method(
            self: "BaseCommand", db_service: DatabaseService
        ) -> CommandResult | None:
            transaction_factory = getattr(db_service, "transaction", None)
            if transaction_factory is None:
                return method(self, db_service)
            try:
                with transaction_factory():
                    result = method(self, db_service)
                    if isinstance(result, CommandResult) and not result.success:
                        raise _RollbackCommandResult(result)
                    return result
            except _RollbackCommandResult as rollback:
                return rollback.result

        atomic_method._kraken_atomic = True  # type: ignore[attr-defined]
        setattr(cls, method_name, atomic_method)

    def __init__(self) -> None:
        """Initializes the command."""
        self._is_executed = False
        self.command_id: str = str(uuid.uuid4())
        self.timestamp: float = time.time()

    @abstractmethod
    def execute(self, db_service: DatabaseService) -> "CommandResult":
        """Performs the action.

        Args:
            db_service (DatabaseService): The database service to operate on.

        Returns:
            CommandResult: Standardized result object indicating success or failure.

        """
        ...

    @abstractmethod
    def undo(
        self, db_service: DatabaseService
    ) -> "CommandResult | None":
        """Reverts the action.

        Args:
            db_service (DatabaseService): The database service to operate on.

        """
        ...

    @abstractmethod
    def to_dict(self) -> dict:
        """Serialize command to dictionary for persistence.

        Returns:
            dict: Dictionary containing all command data needed for reconstruction.

        """
        ...

    @classmethod
    @abstractmethod
    def from_dict(cls, data: dict) -> "BaseCommand":
        """Deserialize command from dictionary.

        Args:
            data (dict): Dictionary containing command data.

        Returns:
            BaseCommand: Reconstructed command instance.

        """
        ...

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
    def is_undoable(self) -> bool:
        """Whether this command belongs in the in-memory undo/redo stack."""
        return True

    @property
    def persist_to_history(self) -> bool:
        """Whether this command should survive an application restart."""
        return self.is_undoable

    @property
    def has_history(self) -> bool:
        """Deprecated compatibility alias for :attr:`is_undoable`."""
        return self.is_undoable

    def restore_base_state(self, data: dict) -> None:
        """Restore base fields shared by every serialized command."""
        self.command_id = str(data.get("command_id") or self.command_id)
        self.timestamp = float(data.get("timestamp", self.timestamp))
        self._is_executed = bool(data.get("is_executed", self._is_executed))

    def base_state_dict(self) -> dict:
        """Return JSON-safe fields shared by every serialized command."""
        return {
            "command_id": self.command_id,
            "timestamp": self.timestamp,
            "is_executed": self._is_executed,
        }

    @staticmethod
    def _assign_tags(
        db_service: DatabaseService,
        object_id: str,
        tags: list[str],
        object_type: Literal["entity", "event"],
    ) -> None:
        """Assigns a list of tags to an entity or event.

        Note:
            This method blindly assigns all supplied tags without checking for
            duplicates. Use :meth:`_sync_tags` when the existing tag state is
            unknown to avoid stale or duplicate entries.

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
        errors: list[str] = []
        for tag_name in tags:
            try:
                assign_fn(object_id, tag_name)
            except Exception as e:
                logger.warning("Failed to assign tag '%s': %s", tag_name, e)
                errors.append(f"{tag_name}: {e}")
        if errors:
            raise RuntimeError("Failed to assign tags: " + "; ".join(errors))

    @staticmethod
    def _sync_tags(
        db_service: DatabaseService,
        object_id: str,
        new_tags: set[str],
        object_type: Literal["entity", "event"],
    ) -> None:
        """Synchronizes normalized tag rows for an entity or event.

        Computes the diff between the currently stored tags and the desired
        set, then removes stale tags and adds new ones.

        Args:
            db_service: The database service to use.
            object_id: The ID of the entity or event.
            new_tags: The desired set of tag names after the update.
            object_type: Either ``"entity"`` or ``"event"``.

        """
        get_fn: Callable[[str], list[dict[str, Any]]]
        remove_fn: Callable[[str, str], None]
        assign_fn: Callable[[str, str], None]
        if object_type == "entity":
            get_fn = db_service.get_tags_for_entity
            remove_fn = db_service.remove_tag_from_entity
            assign_fn = db_service.assign_tag_to_entity
        else:
            get_fn = db_service.get_tags_for_event
            remove_fn = db_service.remove_tag_from_event
            assign_fn = db_service.assign_tag_to_event

        current_tags: set[str] = {t["name"] for t in get_fn(object_id)}

        errors: list[str] = []
        for tag_name in current_tags - new_tags:
            try:
                remove_fn(object_id, tag_name)
            except Exception as e:
                logger.warning("Failed to remove tag '%s': %s", tag_name, e)
                errors.append(f"remove {tag_name}: {e}")

        for tag_name in new_tags - current_tags:
            try:
                assign_fn(object_id, tag_name)
            except Exception as e:
                logger.warning("Failed to assign tag '%s': %s", tag_name, e)
                errors.append(f"assign {tag_name}: {e}")
        if errors:
            raise RuntimeError("Failed to synchronize tags: " + "; ".join(errors))
