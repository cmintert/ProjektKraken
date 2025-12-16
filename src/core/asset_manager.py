"""
Asset Management Utilities for Maps.

Provides utilities for managing map image assets:
- Copying images into project-relative assets/maps/ directory
- Computing checksums for image verification
- Path normalization and validation
- Asset cleanup

All paths are project-relative for portability across machines.
"""

import os
import shutil
import hashlib
import logging
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class AssetManager:
    """
    Manages map image assets in the project directory.

    Handles copying images into the project structure, computing checksums,
    and ensuring path consistency for portability.
    """

    def __init__(self, project_root: str):
        """
        Initializes the AssetManager with a project root directory.

        Args:
            project_root: Absolute path to the project root (e.g., /path/to/world.kraken)
        """
        self.project_root = Path(project_root).resolve()
        self.assets_dir = self.project_root / "assets" / "maps"
        logger.info(f"AssetManager initialized with root: {self.project_root}")

    def ensure_assets_dir(self) -> None:
        """
        Creates the assets/maps directory if it doesn't exist.

        Raises:
            OSError: If directory creation fails.
        """
        try:
            self.assets_dir.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Ensured assets directory exists: {self.assets_dir}")
        except OSError as e:
            logger.error(f"Failed to create assets directory: {e}")
            raise

    def import_image(
        self, source_path: str, filename: Optional[str] = None
    ) -> Tuple[str, str]:
        """
        Copies an image file into the assets/maps directory.

        If the file already exists with the same checksum, skips copying.
        If it exists with a different checksum, appends a number to the filename.

        Args:
            source_path: Absolute path to the source image file.
            filename: Optional custom filename. If None, uses source filename.

        Returns:
            Tuple[str, str]: (relative_path, checksum)
                relative_path: Project-relative path (e.g., "assets/maps/world.png")
                checksum: SHA256 checksum of the file

        Raises:
            FileNotFoundError: If source file doesn't exist.
            OSError: If copy operation fails.
        """
        source = Path(source_path).resolve()
        if not source.exists():
            raise FileNotFoundError(f"Source image not found: {source}")

        if not source.is_file():
            raise ValueError(f"Source path is not a file: {source}")

        # Ensure assets directory exists
        self.ensure_assets_dir()

        # Determine target filename
        if filename is None:
            filename = source.name

        # Compute checksum of source
        checksum = self._compute_checksum(source)

        # Check if file with same name exists
        target = self.assets_dir / filename
        if target.exists():
            existing_checksum = self._compute_checksum(target)
            if existing_checksum == checksum:
                # Same file, no need to copy
                logger.info(f"File already exists with same checksum: {filename}")
                relative_path = str(Path("assets") / "maps" / filename)
                return (relative_path, checksum)
            else:
                # Different file, append number
                filename = self._get_unique_filename(filename)
                target = self.assets_dir / filename

        # Copy file
        try:
            shutil.copy2(source, target)
            logger.info(f"Copied image {source.name} to {target}")
        except OSError as e:
            logger.error(f"Failed to copy image: {e}")
            raise

        relative_path = str(Path("assets") / "maps" / filename)
        return (relative_path, checksum)

    def get_absolute_path(self, relative_path: str) -> Path:
        """
        Converts a project-relative path to an absolute path.

        Args:
            relative_path: Project-relative path (e.g., "assets/maps/world.png")

        Returns:
            Path: Absolute path to the file.
        """
        return self.project_root / relative_path

    def verify_checksum(self, relative_path: str, expected_checksum: str) -> bool:
        """
        Verifies that a file's checksum matches the expected value.

        Args:
            relative_path: Project-relative path to the file.
            expected_checksum: Expected SHA256 checksum.

        Returns:
            bool: True if checksums match, False otherwise.
        """
        absolute_path = self.get_absolute_path(relative_path)
        if not absolute_path.exists():
            logger.warning(f"Cannot verify checksum: File not found: {absolute_path}")
            return False

        actual_checksum = self._compute_checksum(absolute_path)
        matches = actual_checksum == expected_checksum

        if not matches:
            logger.warning(
                f"Checksum mismatch for {relative_path}: "
                f"expected {expected_checksum}, got {actual_checksum}"
            )

        return matches

    def delete_asset(self, relative_path: str) -> bool:
        """
        Deletes an asset file from the project.

        Args:
            relative_path: Project-relative path to the file.

        Returns:
            bool: True if deletion succeeded, False if file not found.

        Raises:
            OSError: If deletion fails for reasons other than file not found.
        """
        absolute_path = self.get_absolute_path(relative_path)
        if not absolute_path.exists():
            logger.warning(f"Cannot delete asset: File not found: {absolute_path}")
            return False

        try:
            absolute_path.unlink()
            logger.info(f"Deleted asset: {relative_path}")
            return True
        except OSError as e:
            logger.error(f"Failed to delete asset {relative_path}: {e}")
            raise

    def _compute_checksum(self, file_path: Path) -> str:
        """
        Computes SHA256 checksum of a file.

        Args:
            file_path: Path to the file.

        Returns:
            str: Hexadecimal SHA256 checksum.
        """
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def _get_unique_filename(self, filename: str) -> str:
        """
        Generates a unique filename by appending a number if necessary.

        Args:
            filename: Original filename.

        Returns:
            str: Unique filename that doesn't exist in assets_dir.
        """
        base, ext = os.path.splitext(filename)
        counter = 1
        while (self.assets_dir / f"{base}_{counter}{ext}").exists():
            counter += 1
        return f"{base}_{counter}{ext}"
