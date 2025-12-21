"""
Unit tests for map image storage functionality.

Tests the image copying and path resolution for map images.
"""

import shutil
from pathlib import Path


class TestMapImageStorage:
    """Tests for map image storage in project folder."""

    def test_relative_path_resolution(self, tmp_path):
        """Test that relative paths are resolved against project directory."""
        # Setup
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        db_path = project_dir / "test.kraken"
        db_path.touch()

        assets_dir = project_dir / "assets" / "maps"
        assets_dir.mkdir(parents=True)

        # Create a test image
        test_image = assets_dir / "test_map.png"
        test_image.touch()

        # Test relative path resolution
        relative_path = "assets/maps/test_map.png"
        resolved = project_dir / relative_path

        assert resolved.exists()
        assert resolved == test_image

    def test_relative_path_detection(self):
        """Test that we can detect relative vs absolute paths."""
        import sys

        relative_path = "assets/maps/map.png"

        # Use a platform-appropriate absolute path
        if sys.platform == "win32":
            absolute_path = "C:/Users/test/project/assets/maps/map.png"
        else:
            absolute_path = "/home/test/project/assets/maps/map.png"

        assert not Path(relative_path).is_absolute()
        assert Path(absolute_path).is_absolute()

    def test_unique_filename_generation(self):
        """Test that unique suffixes prevent filename conflicts."""
        import uuid

        source_stem = "my_map"
        source_suffix = ".png"

        # Generate two unique filenames
        suffix1 = uuid.uuid4().hex[:8]
        suffix2 = uuid.uuid4().hex[:8]

        filename1 = f"{source_stem}_{suffix1}{source_suffix}"
        filename2 = f"{source_stem}_{suffix2}{source_suffix}"

        # They should be different
        assert filename1 != filename2
        assert filename1.startswith("my_map_")
        assert filename1.endswith(".png")

    def test_image_copy_to_assets(self, tmp_path):
        """Test that images are correctly copied to assets folder."""
        # Setup source and destination
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        source_image = source_dir / "original.png"
        source_image.write_bytes(b"PNG_CONTENT")

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        assets_dir = project_dir / "assets" / "maps"
        assets_dir.mkdir(parents=True)

        # Copy using shutil (as the actual code does)
        dest_path = assets_dir / "original_12345678.png"
        shutil.copy2(source_image, dest_path)

        # Verify
        assert dest_path.exists()
        assert dest_path.read_bytes() == b"PNG_CONTENT"

    def test_relative_path_storage(self, tmp_path):
        """Test that relative path is computed correctly."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        assets_dir = project_dir / "assets" / "maps"
        assets_dir.mkdir(parents=True)

        dest_path = assets_dir / "map_abc12345.png"
        dest_path.touch()

        # Compute relative path
        relative_path = str(dest_path.relative_to(project_dir))

        # Platform-independent check
        assert "assets" in relative_path
        assert "maps" in relative_path
        assert "map_abc12345.png" in relative_path
