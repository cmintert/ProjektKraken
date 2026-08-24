"""Asset Store Module.

Manages filesystem operations for project assets including images, thumbnails, and trash
functionality for undo/redo support.
"""

import logging
import shutil
import uuid
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image

logger = logging.getLogger(__name__)


class AssetStore:
    """Manages filesystem operations for project assets (images, thumbnails). Ensures
    deterministic paths and safe file handling.

    In portable-only mode, assets are stored within the world directory at
    <world_dir>/assets/ rather than a separate project root.
    """

    def __init__(self, project_root: str) -> None:
        """Initialize the asset store.

        Args:
            project_root: Root directory of the world containing assets folder.
                         In portable mode, this is the world directory itself.

        """
        self.project_root = Path(project_root).resolve()
        self.assets_dir = self.project_root / "assets"
        self.images_dir = self.assets_dir / "images"
        self.thumbs_dir = self.assets_dir / "thumbnails"
        self.trash_dir = self.assets_dir / ".trash"

        self._validate_managed_roots()
        self._ensure_directories()
        self._validate_managed_roots()

    # Allowed extensions for icon imports (preserved without conversion)
    ALLOWED_ICON_EXTENSIONS = {".svg", ".png", ".jpg", ".jpeg", ".webp"}

    def _ensure_directories(self) -> None:
        """Creates necessary asset directories if they don't exist."""
        for path in [self.images_dir, self.thumbs_dir, self.trash_dir]:
            path.mkdir(parents=True, exist_ok=True)

    def _validate_managed_roots(self) -> None:
        """Ensure managed asset directories cannot escape the world directory."""
        for path in (self.assets_dir, self.images_dir, self.thumbs_dir, self.trash_dir):
            self._resolve_managed_root(path)

    def _resolve_managed_root(self, path: Path) -> Path:
        """Resolve a managed root and reject a symlink escaping the world."""
        resolved_path = path.resolve()
        try:
            resolved_path.relative_to(self.project_root)
        except ValueError as error:
            raise ValueError(
                "Managed asset directories must remain inside the world directory"
            ) from error
        return resolved_path

    def _resolve_stored_path(
        self, relative_path: str, allowed_root: Path, path_kind: str
    ) -> Path:
        """Resolve a persisted asset path beneath its expected managed root."""
        stored_path = Path(relative_path)
        if stored_path.is_absolute() or ".." in stored_path.parts:
            raise ValueError(f"{path_kind} must be a contained relative asset path")

        resolved_root = self._resolve_managed_root(allowed_root)
        resolved_path = (self.project_root / stored_path).resolve()
        try:
            resolved_path.relative_to(resolved_root)
        except ValueError as error:
            raise ValueError(
                f"{path_kind} must remain inside its managed asset directory"
            ) from error
        return resolved_path

    def import_icon(self, source_path: str) -> str:
        """Imports an icon file into the world's assets/images directory.

        Copies the file preserving its original extension (svg/png/jpg/webp).
        Generates a UUID-based filename to avoid collisions.

        Args:
            source_path: Absolute path to the source icon file.

        Returns:
            Relative posix path (e.g. 'assets/images/icon_<uuid>.svg').

        Raises:
            FileNotFoundError: If the source file does not exist.
            ValueError: If the file extension is not allowed.
            OSError: If the copy operation fails.

        """
        source = Path(source_path)

        if not source.is_file():
            raise FileNotFoundError(f"Source file not found: {source_path}")

        ext = source.suffix.lower()
        if ext not in self.ALLOWED_ICON_EXTENSIONS:
            raise ValueError(
                f"Disallowed icon file type: {ext}. "
                f"Allowed: {self.ALLOWED_ICON_EXTENSIONS}"
            )

        self.images_dir.mkdir(parents=True, exist_ok=True)
        safe_name = f"icon_{uuid.uuid4().hex}{ext}"
        target = self.images_dir / safe_name

        try:
            shutil.copy2(str(source), str(target))
            rel_path = target.relative_to(self.project_root).as_posix()
            logger.info(f"Imported icon: {source_path} -> {rel_path}")
            return rel_path
        except OSError as e:
            logger.error(f"Failed to import icon: {e}")
            if target.exists():
                target.unlink()
            raise

    def get_owner_dir(
        self, owner_type: str, owner_id: str, is_thumbnail: bool = False
    ) -> Path:
        """Returns the directory path for a specific owner's images.

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
        """Imports an image file:
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
            with Image.open(source) as opened_image:
                # Normalize orientation (EXIF)
                from PIL import ImageOps

                img: Image.Image = ImageOps.exif_transpose(opened_image)

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
        """Moves files to trash instead of permanent deletion.

        Returns path to moved files in trash (relative to project root).
        """
        import time

        try:
            full_img_path = self._resolve_stored_path(
                image_rel_path, self.images_dir, "Image path"
            )
            full_thumb_path = (
                self._resolve_stored_path(
                    thumb_rel_path, self.thumbs_dir, "Thumbnail path"
                )
                if thumb_rel_path
                else None
            )
            trash_root = self._resolve_managed_root(self.trash_dir)

            timestamp = int(time.time())
            trash_subdir = trash_root / str(timestamp)
            trash_subdir.mkdir(exist_ok=True)

            img_trash_rel = None
            thumb_trash_rel = None

            if full_img_path.exists():
                # Prefix with 'img_' to avoid collision with thumbnail (same UUID name)
                trash_img = trash_subdir / f"img_{full_img_path.name}"
                shutil.move(str(full_img_path), str(trash_img))
                img_trash_rel = trash_img.relative_to(self.project_root).as_posix()

            if full_thumb_path:
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
        """Restores files from trash to their original location."""
        try:
            img_trash_path = (
                self._resolve_stored_path(
                    img_trash_rel, self.trash_dir, "Image trash path"
                )
                if img_trash_rel
                else None
            )
            img_target_path = self._resolve_stored_path(
                img_target_rel, self.images_dir, "Image target path"
            )
            thumb_trash_path = (
                self._resolve_stored_path(
                    thumb_trash_rel, self.trash_dir, "Thumbnail trash path"
                )
                if thumb_trash_rel
                else None
            )
            thumb_target_path = (
                self._resolve_stored_path(
                    thumb_target_rel, self.thumbs_dir, "Thumbnail target path"
                )
                if thumb_target_rel
                else None
            )

            if img_trash_path:
                # Ensure target dir exists
                img_target_path.parent.mkdir(parents=True, exist_ok=True)

                if img_trash_path.exists() and not img_target_path.exists():
                    shutil.move(str(img_trash_path), str(img_target_path))

            if thumb_trash_path and thumb_target_path:
                thumb_target_path.parent.mkdir(parents=True, exist_ok=True)

                if thumb_trash_path.exists() and not thumb_target_path.exists():
                    shutil.move(str(thumb_trash_path), str(thumb_target_path))

            logger.info(f"Restored images from trash to {img_target_rel}")

        except Exception as e:
            logger.error(f"Failed to restore files: {e}")
            raise
