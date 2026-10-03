"""File-backed regressions for backup snapshots and restore failure safety."""

import shutil
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from src.core.backup_config import BackupConfig
from src.services.backup_service import BackupService
from src.services.database_restore_service import DatabaseRestoreService

pytestmark = pytest.mark.ci_fast


def read_values(path: Path) -> list[str]:
    with closing(sqlite3.connect(path)) as connection:
        return [row[0] for row in connection.execute("SELECT value FROM trust")]


def test_manual_backup_includes_committed_wal(tmp_path):
    source = tmp_path / "world.kraken"
    connection = sqlite3.connect(source)
    try:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA wal_autocheckpoint=0")
        connection.execute("CREATE TABLE trust (value TEXT)")
        connection.execute("INSERT INTO trust VALUES ('saved in WAL')")
        connection.commit()
        service = BackupService(BackupConfig(backup_dir=tmp_path / "backups"))
        metadata = service.create_backup(source)
        assert metadata is not None
        assert read_values(metadata.backup_path) == ["saved in WAL"]
    finally:
        connection.close()


@pytest.mark.parametrize("failure", ["corrupt", "replace"])
def test_restore_failure_preserves_original(tmp_path, monkeypatch, failure):
    backups = tmp_path / "backups"
    backups.mkdir()
    backup = backups / "saved.kraken"
    target = tmp_path / "world.kraken"
    for path, value in [(backup, "old"), (target, "current")]:
        with closing(sqlite3.connect(path)) as connection:
            connection.execute("CREATE TABLE trust (value TEXT)")
            connection.execute("INSERT INTO trust VALUES (?)", (value,))
            connection.commit()
    if failure == "corrupt":
        backup.write_bytes(b"invalid database")
    else:
        original_replace = Path.replace

        def fail_replace(self, destination):
            if Path(destination) == target:
                raise PermissionError("injected replacement failure")
            return original_replace(self, destination)

        monkeypatch.setattr(Path, "replace", fail_replace)
    service = BackupService(BackupConfig(backup_dir=backups))
    assert not service.restore_backup(backup, target)
    assert read_values(target) == ["current"]
    if failure == "replace":
        assert service.last_restore_result.safety_path
        assert read_values(Path(service.last_restore_result.safety_path)) == ["current"]


def test_staging_failure_leaves_world_unchanged(tmp_path, monkeypatch):
    backups = tmp_path / "backups"
    backups.mkdir()
    source = backups / "saved.kraken"
    target = tmp_path / "world.kraken"
    for path in (source, target):
        with closing(sqlite3.connect(path)) as connection:
            connection.execute("CREATE TABLE trust (value TEXT)")
            connection.execute("INSERT INTO trust VALUES ('current')")
            connection.commit()
    original = target.read_bytes()

    def fail_snapshot(*args):
        raise OSError("injected staging failure")

    monkeypatch.setattr(
        "src.services.database_restore_service.snapshot_database", fail_snapshot
    )
    result = DatabaseRestoreService().restore(source, target, backups)
    assert not result.success
    assert result.safety_path == ""
    assert target.read_bytes() == original
    assert not list(tmp_path.glob(".restore-*"))


def test_restore_safety_snapshot_includes_uncheckpointed_world(tmp_path):
    """An offline world left with a WAL must remain recoverable after restore."""
    backups = tmp_path / "backups"
    backups.mkdir()
    backup = backups / "old.kraken"
    with closing(sqlite3.connect(backup)) as db:
        db.execute("CREATE TABLE trust (value TEXT)")
        db.execute("INSERT INTO trust VALUES ('old')")
        db.commit()
    live = tmp_path / "live.kraken"
    target = tmp_path / "world.kraken"
    with closing(sqlite3.connect(live)) as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA wal_autocheckpoint=0")
        db.execute("CREATE TABLE trust (value TEXT)")
        db.execute("INSERT INTO trust VALUES ('committed WAL state')")
        db.commit()
        # Reproduce an offline world after abrupt exit, without a shutdown checkpoint.
        shutil.copyfile(live, target)
        shutil.copyfile(str(live) + "-wal", str(target) + "-wal")
    result = DatabaseRestoreService().restore(backup, target, backups)
    assert result.success, result.error
    assert read_values(Path(result.safety_path)) == ["committed WAL state"]
    assert read_values(target) == ["old"]
    assert not Path(str(target) + "-wal").exists()
