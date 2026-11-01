"""One atomic, serializable metadata edit across mixed lore objects."""

import logging
import time
from copy import deepcopy
from typing import Any

from src.commands.base_command import BaseCommand
from src.core.batch_metadata import MetadataOperation, normalize_targets, values_equal
from src.core.command import CommandResult, LoreMutationEffect
from src.core.entities import Entity
from src.services.batch_metadata_service import load_record, prepare_metadata
from src.services.db_service import DatabaseService

logger = logging.getLogger(__name__)


class BatchMetadataCommand(BaseCommand):
    """Patch only reviewed metadata, retaining presence-aware undo state."""

    def __init__(self, targets: list, operation: dict, expected: list[dict]) -> None:
        """Own detached intent and worker-preview expectations."""
        super().__init__()
        self.targets = normalize_targets(targets)
        self.operation = MetadataOperation.from_dict(deepcopy(operation))
        self.expected = deepcopy(expected)
        self.changes: list[dict[str, Any]] = []

    @property
    def is_undoable(self) -> bool:
        """Exclude successful empty operations from history."""
        return bool(self.changes)

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Validate the entire preview before writing any changed records."""
        try:
            if self.changes:
                return self._apply(db_service, reverse=False)
            preview = prepare_metadata(db_service, self.targets, self.operation)
            if not values_equal(preview["rows"], self.expected):
                return CommandResult(
                    False, "Saved metadata changed. Preview the batch again."
                )
            changes = [
                row
                for row in preview["rows"]
                if not values_equal(row["before"], row["after"])
            ]
            result = self._write(db_service, changes, reverse=False)
            self.changes = deepcopy(changes)
            self._is_executed = bool(changes)
            return result
        except Exception as exc:
            logger.warning("Batch metadata failed: %s", type(exc).__name__)
            return CommandResult(False, f"Batch edit failed: {exc}")

    def undo(self, db_service: DatabaseService) -> CommandResult:
        """Restore affected keys only, atomically, including original absence."""
        try:
            return self._apply(db_service, reverse=True)
        except Exception as exc:
            logger.warning("Batch metadata undo failed: %s", type(exc).__name__)
            return CommandResult(False, f"Batch undo failed: {exc}")

    def _apply(self, db: DatabaseService, *, reverse: bool) -> CommandResult:
        result = self._write(db, self.changes, reverse=reverse)
        self._is_executed = not reverse
        return result

    def _write(
        self, db: DatabaseService, rows: list[dict], *, reverse: bool
    ) -> CommandResult:
        key = self.operation.affected_key
        records = []
        for row in rows:
            record = load_record(db, (row["kind"], row["id"]))
            current = {
                "present": key in record.attributes,
                "value": record.attributes.get(key),
            }
            expected = row["after"] if reverse else row["before"]
            if not values_equal(current, expected):
                raise ValueError("Affected metadata changed; nothing was applied.")
            records.append(record)
        effects: list[LoreMutationEffect] = []
        for row, record in zip(rows, records, strict=True):
            state = row["before"] if reverse else row["after"]
            if state["present"]:
                record.attributes[key] = deepcopy(state["value"])
            else:
                record.attributes.pop(key, None)
            record.modified_at = time.time()
            if isinstance(record, Entity):
                db.insert_entity(record)
            else:
                db.insert_event(record)
            if key == "_tags":
                self._sync_tags(db, record.id, set(record.tags), row["kind"])
            effects.append(
                {
                    "object_type": row["kind"],
                    "operation": "upsert",
                    "object_id": record.id,
                    "snapshot": deepcopy(record.to_dict()),
                    "relations_changed": False,
                }
            )
        return CommandResult(
            True,
            f"Batch edit changed {len(effects)} objects.",
            data={"lore_effects": effects, "changed": len(effects)}
            if effects
            else {"changed": 0},
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize intent, preview assumptions and inverse patches."""
        return deepcopy(
            {
                "targets": self.targets,
                "operation": self.operation.to_dict(),
                "expected": self.expected,
                "changes": self.changes,
            }
        )

    @classmethod
    def from_dict(cls, data: dict) -> "BatchMetadataCommand":
        """Restore command state for worker dispatch and persisted history."""
        command = cls(data["targets"], data["operation"], data["expected"])
        command.changes = deepcopy(data.get("changes", []))
        return command

    def get_description(self) -> str:
        """Name the entire selection as one history action."""
        return f"Batch edit metadata ({len(self.targets)} objects)"
