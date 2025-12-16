"""Unit tests for asset management."""

import pytest
import tempfile
import shutil
from pathlib import Path
from src.core.asset_manager import AssetManager


@pytest.fixture
def temp_project_dir():
    """Create a temporary project directory for testing."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def asset_manager(temp_project_dir):
    """Create an AssetManager instance with a temp directory."""
    return AssetManager(temp_project_dir)


@pytest.fixture
def temp_image_file():
    """Create a temporary test image file."""
    temp_file = tempfile.NamedTemporaryFile(
        mode="wb", suffix=".png", delete=False
    )
    # Write some test data
    temp_file.write(b"fake image data for testing")
    temp_file.close()
    yield temp_file.name
    Path(temp_file.name).unlink(missing_ok=True)


class TestAssetManager:
    """Tests for AssetManager."""

    def test_ensure_assets_dir_creates_directory(self, asset_manager):
        """Test that ensure_assets_dir creates the directory structure."""
        assert not asset_manager.assets_dir.exists()
        asset_manager.ensure_assets_dir()
        assert asset_manager.assets_dir.exists()
        assert asset_manager.assets_dir.is_dir()

    def test_ensure_assets_dir_idempotent(self, asset_manager):
        """Test that calling ensure_assets_dir multiple times is safe."""
        asset_manager.ensure_assets_dir()
        asset_manager.ensure_assets_dir()
        assert asset_manager.assets_dir.exists()

    def test_import_image_success(self, asset_manager, temp_image_file):
        """Test importing an image successfully."""
        relative_path, checksum = asset_manager.import_image(temp_image_file)

        # Check relative path format
        assert relative_path.startswith("assets/maps/")
        assert relative_path.endswith(".png")

        # Check checksum is valid hex
        assert len(checksum) == 64  # SHA256 hex length
        assert all(c in "0123456789abcdef" for c in checksum)

        # Check file was copied
        absolute_path = asset_manager.get_absolute_path(relative_path)
        assert absolute_path.exists()

    def test_import_image_custom_filename(self, asset_manager, temp_image_file):
        """Test importing with a custom filename."""
        relative_path, checksum = asset_manager.import_image(
            temp_image_file, filename="custom_name.png"
        )

        assert "custom_name.png" in relative_path
        absolute_path = asset_manager.get_absolute_path(relative_path)
        assert absolute_path.exists()
        assert absolute_path.name == "custom_name.png"

    def test_import_image_source_not_found(self, asset_manager):
        """Test that importing non-existent file raises error."""
        with pytest.raises(FileNotFoundError):
            asset_manager.import_image("/nonexistent/path/image.png")

    def test_import_image_duplicate_same_content(
        self, asset_manager, temp_image_file
    ):
        """Test that importing same file twice returns same path."""
        path1, checksum1 = asset_manager.import_image(temp_image_file)
        path2, checksum2 = asset_manager.import_image(temp_image_file)

        assert path1 == path2
        assert checksum1 == checksum2

    def test_import_image_duplicate_different_content(
        self, asset_manager, temp_project_dir
    ):
        """Test that importing different files with same name creates unique names."""
        # Create first file
        file1 = Path(temp_project_dir) / "test1.png"
        file1.write_bytes(b"content 1")

        # Create second file with same name but different content
        file2 = Path(temp_project_dir) / "test2.png"
        file2.write_bytes(b"content 2")

        # Import both with same target name
        path1, checksum1 = asset_manager.import_image(str(file1), "same.png")
        path2, checksum2 = asset_manager.import_image(str(file2), "same.png")

        # Should have different paths and checksums
        assert path1 != path2
        assert checksum1 != checksum2
        assert "same.png" in path1
        assert "same_1.png" in path2

    def test_get_absolute_path(self, asset_manager):
        """Test converting relative to absolute path."""
        relative = "assets/maps/test.png"
        absolute = asset_manager.get_absolute_path(relative)

        assert absolute.is_absolute()
        assert str(absolute).endswith("assets/maps/test.png")
        assert asset_manager.project_root in absolute.parents

    def test_verify_checksum_success(self, asset_manager, temp_image_file):
        """Test checksum verification succeeds for matching checksums."""
        relative_path, checksum = asset_manager.import_image(temp_image_file)
        assert asset_manager.verify_checksum(relative_path, checksum) is True

    def test_verify_checksum_mismatch(self, asset_manager, temp_image_file):
        """Test checksum verification fails for mismatched checksums."""
        relative_path, _ = asset_manager.import_image(temp_image_file)
        wrong_checksum = "0" * 64
        assert asset_manager.verify_checksum(relative_path, wrong_checksum) is False

    def test_verify_checksum_file_not_found(self, asset_manager):
        """Test checksum verification returns False for non-existent file."""
        assert (
            asset_manager.verify_checksum(
                "assets/maps/nonexistent.png", "0" * 64
            )
            is False
        )

    def test_delete_asset_success(self, asset_manager, temp_image_file):
        """Test deleting an asset successfully."""
        relative_path, _ = asset_manager.import_image(temp_image_file)
        absolute_path = asset_manager.get_absolute_path(relative_path)

        # Verify file exists
        assert absolute_path.exists()

        # Delete
        result = asset_manager.delete_asset(relative_path)
        assert result is True
        assert not absolute_path.exists()

    def test_delete_asset_not_found(self, asset_manager):
        """Test deleting non-existent asset returns False."""
        result = asset_manager.delete_asset("assets/maps/nonexistent.png")
        assert result is False

    def test_compute_checksum_consistency(self, asset_manager, temp_project_dir):
        """Test that computing checksum for same content gives same result."""
        # Create a test file
        test_file = Path(temp_project_dir) / "test.bin"
        test_content = b"test content for checksum"
        test_file.write_bytes(test_content)

        checksum1 = asset_manager._compute_checksum(test_file)
        checksum2 = asset_manager._compute_checksum(test_file)

        assert checksum1 == checksum2
        assert len(checksum1) == 64  # SHA256 hex

    def test_compute_checksum_different_content(
        self, asset_manager, temp_project_dir
    ):
        """Test that different content produces different checksums."""
        file1 = Path(temp_project_dir) / "file1.bin"
        file2 = Path(temp_project_dir) / "file2.bin"

        file1.write_bytes(b"content A")
        file2.write_bytes(b"content B")

        checksum1 = asset_manager._compute_checksum(file1)
        checksum2 = asset_manager._compute_checksum(file2)

        assert checksum1 != checksum2

    def test_get_unique_filename(self, asset_manager):
        """Test generating unique filenames."""
        asset_manager.ensure_assets_dir()

        # Create a file
        (asset_manager.assets_dir / "test.png").touch()

        # Should generate test_1.png
        unique = asset_manager._get_unique_filename("test.png")
        assert unique == "test_1.png"

        # Create that too
        (asset_manager.assets_dir / "test_1.png").touch()

        # Should generate test_2.png
        unique = asset_manager._get_unique_filename("test.png")
        assert unique == "test_2.png"

    def test_import_preserves_content(self, asset_manager, temp_project_dir):
        """Test that imported file content matches source."""
        source_file = Path(temp_project_dir) / "source.png"
        test_content = b"test image content with special bytes \x00\xFF"
        source_file.write_bytes(test_content)

        relative_path, _ = asset_manager.import_image(str(source_file))
        imported_file = asset_manager.get_absolute_path(relative_path)

        assert imported_file.read_bytes() == test_content
