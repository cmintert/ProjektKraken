"""Atomic, persistent undo/redo for a reviewed lore import."""

from __future__ import annotations

import copy
from typing import Any

from src.commands.base_command import BaseCommand, CommandResult
from src.services.db_service import DatabaseService
from src.services.repositories.transfer_repository import (
    apply_changes,
    revision,
    snapshot,
)
from src.services.transfer_exchange import fingerprint


class ApplyTransferCommand(BaseCommand):
    """Apply the exact reviewed changes, refusing stale world or source input."""

    def __init__(self, preview: dict[str, Any]) -> None:
        """Capture a serializable review, never a live database or GUI object."""
        super().__init__()
        self.preview = copy.deepcopy(preview)
        self.applied_once = False

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Validate the review and apply all rows in the BaseCommand transaction."""
        try:
            connection = db_service.get_connection()
            if connection is None or db_service.db_path != self.preview["db_path"]:
                raise ValueError("The active world changed. Review the import again.")
            if not self.applied_once:
                if revision(snapshot(connection)) != self.preview["revision"]:
                    raise ValueError("World data changed. Review the import again.")
                for path, digest in self.preview.get("source_hashes", {}).items():
                    if fingerprint(path) != digest:
                        raise ValueError(
                            f"Source changed: {path}. Review the import again."
                        )
            if self.preview.get("errors"):
                raise ValueError("Resolve all import errors before applying.")
            apply_changes(connection, self.preview["delta"])
            self.applied_once = True
            self._is_executed = True
            return CommandResult(
                True,
                "Import complete. Undo is available.",
                data={"transfer_id": self.command_id},
                command_name="ApplyTransferCommand",
            )
        except Exception as exc:
            return CommandResult(
                False,
                str(exc),
                data={"transfer_id": self.command_id},
                command_name="ApplyTransferCommand",
            )

    def undo(self, db_service: DatabaseService) -> CommandResult:
        """Restore only changed rows, including exact normalized tag state."""
        try:
            connection = db_service.get_connection()
            if connection is None:
                raise ValueError("No world is open.")
            apply_changes(connection, self.preview["delta"], reverse=True)
            self._is_executed = False
            return CommandResult(
                True, "Import undone.", command_name="ApplyTransferCommand"
            )
        except Exception as exc:
            return CommandResult(False, str(exc), command_name="ApplyTransferCommand")

    def to_dict(self) -> dict[str, Any]:
        """Persist reviewed deltas so undo survives restart."""
        return {
            "preview": self.preview,
            "applied_once": self.applied_once,
            "is_executed": self._is_executed,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ApplyTransferCommand:
        """Reconstruct an import command for worker dispatch or history."""
        command = cls(data["preview"])
        command.applied_once = data.get("applied_once", False)
        command._is_executed = data.get("is_executed", False)
        return command

    def get_description(self) -> str:
        """Give the undo action a clear user-facing name."""
        return "Import lore"
