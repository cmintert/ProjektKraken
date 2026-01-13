"""
World Management Module.

Manages world/workspace directories in portable-only mode.
Each world is a self-contained folder with:
- <world_name>.kraken (SQLite database)
- world.json (manifest)
- assets/ (images, thumbnails, etc.)
"""

import json
import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class WorldManifest:
    """
    Manifest file for a world (world.json).
    
    Contains metadata about the world including its ID, name, description,
    and creation/modification timestamps.
    """
    
    id: str
    name: str
    description: str = ""
    created_at: float = 0.0
    modified_at: float = 0.0
    version: str = "0.6.0"
    db_filename: str = ""
    
    def to_dict(self) -> dict:
        """
        Converts the manifest to a dictionary for JSON serialization.
        
        Returns:
            dict: Dictionary representation of the manifest.
        """
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
            "version": self.version,
            "db_filename": self.db_filename,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "WorldManifest":
        """
        Creates a WorldManifest from a dictionary.
        
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
        )


@dataclass
class World:
    """
    Represents a world/workspace in the portable structure.
    
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
        return self.path / self.manifest.db_filename
    
    @property
    def assets_path(self) -> Path:
        """Returns the path to the world's assets directory."""
        return self.path / "assets"
    
    @property
    def manifest_path(self) -> Path:
        """Returns the path to the world's manifest file."""
        return self.path / "world.json"
    
    def ensure_structure(self) -> None:
        """
        Ensures the world directory structure exists.
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
    def load(cls, world_path: Path) -> Optional["World"]:
        """
        Loads a world from a directory.
        
        Args:
            world_path: Path to the world directory.
            
        Returns:
            World instance if valid, None otherwise.
        """
        manifest_path = world_path / "world.json"
        
        if not manifest_path.exists():
            logger.warning(f"No manifest found at: {manifest_path}")
            return None
        
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest_data = json.load(f)
            
            manifest = WorldManifest.from_dict(manifest_data)
            world = cls(path=world_path, manifest=manifest)
            
            # Validate database exists
            if not world.db_path.exists():
                logger.warning(f"Database file missing for world: {world.name}")
                return None
            
            return world
            
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load world from {world_path}: {e}")
            return None
    
    @classmethod
    def create(cls, worlds_dir: Path, name: str, description: str = "") -> "World":
        """
        Creates a new world with proper structure.
        
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
        )
        
        world = cls(path=world_path, manifest=manifest)
        world.ensure_structure()
        
        # Create empty database file
        world.db_path.touch()
        
        logger.info(f"Created new world: {name} at {world_path}")
        return world


class WorldManager:
    """
    Manages discovery and validation of worlds in the portable structure.
    """
    
    def __init__(self, worlds_dir: Path) -> None:
        """
        Initialize the WorldManager.
        
        Args:
            worlds_dir: Path to the worlds/ directory.
        """
        self.worlds_dir = worlds_dir
        self.worlds_dir.mkdir(parents=True, exist_ok=True)
    
    def discover_worlds(self) -> List[World]:
        """
        Discovers all valid worlds in the worlds directory.
        
        Returns:
            List of World instances found in the directory.
        """
        worlds = []
        
        if not self.worlds_dir.exists():
            return worlds
        
        # Look for subdirectories with world.json
        for item in self.worlds_dir.iterdir():
            if item.is_dir():
                world = World.load(item)
                if world:
                    worlds.append(world)
        
        # Sort by name
        worlds.sort(key=lambda w: w.name.lower())
        
        logger.info(f"Discovered {len(worlds)} worlds in {self.worlds_dir}")
        return worlds
    
    def get_world(self, name: str) -> Optional[World]:
        """
        Gets a specific world by name.
        
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
        """
        Creates a new world.
        
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
        """
        Deletes a world and all its contents.
        
        Args:
            world: World instance to delete.
            
        Raises:
            OSError: If deletion fails.
        """
        import shutil
        
        if world.path.exists():
            shutil.rmtree(world.path)
            logger.info(f"Deleted world: {world.name}")
