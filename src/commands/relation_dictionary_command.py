"""Persist one reviewed relation definition without changing relation rows."""

from copy import deepcopy
from typing import Any

from src.commands.base_command import BaseCommand, CommandResult
from src.core.relation_dictionary import edit_document
from src.core.relation_vocabulary import VOCABULARY_KEY, load_document
from src.services.db_service import DatabaseService
from src.services.relation_dictionary import usage
from src.services.repositories.settings_repository import SettingsRepository


class EditRelationDefinitionCommand(BaseCommand):
    """Save and undo an exact versioned metadata change."""

    def __init__(
        self,
        database: str,
        expected: str | None,
        definition: dict[str, Any],
        original_key: str | None,
        reviewed_usage: dict[str, Any],
    ) -> None:
        """Capture detached review evidence for worker-side validation."""
        super().__init__()
        self.database = database
        self.expected = expected
        self.definition = deepcopy(definition)
        self.original_key = original_key
        self.reviewed_usage = deepcopy(reviewed_usage)
        self.applied: str | None = None

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Reject stale reviews before saving the reviewed definition."""
        if (
            self.database and self.database != db_service.db_path
        ) or db_service.read_only:
            return CommandResult(
                False, "The originating world is unavailable for editing."
            )
        connection = db_service.require_connection()
        repository = SettingsRepository(connection)
        if repository.raw(VOCABULARY_KEY) != self.expected:
            return CommandResult(
                False, "The dictionary changed. Review the current definition."
            )
        try:
            if self.applied is None:
                key = self.definition.get("key")
                if not isinstance(key, str):
                    raise ValueError("Enter a relation key.")
                current_usage = usage(connection, key)
                if current_usage != self.reviewed_usage:
                    raise ValueError(
                        "Relation usage changed. Review the current impact."
                    )
                if (
                    self.original_key is not None
                    and not current_usage["count"]
                    and all(
                        entry["key"] != self.original_key
                        for entry in load_document(self.expected)["definitions"]
                    )
                ):
                    raise ValueError("The selected key is no longer in use.")
            updated = edit_document(self.expected, self.definition, self.original_key)
        except ValueError as exc:
            return CommandResult(False, str(exc))
        repository.restore(VOCABULARY_KEY, updated)
        self.applied = updated
        self.database = ""
        self._is_executed = True
        return CommandResult(
            True, "Relation definition saved.", command_name=type(self).__name__
        )

    def undo(self, db_service: DatabaseService) -> None:
        """Restore the exact previous metadata value."""
        repository = SettingsRepository(db_service.require_connection())
        if repository.raw(VOCABULARY_KEY) != self.applied:
            raise ValueError("The dictionary changed since this edit was applied.")
        repository.restore(VOCABULARY_KEY, self.expected)
        self._is_executed = False

    def to_dict(self) -> dict[str, Any]:
        """Serialize detached review and history state."""
        return {
            "database": self.database,
            "expected": self.expected,
            "definition": self.definition,
            "original_key": self.original_key,
            "reviewed_usage": self.reviewed_usage,
            "applied": self.applied,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EditRelationDefinitionCommand":
        """Reconstruct a queued save or portable history entry."""
        command = cls(
            data["database"],
            data["expected"],
            data["definition"],
            data["original_key"],
            data["reviewed_usage"],
        )
        command.applied = data.get("applied")
        return command

    def get_description(self) -> str:
        """Name the single undoable edit."""
        return f"Edit relation definition: {self.definition['key']}"
