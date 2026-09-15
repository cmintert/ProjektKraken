"""Filesystem isolation and integrity checks for measurement runs."""

from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass
from pathlib import Path


class UnsafePerformancePathError(ValueError):
    """Raised when performance output could overlap user or tracked data."""


@dataclass(frozen=True)
class IntegritySnapshot:
    """Hashes captured without interpreting any protected file."""

    tracked: dict[str, str]
    world_databases: dict[str, str]
    git_status: str


def validate_run_root(repo_root: Path, run_root: Path) -> Path:
    """Require output below the repository's ignored performance directory."""
    repository = repo_root.resolve(strict=True)
    allowed = (repository / "tmp" / "performance").resolve(strict=False)
    candidate = run_root.resolve(strict=False)
    worlds = (repository / "worlds").resolve(strict=False)
    if candidate == allowed or not candidate.is_relative_to(allowed):
        raise UnsafePerformancePathError(
            f"Performance run must be a child of {allowed}; got {candidate}"
        )
    if candidate.is_relative_to(worlds):
        raise UnsafePerformancePathError("Performance output cannot be inside worlds/")
    return candidate


def _git(repo_root: Path, *args: str) -> str:
    command = [
        "git",
        "-c",
        f"safe.directory={repo_root.resolve(strict=False).as_posix()}",
        *args,
    ]
    result = subprocess.run(
        command,
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.stdout


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def capture_integrity(repo_root: Path) -> IntegritySnapshot:
    """Hash tracked files and world DB bytes without opening a world in Kraken."""
    tracked: dict[str, str] = {}
    for relative in _git(repo_root, "ls-files", "-z").split("\0"):
        if not relative:
            continue
        path = repo_root / relative
        if path.is_file():
            tracked[relative] = _hash_file(path)

    world_databases: dict[str, str] = {}
    worlds_root = repo_root / "worlds"
    if worlds_root.is_dir():
        for path in sorted(worlds_root.rglob("*.kraken")):
            if path.is_file():
                relative = path.relative_to(repo_root).as_posix()
                world_databases[relative] = _hash_file(path)

    return IntegritySnapshot(
        tracked=tracked,
        world_databases=world_databases,
        git_status=_git(repo_root, "status", "--short", "--untracked-files=no"),
    )


def compare_integrity(
    before: IntegritySnapshot, after: IntegritySnapshot
) -> dict[str, object]:
    """Return an explicit before/after integrity verdict."""
    tracked_changes = sorted(
        key
        for key in before.tracked.keys() | after.tracked.keys()
        if before.tracked.get(key) != after.tracked.get(key)
    )
    world_changes = sorted(
        key
        for key in before.world_databases.keys() | after.world_databases.keys()
        if before.world_databases.get(key) != after.world_databases.get(key)
    )
    return {
        "success": not tracked_changes and not world_changes,
        "tracked_changes": tracked_changes,
        "world_database_changes": world_changes,
        "git_status_before": before.git_status,
        "git_status_after": after.git_status,
    }

