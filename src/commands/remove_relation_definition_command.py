"""Undoable removal of a world's relation wording."""

from copy import deepcopy
from typing import Any

from src.commands.base_command import BaseCommand, CommandResult
from src.core.relation_dictionary import remove_definition
from src.core.relation_vocabulary import VOCABULARY_KEY
from src.services.db_service import DatabaseService
from src.services.relation_dictionary import usage
from src.services.repositories.settings_repository import SettingsRepository


class RemoveRelationDefinitionCommand(BaseCommand):
    """Remove only the reviewed dictionary entry."""

    def __init__(
        self, database: str, expected: str, key: str, evidence: dict[str, Any]
    ) -> None:
        """Capture the original world and reviewed wording impact."""
        super().__init__()
        self.database = database
        self.expected = expected
        self.key = key
        self.evidence = deepcopy(evidence)
        self.applied: str | None = None

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Verify the reviewed dictionary and usage before removing the entry."""
        if db_service.read_only or (
            self.database and self.database != db_service.db_path
        ):
            return CommandResult(
                False, "The originating world is unavailable for editing."
            )
        connection = db_service.require_connection()
        repository = SettingsRepository(connection)
        if repository.raw(VOCABULARY_KEY) != self.expected or (
            self.applied is None and usage(connection, self.key) != self.evidence
        ):
            return CommandResult(
                False, "The dictionary or usage changed. Review removal again."
            )
        try:
            updated = remove_definition(self.expected, self.key)
        except ValueError as exc:
            return CommandResult(False, str(exc))
        repository.restore(VOCABULARY_KEY, updated)
        self.applied = updated
        self.database = ""
        self._is_executed = True
        return CommandResult(True, "Relation definition removed.")

    def undo(self, db_service: DatabaseService) -> None:
        """Restore the exact prior dictionary document."""
        repository = SettingsRepository(db_service.require_connection())
        if self.applied is None or repository.raw(VOCABULARY_KEY) != self.applied:
            raise ValueError(
                "The dictionary changed since this definition was removed."
            )
        repository.restore(VOCABULARY_KEY, self.expected)
        self._is_executed = False

    def to_dict(self) -> dict[str, Any]:
        """Serialize the review and undo data."""
        return {
            "database": self.database,
            "expected": self.expected,
            "key": self.key,
            "evidence": self.evidence,
            "applied": self.applied,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RemoveRelationDefinitionCommand":
        """Load a queued command or portable history entry."""
        command = cls(data["database"], data["expected"], data["key"], data["evidence"])
        command.applied = data.get("applied")
        return command

    def get_description(self) -> str:
        """Name the history entry."""
        return f"Remove relation definition: {self.key}"
