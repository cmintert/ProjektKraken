"""Commit a reviewed preset as one world-local history entry."""

from copy import deepcopy
from typing import Any

from src.commands.base_command import BaseCommand, CommandResult
from src.core.relation_presets import apply_preset
from src.core.relation_vocabulary import VOCABULARY_KEY
from src.services.db_service import DatabaseService
from src.services.relation_dictionary import usage
from src.services.repositories.settings_repository import SettingsRepository


class ImportRelationPresetCommand(BaseCommand):
    """Persist only the chosen definitions after checking the review evidence."""

    def __init__(
        self,
        database: str,
        expected: str | None,
        definitions: list[dict[str, Any]],
        choices: dict[str, str],
        evidence: dict[str, dict[str, Any]],
    ) -> None:
        """Capture the exact review and its destination."""
        super().__init__()
        self.database = database
        self.expected = expected
        self.definitions = deepcopy(definitions)
        self.choices = dict(choices)
        self.evidence = deepcopy(evidence)
        self.applied: str | None = None

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Commit once, or replay the saved result for redo."""
        if db_service.read_only or (
            self.database and self.database != db_service.db_path
        ):
            return CommandResult(
                False, "The destination world is unavailable for editing."
            )
        connection = db_service.require_connection()
        repository = SettingsRepository(connection)
        if repository.raw(VOCABULARY_KEY) != self.expected:
            return CommandResult(
                False, "The dictionary changed. Review the preset again."
            )
        if self.applied is None:
            selected = [
                key
                for key, choice in self.choices.items()
                if choice in {"import", "replace"}
            ]
            if not selected:
                return CommandResult(False, "Select at least one definition to import.")
            if any(
                usage(connection, key) != self.evidence.get(key) for key in selected
            ):
                return CommandResult(
                    False, "Relation usage changed. Review the preset again."
                )
            try:
                updated = apply_preset(
                    self.expected,
                    self.definitions,
                    self.choices,
                    {key: row["count"] for key, row in self.evidence.items()},
                )
            except (KeyError, ValueError) as exc:
                return CommandResult(False, str(exc))
        else:
            updated = self.applied
        repository.restore(VOCABULARY_KEY, updated)
        self.applied = updated
        self.database = ""
        self._is_executed = True
        return CommandResult(
            True, "Relation preset imported.", command_name=type(self).__name__
        )

    def undo(self, db_service: DatabaseService) -> None:
        """Restore the exact previous world document."""
        repository = SettingsRepository(db_service.require_connection())
        if self.applied is None or repository.raw(VOCABULARY_KEY) != self.applied:
            raise ValueError("The dictionary changed since this preset was imported.")
        repository.restore(VOCABULARY_KEY, self.expected)
        self._is_executed = False

    def to_dict(self) -> dict[str, Any]:
        """Serialize review and history state."""
        return {
            "database": self.database,
            "expected": self.expected,
            "definitions": self.definitions,
            "choices": self.choices,
            "evidence": self.evidence,
            "applied": self.applied,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ImportRelationPresetCommand":
        """Restore a queued request or persisted history entry."""
        command = cls(
            data["database"],
            data["expected"],
            data["definitions"],
            data["choices"],
            data["evidence"],
        )
        command.applied = data.get("applied")
        return command

    def get_description(self) -> str:
        """Name the batch in world history."""
        return "Import relation preset"
