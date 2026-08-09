"""
Tests for the World module (WorldManifest, World, WorldManager).
"""

import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

import pytest

from src.core.world import (
    EXTERNAL_DATABASE_STORAGE,
    InvalidDatabasePathError,
    World,
    WorldManager,
    WorldManifest,
)


def test_world_manifest_creation():
    """Test creating a WorldManifest with required fields."""
    manifest = WorldManifest(
        id="test-id",
        name="Test World",
        description="A test world",
        created_at=1000.0,
        modified_at=2000.0,
        version="0.6.0",
        db_filename="test.kraken",
    )

    assert manifest.id == "test-id"
    assert manifest.name == "Test World"
    assert manifest.description == "A test world"
    assert manifest.created_at == 1000.0
    assert manifest.modified_at == 2000.0
    assert manifest.version == "0.6.0"
    assert manifest.db_filename == "test.kraken"


def test_world_manifest_defaults():
    """Test WorldManifest default values."""
    manifest = WorldManifest(id="test-id", name="Test World")

    assert manifest.description == ""
    assert manifest.created_at == 0.0
    assert manifest.modified_at == 0.0
    assert manifest.version == "0.6.0"
    assert manifest.db_filename == ""


def test_world_manifest_to_dict():
    """Test converting WorldManifest to dictionary."""
    manifest = WorldManifest(
        id="test-id",
        name="Test World",
        description="A test world",
        created_at=1000.0,
        modified_at=2000.0,
        version="0.6.0",
        db_filename="test.kraken",
    )

    result = manifest.to_dict()

    assert result["id"] == "test-id"
    assert result["name"] == "Test World"
    assert result["description"] == "A test world"
    assert result["created_at"] == 1000.0
    assert result["modified_at"] == 2000.0
    assert result["version"] == "0.6.0"
    assert result["db_filename"] == "test.kraken"


def test_world_manifest_from_dict():
    """Test creating WorldManifest from dictionary."""
    data = {
        "id": "test-id",
        "name": "Test World",
        "description": "A test world",
        "created_at": 1000.0,
        "modified_at": 2000.0,
        "version": "0.6.0",
        "db_filename": "test.kraken",
    }

    manifest = WorldManifest.from_dict(data)

    assert manifest.id == "test-id"
    assert manifest.name == "Test World"
    assert manifest.description == "A test world"
    assert manifest.created_at == 1000.0
    assert manifest.modified_at == 2000.0
    assert manifest.version == "0.6.0"
    assert manifest.db_filename == "test.kraken"


def test_world_manifest_from_dict_with_defaults():
    """Test creating WorldManifest from dict with missing values."""
    data = {}

    manifest = WorldManifest.from_dict(data)

    # Should use defaults from from_dict method
    assert manifest.name == "Unnamed World"
    assert manifest.description == ""
    assert manifest.created_at == 0.0
    assert manifest.modified_at == 0.0
    assert manifest.version == "0.6.0"
    assert manifest.db_filename == "world.kraken"
    # ID should be generated
    assert len(manifest.id) > 0


def test_world_manifest_roundtrip():
    """Test that to_dict and from_dict are inverse operations."""
    original = WorldManifest(
        id="test-id",
        name="Test World",
        description="Description",
        created_at=1000.0,
        modified_at=2000.0,
        version="0.6.0",
        db_filename="test.kraken",
    )

    data = original.to_dict()
    restored = WorldManifest.from_dict(data)

    assert restored.id == original.id
    assert restored.name == original.name
    assert restored.description == original.description
    assert restored.created_at == original.created_at
    assert restored.modified_at == original.modified_at
    assert restored.version == original.version
    assert restored.db_filename == original.db_filename


def test_world_properties():
    """Test World properties."""
    manifest = WorldManifest(
        id="test-id",
        name="Test World",
        db_filename="test.kraken",
    )
    world = World(path=Path("/tmp/test_world"), manifest=manifest)

    assert world.name == "Test World"
    assert world.db_path == Path("/tmp/test_world/test.kraken")
    assert world.assets_path == Path("/tmp/test_world/assets")
    assert world.manifest_path == Path("/tmp/test_world/world.json")


def test_world_ensure_structure():
    """Test World.ensure_structure creates necessary directories."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        world_path = tmppath / "test_world"

        manifest = WorldManifest(
            id="test-id",
            name="Test World",
            db_filename="test.kraken",
        )
        world = World(path=world_path, manifest=manifest)

        world.ensure_structure()

        # Check directories created
        assert world_path.exists()
        assert (world_path / "assets").exists()
        assert (world_path / "assets" / "images").exists()
        assert (world_path / "assets" / "thumbnails").exists()
        assert (world_path / "world.json").exists()


def test_world_save_manifest():
    """Test World.save_manifest writes manifest file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        world_path = tmppath / "test_world"
        world_path.mkdir()

        manifest = WorldManifest(
            id="test-id",
            name="Test World",
            description="Test description",
            db_filename="test.kraken",
        )
        world = World(path=world_path, manifest=manifest)

        world.save_manifest()

        # Verify manifest file exists and contains correct data
        manifest_file = world_path / "world.json"
        assert manifest_file.exists()

        with open(manifest_file, "r") as f:
            data = json.load(f)

        assert data["id"] == "test-id"
        assert data["name"] == "Test World"
        assert data["description"] == "Test description"


def test_world_save_manifest_updates_modified_at():
    """Test that save_manifest updates the modified_at timestamp."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        world_path = tmppath / "test_world"
        world_path.mkdir()

        manifest = WorldManifest(
            id="test-id",
            name="Test World",
            modified_at=1000.0,
        )
        world = World(path=world_path, manifest=manifest)

        before = time.time()
        world.save_manifest()
        after = time.time()

        # Modified timestamp should be updated
        assert before <= world.manifest.modified_at <= after


def test_world_load_success():
    """Test World.load successfully loads a valid world."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        world_path = tmppath / "test_world"
        world_path.mkdir()

        # Create manifest
        manifest_data = {
            "id": "test-id",
            "name": "Test World",
            "description": "Test",
            "created_at": 1000.0,
            "modified_at": 2000.0,
            "version": "0.6.0",
            "db_filename": "test.kraken",
        }
        with open(world_path / "world.json", "w") as f:
            json.dump(manifest_data, f)

        # Create database file
        (world_path / "test.kraken").touch()

        # Load world
        world = World.load(world_path)

        assert world is not None
        assert world.name == "Test World"
        assert world.manifest.id == "test-id"


def test_world_load_missing_manifest():
    """Test World.load returns None when manifest missing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        world_path = tmppath / "test_world"
        world_path.mkdir()

        # No manifest file created
        world = World.load(world_path)

        assert world is None


def test_world_load_missing_database():
    """Test World.load returns None when database missing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        world_path = tmppath / "test_world"
        world_path.mkdir()

        # Create manifest but no database
        manifest_data = {
            "id": "test-id",
            "name": "Test World",
            "db_filename": "test.kraken",
        }
        with open(world_path / "world.json", "w") as f:
            json.dump(manifest_data, f)

        world = World.load(world_path)

        assert world is None


def test_world_load_invalid_json():
    """Test World.load handles invalid JSON gracefully."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        world_path = tmppath / "test_world"
        world_path.mkdir()

        # Create invalid manifest
        with open(world_path / "world.json", "w") as f:
            f.write("invalid json {")

        world = World.load(world_path)

        assert world is None


@pytest.mark.parametrize(
    "db_filename",
    [
        "../outside.kraken",
        r"..\outside.kraken",
        "/tmp/outside.kraken",
        r"C:\Users\Public\outside.kraken",
        r"C:outside.kraken",
        r"\\server\share\outside.kraken",
    ],
)
def test_world_load_rejects_self_contained_path_redirection(tmp_path, db_filename):
    """Ordinary manifests cannot redirect SQLite outside the world folder."""
    world_path = tmp_path / "world"
    world_path.mkdir()
    (world_path / "world.json").write_text(
        json.dumps(
            {
                "id": "unsafe",
                "name": "Unsafe",
                "db_filename": db_filename,
            }
        ),
        encoding="utf-8",
    )

    assert World.load(world_path) is None


def test_world_load_rejects_wrong_database_extension(tmp_path):
    """Manifest database paths must retain the expected file extension."""
    world_path = tmp_path / "world"
    world_path.mkdir()
    (world_path / "world.json").write_text(
        json.dumps(
            {
                "id": "wrong-extension",
                "name": "Wrong Extension",
                "db_filename": "world.sqlite",
            }
        ),
        encoding="utf-8",
    )
    (world_path / "world.sqlite").touch()

    assert World.load(world_path) is None


def test_world_load_rejects_non_string_storage_mode(tmp_path):
    """Malformed storage-mode data cannot crash world discovery."""
    world_path = tmp_path / "world"
    world_path.mkdir()
    (world_path / "world.json").write_text(
        json.dumps(
            {
                "id": "malformed-mode",
                "name": "Malformed Mode",
                "db_filename": "world.kraken",
                "storage_mode": ["external_database"],
            }
        ),
        encoding="utf-8",
    )
    (world_path / "world.kraken").touch()

    assert World.load(world_path) is None


def test_world_discovery_ignores_non_string_manifest_identity(tmp_path):
    """Malformed display metadata cannot crash sorting during discovery."""
    world_path = tmp_path / "world"
    world_path.mkdir()
    (world_path / "world.json").write_text(
        json.dumps(
            {
                "id": ["not", "a", "string"],
                "name": {"not": "a string"},
                "db_filename": "world.kraken",
            }
        ),
        encoding="utf-8",
    )
    (world_path / "world.kraken").touch()

    manager = WorldManager(tmp_path / "other-worlds", [world_path])

    assert manager.inspect_worlds() == []


def test_world_load_rejects_symlink_escape(tmp_path):
    """An in-folder symlink cannot redirect the database outside the world."""
    world_path = tmp_path / "world"
    world_path.mkdir()
    outside_directory = tmp_path / "outside"
    outside_directory.mkdir()
    outside = outside_directory / "outside.kraken"
    outside.touch()
    link = world_path / "linked"
    try:
        link.symlink_to(outside_directory, target_is_directory=True)
    except OSError as exc:
        if os.name != "nt":
            pytest.skip(f"Symlink creation is unavailable: {exc}")
        junction = subprocess.run(
            [
                "cmd.exe",
                "/c",
                "mklink",
                "/J",
                str(link),
                str(outside_directory),
            ],
            capture_output=True,
            check=False,
            text=True,
        )
        if junction.returncode != 0:
            pytest.skip(f"Junction creation is unavailable: {junction.stderr}")
    (world_path / "world.json").write_text(
        json.dumps(
            {
                "id": "symlink",
                "name": "Symlink",
                "db_filename": f"{link.name}/outside.kraken",
            }
        ),
        encoding="utf-8",
    )

    assert World.load(world_path) is None


def test_external_database_requires_exact_local_approval(tmp_path):
    """External mode does not open until the resolved path is approved."""
    world_path = tmp_path / "world"
    world_path.mkdir()
    external_database = tmp_path / "external" / "world.kraken"
    external_database.parent.mkdir()
    external_database.touch()
    (world_path / "world.json").write_text(
        json.dumps(
            {
                "id": "external",
                "name": "External",
                "db_filename": str(external_database),
                "storage_mode": EXTERNAL_DATABASE_STORAGE,
            }
        ),
        encoding="utf-8",
    )

    assert World.load(world_path) is None
    assert World.load(world_path, [tmp_path / "different.kraken"]) is None

    loaded = World.load(world_path, [external_database])

    assert loaded is not None
    assert loaded.db_path == external_database.resolve()


def test_missing_approved_external_database_is_not_created(tmp_path):
    """An approved external target must exist before a world can load."""
    world_path = tmp_path / "world"
    world_path.mkdir()
    external_database = tmp_path / "missing.kraken"
    (world_path / "world.json").write_text(
        json.dumps(
            {
                "id": "missing-external",
                "name": "Missing External",
                "db_filename": str(external_database),
                "storage_mode": EXTERNAL_DATABASE_STORAGE,
            }
        ),
        encoding="utf-8",
    )

    assert World.load(world_path, [external_database]) is None
    assert not external_database.exists()


def test_complete_world_folder_loads_from_registered_location(tmp_path):
    """A self-contained world remains valid outside the default worlds root."""
    default_root = tmp_path / "default-worlds"
    shared_root = tmp_path / "shared-location"
    world = World.create(shared_root, "Shared World")
    manager = WorldManager(
        default_root,
        additional_world_paths=[world.path],
    )

    assert [candidate.name for candidate in manager.discover_worlds()] == [
        "Shared World"
    ]


def test_resolver_rejects_external_mode_with_relative_path(tmp_path):
    """External mode cannot disguise a relative or traversal path."""
    world = World(
        path=tmp_path,
        manifest=WorldManifest(
            id="external-relative",
            name="External Relative",
            db_filename="../outside.kraken",
            storage_mode=EXTERNAL_DATABASE_STORAGE,
        ),
    )

    with pytest.raises(InvalidDatabasePathError, match="must be absolute"):
        world.resolve_database_path()


def test_world_create():
    """Test World.create creates a new world with proper structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        world = World.create(
            worlds_dir=tmppath,
            name="New World",
            description="A new world",
        )

        assert world.name == "New World"
        assert world.manifest.description == "A new world"
        assert world.path.exists()
        assert world.db_path.exists()
        assert world.manifest_path.exists()
        assert world.assets_path.exists()


def test_world_create_sanitizes_name():
    """Test World.create sanitizes world name for directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        world = World.create(
            worlds_dir=tmppath,
            name="Test/World\\Name",
            description="Test",
        )

        # Slashes should be replaced with underscores
        assert world.path.name == "Test_World_Name"


def test_world_create_duplicate_name():
    """Test World.create raises error for duplicate names."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        # Create first world
        World.create(worlds_dir=tmppath, name="Test World")

        # Try to create duplicate
        with pytest.raises(ValueError, match="already exists"):
            World.create(worlds_dir=tmppath, name="Test World")


def test_world_manager_init():
    """Test WorldManager initialization."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        worlds_dir = tmppath / "worlds"

        manager = WorldManager(worlds_dir)

        assert manager.worlds_dir == worlds_dir
        assert worlds_dir.exists()


def test_world_manager_discover_worlds_empty():
    """Test WorldManager.discover_worlds with no worlds."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        worlds_dir = tmppath / "worlds"

        manager = WorldManager(worlds_dir)
        worlds = manager.discover_worlds()

        assert len(worlds) == 0


def test_world_manager_discover_worlds():
    """Test WorldManager.discover_worlds finds valid worlds."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        worlds_dir = tmppath / "worlds"
        worlds_dir.mkdir()

        # Create two worlds
        World.create(worlds_dir, "World A", "First world")
        World.create(worlds_dir, "World B", "Second world")

        manager = WorldManager(worlds_dir)
        worlds = manager.discover_worlds()

        assert len(worlds) == 2
        # Should be sorted by name
        assert worlds[0].name == "World A"
        assert worlds[1].name == "World B"


def test_world_manager_discover_worlds_ignores_invalid():
    """Test WorldManager.discover_worlds ignores invalid directories."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        worlds_dir = tmppath / "worlds"
        worlds_dir.mkdir()

        # Create valid world
        World.create(worlds_dir, "Valid World")

        # Create invalid directory (no manifest)
        invalid_dir = worlds_dir / "invalid"
        invalid_dir.mkdir()

        manager = WorldManager(worlds_dir)
        worlds = manager.discover_worlds()

        assert len(worlds) == 1
        assert worlds[0].name == "Valid World"


def test_world_manager_get_world():
    """Test WorldManager.get_world finds world by name."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        worlds_dir = tmppath / "worlds"
        worlds_dir.mkdir()

        World.create(worlds_dir, "World A")
        World.create(worlds_dir, "World B")

        manager = WorldManager(worlds_dir)
        world = manager.get_world("World B")

        assert world is not None
        assert world.name == "World B"


def test_world_manager_get_world_not_found():
    """Test WorldManager.get_world returns None for missing world."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        worlds_dir = tmppath / "worlds"

        manager = WorldManager(worlds_dir)
        world = manager.get_world("Nonexistent")

        assert world is None


def test_world_manager_create_world():
    """Test WorldManager.create_world creates a new world."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        worlds_dir = tmppath / "worlds"

        manager = WorldManager(worlds_dir)
        world = manager.create_world("New World", "Description")

        assert world.name == "New World"
        assert world.manifest.description == "Description"
        assert world.path.exists()
