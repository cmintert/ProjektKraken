"""
Attachment Repository Module.

Provides database persistence layer for image attachments
using the repository pattern.
"""

import logging
from typing import Any, List, Optional

from src.core.image_attachment import ImageAttachment
from src.services.repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class AttachmentRepository(BaseRepository):
    """
    Repository for managing ImageAttachment persistence in SQLite.
    """

    def insert(self, attachment: ImageAttachment) -> None:
        """
        Inserts a new image attachment record.
        """
        sql = """
            INSERT INTO image_attachments (
                id, owner_type, owner_id, image_rel_path, thumb_rel_path,
                caption, order_index, created_at, resolution, source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        resolution_str = (
            f"{attachment.resolution[0]}x{attachment.resolution[1]}"
            if attachment.resolution
            else None
        )

        with self.transaction() as conn:
            conn.execute(
                sql,
                (
                    attachment.id,
                    attachment.owner_type,
                    attachment.owner_id,
                    attachment.image_rel_path,
                    attachment.thumb_rel_path,
                    attachment.caption,
                    attachment.order_index,
                    attachment.created_at,
                    resolution_str,
                    attachment.source,
                ),
            )

    def get(self, attachment_id: str) -> Optional[ImageAttachment]:
        """
        Retrieves a single attachment by ID.
        """
        sql = "SELECT * FROM image_attachments WHERE id = ?"
        if not self._connection:
            # Should be handled by DatabaseService connecting it, but safety check
            return None

        cursor = self._connection.execute(sql, (attachment_id,))
        row = cursor.fetchone()
        if row:
            return self._row_to_domain(row)
        return None

    def list_by_owner(self, owner_type: str, owner_id: str) -> List[ImageAttachment]:
        """
        Retrieves all attachments for a specific owner, ordered by index.
        """
        sql = """
            SELECT * FROM image_attachments
            WHERE owner_type = ? AND owner_id = ?
            ORDER BY order_index ASC
        """
        if not self._connection:
            return []

        cursor = self._connection.execute(sql, (owner_type, owner_id))
        return [self._row_to_domain(row) for row in cursor.fetchall()]

    def delete(self, attachment_id: str) -> None:
        """
        Deletes an attachment record by ID.
        """
        sql = "DELETE FROM image_attachments WHERE id = ?"
        with self.transaction() as conn:
            conn.execute(sql, (attachment_id,))

    def update_caption(self, attachment_id: str, caption: Optional[str]) -> None:
        """
        Updates the caption of an attachment.
        """
        sql = "UPDATE image_attachments SET caption = ? WHERE id = ?"
        with self.transaction() as conn:
            conn.execute(sql, (caption, attachment_id))

    def update_order(
        self, owner_type: str, owner_id: str, ordered_ids: List[str]
    ) -> None:
        """
        Updates the order_index for a list of attachment IDs belonging to an owner.
        """
        sql = """
            UPDATE image_attachments
            SET order_index = ?
            WHERE id = ? AND owner_type = ? AND owner_id = ?
        """
        with self.transaction() as conn:
            for index, att_id in enumerate(ordered_ids):
                conn.execute(sql, (index, att_id, owner_type, owner_id))

    def _row_to_domain(self, row: Any) -> ImageAttachment:
        """
        Converts a DB row to an ImageAttachment domain object.
        """
        resolution = None
        if row["resolution"]:
            try:
                parts = row["resolution"].split("x")
                if len(parts) == 2:
                    resolution = (int(parts[0]), int(parts[1]))
            except ValueError:
                pass

        return ImageAttachment(
            id=row["id"],
            owner_type=row["owner_type"],
            owner_id=row["owner_id"],
            image_rel_path=row["image_rel_path"],
            thumb_rel_path=row["thumb_rel_path"],
            caption=row["caption"],
            order_index=row["order_index"],
            created_at=row["created_at"],
            resolution=resolution,
            source=row["source"],
        )
