"""
Image Attachment Module.

Defines the domain model for image attachments associated with
events and entities in the worldbuilding application.
"""

import time
from dataclasses import dataclass, field
from typing import Optional, Tuple


@dataclass
class ImageAttachment:
    """
    Domain object representing an image attached to an Event or Entity.
    """

    id: str
    owner_type: str  # "event" or "entity"
    owner_id: str
    image_rel_path: str  # Relative path to <project_root>/assets/images/...
    thumb_rel_path: Optional[str] = (
        None  # Relative path to <project_root>/assets/thumbnails/...
    )
    caption: Optional[str] = None
    order_index: int = 0
    created_at: float = field(default_factory=time.time)
    resolution: Optional[Tuple[int, int]] = None  # (width, height)
    source: Optional[str] = None  # Original filename or source URL/path

    # Optional metadata like filesize, hash, etc. could go into a generic dict
    # if needed, but for now we keep it strict as requested.

    @property
    def is_thumbnail_available(self) -> bool:
        """
        Check if a thumbnail is available for this attachment.

        Returns:
            bool: True if thumbnail path is set, False otherwise.
        """
        return bool(self.thumb_rel_path)
