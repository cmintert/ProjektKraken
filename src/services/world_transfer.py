"""Self-contained portable-world archives, independent of backup restoration."""

from __future__ import annotations

import json
import ntpath
import re
import shutil
import sqlite3
import stat
import tempfile
import time
import uuid
import zipfile
from collections.abc import Callable
from contextlib import closing
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from src.core.world import SELF_CONTAINED_STORAGE, World, WorldManifest
from src.services.transfer_files import staged_output

PACKAGE_VERSION = 1
MAX_MEMBERS = 100_000
MAX_UNPACKED_BYTES = 20 * 1024**3
MAX_METADATA_BYTES = 65536


def check_cancel(cancelled: Callable[[], bool]) -> None:
    """Cooperatively interrupt file preparation between entries."""
    if cancelled():
        raise InterruptedError("Transfer cancelled.")


def validate_assets(connection: sqlite3.Connection, world_path: Path) -> None:
    """Check persisted asset references, including JSON-backed map/raster paths."""
    missing: set[str] = set()
    tables = [
        r[0]
        for r in connection.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        if r[0] not in {"command_history", "embeddings", "edit_sessions"}
    ]
    for table in tables:
        quoted = '"' + table.replace('"', '""') + '"'
        for row in connection.execute(f"SELECT * FROM {quoted}"):
            for value in row:
                if not isinstance(value, str):
                    continue
                for asset in _asset_references(value):
                    asset = asset.replace("\\\\", "/").replace("\\", "/")
                    path = (world_path / asset).resolve()
                    if (
                        not path.is_relative_to(world_path.resolve())
                        or not path.is_file()
                    ):
                        missing.add(asset)
    if missing:
        raise ValueError(
            "Missing or unsafe world assets:\n" + "\n".join(sorted(missing))
        )


def _asset_references(value: Any) -> set[str]:
    """Find asset fields and prose image references without truncating spaces."""
    if isinstance(value, dict):
        return set().union(*(_asset_references(v) for v in value.values()))
    if isinstance(value, list):
        return set().union(*(_asset_references(v) for v in value))
    if not isinstance(value, str):
        return set()
    if value.startswith(("{", "[")):
        try:
            return _asset_references(json.loads(value))
        except ValueError:
            pass
    if value.startswith(("assets/", "assets\\")):
        return {value}
    return set(re.findall(r'(?:\(|["\'])((?:assets/|assets\\)[^"\'<>\)\]]+)', value))


def export_world(
    connection: sqlite3.Connection,
    world: dict[str, Any],
    destination: Path,
    cancelled: Callable[[], bool],
) -> None:
    """Package a database connection using SQLite's consistent backup API."""
    root = Path(world["path"]).resolve()
    if destination.resolve().is_relative_to(root / "assets"):
        raise ValueError("Save the package outside the world's assets folder.")
    validate_assets(connection, root)
    manifest = WorldManifest.from_dict(world["manifest"])
    manifest.storage_mode = SELF_CONTAINED_STORAGE
    manifest.db_filename = "world.kraken"
    with staged_output(destination, cancelled=cancelled) as output:
        with tempfile.TemporaryDirectory(prefix="kraken-world-") as temporary:
            database = Path(temporary) / "world.kraken"
            with closing(sqlite3.connect(database)) as target:
                connection.backup(
                    target, pages=256, progress=lambda *_: check_cancel(cancelled)
                )
            with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr(
                    "package.json", json.dumps({"package_version": PACKAGE_VERSION})
                )
                archive.writestr(
                    "world.json", json.dumps(manifest.to_dict(), ensure_ascii=False)
                )
                archive.write(database, "world.kraken")
                assets = root / "assets"
                if assets.exists():
                    for path in sorted(assets.rglob("*")):
                        check_cancel(cancelled)
                        if path.is_symlink() or not path.resolve().is_relative_to(root):
                            raise ValueError(f"Asset link cannot be packaged: {path}")
                        if path.is_file():
                            archive.write(path, path.relative_to(root).as_posix())


def inspect_package(path: Path) -> dict[str, Any]:
    """Validate an archive and return its manifest without extraction."""
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        if (
            len(members) > MAX_MEMBERS
            or sum(m.file_size for m in members) > MAX_UNPACKED_BYTES
        ):
            raise ValueError("World package exceeds the supported extraction size.")
        seen: set[str] = set()
        for member in members:
            name = member.filename
            parts = PurePosixPath(name).parts
            mode = member.external_attr >> 16
            if (
                not parts
                or "\\" in name
                or ":" in name
                or name.startswith("/")
                or ".." in parts
                or PureWindowsPath(name).drive
                or stat.S_ISLNK(mode)
                or name.casefold() in seen
                or any(part.endswith((" ", ".")) for part in parts)
                or any(ntpath.isreserved(part) for part in parts)
            ):
                raise ValueError(f"Unsafe or duplicate package path: {name}")
            if (
                name not in {"package.json", "world.json", "world.kraken"}
                and parts[0] != "assets"
            ):
                raise ValueError(f"Unexpected package member: {name}")
            seen.add(name.casefold())
        for required in ("package.json", "world.json", "world.kraken"):
            if required not in archive.namelist():
                raise ValueError(f"Missing package member: {required}")
        if (
            archive.getinfo("package.json").file_size > MAX_METADATA_BYTES
            or archive.getinfo("world.json").file_size > MAX_METADATA_BYTES
        ):
            raise ValueError("Package metadata is too large.")
        metadata = json.loads(archive.read("package.json"))
        if metadata.get("package_version") != PACKAGE_VERSION:
            raise ValueError("Unsupported world package version.")
        manifest = json.loads(archive.read("world.json"))
        if (
            manifest.get("db_filename") != "world.kraken"
            or manifest.get("storage_mode") != SELF_CONTAINED_STORAGE
        ):
            raise ValueError("Packaged worlds must use their included database.")
        return {
            "manifest": manifest,
            "files": len(members),
            "bytes": sum(m.file_size for m in members),
        }


def import_world(
    package: Path, worlds_root: Path, name: str, cancelled: Callable[[], bool]
) -> Path:
    """Install as a new world after validation without overwriting a folder."""
    info = inspect_package(package)
    name = name.strip()
    if (
        not name
        or name in {".", ".."}
        or any(c in name for c in '/\\:*?"<>|')
        or name.endswith((" ", "."))
        or ntpath.isreserved(name)
    ):
        raise ValueError("Choose a valid new world folder name.")
    destination = worlds_root / name
    worlds_root.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise ValueError(
            "A world folder with this name already exists. Choose another name."
        )
    with tempfile.TemporaryDirectory(
        prefix=".kraken-import-", dir=worlds_root
    ) as temporary:
        stage = Path(temporary) / "world"
        stage.mkdir()
        with zipfile.ZipFile(package) as archive:
            for member in archive.infolist():
                check_cancel(cancelled)
                target = stage / member.filename
                if member.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(member) as source, target.open("wb") as output:
                        shutil.copyfileobj(source, output)
        with closing(
            sqlite3.connect(f"{(stage / 'world.kraken').as_uri()}?mode=ro", uri=True)
        ) as database:
            if database.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("The packaged database failed its integrity check.")
            tables = {
                r[0]
                for r in database.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            if not {"entities", "events", "relations"}.issubset(tables):
                raise ValueError("This is not a ProjektKraken world database.")
            validate_assets(database, stage)
        manifest = WorldManifest.from_dict(info["manifest"])
        manifest.id = str(uuid.uuid4())
        manifest.name = name
        manifest.modified_at = time.time()
        (stage / "world.json").write_text(
            json.dumps(manifest.to_dict(), indent=2), encoding="utf-8"
        )
        (stage / "package.json").unlink()
        (stage / "assets").mkdir(exist_ok=True)
        World(stage, manifest).resolve_database_path()
        check_cancel(cancelled)
        stage.rename(destination)
    return destination
