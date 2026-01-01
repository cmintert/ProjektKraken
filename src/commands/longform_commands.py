"""
Longform Commands Module.

Provides command classes for manipulating longform document structure:
- MoveLongformEntryCommand: Move an entry to a new position
- PromoteLongformEntryCommand: Reduce depth and change parent
- DemoteLongformEntryCommand: Increase depth and reparent to sibling
- RemoveLongformEntryCommand: Remove from longform document

All commands support undo/redo operations and return CommandResult objects.
"""

import logging
from typing import Any, Dict

from src.commands.base_command import BaseCommand, CommandResult
from src.services import longform_builder
from src.services.db_service import DatabaseService

logger = logging.getLogger(__name__)


class MoveLongformEntryCommand(BaseCommand):
    """
    Command to move a longform entry to a new position.

    Stores old and new metadata for undo/redo support.
    """

    def __init__(
        self,
        table: str,
        row_id: str,
        old_meta: Dict[str, Any],
        new_meta: Dict[str, Any],
        doc_id: str = longform_builder.DOC_ID_DEFAULT,
    ):
        """
        Initialize the MoveLongformEntryCommand.

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
        """
        Execute the move by applying new metadata.

        Args:
            db_service: The database service to operate on.

        Returns:
            CommandResult: Result object indicating success or failure.
        """
        try:
            if not db_service._connection:
                db_service.connect()
            assert db_service._connection is not None

            logger.info(f"Executing MoveLongformEntry: {self.table}.{self.row_id}")
            longform_builder.insert_or_update_longform_meta(
                db_service._connection,
                self.table,
                self.row_id,
                position=self.new_meta.get("position"),
                parent_id=self.new_meta.get("parent_id"),
                depth=self.new_meta.get("depth"),
                title_override=self.new_meta.get("title_override"),
                doc_id=self.doc_id,
            )
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

    def undo(self, db_service: DatabaseService) -> None:
        """
        Undo the move by restoring old metadata.

        Args:
            db_service: The database service to operate on.
        """
        if not self._is_executed:
            return

        if not db_service._connection:
            db_service.connect()
        assert db_service._connection is not None

        logger.info(f"Undoing MoveLongformEntry: {self.table}.{self.row_id}")
        longform_builder.insert_or_update_longform_meta(
            db_service._connection,
            self.table,
            self.row_id,
            position=self.old_meta.get("position"),
            parent_id=self.old_meta.get("parent_id"),
            depth=self.old_meta.get("depth"),
            title_override=self.old_meta.get("title_override"),
            doc_id=self.doc_id,
        )
        self._is_executed = False


class PromoteLongformEntryCommand(BaseCommand):
    """
    Command to promote a longform entry (reduce depth).

    Stores old metadata for undo support.
    """

    def __init__(
        self,
        table: str,
        row_id: str,
        old_meta: Dict[str, Any],
        doc_id: str = longform_builder.DOC_ID_DEFAULT,
    ):
        """
        Initialize the PromoteLongformEntryCommand.

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
        """
        Execute the promote operation.

        Args:
            db_service: The database service to operate on.

        Returns:
            CommandResult: Result object indicating success or failure.
        """
        try:
            if not db_service._connection:
                db_service.connect()
            assert db_service._connection is not None

            logger.info(f"Executing PromoteLongformEntry: {self.table}.{self.row_id}")
            longform_builder.promote_item(
                db_service._connection,
                self.table,
                self.row_id,
                self.doc_id,
            )
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

    def undo(self, db_service: DatabaseService) -> None:
        """
        Undo the promote by restoring old metadata.

        Args:
            db_service: The database service to operate on.
        """
        if not self._is_executed:
            return

        if not db_service._connection:
            db_service.connect()
        assert db_service._connection is not None

        logger.info(f"Undoing PromoteLongformEntry: {self.table}.{self.row_id}")
        longform_builder.insert_or_update_longform_meta(
            db_service._connection,
            self.table,
            self.row_id,
            position=self.old_meta.get("position"),
            parent_id=self.old_meta.get("parent_id"),
            depth=self.old_meta.get("depth"),
            title_override=self.old_meta.get("title_override"),
            doc_id=self.doc_id,
        )
        self._is_executed = False


class DemoteLongformEntryCommand(BaseCommand):
    """
    Command to demote a longform entry (increase depth).

    Stores old metadata for undo support.
    """

    def __init__(
        self,
        table: str,
        row_id: str,
        old_meta: Dict[str, Any],
        doc_id: str = longform_builder.DOC_ID_DEFAULT,
    ):
        """
        Initialize the DemoteLongformEntryCommand.

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
        """
        Execute the demote operation.

        Args:
            db_service: The database service to operate on.

        Returns:
            CommandResult: Result object indicating success or failure.
        """
        try:
            if not db_service._connection:
                db_service.connect()
            assert db_service._connection is not None

            logger.info(f"Executing DemoteLongformEntry: {self.table}.{self.row_id}")
            longform_builder.demote_item(
                db_service._connection,
                self.table,
                self.row_id,
                self.doc_id,
            )
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

    def undo(self, db_service: DatabaseService) -> None:
        """
        Undo the demote by restoring old metadata.

        Args:
            db_service: The database service to operate on.
        """
        if not self._is_executed:
            return

        if not db_service._connection:
            db_service.connect()
        assert db_service._connection is not None

        logger.info(f"Undoing DemoteLongformEntry: {self.table}.{self.row_id}")
        longform_builder.insert_or_update_longform_meta(
            db_service._connection,
            self.table,
            self.row_id,
            position=self.old_meta.get("position"),
            parent_id=self.old_meta.get("parent_id"),
            depth=self.old_meta.get("depth"),
            title_override=self.old_meta.get("title_override"),
            doc_id=self.doc_id,
        )
        self._is_executed = False


class RemoveLongformEntryCommand(BaseCommand):
    """
    Command to remove an entry from the longform document.

    Stores old metadata for undo support.
    """

    def __init__(
        self,
        table: str,
        row_id: str,
        old_meta: Dict[str, Any],
        doc_id: str = longform_builder.DOC_ID_DEFAULT,
    ):
        """
        Initialize the RemoveLongformEntryCommand.

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

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """
        Execute the removal operation.

        Args:
            db_service: The database service to operate on.

        Returns:
            CommandResult: Result object indicating success or failure.
        """
        try:
            if not db_service._connection:
                db_service.connect()
            assert db_service._connection is not None

            logger.info(f"Executing RemoveLongformEntry: {self.table}.{self.row_id}")
            longform_builder.remove_from_longform(
                db_service._connection,
                self.table,
                self.row_id,
                self.doc_id,
            )
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

    def undo(self, db_service: DatabaseService) -> None:
        """
        Undo the removal by restoring old metadata.

        Args:
            db_service: The database service to operate on.
        """
        if not self._is_executed:
            return

        if not db_service._connection:
            db_service.connect()
        assert db_service._connection is not None

        logger.info(f"Undoing RemoveLongformEntry: {self.table}.{self.row_id}")
        longform_builder.insert_or_update_longform_meta(
            db_service._connection,
            self.table,
            self.row_id,
            position=self.old_meta.get("position"),
            parent_id=self.old_meta.get("parent_id"),
            depth=self.old_meta.get("depth"),
            title_override=self.old_meta.get("title_override"),
            doc_id=self.doc_id,
        )
        self._is_executed = False
