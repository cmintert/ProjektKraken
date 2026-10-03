"""SQLite snapshots and offline, failure-safe database replacement."""

from __future__ import annotations

import os
import sqlite3
from contextlib import closing
from dataclasses import asdict, dataclass
from pathlib import Path
from tempfile import mkstemp


def verify_database(path: Path) -> None:
    """Reject missing, corrupt, empty, or trailing-data SQLite snapshots."""
    with closing(sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)) as db:
        if db.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            raise ValueError("Database integrity check failed")
        pages = db.execute("PRAGMA page_count").fetchone()[0]
        size = db.execute("PRAGMA page_size").fetchone()[0]
        if not pages or path.stat().st_size != pages * size:
            raise ValueError("Database snapshot size is invalid")


def snapshot_database(source: Path, destination: Path) -> None:
    """Copy a consistent SQLite snapshot including committed WAL contents."""
    with (
        closing(
            sqlite3.connect(f"{source.resolve().as_uri()}?mode=ro", uri=True)
        ) as reader,
        closing(sqlite3.connect(destination)) as writer,
    ):
        reader.backup(writer)
        writer.execute("PRAGMA journal_mode=DELETE")
    verify_database(destination)


@dataclass(frozen=True)
class RestoreResult:
    """Actual restore outcome, suitable for queued GUI delivery."""

    success: bool = False
    safety_path: str = ""
    error: str = ""

    def to_dict(self) -> dict[str, bool | str]:
        """Return a serializable outcome."""
        return asdict(self)


class DatabaseRestoreService:
    """Restore only after the caller has closed all target database clients."""

    @staticmethod
    def validate(backup: Path, target: Path, authorized_directory: Path) -> None:
        """Validate source authorization and integrity without changing the world."""
        if not backup.resolve().is_relative_to(authorized_directory.resolve()):
            raise ValueError(
                "Security Violation: Backup must be inside the configured backup directory"
            )
        if backup.resolve() == target.resolve():
            raise ValueError("Backup and current database must be different files")
        verify_database(backup)

    def restore(
        self, backup: Path, target: Path, authorized_directory: Path
    ) -> RestoreResult:
        """Stage and verify replacement, preserve a safety snapshot, then replace."""
        stage: Path | None = None
        safety_path = ""
        try:
            self.validate(backup, target, authorized_directory)
            descriptor, name = mkstemp(prefix=".restore-", dir=target.parent)
            os.close(descriptor)
            stage = Path(name)
            snapshot_database(backup, stage)
            if target.exists():
                descriptor, name = mkstemp(
                    prefix="pre_restore_", suffix=".kraken", dir=target.parent
                )
                os.close(descriptor)
                safety = Path(name)
                try:
                    snapshot_database(target, safety)
                except Exception:
                    safety.unlink(missing_ok=True)
                    raise
                safety_path = str(safety)
                # Offline checkpoint protects the original even if replacement fails.
                with closing(sqlite3.connect(target)) as db:
                    busy, _, _ = db.execute(
                        "PRAGMA wal_checkpoint(TRUNCATE)"
                    ).fetchone()
                    if busy:
                        raise RuntimeError("Database still has an active client")
                for suffix in ("-wal", "-shm"):
                    Path(str(target) + suffix).unlink(missing_ok=True)
            stage.replace(target)
            return RestoreResult(True, safety_path)
        except Exception as exc:
            return RestoreResult(False, safety_path, str(exc))
        finally:
            if stage is not None:
                stage.unlink(missing_ok=True)
