"""
Image Commands Module.

Provides command pattern implementations for image attachment operations
including adding, removing, reordering, and updating captions.
"""

from typing import Any, Dict, List, Optional

from src.commands.base_command import BaseCommand, CommandResult
from src.services.db_service import DatabaseService


class AddImagesCommand(BaseCommand):
    """
    Command to add images to an owner.
    """

    def __init__(self, owner_type: str, owner_id: str, source_paths: List[str]):
        """
        Initialize the add images command.

        Args:
            owner_type: The type of owner ("event" or "entity").
            owner_id: The UUID of the owner object.
            source_paths: List of file paths to import as attachments.
        """
        super().__init__()
        self.owner_type = owner_type
        self.owner_id = owner_id
        self.source_paths = source_paths
        self._added_attachment_ids: List[str] = []
        self._trash_infos: Dict[
            str, Any
        ] = {}  # For Redo if needed? No, Undo of Add = Remove.

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """
        Execute the add images command.

        Imports images from source paths and adds them to the owner.

        Args:
            db_service: The database service instance.

        Returns:
            CommandResult: Result containing success status and attachment IDs.
        """
        if not hasattr(db_service, "attachment_service"):
            return CommandResult(False, "AttachmentService not available")

        # If re-executing (Redo), and we previously Undid (which removed images),
        # we need to decide: do we import again from source?
        # Yes, simplest is to re-import. If source missing, it might fail.
        # Ideally Redo should restore the removed images to avoid data loss if source
        # moved. But for MVP, re-import is standard "Do".
        # If executing for first time:

        try:
            # We clear this list in case of re-execution
            self._added_attachment_ids = []

            attachments = db_service.attachment_service.add_images(
                self.owner_type, self.owner_id, self.source_paths
            )

            self._added_attachment_ids = [a.id for a in attachments]
            self._is_executed = True

            result = CommandResult(True, f"Added {len(attachments)} images")
            result.data = {"owner_type": self.owner_type, "owner_id": self.owner_id}
            return result
        except Exception as e:
            return CommandResult(False, str(e))

    def undo(self, db_service: DatabaseService) -> None:
        """
        Undo the add images command.

        Removes all images that were added by this command.

        Args:
            db_service: The database service instance.
        """
        if not hasattr(db_service, "attachment_service"):
            return

        # Remove the images we added
        # We store trash info if we want to support Redo without re-importing?
        # Actually standard Redo just calls execute().
        # If Execute re-imports, we just need to delete here.
        # We use remove_image which moves to trash.
        for att_id in self._added_attachment_ids:
            # We ignore result/trash info for now unless we want to use it for Redo
            # optimization
            db_service.attachment_service.remove_image(att_id)

        self._is_executed = False


class RemoveImageCommand(BaseCommand):
    """
    Command to remove an image attachment.
    """

    def __init__(self, attachment_id: str):
        """
        Initialize the remove image command.

        Args:
            attachment_id: The UUID of the attachment to remove.
        """
        super().__init__()
        self.attachment_id = attachment_id
        self._trash_info: Optional[Dict[str, Any]] = None

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """
        Execute the remove image command.

        Removes the specified attachment, moving files to trash.

        Args:
            db_service: The database service instance.

        Returns:
            CommandResult: Result containing success status.
        """
        if not hasattr(db_service, "attachment_service"):
            return CommandResult(False, "AttachmentService not available")

        try:
            success, info = db_service.attachment_service.remove_image(
                self.attachment_id
            )
            if success:
                self._trash_info = info
                self._is_executed = True
                result = CommandResult(True, "Image removed")
                # We return attachment_id so listeners can check if they care
                result.data = {"attachment_id": self.attachment_id}
                return result
            else:
                return CommandResult(False, "Image not found")
        except Exception as e:
            return CommandResult(False, str(e))

    def undo(self, db_service: DatabaseService) -> None:
        """
        Undo the remove image command.

        Restores the removed image from trash.

        Args:
            db_service: The database service instance.
        """
        if self._trash_info and hasattr(db_service, "attachment_service"):
            db_service.attachment_service.restore_image(self._trash_info)
            self._is_executed = False


class ReorderImagesCommand(BaseCommand):
    """
    Command to reorder attachments for an owner.
    """

    def __init__(self, owner_type: str, owner_id: str, new_order_ids: List[str]):
        """
        Initialize the reorder images command.

        Args:
            owner_type: The type of owner ("event" or "entity").
            owner_id: The UUID of the owner object.
            new_order_ids: List of attachment IDs in the desired order.
        """
        super().__init__()
        self.owner_type = owner_type
        self.owner_id = owner_id
        self.new_order_ids = new_order_ids
        self._previous_order_ids: List[str] = []

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """
        Execute the reorder images command.

        Updates the display order of attachments for the owner.

        Args:
            db_service: The database service instance.

        Returns:
            CommandResult: Result containing success status.
        """
        if not hasattr(db_service, "attachment_service"):
            return CommandResult(False, "AttachmentService not available")

        # Capture current order for Undo
        current_atts = db_service.attachment_service.get_attachments(
            self.owner_type, self.owner_id
        )
        # Sort by current index
        current_atts.sort(key=lambda x: x.order_index)
        self._previous_order_ids = [a.id for a in current_atts]

        try:
            db_service.attachment_service.update_order(
                self.owner_type, self.owner_id, self.new_order_ids
            )
            self._is_executed = True
            result = CommandResult(True, "Images reordered")
            result.data = {"owner_type": self.owner_type, "owner_id": self.owner_id}
            return result
        except Exception as e:
            return CommandResult(False, str(e))

    def undo(self, db_service: DatabaseService) -> None:
        """
        Undo the reorder images command.

        Restores the previous display order of attachments.

        Args:
            db_service: The database service instance.
        """
        if hasattr(db_service, "attachment_service") and self._previous_order_ids:
            db_service.attachment_service.update_order(
                self.owner_type, self.owner_id, self._previous_order_ids
            )
            self._is_executed = False


class UpdateImageCaptionCommand(BaseCommand):
    """
    Command to update an image caption.
    """

    def __init__(self, attachment_id: str, new_caption: Optional[str]):
        """
        Initialize the update image caption command.

        Args:
            attachment_id: The UUID of the attachment.
            new_caption: The new caption text (or None to clear).
        """
        super().__init__()
        self.attachment_id = attachment_id
        self.new_caption = new_caption
        self._old_caption: Optional[str] = None

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """
        Execute the update image caption command.

        Updates the caption of the specified attachment.

        Args:
            db_service: The database service instance.

        Returns:
            CommandResult: Result containing success status.
        """
        if not hasattr(db_service, "attachment_service"):
            return CommandResult(False, "AttachmentService not available")

        try:
            # Capture old caption
            att = db_service.attachment_service.get_attachment(self.attachment_id)
            if att:
                self._old_caption = att.caption

            db_service.attachment_service.update_caption(
                self.attachment_id, self.new_caption
            )
            self._is_executed = True
            result = CommandResult(True, "Caption updated")
            result.data = {"attachment_id": self.attachment_id}
            return result
        except Exception as e:
            return CommandResult(False, str(e))

    def undo(self, db_service: DatabaseService) -> None:
        """
        Undo the update image caption command.

        Restores the previous caption value.

        Args:
            db_service: The database service instance.
        """
        if hasattr(db_service, "attachment_service"):
            db_service.attachment_service.update_caption(
                self.attachment_id, self._old_caption
            )
            self._is_executed = False
