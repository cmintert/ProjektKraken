"""Longform Commands Module.

Provides command classes for manipulating longform document structure:
- MoveLongformEntryCommand: Move an entry to a new position
- PromoteLongformEntryCommand: Reduce depth and change parent
- DemoteLongformEntryCommand: Increase depth and reparent to sibling
- RemoveLongformEntryCommand: Remove from longform document

All commands support undo/redo operations and return CommandResult objects.
"""

import logging
from copy import deepcopy
from typing import Any, Dict

from src.commands.base_command import BaseCommand, CommandResult
from src.services import longform_builder
from src.services.db_service import DatabaseService

logger = logging.getLogger(__name__)


class _LongformMetadataCommand(BaseCommand):
    """Share exact, worker-captured metadata restoration across outline edits."""

    table: str
    row_id: str
    doc_id: str
    old_meta: dict[str, Any]

    def __init__(self) -> None:
        """Initialize snapshot state without retaining a database service."""
        super().__init__()
        self._metadata_before: longform_builder.LongformMetadataSnapshot | None = None

    def _snapshot_before_execute(
        self, db_service: DatabaseService
    ) -> longform_builder.LongformMetadataSnapshot:
        """Capture once on the worker; redo retains the original undo target."""
        if self._metadata_before is not None:
            return self._metadata_before
        return longform_builder.capture_longform_metadata(
            db_service.require_connection(), self.table, self.row_id, self.doc_id
        )

    def _snapshot_payload(self) -> dict[str, Any]:
        """Include captured snapshots while leaving unexecuted requests unchanged."""
        if self._metadata_before is None:
            return {}
        return {"metadata_before": deepcopy(self._metadata_before)}

    def _load_metadata_snapshot(self, data: dict[str, Any]) -> None:
        """Load a validated snapshot; old history retains its supplied metadata."""
        if "metadata_before" not in data:
            return
        snapshot = data["metadata_before"]
        if not isinstance(snapshot, dict):
            raise ValueError("Invalid longform metadata snapshot")
        metadata = snapshot.get("metadata")
        present = snapshot.get("container_present")
        if (
            "metadata" not in snapshot
            or (metadata is not None and not isinstance(metadata, dict))
            or not isinstance(present, bool)
            or (metadata is not None and not present)
        ):
            raise ValueError("Invalid longform metadata snapshot")
        self._metadata_before = {
            "metadata": deepcopy(metadata),
            "container_present": present,
        }

    def undo(self, db_service: DatabaseService) -> None:
        """Restore the entire saved metadata, preserving absence and extra fields.

        Args:
            db_service: Worker-owned service inside the command transaction.
        """
        if not self._is_executed:
            return
        snapshot = self._metadata_before
        if snapshot is None:
            # Legacy history cannot reconstruct fields it never recorded.
            snapshot = {
                "metadata": deepcopy(self.old_meta),
                "container_present": True,
            }
        longform_builder.restore_longform_metadata(
            db_service.require_connection(),
            self.table,
            self.row_id,
            snapshot,
            self.doc_id,
        )
        self._is_executed = False


class MoveLongformEntryCommand(_LongformMetadataCommand):
    """Command to move a longform entry to a new position.

    Stores old and new metadata for undo/redo support.
    """

    def __init__(
        self,
        table: str,
        row_id: str,
        old_meta: Dict[str, Any],
        new_meta: Dict[str, Any],
        doc_id: str = longform_builder.DOC_ID_DEFAULT,
    ) -> None:
        """Initialize the MoveLongformEntryCommand.

        Args:
            table: Table name ("events" or "entities").
            row_id: ID of the row to move.
            old_meta: Previous longform metadata.
            new_meta: New longform metadata.
            doc_id: Document ID.

        """
        super().__init__()
        self.table = table
        self.row_id = row_id
        self.old_meta = old_meta.copy()
        self.new_meta = new_meta.copy()
        self.doc_id = doc_id

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Execute the move by applying new metadata.

        Args:
            db_service: The database service to operate on.

        Returns:
            CommandResult: Result object indicating success or failure.

        """
        try:
            metadata_before = self._snapshot_before_execute(db_service)
            logger.info(f"Executing MoveLongformEntry: {self.table}.{self.row_id}")
            longform_builder.insert_or_update_longform_meta(
                db_service.require_connection(),
                self.table,
                self.row_id,
                position=self.new_meta.get("position"),
                parent_id=self.new_meta.get("parent_id"),
                depth=self.new_meta.get("depth"),
                title_override=self.new_meta.get("title_override"),
                doc_id=self.doc_id,
            )
            self._metadata_before = metadata_before
            self._is_executed = True
            return CommandResult(
                success=True,
                message=f"Moved longform entry {self.row_id}",
                command_name="MoveLongformEntryCommand",
            )
        except Exception as e:
            logger.error(f"Failed to move longform entry: {e}")
            return CommandResult(
                success=False,
                message=f"Failed to move longform entry: {e}",
                command_name="MoveLongformEntryCommand",
            )

    def to_dict(self) -> dict:
        """Serialize command to dictionary."""
        return {
            "table": self.table,
            "row_id": self.row_id,
            "old_meta": self.old_meta,
            "new_meta": self.new_meta,
            "doc_id": self.doc_id,
            "is_executed": self._is_executed,
            **self._snapshot_payload(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MoveLongformEntryCommand":
        """Deserialize command from dictionary."""
        cmd = cls(
            table=data["table"],
            row_id=data["row_id"],
            old_meta=data["old_meta"],
            new_meta=data["new_meta"],
            doc_id=data.get("doc_id", longform_builder.DOC_ID_DEFAULT),
        )
        cmd._load_metadata_snapshot(data)
        cmd._is_executed = data.get("is_executed", False)
        return cmd


class AddLongformEntryCommand(MoveLongformEntryCommand):
    """Append existing world content once without changing existing membership."""

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Determine the append position on the worker and retain exact undo."""
        try:
            conn = db_service.require_connection()
            snapshot = self._snapshot_before_execute(db_service)
            metadata = snapshot["metadata"]
            if metadata is not None:
                self._metadata_before = snapshot
                self._is_executed = True
                return CommandResult(
                    success=True,
                    message="Entry is already in this document",
                    command_name="AddLongformEntryCommand",
                )
            if self._metadata_before is None:
                items = longform_builder.read_all_longform_items(conn, self.doc_id)
                position = (
                    max(
                        (item["meta"].get("position", 0.0) for item in items),
                        default=0.0,
                    )
                    + longform_builder.DEFAULT_POSITION_GAP
                )
                self.new_meta = {"position": position, "parent_id": None, "depth": 0}
            result = super().execute(db_service)
            result.command_name = "AddLongformEntryCommand"
            if result.success:
                result.message = "Added content to document"
            return result
        except Exception as exc:
            return CommandResult(
                success=False, message=str(exc), command_name="AddLongformEntryCommand"
            )


class PromoteLongformEntryCommand(_LongformMetadataCommand):
    """Command to promote a longform entry (reduce depth).

    Stores old metadata for undo support.
    """

    def __init__(
        self,
        table: str,
        row_id: str,
        old_meta: Dict[str, Any],
        doc_id: str = longform_builder.DOC_ID_DEFAULT,
    ) -> None:
        """Initialize the PromoteLongformEntryCommand.

        Args:
            table: Table name ("events" or "entities").
            row_id: ID of the row to promote.
            old_meta: Previous longform metadata for undo.
            doc_id: Document ID.

        """
        super().__init__()
        self.table = table
        self.row_id = row_id
        self.old_meta = old_meta.copy()
        self.doc_id = doc_id

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Execute the promote operation.

        Args:
            db_service: The database service to operate on.

        Returns:
            CommandResult: Result object indicating success or failure.

        """
        try:
            metadata_before = self._snapshot_before_execute(db_service)
            logger.info(f"Executing PromoteLongformEntry: {self.table}.{self.row_id}")
            longform_builder.promote_item(
                db_service.require_connection(),
                self.table,
                self.row_id,
                self.doc_id,
            )
            self._metadata_before = metadata_before
            self._is_executed = True
            return CommandResult(
                success=True,
                message=f"Promoted longform entry {self.row_id}",
                command_name="PromoteLongformEntryCommand",
            )
        except Exception as e:
            logger.error(f"Failed to promote longform entry: {e}")
            return CommandResult(
                success=False,
                message=f"Failed to promote longform entry: {e}",
                command_name="PromoteLongformEntryCommand",
            )

    def to_dict(self) -> dict:
        """Serialize command to dictionary."""
        return {
            "table": self.table,
            "row_id": self.row_id,
            "old_meta": self.old_meta,
            "doc_id": self.doc_id,
            "is_executed": self._is_executed,
            **self._snapshot_payload(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PromoteLongformEntryCommand":
        """Deserialize command from dictionary."""
        cmd = cls(
            table=data["table"],
            row_id=data["row_id"],
            old_meta=data["old_meta"],
            doc_id=data.get("doc_id", longform_builder.DOC_ID_DEFAULT),
        )
        cmd._load_metadata_snapshot(data)
        cmd._is_executed = data.get("is_executed", False)
        return cmd


class DemoteLongformEntryCommand(_LongformMetadataCommand):
    """Command to demote a longform entry (increase depth).

    Stores old metadata for undo support.
    """

    def __init__(
        self,
        table: str,
        row_id: str,
        old_meta: Dict[str, Any],
        doc_id: str = longform_builder.DOC_ID_DEFAULT,
    ) -> None:
        """Initialize the DemoteLongformEntryCommand.

        Args:
            table: Table name ("events" or "entities").
            row_id: ID of the row to demote.
            old_meta: Previous longform metadata for undo.
            doc_id: Document ID.

        """
        super().__init__()
        self.table = table
        self.row_id = row_id
        self.old_meta = old_meta.copy()
        self.doc_id = doc_id

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Execute the demote operation.

        Args:
            db_service: The database service to operate on.

        Returns:
            CommandResult: Result object indicating success or failure.

        """
        try:
            metadata_before = self._snapshot_before_execute(db_service)
            logger.info(f"Executing DemoteLongformEntry: {self.table}.{self.row_id}")
            longform_builder.demote_item(
                db_service.require_connection(),
                self.table,
                self.row_id,
                self.doc_id,
            )
            self._metadata_before = metadata_before
            self._is_executed = True
            return CommandResult(
                success=True,
                message=f"Demoted longform entry {self.row_id}",
                command_name="DemoteLongformEntryCommand",
            )
        except Exception as e:
            logger.error(f"Failed to demote longform entry: {e}")
            return CommandResult(
                success=False,
                message=f"Failed to demote longform entry: {e}",
                command_name="DemoteLongformEntryCommand",
            )

    def to_dict(self) -> dict:
        """Serialize command to dictionary."""
        return {
            "table": self.table,
            "row_id": self.row_id,
            "old_meta": self.old_meta,
            "doc_id": self.doc_id,
            "is_executed": self._is_executed,
            **self._snapshot_payload(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DemoteLongformEntryCommand":
        """Deserialize command from dictionary."""
        cmd = cls(
            table=data["table"],
            row_id=data["row_id"],
            old_meta=data["old_meta"],
            doc_id=data.get("doc_id", longform_builder.DOC_ID_DEFAULT),
        )
        cmd._load_metadata_snapshot(data)
        cmd._is_executed = data.get("is_executed", False)
        return cmd


class RemoveLongformEntryCommand(_LongformMetadataCommand):
    """Command to remove an entry from the longform document.

    Stores old metadata for undo support.
    """

    def __init__(
        self,
        table: str,
        row_id: str,
        old_meta: Dict[str, Any],
        doc_id: str = longform_builder.DOC_ID_DEFAULT,
    ) -> None:
        """Initialize the RemoveLongformEntryCommand.

        Args:
            table: Table name ("events" or "entities").
            row_id: ID of the row to remove from longform.
            old_meta: Previous longform metadata for undo.
            doc_id: Document ID.

        """
        super().__init__()
        self.table = table
        self.row_id = row_id
        self.old_meta = old_meta.copy()
        self.doc_id = doc_id
        self._child_moves: list[MoveLongformEntryCommand] | None = None

    def _prepare_child_moves(self, db_service: DatabaseService) -> None:
        """Lift descendants on the worker so removing a section cannot hide them."""
        if self._child_moves is not None:
            return
        conn = db_service.require_connection()
        updates = longform_builder.membership_removal_updates(
            conn, self.table, self.row_id, self.doc_id
        )
        self._child_moves = [
            MoveLongformEntryCommand(
                item["table"], item["id"], item["meta"], new_meta, self.doc_id
            )
            for item, new_meta in updates
        ]

    def undo(self, db_service: DatabaseService) -> None:
        """Restore the section and exact descendant metadata as one undo step."""
        if not self._is_executed:
            return
        super().undo(db_service)
        for move in reversed(self._child_moves or []):
            move.undo(db_service)

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Execute the removal operation.

        Args:
            db_service: The database service to operate on.

        Returns:
            CommandResult: Result object indicating success or failure.

        """
        try:
            metadata_before = self._snapshot_before_execute(db_service)
            logger.info(f"Executing RemoveLongformEntry: {self.table}.{self.row_id}")
            self._prepare_child_moves(db_service)
            for move in self._child_moves or []:
                result = move.execute(db_service)
                if not result.success:
                    raise RuntimeError(result.message)
            longform_builder.remove_from_longform(
                db_service.require_connection(),
                self.table,
                self.row_id,
                self.doc_id,
            )
            self._metadata_before = metadata_before
            self._is_executed = True
            return CommandResult(
                success=True,
                message=f"Removed longform entry {self.row_id}",
                command_name="RemoveLongformEntryCommand",
            )
        except Exception as e:
            logger.error(f"Failed to remove longform entry: {e}")
            return CommandResult(
                success=False,
                message=f"Failed to remove longform entry: {e}",
                command_name="RemoveLongformEntryCommand",
            )

    def to_dict(self) -> dict:
        """Serialize command to dictionary."""
        return {
            "table": self.table,
            "row_id": self.row_id,
            "old_meta": self.old_meta,
            "doc_id": self.doc_id,
            "is_executed": self._is_executed,
            **self._snapshot_payload(),
            **(
                {"child_moves": [move.to_dict() for move in self._child_moves]}
                if self._child_moves is not None
                else {}
            ),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RemoveLongformEntryCommand":
        """Deserialize command from dictionary."""
        cmd = cls(
            table=data["table"],
            row_id=data["row_id"],
            old_meta=data["old_meta"],
            doc_id=data.get("doc_id", longform_builder.DOC_ID_DEFAULT),
        )
        cmd._load_metadata_snapshot(data)
        if "child_moves" in data:
            cmd._child_moves = [
                MoveLongformEntryCommand.from_dict(move) for move in data["child_moves"]
            ]
        cmd._is_executed = data.get("is_executed", False)
        return cmd
