"""Version-five history resets only after a verified recovery copy exists."""

import json
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from src.core.map import Map
from src.services.db_service import DatabaseService
from src.services.migrations import MigrationError, recovery, runner

pytestmark = [pytest.mark.integration, pytest.mark.ci_fast]


def version_five_world(tmp_path, monkeypatch):
    monkeypatch.setattr(recovery, "get_backup_directory", lambda: tmp_path / "backups")
    path = tmp_path / "world.kraken"
    db = DatabaseService(str(path))
    db.connect()
    db.insert_map(Map("Authored", "map.png", id="map", attributes={"notes": "keep"}))
    db.close()
    artifact = tmp_path / "assets/.history/old-command/raster.bin"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b"old undo artwork")
    payload = json.dumps(
        {
            "artifact_manifest": {
                "assets/raster.bin": "assets/.history/old-command/raster.bin"
            }
        }
    )
    with closing(sqlite3.connect(path)) as conn:
        conn.execute("DELETE FROM migration_history WHERE version=6")
        conn.execute("DROP INDEX IF EXISTS idx_ch_world_identity")
        runner._stamp(conn, 5, "created_current", "created")
        conn.execute("DELETE FROM system_meta WHERE key='command_history_format'")
        conn.execute(
            "INSERT INTO system_meta VALUES ('commandXhistoryXstacksXv2:keep','authored')"
        )
        conn.execute(
            "INSERT INTO command_history "
            "(world_id,session_id,command_type,command_data,timestamp) "
            "VALUES ('world','old','Legacy',?,1)",
            (payload,),
        )
        conn.commit()
    return path, artifact, payload


def test_upgrade_preserves_recovery_and_does_not_reset_again(tmp_path, monkeypatch):
    path, artifact, payload = version_five_world(tmp_path, monkeypatch)
    db = DatabaseService(str(path))
    db.connect()
    status = db.migration_status
    assert status["history_archived"] and status["upgraded_from"] == 5
    assert (
        db.require_connection().execute("SELECT * FROM command_history").fetchall()
        == []
    )
    assert db.get_map("map").attributes == {"notes": "keep"}
    assert (
        db.require_connection()
        .execute("SELECT 1 FROM sqlite_master WHERE name='idx_ch_world_identity'")
        .fetchone()
    )
    assert (
        db.require_connection()
        .execute(
            "SELECT value FROM system_meta WHERE key='commandXhistoryXstacksXv2:keep'"
        )
        .fetchone()[0]
        == "authored"
    )
    bundle = Path(status["recovery_path"])
    assert json.loads((bundle / "recovery.json").read_text())["complete"]
    assert (
        bundle / "command_artifacts/old-command/raster.bin"
    ).read_bytes() == artifact.read_bytes()
    with closing(sqlite3.connect(bundle / "database.kraken")) as old:
        assert (
            old.execute("SELECT command_data FROM command_history").fetchone()[0]
            == payload
        )
    db.close()
    db.connect()
    assert "upgraded_from" not in db.migration_status
    db.close()


def test_history_reset_rolls_back_on_upgrade_failure(tmp_path, monkeypatch):
    path, artifact, payload = version_five_world(tmp_path, monkeypatch)
    original = runner._stamp

    def fail_at_new_version(conn, version, *args):
        if version == 6:
            raise RuntimeError("injected ledger failure")
        original(conn, version, *args)

    monkeypatch.setattr(runner, "_stamp", fail_at_new_version)
    with pytest.raises(MigrationError, match="injected"):
        DatabaseService(str(path)).connect()
    with closing(sqlite3.connect(path)) as conn:
        assert (
            conn.execute("SELECT command_data FROM command_history").fetchone()[0]
            == payload
        )
        assert (
            conn.execute(
                "SELECT value FROM system_meta WHERE key='schema_version'"
            ).fetchone()[0]
            == "5"
        )
    assert artifact.read_bytes() == b"old undo artwork"


def test_read_only_open_does_not_reset_legacy_history(tmp_path, monkeypatch):
    path, artifact, payload = version_five_world(tmp_path, monkeypatch)
    before = path.read_bytes()
    db = DatabaseService(str(path), read_only=True)
    db.connect()
    assert (
        db.require_connection()
        .execute("SELECT command_data FROM command_history")
        .fetchone()[0]
        == payload
    )
    db.close()
    assert path.read_bytes() == before
    assert artifact.exists()
