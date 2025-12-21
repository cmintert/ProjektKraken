from unittest.mock import MagicMock

from src.commands.image_commands import (
    RemoveImageCommand,
    UpdateImageCaptionCommand,
)
from src.core.image_attachment import ImageAttachment
from src.services.db_service import DatabaseService


def test_update_image_caption_command():
    """Test that UpdateImageCaptionCommand uses attachment_service correctly."""
    # Setup
    db_service = MagicMock(spec=DatabaseService)
    attachment_service = MagicMock()
    # Mock the attribute access to return the mock service
    # Note: In production, db_service instance must have attachment_service attribute
    db_service.attachment_service = attachment_service

    # Mock get_attachment to return a dummy attachment (for Undo capture)
    dummy_att = MagicMock(spec=ImageAttachment)
    dummy_att.caption = "Old Caption"
    attachment_service.get_attachment.return_value = dummy_att

    cmd = UpdateImageCaptionCommand("att_1", "New Caption")

    # Execute
    result = cmd.execute(db_service)

    # Verify
    assert result.success
    # Ensure it called get_attachment on service, NOT repo on db_service
    attachment_service.get_attachment.assert_called_with("att_1")
    attachment_service.update_caption.assert_called_with("att_1", "New Caption")

    # Verify Undo capture
    assert cmd._old_caption == "Old Caption"

    # Verify Undo
    cmd.undo(db_service)
    attachment_service.update_caption.assert_called_with("att_1", "Old Caption")


def test_remove_image_command():
    """Test RemoveImageCommand."""
    db_service = MagicMock(spec=DatabaseService)
    attachment_service = MagicMock()
    db_service.attachment_service = attachment_service

    attachment_service.remove_image.return_value = (True, {"some": "trash_info"})

    cmd = RemoveImageCommand("att_1")
    result = cmd.execute(db_service)

    assert result.success
    attachment_service.remove_image.assert_called_with("att_1")

    # Undo
    cmd.undo(db_service)
    attachment_service.restore_image.assert_called_with({"some": "trash_info"})
