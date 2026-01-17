"""
Tests for the AssetStore service.
"""

import tempfile
from pathlib import Path

import pytest
from PIL import Image

from src.services.asset_store import AssetStore


@pytest.fixture
def temp_project_root():
    """Creates a temporary project root directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def asset_store(temp_project_root):
    """Creates an AssetStore instance with temporary directory."""
    return AssetStore(temp_project_root)


@pytest.fixture
def test_image():
    """Creates a temporary test image file."""
    import os

    # Use mkstemp to get a file handle we can close before PIL uses it
    fd, tmp_path = tempfile.mkstemp(suffix=".png")
    os.close(fd)  # Close the file descriptor immediately

    try:
        img = Image.new("RGB", (800, 600), color="red")
        img.save(tmp_path, "PNG")
        yield tmp_path
    finally:
        # Robust cleanup for Windows - may need to retry
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except PermissionError:
            pass  # File is locked, will be cleaned up by OS later


def test_asset_store_initialization(temp_project_root):
    """Test AssetStore initializes with correct directory structure."""
    store = AssetStore(temp_project_root)

    assert store.project_root == Path(temp_project_root)
    assert store.assets_dir == Path(temp_project_root) / "assets"
    assert store.images_dir == Path(temp_project_root) / "assets" / "images"
    assert store.thumbs_dir == Path(temp_project_root) / "assets" / "thumbnails"
    assert store.trash_dir == Path(temp_project_root) / "assets" / ".trash"


def test_asset_store_creates_directories(temp_project_root):
    """Test AssetStore creates necessary directories on initialization."""
    store = AssetStore(temp_project_root)

    assert store.images_dir.exists()
    assert store.thumbs_dir.exists()
    assert store.trash_dir.exists()


def test_get_owner_dir_for_images(asset_store):
    """Test get_owner_dir returns correct path for images."""
    owner_dir = asset_store.get_owner_dir("event", "event-123", is_thumbnail=False)

    assert owner_dir == asset_store.images_dir / "events" / "event-123"


def test_get_owner_dir_for_thumbnails(asset_store):
    """Test get_owner_dir returns correct path for thumbnails."""
    owner_dir = asset_store.get_owner_dir("entity", "entity-456", is_thumbnail=True)

    assert owner_dir == asset_store.thumbs_dir / "entities" / "entity-456"


def test_get_owner_dir_pluralizes_owner_type(asset_store):
    """Test get_owner_dir adds 's' to owner_type for directory structure."""
    event_dir = asset_store.get_owner_dir("event", "id-1")
    entity_dir = asset_store.get_owner_dir("entity", "id-2")

    assert "events" in str(event_dir)
    assert "entities" in str(entity_dir)


def test_import_image_success(asset_store, test_image):
    """Test importing an image successfully."""
    image_rel, thumb_rel, (width, height) = asset_store.import_image(
        "event", "event-123", test_image
    )

    # Check that paths are relative and use forward slashes
    assert image_rel.startswith("assets/images/events/event-123/")
    assert thumb_rel.startswith("assets/thumbnails/events/event-123/")
    assert image_rel.endswith(".webp")
    assert thumb_rel.endswith(".webp")

    # Check dimensions
    assert width == 800
    assert height == 600

    # Check files were created
    full_image_path = asset_store.project_root / image_rel
    full_thumb_path = asset_store.project_root / thumb_rel
    assert full_image_path.exists()
    assert full_thumb_path.exists()


def test_import_image_creates_owner_directories(asset_store, test_image):
    """Test import_image creates owner-specific directories."""
    owner_id = "new-owner-123"

    asset_store.import_image("event", owner_id, test_image)

    owner_img_dir = asset_store.images_dir / "events" / owner_id
    owner_thumb_dir = asset_store.thumbs_dir / "events" / owner_id

    assert owner_img_dir.exists()
    assert owner_thumb_dir.exists()


def test_import_image_generates_thumbnail(asset_store, test_image):
    """Test import_image generates thumbnail with correct size."""
    _, thumb_rel, _ = asset_store.import_image("event", "event-123", test_image)

    thumb_path = asset_store.project_root / thumb_rel
    with Image.open(thumb_path) as thumb:
        # Thumbnail should be scaled down (max 256x256)
        assert thumb.width <= 256
        assert thumb.height <= 256


def test_import_image_handles_rgba(asset_store):
    """Test import_image handles RGBA images correctly."""
    import os

    # Create RGBA test image using mkstemp to avoid Windows file locking
    fd, tmp_path = tempfile.mkstemp(suffix=".png")
    os.close(fd)

    try:
        img = Image.new("RGBA", (400, 300), color=(255, 0, 0, 128))
        img.save(tmp_path, "PNG")

        image_rel, thumb_rel, (width, height) = asset_store.import_image(
            "event", "event-123", tmp_path
        )

        assert width == 400
        assert height == 300

        # Files should exist
        full_image_path = asset_store.project_root / image_rel
        assert full_image_path.exists()
    finally:
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except PermissionError:
            pass  # File locked, will be cleaned by OS


def test_import_image_missing_file(asset_store):
    """Test import_image raises error for missing source file."""
    with pytest.raises(FileNotFoundError):
        asset_store.import_image("event", "event-123", "/nonexistent/file.jpg")


def test_import_image_cleanup_on_error(asset_store, temp_project_root):
    """Test import_image cleans up partial files on error."""
    import os

    # Create a corrupted image file using mkstemp to avoid Windows file locking
    fd, tmp_path = tempfile.mkstemp(suffix=".png")
    os.write(fd, b"not a valid image")
    os.close(fd)

    try:
        with pytest.raises(Exception):
            asset_store.import_image("event", "event-123", tmp_path)

        # Check no orphaned files remain
        owner_dir = asset_store.images_dir / "events" / "event-123"
        if owner_dir.exists():
            assert len(list(owner_dir.iterdir())) == 0
    finally:
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except PermissionError:
            pass  # File locked, will be cleaned by OS


def test_delete_files_moves_to_trash(asset_store, test_image):
    """Test delete_files moves files to trash instead of deleting."""
    # Import image first
    image_rel, thumb_rel, _ = asset_store.import_image("event", "event-123", test_image)

    # Verify files exist
    image_path = asset_store.project_root / image_rel
    thumb_path = asset_store.project_root / thumb_rel
    assert image_path.exists()
    assert thumb_path.exists()

    # Delete files
    trash_img_rel, trash_thumb_rel = asset_store.delete_files(image_rel, thumb_rel)

    # Original files should be gone
    assert not image_path.exists()
    assert not thumb_path.exists()

    # Files should be in trash
    assert trash_img_rel.startswith("assets/.trash/")
    assert trash_thumb_rel.startswith("assets/.trash/")
    trash_img_path = asset_store.project_root / trash_img_rel
    trash_thumb_path = asset_store.project_root / trash_thumb_rel
    assert trash_img_path.exists()
    assert trash_thumb_path.exists()


def test_delete_files_only_image(asset_store, test_image):
    """Test delete_files works with only image (no thumbnail)."""
    image_rel, _, _ = asset_store.import_image("event", "event-123", test_image)

    trash_img_rel, trash_thumb_rel = asset_store.delete_files(image_rel, None)

    assert trash_img_rel is not None
    assert trash_thumb_rel is None


def test_delete_files_nonexistent_file(asset_store):
    """Test delete_files handles nonexistent files gracefully."""
    # Should not raise error for nonexistent file
    trash_img_rel, trash_thumb_rel = asset_store.delete_files(
        "assets/images/nonexistent.webp", None
    )

    # Should return None for missing files
    assert trash_img_rel is None


def test_restore_files_success(asset_store, test_image):
    """Test restore_files moves files back from trash."""
    # Import and delete image
    image_rel, thumb_rel, _ = asset_store.import_image("event", "event-123", test_image)
    trash_img_rel, trash_thumb_rel = asset_store.delete_files(image_rel, thumb_rel)

    # Verify files are in trash
    trash_img_path = asset_store.project_root / trash_img_rel
    trash_thumb_path = asset_store.project_root / trash_thumb_rel
    assert trash_img_path.exists()
    assert trash_thumb_path.exists()

    # Restore files
    asset_store.restore_files(trash_img_rel, image_rel, trash_thumb_rel, thumb_rel)

    # Files should be back at original location
    original_img_path = asset_store.project_root / image_rel
    original_thumb_path = asset_store.project_root / thumb_rel
    assert original_img_path.exists()
    assert original_thumb_path.exists()

    # Trash should be empty (files moved out)
    assert not trash_img_path.exists()
    assert not trash_thumb_path.exists()


def test_restore_files_creates_target_directories(asset_store):
    """Test restore_files creates target directories if they don't exist."""
    # Create trash file manually
    trash_dir = asset_store.trash_dir / "test"
    trash_dir.mkdir()
    trash_file = trash_dir / "test.webp"
    trash_file.write_bytes(b"test content")

    trash_rel = trash_file.relative_to(asset_store.project_root).as_posix()
    target_rel = "assets/images/events/new-event/test.webp"

    # Target directory doesn't exist yet
    target_path = asset_store.project_root / target_rel
    assert not target_path.parent.exists()

    # Restore should create directories
    asset_store.restore_files(trash_rel, target_rel, None, None)

    assert target_path.exists()


def test_restore_files_skips_if_target_exists(asset_store, test_image):
    """Test restore_files doesn't overwrite existing target files."""
    # Import image
    image_rel, thumb_rel, _ = asset_store.import_image("event", "event-123", test_image)
    original_path = asset_store.project_root / image_rel
    original_content = original_path.read_bytes()

    # Create fake trash file
    trash_dir = asset_store.trash_dir / "test"
    trash_dir.mkdir()
    trash_file = trash_dir / "fake.webp"
    trash_file.write_bytes(b"different content")
    trash_rel = trash_file.relative_to(asset_store.project_root).as_posix()

    # Try to restore - should skip because target exists
    asset_store.restore_files(trash_rel, image_rel, None, None)

    # Original file should be unchanged
    assert original_path.read_bytes() == original_content


def test_asset_store_webp_format(asset_store, test_image):
    """Test that AssetStore converts images to WebP format."""
    image_rel, _, _ = asset_store.import_image("event", "event-123", test_image)

    image_path = asset_store.project_root / image_rel

    # Check file extension
    assert image_path.suffix == ".webp"

    # Verify it's actually a WebP image
    with Image.open(image_path) as img:
        assert img.format == "WEBP"
