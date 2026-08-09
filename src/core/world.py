"""World Management Module.

Manages portable world folders and explicitly approved external databases.
Each world is a self-contained folder with:
- <world_name>.kraken (SQLite database)
- world.json (manifest)
- assets/ (images, thumbnails, etc.)
"""

import json
import logging
import os
import uuid
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Collection, Dict, List, Mapping, Optional

logger = logging.getLogger(__name__)

SELF_CONTAINED_STORAGE = "self_contained"
EXTERNAL_DATABASE_STORAGE = "external_database"
SUPPORTED_STORAGE_MODES = {
    SELF_CONTAINED_STORAGE,
    EXTERNAL_DATABASE_STORAGE,
}


class InvalidDatabasePathError(ValueError):
    """Raised when a manifest database path violates the storage policy."""


def canonical_path(path: Path | str) -> str:
    """Return a stable, platform-normalized path for trust comparisons."""
    return os.path.normcase(str(Path(path).resolve(strict=False)))


def _has_absolute_or_drive_syntax(value: str) -> bool:
    """Recognize native, Windows, UNC, and POSIX absolute path syntax."""
    windows_path = PureWindowsPath(value)
    return bool(
        Path(value).is_absolute()
        or PurePosixPath(value).is_absolute()
        or windows_path.is_absolute()
        or windows_path.drive
    )


@dataclass
class WorldManifest:
    """Manifest file for a world (world.json).

    Contains metadata about the world including its ID, name, description, and
    creation/modification timestamps.
    """

    id: str
    name: str
    description: str = ""
    created_at: float = 0.0
    modified_at: float = 0.0
    version: str = "0.6.0"
    db_filename: str = ""
    storage_mode: str = SELF_CONTAINED_STORAGE

    def to_dict(self) -> Dict[str, Any]:
        """Converts the manifest to a dictionary for JSON serialization.

        Returns:
            Dict[str, Any]: Dictionary containing manifest data with keys:
                - 'id' (str): Unique world identifier
                - 'name' (str): World display name
                - 'description' (str): World description
                - 'created_at' (float): Creation timestamp
                - 'modified_at' (float): Last modification timestamp
                - 'version' (str): Application version
                - 'db_filename' (str): Database filename

        """
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
            "version": self.version,
            "db_filename": self.db_filename,
            "storage_mode": self.storage_mode,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WorldManifest":
        """Creates a WorldManifest from a dictionary.

        Args:
            data: Dictionary containing manifest data.

        Returns:
            WorldManifest: Manifest instance.

        """
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            name=data.get("name", "Unnamed World"),
            description=data.get("description", ""),
            created_at=data.get("created_at", 0.0),
            modified_at=data.get("modified_at", 0.0),
            version=data.get("version", "0.6.0"),
            db_filename=data.get("db_filename", "world.kraken"),
            storage_mode=data.get("storage_mode", SELF_CONTAINED_STORAGE),
        )


@dataclass
class World:
    """Represents a world/workspace in the portable structure.

    A world consists of:
    - Directory: worlds/<world_name>/
    - Manifest: worlds/<world_name>/world.json
    - Database: worlds/<world_name>/<world_name>.kraken
    - Assets: worlds/<world_name>/assets/
    """

    path: Path
    manifest: WorldManifest

    @property
    def name(self) -> str:
        """Returns the world name."""
        return self.manifest.name

    @property
    def db_path(self) -> Path:
        """Returns the path to the world's database file."""
        return self.resolve_database_path()

    @property
    def is_external_database(self) -> bool:
        """Return whether this world deliberately uses an external database."""
        return self.manifest.storage_mode == EXTERNAL_DATABASE_STORAGE

    def resolve_database_path(self) -> Path:
        """Resolve and validate the manifest's database path.

        Self-contained manifests may only reference ``.kraken`` files within
        the world directory. External paths require the explicit external
        storage mode and must use an absolute path native to this platform.

        Raises:
            InvalidDatabasePathError: If the path or storage mode is unsafe.

        """
        raw_path = self.manifest.db_filename
        if not isinstance(raw_path, str):
            raise InvalidDatabasePathError("Database path must be a string")

        raw_path = raw_path.strip()
        if not raw_path or "\x00" in raw_path:
            raise InvalidDatabasePathError("Database path is empty or malformed")
        if Path(raw_path).suffix.lower() != ".kraken":
            raise InvalidDatabasePathError(
                "World databases must use the .kraken extension"
            )
        if (
            not isinstance(self.manifest.storage_mode, str)
            or self.manifest.storage_mode not in SUPPORTED_STORAGE_MODES
        ):
            raise InvalidDatabasePathError(
                f"Unsupported database storage mode: {self.manifest.storage_mode!r}"
            )

        world_root = self.path.resolve(strict=False)
        if self.manifest.storage_mode == SELF_CONTAINED_STORAGE:
            if _has_absolute_or_drive_syntax(raw_path):
                raise InvalidDatabasePathError(
                    "Self-contained database paths must be relative"
                )
            if ".." in PurePosixPath(raw_path.replace("\\", "/")).parts:
                raise InvalidDatabasePathError(
                    "Self-contained database paths cannot contain '..'"
                )

            database_path = self.path / raw_path
            resolved_database_path = database_path.resolve(strict=False)
            if not resolved_database_path.is_relative_to(world_root):
                raise InvalidDatabasePathError(
                    "Self-contained database path escapes the world directory"
                )
            return database_path

        if not Path(raw_path).is_absolute():
            raise InvalidDatabasePathError(
                "External database paths must be absolute on this platform"
            )
        return Path(raw_path).resolve(strict=False)

    @property
    def assets_path(self) -> Path:
        """Returns the path to the world's assets directory."""
        return self.path / "assets"

    @property
    def id(self) -> str:
        """Returns the world's unique identifier."""
        return self.manifest.id

    @property
    def manifest_path(self) -> Path:
        """Returns the path to the world's manifest file."""
        return self.path / "world.json"

    def ensure_structure(self) -> None:
        """Ensures the world directory structure exists.

        Creates missing directories and manifest file if needed.
        """
        # Create world directory
        self.path.mkdir(parents=True, exist_ok=True)

        # Create assets subdirectories
        (self.assets_path / "images").mkdir(parents=True, exist_ok=True)
        (self.assets_path / "thumbnails").mkdir(parents=True, exist_ok=True)

        # Create or update manifest
        self.save_manifest()

        logger.info(f"World structure ensured at: {self.path}")

    def save_manifest(self) -> None:
        """Saves the manifest to world.json."""
        import time

        # Update modified timestamp
        self.manifest.modified_at = time.time()

        manifest_data = self.manifest.to_dict()
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2)

        logger.debug(f"Saved manifest for world: {self.name}")

    @classmethod
    def inspect(cls, world_path: Path) -> Optional["World"]:
        """Read and validate a manifest without authorizing database access."""
        world_path = world_path.resolve(strict=False)
        manifest_path = (world_path / "world.json").resolve(strict=False)

        if not manifest_path.is_relative_to(world_path):
            logger.error(
                "Security violation: manifest path %s is outside world %s",
                manifest_path,
                world_path,
            )
            return None
        if not manifest_path.is_file():
            logger.warning("No manifest found at: %s", manifest_path)
            return None

        try:
            with open(manifest_path, "r", encoding="utf-8") as manifest_file:
                manifest_data = json.load(manifest_file)
            if not isinstance(manifest_data, dict):
                raise InvalidDatabasePathError("World manifest must be a JSON object")

            world = cls(
                path=world_path,
                manifest=WorldManifest.from_dict(manifest_data),
            )
            if not isinstance(world.manifest.id, str) or not isinstance(
                world.manifest.name, str
            ):
                raise InvalidDatabasePathError(
                    "World manifest id and name must be strings"
                )
            world.resolve_database_path()
            return world
        except (json.JSONDecodeError, OSError, InvalidDatabasePathError) as exc:
            logger.error("Failed to inspect world from %s: %s", world_path, exc)
            return None

    @classmethod
    def load(
        cls,
        world_path: Path,
        approved_external_paths: Collection[Path | str] = (),
    ) -> Optional["World"]:
        """Loads a world from a directory.

        Args:
            world_path: Path to the world directory.

        Returns:
            World instance if valid, None otherwise.

        """
        world = cls.inspect(world_path)
        if world is None:
            return None

        database_path = world.resolve_database_path()
        if world.is_external_database:
            approved = {canonical_path(path) for path in approved_external_paths}
            if canonical_path(database_path) not in approved:
                logger.warning(
                    "External database requires approval for world %s: %s",
                    world.name,
                    database_path,
                )
                return None

        if not database_path.is_file():
            logger.warning(
                "Database file missing for world %s: %s",
                world.name,
                database_path,
            )
            return None
        return world

    @classmethod
    def create(cls, worlds_dir: Path, name: str, description: str = "") -> "World":
        """Creates a new world with proper structure.

        Args:
            worlds_dir: Parent directory containing all worlds.
            name: Name of the new world.
            description: Optional description of the world.

        Returns:
            World: Newly created world instance.

        Raises:
            ValueError: If world with same name already exists.

        """
        import time

        # Sanitize name for directory
        safe_name = name.strip().replace("/", "_").replace("\\", "_")
        world_path = worlds_dir / safe_name

        if world_path.exists():
            raise ValueError(f"World '{name}' already exists at: {world_path}")

        # Create manifest
        manifest = WorldManifest(
            id=str(uuid.uuid4()),
            name=name,
            description=description,
            created_at=time.time(),
            modified_at=time.time(),
            db_filename=f"{safe_name}.kraken",
            storage_mode=SELF_CONTAINED_STORAGE,
        )

        world = cls(path=world_path, manifest=manifest)
        world.ensure_structure()

        # Create empty database file
        world.db_path.touch()

        logger.info(f"Created new world: {name} at {world_path}")
        return world


class WorldManager:
    """Manages discovery and validation of worlds in the portable structure."""

    def __init__(
        self,
        worlds_dir: Path,
        additional_world_paths: Collection[Path | str] = (),
        approved_external_paths: Mapping[Path | str, Path | str] | None = None,
    ) -> None:
        """Initialize the WorldManager.

        Args:
            worlds_dir: Path to the worlds/ directory.

        """
        self.worlds_dir = worlds_dir
        self.worlds_dir.mkdir(parents=True, exist_ok=True)
        self.additional_world_paths = tuple(
            Path(path).resolve(strict=False) for path in additional_world_paths
        )
        self.approved_external_paths = {
            canonical_path(world_path): database_path
            for world_path, database_path in (approved_external_paths or {}).items()
        }

    def _candidate_paths(self) -> list[Path]:
        """Return de-duplicated default and user-registered world folders."""
        candidates = [item for item in self.worlds_dir.iterdir() if item.is_dir()]
        candidates.extend(self.additional_world_paths)

        unique: dict[str, Path] = {}
        for candidate in candidates:
            unique[canonical_path(candidate)] = candidate
        return list(unique.values())

    def inspect_worlds(self) -> List[World]:
        """Inspect structurally valid worlds, including unapproved externals."""
        worlds = []
        for item in self._candidate_paths():
            world = World.inspect(item)
            if world is not None:
                worlds.append(world)
        worlds.sort(key=lambda world: world.name.lower())
        return worlds

    def discover_worlds(self) -> List[World]:
        """Discovers all valid worlds in the worlds directory.

        Returns:
            List of World instances found in the directory.

        """
        worlds: list[World] = []

        if not self.worlds_dir.exists():
            return worlds

        for item in self._candidate_paths():
            approved_path = self.approved_external_paths.get(canonical_path(item))
            approvals = [approved_path] if approved_path is not None else []
            world = World.load(item, approvals)
            if world:
                worlds.append(world)

        # Sort by name
        worlds.sort(key=lambda w: w.name.lower())

        logger.info(f"Discovered {len(worlds)} worlds in {self.worlds_dir}")
        return worlds

    def get_world(self, name: str) -> Optional[World]:
        """Gets a specific world by name.

        Args:
            name: Name of the world to find.

        Returns:
            World instance if found, None otherwise.

        """
        worlds = self.discover_worlds()
        for world in worlds:
            if world.name == name:
                return world
        return None

    def create_world(self, name: str, description: str = "") -> World:
        """Creates a new world.

        Args:
            name: Name of the new world.
            description: Optional description.

        Returns:
            World: Newly created world.

        Raises:
            ValueError: If world with same name exists.

        """
        return World.create(self.worlds_dir, name, description)

    def delete_world(self, world: World) -> None:
        """Deletes a world and all its contents.

        Args:
            world: World instance to delete.

        Raises:
            OSError: If deletion fails.

        """
        import shutil

        if world.path.exists():
            shutil.rmtree(world.path)
            logger.info(f"Deleted world: {world.name}")
