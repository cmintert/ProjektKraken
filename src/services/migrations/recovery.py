"""Verified, WAL-aware recovery bundles retained independently of auto backups."""

import hashlib
import json
import os
import shutil
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.core.paths import get_backup_directory
from src.services.migrations.errors import MigrationError


def _digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _inventory(root: Path) -> dict[str, str]:
    if not root.exists():
        return {}
    result: dict[str, str] = {}
    for path in [root, *root.rglob("*")]:
        if path.is_symlink() or path.is_junction():
            raise MigrationError(f"Recovery source contains a linked path: {path}")
        if path.is_file():
            result[path.relative_to(root).as_posix()] = _digest(path)
    return result


def _artifact_paths(value: Any) -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "artifact_manifest":
                if not isinstance(item, dict) or any(
                    not isinstance(path, str) for path in item.values()
                ):
                    raise MigrationError("Invalid saved undo artifact manifest")
                paths.extend(item.values())
            elif key in ("img_trash_path", "thumb_trash_path") and item is not None:
                if not isinstance(item, str):
                    raise MigrationError("Invalid saved attachment trash path")
                paths.append(item)
            else:
                paths.extend(_artifact_paths(item))
    elif isinstance(value, list):
        for item in value:
            paths.extend(_artifact_paths(item))
    return paths


def _verify_history_references(
    conn: sqlite3.Connection, root: Path, inventory: dict[str, str]
) -> None:
    if not conn.execute(
        "SELECT 1 FROM sqlite_master WHERE name='command_history' AND type='table'"
    ).fetchone():
        return
    for record_id, raw in conn.execute("SELECT id, command_data FROM command_history"):
        try:
            paths = _artifact_paths(json.loads(raw))
            for relative in paths:
                target = (root / relative).resolve()
                if not target.is_relative_to(root):
                    raise ValueError("Undo artifact escapes world storage")
                if target.relative_to(root).as_posix() not in inventory:
                    raise ValueError(f"Missing saved undo artifact: {relative}")
        except (ValueError, TypeError) as exc:
            raise MigrationError(
                f"Cannot preserve undo history record {record_id}: {exc}",
                record_ids=[str(record_id)],
            ) from exc


def create_recovery_bundle(
    conn: sqlite3.Connection,
    database_path: str,
    world_root: Path | None,
    status: dict[str, Any],
) -> Path:
    """Back up the locked database and verify all referenced command artifacts.

    The caller must hold a writer reservation before calling. A separate read
    connection avoids backing up from an active write transaction, which can
    stall SQLite's backup API. The reservation prevents a competing commit.
    """
    database = Path(database_path).resolve()
    root = (world_root or database.parent).resolve()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    bundle = get_backup_directory() / "migrations" / f"{stamp}-{uuid.uuid4().hex}"
    bundle.mkdir(parents=True)
    try:
        history_root = root / "assets" / ".history"
        inventory = _inventory(history_root)
        trash_root = root / "assets" / ".trash"
        trash_inventory = _inventory(trash_root)
        references = {
            **{f"assets/.history/{path}": digest for path, digest in inventory.items()},
            **{
                f"assets/.trash/{path}": digest
                for path, digest in trash_inventory.items()
            },
        }
        _verify_history_references(conn, root, references)
        backup = bundle / "database.kraken"
        with (
            closing(
                sqlite3.connect(f"{database.as_uri()}?mode=ro", uri=True)
            ) as source,
            closing(sqlite3.connect(backup)) as destination,
        ):
            source.backup(destination)
            if destination.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise MigrationError("Pre-upgrade database backup failed verification")
        if history_root.exists():
            shutil.copytree(
                history_root,
                bundle / "command_artifacts",
                copy_function=shutil.copyfile,
            )
        if inventory != _inventory(
            bundle / "command_artifacts"
        ) or inventory != _inventory(history_root):
            raise MigrationError("Command artifacts changed during recovery backup")
        if trash_root.exists():
            shutil.copytree(
                trash_root, bundle / "trashed_assets", copy_function=shutil.copyfile
            )
        if trash_inventory != _inventory(
            bundle / "trashed_assets"
        ) or trash_inventory != _inventory(trash_root):
            raise MigrationError("Attachment trash changed during recovery backup")
        manifest = root / "world.json"
        manifest_digest: str | None = None
        if manifest.exists():
            if manifest.is_symlink():
                raise MigrationError("World manifest is a linked path")
            manifest_digest = _digest(manifest)
            shutil.copyfile(manifest, bundle / "world.json")
            if manifest_digest != _digest(bundle / "world.json"):
                raise MigrationError("World manifest backup verification failed")
        metadata = {
            "complete": True,
            "database_path": str(database),
            "world_root": str(root),
            "schema_status": status,
            "database_sha256": _digest(backup),
            "artifact_sha256": inventory,
            "trash_sha256": trash_inventory,
            "manifest_sha256": manifest_digest,
            "recovery": (
                "Close Kraken and all database clients. Preserve the failed world. "
                "Restore database.kraken to the recorded database_path, remove only "
                "that database's stale -wal and -shm sidecars, and restore "
                "command_artifacts to world_root/assets/.history and "
                "trashed_assets to world_root/assets/.trash, when included. "
                "Use the previous Kraken version to open the restored world. "
                "Attachments and live assets were not modified by this upgrade."
            ),
        }
        pending_metadata = bundle / "recovery.pending.json"
        pending_metadata.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        for path in [
            backup,
            pending_metadata,
            *[
                file
                for file in bundle.rglob("*")
                if file.is_file() and file not in (backup, pending_metadata)
            ],
        ]:
            # Windows _commit requires a descriptor opened for writing.
            with path.open("r+b") as stream:
                os.fsync(stream.fileno())
        pending_metadata.replace(bundle / "recovery.json")
        return bundle
    except Exception as exc:
        # Leave partial output for diagnosis; only recovery.json marks success.
        raise MigrationError(
            f"A verified recovery backup could not be created: {exc}. "
            "No migration was applied. Check free space and backup permissions.",
            step="recovery_backup",
            database_path=str(database),
            recovery_path=str(bundle),
            record_ids=exc.record_ids if isinstance(exc, MigrationError) else None,
        ) from exc
