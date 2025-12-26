"""
Attachment Service Module.

Orchestrates database and filesystem operations for image attachments,
providing a high-level API for image management with undo/redo support.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from src.core.image_attachment import ImageAttachment
from src.services.asset_store import AssetStore
from src.services.repositories.attachment_repository import AttachmentRepository

logger = logging.getLogger(__name__)


class AttachmentService:
    """
    Service for managing image attachments. Orchestrates DB and Filesystem operations.
    """

    def __init__(self, repository: AttachmentRepository, asset_store: AssetStore):
        """
        Initialize the attachment service.

        Args:
            repository: Repository for database operations.
            asset_store: Store for filesystem operations.
        """
        self._repo = repository
        self._store = asset_store

    def add_images(
        self, owner_type: str, owner_id: str, source_paths: List[str]
    ) -> List[ImageAttachment]:
        """
        Imports multiple images and adds them to the database for the given owner.

        Args:
            owner_type: The type of the owner ("event" or "entity").
            owner_id: The ID of the owner.
            source_paths: List of absolute paths to source images.

        Returns:
            List of created ImageAttachment objects.
        """
        created_attachments = []

        # Get current max order index to append new images at the end
        existing = self._repo.list_by_owner(owner_type, owner_id)
        current_index = len(existing)

        for path in source_paths:
            try:
                # 1. Import to filesystem
                img_rel, thumb_rel, size = self._store.import_image(
                    owner_type, owner_id, path
                )

                # 2. Create Domain Object
                # UUIDs on file are used as attachment IDs (from AssetStore)
                # But AssetStore returns paths, we need the ID.
                # But AssetStore returns paths, we need the ID.
                # In current AssetStore implementation, filename IS the ID + extension.
                import os

                filename = os.path.basename(img_rel)
                attachment_id = os.path.splitext(filename)[0]

                attachment = ImageAttachment(
                    id=attachment_id,
                    owner_type=owner_type,
                    owner_id=owner_id,
                    image_rel_path=img_rel,
                    thumb_rel_path=thumb_rel,
                    caption=None,
                    order_index=current_index,
                    resolution=size,
                    source=path,  # Store original source
                )

                # 3. Persist to DB
                self._repo.insert(attachment)

                created_attachments.append(attachment)
                current_index += 1

                logger.info(
                    f"Added attachment {attachment.id} to {owner_type}/{owner_id}"
                )

            except Exception as e:
                logger.error(f"Failed to add image {path}: {e}")
                # Continue with others? Or abort all?
                # For now, simplistic approach: log and continue.
                continue

        return created_attachments

    def remove_image(self, attachment_id: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Removes an image attachment. Moves files to trash and deletes DB record.

        Returns:
            (success, trash_info)
            trash_info contains paths needed for restoration.
        """
        attachment = self._repo.get(attachment_id)
        if not attachment:
            logger.warning(
                f"Attempted to delete non-existent attachment {attachment_id}"
            )
            return False, None

        try:
            # 1. Move files to trash (Filesystem side)
            img_trash, thumb_trash = self._store.delete_files(
                attachment.image_rel_path, attachment.thumb_rel_path
            )

            # 2. Delete from DB
            self._repo.delete(attachment_id)

            trash_info = {
                "attachment_data": attachment,
                "img_trash_path": img_trash,
                "thumb_trash_path": thumb_trash,
            }

            logger.info(f"Removed attachment {attachment_id}")
            return True, trash_info
        except Exception as e:
            logger.error(f"Failed to remove attachment {attachment_id}: {e}")
            raise

    def restore_image(self, trash_info: Dict[str, Any]) -> None:
        """
        Restores an image from trash and re-inserts into DB.
        """
        attachment: ImageAttachment = trash_info["attachment_data"]
        img_trash = trash_info["img_trash_path"]
        thumb_trash = trash_info["thumb_trash_path"]

        try:
            # 1. Restore files
            self._store.restore_files(
                img_trash,
                attachment.image_rel_path,
                thumb_trash,
                attachment.thumb_rel_path,
            )

            # 2. Restore DB
            self._repo.insert(attachment)

            logger.info(f"Restored attachment {attachment.id}")

        except Exception as e:
            logger.error(f"Failed to restore attachment {attachment.id}: {e}")
            raise

    def get_attachments(self, owner_type: str, owner_id: str) -> List[ImageAttachment]:
        """Retrieves all attachments for an owner."""
        return self._repo.list_by_owner(owner_type, owner_id)

    def update_order(
        self, owner_type: str, owner_id: str, ordered_ids: List[str]
    ) -> None:
        """Updates the order of attachments."""
        self._repo.update_order(owner_type, owner_id, ordered_ids)

    def update_caption(self, attachment_id: str, caption: Optional[str]) -> None:
        """Updates the caption of an attachment."""
        self._repo.update_caption(attachment_id, caption)

    def get_attachment(self, attachment_id: str) -> Optional[ImageAttachment]:
        """Retrieves a single attachment by ID."""
        return self._repo.get(attachment_id)
