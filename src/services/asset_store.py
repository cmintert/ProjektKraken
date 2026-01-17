"""
Asset Store Module.

Manages filesystem operations for project assets including images,
thumbnails, and trash functionality for undo/redo support.
"""

import logging
import shutil
import uuid
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image

logger = logging.getLogger(__name__)


class AssetStore:
    """
    Manages filesystem operations for project assets (images, thumbnails).
    Ensures deterministic paths and safe file handling.

    In portable-only mode, assets are stored within the world directory
    at <world_dir>/assets/ rather than a separate project root.
    """

    def __init__(self, project_root: str) -> None:
        """
        Initialize the asset store.

        Args:
            project_root: Root directory of the world containing assets folder.
                         In portable mode, this is the world directory itself.
        """
        self.project_root = Path(project_root)
        self.assets_dir = self.project_root / "assets"
        self.images_dir = self.assets_dir / "images"
        self.thumbs_dir = self.assets_dir / "thumbnails"
        self.trash_dir = self.assets_dir / ".trash"

        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Creates necessary asset directories if they don't exist."""
        for path in [self.images_dir, self.thumbs_dir, self.trash_dir]:
            path.mkdir(parents=True, exist_ok=True)

    def get_owner_dir(
        self, owner_type: str, owner_id: str, is_thumbnail: bool = False
    ) -> Path:
        """
        Returns the directory path for a specific owner's images.
        Example: assets/images/event/<uuid>/
        """
        base_dir = self.thumbs_dir if is_thumbnail else self.images_dir
        # Pluralize owner_type for cleaner structure (events/entities)
        # Handle words ending in 'y' -> 'ies' (entity -> entities)
        if owner_type.endswith("y"):
            type_segment = f"{owner_type[:-1]}ies"
        else:
            type_segment = f"{owner_type}s"
        return base_dir / type_segment / owner_id

    def import_image(
        self, owner_type: str, owner_id: str, source_path: str
    ) -> Tuple[str, Optional[str], Tuple[int, int]]:
        """
        Imports an image file:
        1. Generates a unique ID (the attachment ID).
        2. Converts/optimizes the image (e.g. to WebP or keeping original if efficient).
        3. Generates a thumbnail.
        4. Saves both to the project assets folder.

        Returns:
            (image_rel_path, thumb_rel_path, (width, height))
        """
        image_id = str(uuid.uuid4())
        source = Path(source_path)

        if not source.exists():
            raise FileNotFoundError(f"Source file not found: {source_path}")

        # Destination paths
        owner_img_dir = self.get_owner_dir(owner_type, owner_id, is_thumbnail=False)
        owner_thumb_dir = self.get_owner_dir(owner_type, owner_id, is_thumbnail=True)

        owner_img_dir.mkdir(parents=True, exist_ok=True)
        owner_thumb_dir.mkdir(parents=True, exist_ok=True)

        # Determine target filename (canonical format: WebP is good for efficiency)
        filename = f"{image_id}.webp"
        target_img_path = owner_img_dir / filename
        target_thumb_path = owner_thumb_dir / filename

        try:
            with Image.open(source) as img:
                # Normalize orientation (EXIF)
                from PIL import ImageOps

                img = ImageOps.exif_transpose(img)

                # Convert to RGB if necessary (e.g. for RGBA -> JPEG,
                # though WebP supports alpha)
                if img.mode not in ("RGB", "RGBA"):
                    img = img.convert("RGB")

                # Save main image
                # We can set quality to something high but reasonable, e.g. 90
                img.save(target_img_path, "WEBP", quality=90)

                width, height = img.size

                # Generate thumbnail
                # Max dimension 256px
                img.thumbnail((256, 256))
                img.save(target_thumb_path, "WEBP", quality=80)

                # Return relative paths
                rel_img = target_img_path.relative_to(self.project_root).as_posix()
                rel_thumb = target_thumb_path.relative_to(self.project_root).as_posix()

                return rel_img, rel_thumb, (width, height)

        except Exception as e:
            logger.error(f"Failed to import image {source_path}: {e}")
            # Cleanup if partial write occurred
            if target_img_path.exists():
                target_img_path.unlink()
            if target_thumb_path.exists():
                target_thumb_path.unlink()
            raise

    def delete_files(
        self, image_rel_path: str, thumb_rel_path: Optional[str] = None
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Moves files to trash instead of permanent deletion.
        Returns path to moved files in trash (relative to project root).
        """
        import time

        timestamp = int(time.time())
        trash_subdir = self.trash_dir / str(timestamp)
        trash_subdir.mkdir(exist_ok=True)

        img_trash_rel = None
        thumb_trash_rel = None

        try:
            full_img_path = self.project_root / image_rel_path
            if full_img_path.exists():
                # Prefix with 'img_' to avoid collision with thumbnail (same UUID name)
                trash_img = trash_subdir / f"img_{full_img_path.name}"
                shutil.move(str(full_img_path), str(trash_img))
                img_trash_rel = trash_img.relative_to(self.project_root).as_posix()

            if thumb_rel_path:
                full_thumb_path = self.project_root / thumb_rel_path
                if full_thumb_path.exists():
                    # Prefix with 'thumb_' to avoid collision with image
                    trash_thumb = trash_subdir / f"thumb_{full_thumb_path.name}"
                    shutil.move(str(full_thumb_path), str(trash_thumb))
                    thumb_trash_rel = trash_thumb.relative_to(
                        self.project_root
                    ).as_posix()

            logger.info(f"Moved images to trash: {image_rel_path}")
            return img_trash_rel, thumb_trash_rel

        except Exception as e:
            logger.error(f"Error moving files to trash: {e}")
            raise

    def restore_files(
        self,
        img_trash_rel: Optional[str],
        img_target_rel: str,
        thumb_trash_rel: Optional[str],
        thumb_target_rel: Optional[str],
    ) -> None:
        """
        Restores files from trash to their original location.
        """
        try:
            if img_trash_rel:
                trash_path = self.project_root / img_trash_rel
                target_path = self.project_root / img_target_rel

                # Ensure target dir exists
                target_path.parent.mkdir(parents=True, exist_ok=True)

                if trash_path.exists() and not target_path.exists():
                    shutil.move(str(trash_path), str(target_path))

            if thumb_trash_rel and thumb_target_rel:
                trash_path = self.project_root / thumb_trash_rel
                target_path = self.project_root / thumb_target_rel

                target_path.parent.mkdir(parents=True, exist_ok=True)

                if trash_path.exists() and not target_path.exists():
                    shutil.move(str(trash_path), str(target_path))

            logger.info(f"Restored images from trash to {img_target_rel}")

        except Exception as e:
            logger.error(f"Failed to restore files: {e}")
            raise
