"""Transactional world settings with exact undo restoration."""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from src.commands.base_command import BaseCommand, CommandResult
from src.core.calendar import CalendarConfig
from src.core.settings_registry import BY_ID
from src.services.db_service import DatabaseService
from src.services.repositories.settings_repository import (
    META_KEYS,
    POLICY_KEY,
    SettingsRepository,
)


class ApplyWorldSettingsCommand(BaseCommand):
    """Apply a detached, validated settings patch to its originating database."""

    def __init__(
        self, changes: dict[str, Any], expected: dict[str, Any], database: str = ""
    ) -> None:
        """Initialize detached settings state and explicit dependencies."""
        super().__init__()
        self.changes = deepcopy(changes)
        self.expected = deepcopy(expected)
        self.database = database
        self.before: dict[str, str | None] = {}
        self.old_calendar: dict[str, Any] | None = None
        self.old_colors: dict[str, str | None] = {}

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Check stale inputs before making a single transactional mutation."""
        from src.services.settings_snapshot import world_snapshot

        if self.database and db_service.db_path != self.database:
            return CommandResult(False, "The active world changed.")
        for key, value in self.changes.items():
            if key not in BY_ID or BY_ID[key].scope != "world":
                return CommandResult(False, "Unknown world setting.")
            BY_ID[key].validate(value)
        current = world_snapshot(db_service)
        if any(current.get(key) != value for key, value in self.expected.items()):
            return CommandResult(
                False, "World settings changed. Review current values."
            )
        repo = SettingsRepository(db_service.require_connection())
        self.before = {key: repo.raw(key) for key in (*META_KEYS.values(), POLICY_KEY)}
        self._write_metadata(repo)
        self._write_calendar(db_service)
        self._write_colors(db_service)
        self._is_executed = True
        # Target identity protects queued forward writes, not portable undo history.
        self.database = ""
        return CommandResult(
            True,
            "World settings applied.",
            data={"settings_changed": True},
            command_name=type(self).__name__,
        )

    def _write_metadata(self, repo: SettingsRepository) -> None:
        for setting, key in META_KEYS.items():
            if setting in self.changes:
                value = self.changes[setting]
                repo.restore(
                    key,
                    value
                    if setting == "world.theme"
                    else json.dumps(value)
                    if value is not None
                    else None,
                )
        policy = repo.policy()
        for setting, key in (
            ("world.auto_relations", "auto_relations"),
            ("world.excluded_attributes", "excluded_attributes"),
        ):
            if setting in self.changes:
                policy[key] = deepcopy(self.changes[setting])
        if "world.excluded_attributes" in self.changes:
            policy["index_requires_rebuild"] = True
        repo.restore(POLICY_KEY, json.dumps(policy))

    def _write_calendar(self, db: DatabaseService) -> None:
        if "world.calendar" not in self.changes:
            return
        previous = db.get_active_calendar_config()
        self.old_calendar = previous.to_dict() if previous else None
        db.insert_calendar_config(
            CalendarConfig.from_dict(self.changes["world.calendar"])
        )
        db.set_active_calendar_config(self.changes["world.calendar"]["id"])

    def _write_colors(self, db: DatabaseService) -> None:
        if "world.tag_colors" not in self.changes:
            return
        self.old_colors = {
            name: (db.get_tag_by_name(name) or {}).get("color")
            for name in self.changes["world.tag_colors"]
        }
        for name, color in self.changes["world.tag_colors"].items():
            db.set_tag_color(name, color)

    def undo(self, db_service: DatabaseService) -> None:
        """Restore the exact prior metadata, calendar and tag colours."""
        repo = SettingsRepository(db_service.require_connection())
        for key, raw in self.before.items():
            repo.restore(key, raw)
        if self.old_calendar is not None:
            db_service.insert_calendar_config(
                CalendarConfig.from_dict(self.old_calendar)
            )
            db_service.set_active_calendar_config(self.old_calendar["id"])
        elif "world.calendar" in self.changes:
            db_service.delete_calendar_config(self.changes["world.calendar"]["id"])
        for name, color in self.old_colors.items():
            db_service.set_tag_color(name, color)
        self._is_executed = False

    def to_dict(self) -> dict[str, Any]:
        """Serialize no credentials or GUI objects."""
        return {
            "changes": self.changes,
            "expected": self.expected,
            "database": self.database,
            "before": self.before,
            "old_calendar": self.old_calendar,
            "old_colors": self.old_colors,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ApplyWorldSettingsCommand:
        """Reconstruct an intent or persisted undo state."""
        command = cls(
            data["changes"], data.get("expected", {}), data.get("database", "")
        )
        command.before = data.get("before", {})
        command.old_calendar = data.get("old_calendar")
        command.old_colors = data.get("old_colors", {})
        return command

    def get_description(self) -> str:
        """Name one coherent history action."""
        return "Apply world settings"
