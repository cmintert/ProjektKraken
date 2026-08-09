"""Trusted application settings for world folders and external databases."""

import json
import logging
from pathlib import Path
from typing import cast

from PySide6.QtCore import QSettings

from src.core.world import World, canonical_path

logger = logging.getLogger(__name__)

SETTINGS_ACTIVE_WORLD_PATH_KEY = "world_storage/active_world_path"
SETTINGS_REGISTERED_WORLD_PATHS_KEY = "world_storage/registered_world_paths"
SETTINGS_EXTERNAL_APPROVALS_KEY = "world_storage/external_database_approvals"


class WorldStorageSettings:
    """Persist non-transferable world locations and external-path approvals."""

    def __init__(self, settings: QSettings | None = None) -> None:
        """Initialize the settings facade.

        Args:
            settings: Optional settings instance, primarily for tests.

        """
        self.settings = settings if settings is not None else QSettings()

    def active_world_path(self) -> Path | None:
        """Return the registered active world folder, if one is configured."""
        value = cast(
            str | None,
            self.settings.value(SETTINGS_ACTIVE_WORLD_PATH_KEY, None, type=str),
        )
        if not value:
            return None
        return Path(value).resolve(strict=False)

    def set_active_world_path(self, world_path: Path) -> None:
        """Persist the active world folder using its canonical local path."""
        self.settings.setValue(
            SETTINGS_ACTIVE_WORLD_PATH_KEY,
            canonical_path(world_path),
        )

    def clear_active_world_path(self) -> None:
        """Remove the active world-folder selection."""
        self.settings.remove(SETTINGS_ACTIVE_WORLD_PATH_KEY)

    def registered_world_paths(self) -> list[Path]:
        """Return world folders explicitly registered outside the default root."""
        values = self._read_json(SETTINGS_REGISTERED_WORLD_PATHS_KEY, [])
        if not isinstance(values, list):
            return []
        return [
            Path(value).resolve(strict=False)
            for value in values
            if isinstance(value, str) and value
        ]

    def register_world_path(self, world_path: Path) -> None:
        """Remember an explicitly selected complete world folder."""
        paths = {canonical_path(path) for path in self.registered_world_paths()}
        paths.add(canonical_path(world_path))
        self._write_json(SETTINGS_REGISTERED_WORLD_PATHS_KEY, sorted(paths))

    def unregister_world_path(self, world_path: Path) -> None:
        """Forget an explicitly registered world folder without deleting it."""
        target = canonical_path(world_path)
        paths = [
            canonical_path(path)
            for path in self.registered_world_paths()
            if canonical_path(path) != target
        ]
        self._write_json(SETTINGS_REGISTERED_WORLD_PATHS_KEY, paths)

    def external_approvals(self) -> dict[Path | str, Path | str]:
        """Return trusted database paths keyed by their manifest folders."""
        return {
            Path(world_path): Path(database_path)
            for world_path, database_path in self._approvals().items()
        }

    def approved_external_path(self, world: World) -> Path | None:
        """Return the external path approved for this exact manifest location."""
        value = self._approvals().get(canonical_path(world.path))
        return Path(value) if value else None

    def is_external_path_approved(self, world: World) -> bool:
        """Return whether this world's current external path is locally trusted."""
        if not world.is_external_database:
            return False
        approved = self.approved_external_path(world)
        return bool(
            approved is not None
            and canonical_path(approved) == canonical_path(world.db_path)
        )

    def approve_external_path(self, world: World) -> None:
        """Trust this world's current external path on this installation."""
        if not world.is_external_database:
            raise ValueError("Only external database paths require approval")
        approvals = self._approvals()
        approvals[canonical_path(world.path)] = canonical_path(world.db_path)
        self._write_json(SETTINGS_EXTERNAL_APPROVALS_KEY, approvals)

    def revoke_external_path(self, world: World) -> None:
        """Revoke any external database approval for this world folder."""
        approvals = self._approvals()
        approvals.pop(canonical_path(world.path), None)
        self._write_json(SETTINGS_EXTERNAL_APPROVALS_KEY, approvals)

    def _approvals(self) -> dict[str, str]:
        values = self._read_json(SETTINGS_EXTERNAL_APPROVALS_KEY, {})
        if not isinstance(values, dict):
            return {}
        return {
            str(key): str(value)
            for key, value in values.items()
            if isinstance(key, str) and isinstance(value, str)
        }

    def _read_json(self, key: str, default: object) -> object:
        raw_value = cast(str, self.settings.value(key, "", type=str))
        if not raw_value:
            return default
        try:
            return json.loads(raw_value)
        except (TypeError, json.JSONDecodeError):
            logger.warning("Ignoring malformed world-storage setting %s", key)
            return default

    def _write_json(self, key: str, value: object) -> None:
        self.settings.setValue(key, json.dumps(value, sort_keys=True))
