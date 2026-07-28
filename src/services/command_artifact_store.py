"""Reversible command-owned file storage for persistent undo."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Iterable

logger = logging.getLogger(__name__)


class CommandArtifactStore:
    """Move world files into command-scoped history storage and restore them."""

    def __init__(self, world_root: Path) -> None:
        self.world_root = world_root.resolve()
        self.history_root = self.world_root / "assets" / ".history"

    def _world_path(self, relative_path: str) -> Path:
        candidate = (self.world_root / relative_path).resolve()
        if not candidate.is_relative_to(self.world_root):
            raise ValueError(f"Path escapes world root: {relative_path}")
        return candidate

    def stash(
        self, command_id: str, relative_paths: Iterable[str]
    ) -> dict[str, str]:
        """Move existing files into this command's artifact directory."""
        artifact_root = (self.history_root / command_id).resolve()
        if not artifact_root.is_relative_to(self.history_root.resolve()):
            raise ValueError("Invalid command artifact path")

        manifest: dict[str, str] = {}
        moved: list[tuple[Path, Path]] = []
        try:
            for relative_path in dict.fromkeys(relative_paths):
                source = self._world_path(relative_path)
                if not source.exists():
                    continue
                normalized_path = source.relative_to(self.world_root).as_posix()
                artifact = artifact_root / normalized_path
                artifact.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(source), str(artifact))
                artifact_rel = artifact.relative_to(self.world_root).as_posix()
                manifest[normalized_path] = artifact_rel
                moved.append((source, artifact))
            return manifest
        except Exception:
            for source, artifact in reversed(moved):
                if artifact.exists() and not source.exists():
                    source.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(artifact), str(source))
            raise

    def restore(self, manifest: dict[str, str]) -> None:
        """Restore files previously returned by :meth:`stash`."""
        restored: list[tuple[Path, Path]] = []
        try:
            for target_rel, artifact_rel in manifest.items():
                target = self._world_path(target_rel)
                artifact = self._world_path(artifact_rel)
                if not artifact.exists():
                    continue
                if target.exists():
                    raise FileExistsError(f"Cannot restore over existing file: {target}")
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(artifact), str(target))
                restored.append((target, artifact))
        except Exception:
            for target, artifact in reversed(restored):
                if target.exists() and not artifact.exists():
                    artifact.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(target), str(artifact))
            raise

    def discard(self, command_id: str) -> None:
        """Delete artifacts after their command is no longer recoverable."""
        target = (self.history_root / command_id).resolve()
        if not target.is_relative_to(self.history_root.resolve()):
            raise ValueError("Invalid command artifact path")
        if target.exists():
            shutil.rmtree(target)
            logger.info("Discarded command artifacts: %s", command_id)

    def discard_all(self) -> None:
        """Delete every artifact when the complete persistent history is cleared."""
        history_root = self.history_root.resolve()
        if not history_root.is_relative_to(self.world_root):
            raise ValueError("Invalid command history path")
        if history_root.exists():
            shutil.rmtree(history_root)
            logger.info("Discarded all command artifacts")
