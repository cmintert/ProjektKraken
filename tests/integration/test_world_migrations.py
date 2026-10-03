"""Real historical world upgrades, WAL backups, and failure recovery."""

import json
import re
import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path
from unittest.mock import Mock

import pytest

from src.services.db_service import DatabaseService
from src.services.migrations import (
    MigrationError,
    prepare_database,
    recovery,
    runner,
    steps,
)
from src.services.worker import DatabaseWorker

pytestmark = [pytest.mark.integration, pytest.mark.ci_fast]
FIXTURES = Path(__file__).parents[1] / "fixtures" / "migrations"
SOURCE_ID = "00000000-0000-0000-0000-000000000001"
TARGET_ID = "00000000-0000-0000-0000-000000000002"


def remove_legacy_foreign_keys(path):
    """Reproduce the benchmark's canonical columns without declared references."""
    with closing(sqlite3.connect(path)) as conn:
        conn.execute("PRAGMA legacy_alter_table=ON")
        for table in steps.LEGACY_FOREIGN_KEY_TABLES:
            sql = conn.execute(
                "SELECT sql FROM sqlite_master WHERE name=?", (table,)
            ).fetchone()[0]
            sql = re.sub(
                r",\s*FOREIGN KEY\s*\([^)]*\) REFERENCES \w+\([^)]*\)"
                r" ON DELETE CASCADE",
                "",
                sql,
            )
            conn.execute(f"ALTER TABLE {table} RENAME TO old_{table}")
            conn.execute(sql)
            conn.execute(f"INSERT INTO {table} SELECT * FROM old_{table}")
            conn.execute(f"DROP TABLE old_{table}")
        conn.commit()


def test_missing_legacy_foreign_keys_preserve_children_and_restore_cascades(tmp_path):
    path = legacy_world(tmp_path)
    remove_legacy_foreign_keys(path)
    add_trajectory(path)
    with closing(sqlite3.connect(path)) as conn:
        conn.execute(
            "INSERT INTO feature_geometry_states VALUES "
            "('geometry','marker',1,'{}',0.1,0.2,1,1)"
        )
        conn.execute("INSERT INTO tags VALUES ('tag','Test',NULL,1)")
        conn.execute("INSERT INTO entity_tags VALUES (?, 'tag',1)", (SOURCE_ID,))
        conn.execute("INSERT INTO event_tags VALUES (?, 'tag',1)", (TARGET_ID,))
        conn.commit()
        before = {
            table: conn.execute(f"SELECT * FROM {table}").fetchall()
            for table in (*steps.LEGACY_FOREIGN_KEY_TABLES, "feature_geometry_states")
        }
    original = database_dump(path)
    service = DatabaseService(str(path))
    service.connect()
    conn = service._connection
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    for table, rows in before.items():
        assert [tuple(row) for row in conn.execute(f"SELECT * FROM {table}")] == rows
        assert steps._table_contract(conn, table) == steps.reference_contracts()[table]
    assert conn.execute("SELECT COUNT(*) FROM moving_features").fetchone()[0] == 1
    bundle = Path(service.migration_status["recovery_path"])
    assert database_dump(bundle / "database.kraken") == original
    service.close()
    migrated = database_dump(path)
    service.connect()
    assert "upgraded_from" not in service.migration_status
    assert database_dump(path) == migrated
    conn = service._connection
    conn.execute("DELETE FROM maps WHERE id='map'")
    conn.execute("DELETE FROM tags WHERE id='tag'")
    for table in (
        *steps.LEGACY_FOREIGN_KEY_TABLES,
        "feature_geometry_states",
        "moving_features",
    ):
        assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
    conn.rollback()
    service.close()


@pytest.mark.parametrize("table", steps.LEGACY_FOREIGN_KEY_TABLES)
def test_missing_legacy_foreign_keys_reject_orphans_without_changes(tmp_path, table):
    path = legacy_world(tmp_path)
    remove_legacy_foreign_keys(path)
    with closing(sqlite3.connect(path)) as conn:
        if table == "markers":
            conn.execute(
                "INSERT INTO markers (id,map_id,object_id,object_type,x,y) "
                "VALUES ('orphan','missing',?,'entity',0,0)",
                (SOURCE_ID,),
            )
        else:
            conn.execute(
                f"INSERT INTO {table} VALUES (?, 'missing',1)",
                (SOURCE_ID if table == "entity_tags" else TARGET_ID,),
            )
        conn.commit()
    before = database_dump(path)
    with pytest.raises(MigrationError, match="orphan"):
        DatabaseService(str(path)).connect()
    assert database_dump(path) == before


def test_constraint_rebuild_failure_rolls_back_and_restores_enforcement(
    tmp_path,
    monkeypatch,
):
    path = legacy_world(tmp_path)
    remove_legacy_foreign_keys(path)
    before = database_dump(path)
    with closing(sqlite3.connect(path)) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        monkeypatch.setattr(
            steps,
            "validate_trajectories",
            Mock(side_effect=MigrationError("injected failure")),
        )
        with pytest.raises(MigrationError, match="injected failure"):
            prepare_database(conn, str(path))
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert not conn.in_transaction
    assert database_dump(path) == before


def test_missing_foreign_keys_remain_strict_for_versioned_worlds(tmp_path):
    path = legacy_world(tmp_path)
    service = DatabaseService(str(path))
    service.connect()
    service.close()
    remove_legacy_foreign_keys(path)
    before = database_dump(path)
    with pytest.raises(MigrationError, match="constraint layout"):
        service.connect()
    assert database_dump(path) == before


def test_missing_legacy_foreign_keys_read_only_open_does_not_rebuild(tmp_path):
    path = legacy_world(tmp_path)
    remove_legacy_foreign_keys(path)
    before = path.read_bytes()
    service = DatabaseService(str(path), read_only=True)
    service.connect()
    assert service.migration_status["detected_version"] == 0
    service.close()
    assert path.read_bytes() == before


@pytest.fixture(autouse=True)
def recovery_directory(tmp_path, monkeypatch):
    directory = tmp_path / "backups"
    monkeypatch.setattr(recovery, "get_backup_directory", lambda: directory)
    return directory


def legacy_world(tmp_path, name="pre_ledger"):
    path = tmp_path / f"{name}.kraken"
    with closing(sqlite3.connect(path)) as conn:
        conn.executescript((FIXTURES / f"{name}.sql").read_text(encoding="utf-8"))
        conn.execute(
            "INSERT INTO entities (id, type, name, attributes) VALUES (?, ?, ?, ?)",
            (SOURCE_ID, "Place", "Source", '{"_temporal_v2":{"schema":1}}'),
        )
        conn.execute(
            "INSERT INTO events (id, type, name, lore_date, lore_duration, attributes) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                TARGET_ID,
                "Event",
                "Target",
                -1.25,
                0.5,
                '{"_temporal_v2":{"schema":1,"expression":{"kind":"exact"}}}',
            ),
        )
        conn.execute("INSERT INTO system_meta VALUES ('current_time', '-1.25')")
        conn.commit()
    return path


def database_dump(path):
    with closing(sqlite3.connect(path)) as conn:
        return "\n".join(conn.iterdump())


def add_trajectory(path, raw="[[0, 0.1, 0.2], [2, 0.3, 0.4]]"):
    with closing(sqlite3.connect(path)) as conn:
        conn.execute(
            "INSERT INTO maps (id,name,image_path) VALUES ('map','Map','map.png')"
        )
        conn.execute(
            "INSERT INTO markers (id,map_id,object_id,object_type,x,y) "
            "VALUES ('marker','map',?,'entity',0.1,0.2)",
            (SOURCE_ID,),
        )
        conn.execute(
            "INSERT INTO moving_features "
            "(id,marker_id,t_start,t_end,trajectory,properties) "
            "VALUES ('trajectory','marker',0,2,?,?)",
            (raw, '{"editor":{"version":2},"custom":true}'),
        )
        conn.commit()


@pytest.mark.parametrize(
    "name",
    [
        "early",
        "trajectories",
        "history",
        "pre_relations",
        "pre_ledger",
    ],
)
def test_historical_schema_upgrade_preserves_world_and_is_idempotent(
    tmp_path,
    name,
    recovery_directory,
):
    path = legacy_world(tmp_path, name)
    before = database_dump(path)
    service = DatabaseService(str(path))
    service.connect()
    status = service.migration_status
    assert status["detected_version"] == steps.CURRENT_VERSION
    assert status["upgraded_from"] == 0
    assert [entry["migration_id"] for entry in status["completed_entries"]] == list(
        steps.MIGRATION_IDS
    )
    assert service.get_entity(SOURCE_ID).attributes == {"_temporal_v2": {"schema": 1}}
    assert service.get_event(TARGET_ID).lore_date == -1.25
    assert service.get_event(TARGET_ID).lore_duration == 0.5
    service.close()
    bundle = Path(status["recovery_path"])
    assert database_dump(bundle / "database.kraken") == before
    metadata = json.loads((bundle / "recovery.json").read_text())
    assert metadata["complete"] is True
    upgraded = database_dump(path)
    count = len(list((recovery_directory / "migrations").iterdir()))
    service.connect()
    assert "upgraded_from" not in service.migration_status
    service.close()
    assert database_dump(path) == upgraded
    assert len(list((recovery_directory / "migrations").iterdir())) == count


def test_structural_columns_are_added_before_history_indexes(tmp_path):
    path = legacy_world(tmp_path, "history")
    with closing(sqlite3.connect(path)) as conn:
        # A historical partial migration: timestamp is absent but rows exist.
        for name in ("idx_ch_world_time", "idx_ch_aggregate"):
            conn.execute(f"DROP INDEX IF EXISTS {name}")
        conn.execute("ALTER TABLE command_history DROP COLUMN timestamp")
        conn.execute("ALTER TABLE tags DROP COLUMN color")
        conn.commit()
    service = DatabaseService(str(path))
    service.connect()
    assert "timestamp" in steps.columns(service._connection, "command_history")
    assert "color" in steps.columns(service._connection, "tags")
    service.close()


def test_upgrade_preserves_map_temporal_attachment_and_calendar_state(tmp_path):
    path = legacy_world(tmp_path)
    add_trajectory(path)
    with closing(sqlite3.connect(path)) as conn:
        conn.execute(
            "INSERT INTO feature_geometry_states VALUES "
            "('geometry','marker',1.5,'{"
            "path"
            ":[]}',0.2,0.3,1,1)"
        )
        conn.execute(
            "INSERT INTO image_attachments (id,owner_type,owner_id,image_rel_path) "
            "VALUES ('image','entity',?,'assets/images/image.png')",
            (SOURCE_ID,),
        )
        conn.execute(
            "INSERT INTO calendar_config (id,name,config_json,is_active) "
            "VALUES ('calendar','Custom','{"
            "months"
            ":[]}',1)"
        )
        conn.commit()
        originals = {
            table: conn.execute(f"SELECT * FROM {table}").fetchall()
            for table in (
                "entities",
                "events",
                "markers",
                "feature_geometry_states",
                "image_attachments",
                "calendar_config",
            )
        }
    assets = tmp_path / "assets" / "images"
    assets.mkdir(parents=True)
    (assets / "image.png").write_bytes(b"attachment-original")
    service = DatabaseService(str(path))
    service.connect()
    for table, rows in originals.items():
        assert [
            tuple(row) for row in service._connection.execute(f"SELECT * FROM {table}")
        ] == rows
    row = service._connection.execute("SELECT * FROM moving_features").fetchone()
    assert json.loads(row["trajectory"]) == {
        "type": "MovingPoint",
        "coordinates": [[0.1, 0.2], [0.3, 0.4]],
        "datetimes": [0, 2],
    }
    assert row["properties"] == '{"editor":{"version":2},"custom":true}'
    assert (assets / "image.png").read_bytes() == b"attachment-original"
    service.close()


@pytest.mark.parametrize(
    "raw",
    [
        "not-json",
        "[]",
        "[[1,2]]",
        "[[2,0,0],[1,0,0]]",
        "[[0,true,0]]",
        '{"type":"MovingPoint","coordinates":[[0,0]],"datetimes":[]}',
    ],
)
def test_malformed_trajectory_blocks_and_rolls_back_every_step(tmp_path, raw):
    path = legacy_world(tmp_path, "trajectories")
    add_trajectory(path, raw)
    before = database_dump(path)
    service = DatabaseService(str(path))
    with pytest.raises(MigrationError) as failure:
        service.connect()
    assert failure.value.step == steps.MIGRATION_IDS[1]
    assert failure.value.record_ids == ["trajectory"]
    assert not service.is_connected()
    assert database_dump(path) == before
    assert (
        database_dump(Path(failure.value.recovery_path) / "database.kraken") == before
    )


@pytest.mark.parametrize("phase", ["structure", "conversion", "validation", "ledger"])
def test_fault_injection_restores_original_database(tmp_path, monkeypatch, phase):
    path = legacy_world(tmp_path, "trajectories")
    add_trajectory(path)
    before = database_dump(path)

    def fail(*args, **kwargs):
        raise sqlite3.OperationalError("injected failure")

    if phase == "structure":
        original = steps.structural_compatibility

        def partial(conn):
            original(conn)
            fail()

        monkeypatch.setattr(steps, "structural_compatibility", partial)
    elif phase == "conversion":
        original = steps.validate_trajectories

        def partial(conn, *, convert):
            original(conn, convert=convert)
            if convert:
                fail()

        monkeypatch.setattr(steps, "validate_trajectories", partial)
    elif phase == "validation":
        monkeypatch.setattr(steps, "validate_integrity", fail)
    else:
        original = runner._stamp

        def partial(*args):
            original(*args)
            fail()

        monkeypatch.setattr(runner, "_stamp", partial)
    with pytest.raises(MigrationError, match="injected failure"):
        DatabaseService(str(path)).connect()
    assert database_dump(path) == before


def test_commit_failure_rolls_back_schema_and_ledger(tmp_path):
    path = legacy_world(tmp_path)
    before = database_dump(path)

    class FailingCommit(sqlite3.Connection):
        def commit(self):
            raise sqlite3.OperationalError("commit failed")

    with closing(sqlite3.connect(path, factory=FailingCommit)) as conn:
        conn.row_factory = sqlite3.Row
        with pytest.raises(MigrationError) as failure:
            prepare_database(conn, str(path))
        assert failure.value.step == "commit"
        assert not conn.in_transaction
    assert database_dump(path) == before


@pytest.mark.parametrize("failure_kind", ["space", "permissions"])
def test_backup_failure_never_changes_world(tmp_path, monkeypatch, failure_kind):
    path = legacy_world(tmp_path)
    before = database_dump(path)
    if failure_kind == "space":
        monkeypatch.setattr(recovery, "_digest", Mock(side_effect=OSError("disk full")))
    else:
        monkeypatch.setattr(
            recovery,
            "get_backup_directory",
            Mock(side_effect=PermissionError("backup directory unavailable")),
        )
    with pytest.raises(MigrationError, match="disk full|unavailable"):
        DatabaseService(str(path)).connect()
    assert database_dump(path) == before


def test_read_only_legacy_open_is_byte_identical_and_does_not_backup(
    tmp_path, monkeypatch
):
    path = legacy_world(tmp_path)
    before = path.read_bytes()
    monkeypatch.setattr(
        runner, "create_recovery_bundle", Mock(side_effect=AssertionError)
    )
    service = DatabaseService(str(path), read_only=True)
    service.connect()
    assert service.migration_status["detected_version"] == 0
    assert service.migration_status["pending_steps"] == list(steps.MIGRATION_IDS)
    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        service._connection.execute("DELETE FROM events")
    service.close()
    assert path.read_bytes() == before


@pytest.mark.parametrize("corruption", ["future", "ledger", "trigger", "marker"])
def test_current_world_rejects_inconsistent_schema_without_repair(tmp_path, corruption):
    path = tmp_path / "current.kraken"
    service = DatabaseService(str(path))
    service.connect()
    service.close()
    with closing(sqlite3.connect(path)) as conn:
        if corruption == "future":
            conn.execute(
                "UPDATE system_meta SET value='999' WHERE key='schema_version'"
            )
        elif corruption == "ledger":
            conn.execute("UPDATE migration_history SET migration_id='unknown'")
        elif corruption == "trigger":
            conn.execute("DROP TRIGGER cleanup_event_relations")
        else:
            conn.execute("DELETE FROM system_meta WHERE key='schema_version'")
        conn.commit()
    before = database_dump(path)
    with pytest.raises(MigrationError):
        service.connect()
    assert not service.is_connected()
    assert database_dump(path) == before


def test_unrelated_or_partial_database_is_not_adopted(tmp_path):
    path = tmp_path / "unrelated.kraken"
    with closing(sqlite3.connect(path)) as conn:
        conn.execute("CREATE TABLE notes (text TEXT)")
        conn.commit()
    before = database_dump(path)
    with pytest.raises(MigrationError, match="recognized"):
        DatabaseService(str(path)).connect()
    assert database_dump(path) == before


def test_wal_backup_includes_committed_wal_and_excludes_competing_writer(tmp_path):
    path = legacy_world(tmp_path)
    with closing(sqlite3.connect(path)) as other:
        other.execute("PRAGMA journal_mode=WAL")
        other.execute("PRAGMA wal_autocheckpoint=0")
        other.execute("UPDATE events SET name='Committed WAL data'")
        other.commit()
        assert Path(str(path) + "-wal").stat().st_size > 0
        before = database_dump(path)
        other.execute("BEGIN IMMEDIATE")
        with closing(sqlite3.connect(path, timeout=0)) as blocked:
            blocked.row_factory = sqlite3.Row
            with pytest.raises(MigrationError) as failure:
                prepare_database(blocked, str(path))
            assert failure.value.step == "writer_lock"
        other.rollback()
        service = DatabaseService(str(path))
        service.connect()
        bundle = Path(service.migration_status["recovery_path"])
        assert database_dump(bundle / "database.kraken") == before
        assert service.get_event(TARGET_ID).name == "Committed WAL data"
        service.close()


def test_archive_history_and_artifacts_with_external_database(tmp_path):
    database_dir = tmp_path / "external"
    database_dir.mkdir()
    path = legacy_world(database_dir)
    world = tmp_path / "portable-world"
    artifact = world / "assets" / ".history" / "command" / "old.png"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b"recoverable undo image")
    (world / "world.json").write_text(json.dumps({"db_filename": str(path)}))
    payload = json.dumps(
        {
            "artifact_manifest": {
                "assets/images/old.png": "assets/.history/command/old.png",
            }
        }
    )
    with closing(sqlite3.connect(path)) as conn:
        conn.execute(
            "INSERT INTO command_history "
            "(world_id,session_id,command_type,command_data,timestamp) "
            "VALUES ('world','session','DeleteMapCommand',?,1)",
            (payload,),
        )
        conn.commit()
    before = database_dump(path)
    service = DatabaseService(str(path), world_root=world)
    service.connect()
    assert service.migration_status["history_archived"] is True
    bundle = Path(service.migration_status["recovery_path"])
    assert database_dump(bundle / "database.kraken") == before
    assert (
        service._connection.execute("SELECT COUNT(*) FROM command_history").fetchone()[
            0
        ]
        == 0
    )
    assert (
        bundle / "command_artifacts" / "command" / "old.png"
    ).read_bytes() == artifact.read_bytes()
    metadata = json.loads((bundle / "recovery.json").read_text())
    assert metadata["database_path"] == str(path.resolve())
    assert metadata["world_root"] == str(world.resolve())
    assert (bundle / "world.json").read_bytes() == (world / "world.json").read_bytes()
    service.close()


def test_missing_undo_artifact_blocks_backup_and_keeps_history(tmp_path):
    path = legacy_world(tmp_path)
    with closing(sqlite3.connect(path)) as conn:
        conn.execute(
            "INSERT INTO command_history "
            "(world_id,session_id,command_type,command_data,timestamp) "
            "VALUES ('world','session','DeleteMapCommand',?,1)",
            (json.dumps({"artifact_manifest": {"image": "assets/.history/missing"}}),),
        )
        conn.commit()
    before = database_dump(path)
    with pytest.raises(MigrationError, match="Missing saved undo artifact") as failure:
        DatabaseService(str(path)).connect()
    assert failure.value.step == "recovery_backup"
    assert database_dump(path) == before


def test_interrupted_upgrade_rolls_back_and_can_restart(tmp_path):
    path = legacy_world(tmp_path, "trajectories")
    add_trajectory(path)
    before = database_dump(path)
    script = """
import os, sys
from pathlib import Path
from src.services.db_service import DatabaseService
from src.services.migrations import recovery, runner
recovery.get_backup_directory = lambda: Path(sys.argv[2])
original = runner._apply
def interrupted(conn, version):
    result = original(conn, version)
    if version == 2:
        os._exit(17)
    return result
runner._apply = interrupted
DatabaseService(sys.argv[1]).connect()
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(path), str(tmp_path / "backups")],
        timeout=30,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 17, result.stderr
    assert database_dump(path) == before
    service = DatabaseService(str(path))
    service.connect()
    assert service.migration_status["detected_version"] == steps.CURRENT_VERSION
    service.close()


def test_worker_failure_emits_recovery_and_clears_database(qapp, tmp_path):
    path = legacy_world(tmp_path, "trajectories")
    add_trajectory(path, "broken")
    worker = DatabaseWorker(str(path))
    reports, initialized = [], []
    worker.migration_report.connect(reports.append)
    worker.initialized.connect(initialized.append)
    worker.initialize_db()
    assert initialized == [False]
    assert reports[0]["record_ids"] == ["trajectory"]
    assert reports[0]["recovery_path"]
    assert worker.db_service is None
    assert worker.history_service is None
    worker.load_events()
    assert worker.db_service is None
    from src.commands.event_commands import CreateEventCommand

    outcomes = []
    worker.command_finished.connect(outcomes.append)
    worker.run_command(CreateEventCommand())
    assert outcomes and outcomes[0].success is False


@pytest.mark.parametrize("version", [1, 2])
def test_versioned_upgrade_preserves_already_normalized_history(tmp_path, version):
    path = legacy_world(tmp_path)
    with closing(sqlite3.connect(path)) as conn:
        conn.execute(
            "INSERT INTO system_meta VALUES ('wikilink_relations_schema_version','2')"
        )
        conn.execute(runner.LEDGER_SQL)
        for applied in range(1, version + 1):
            runner._stamp(conn, applied, steps.MIGRATION_IDS[applied - 1], "upgraded")
        conn.execute(
            "INSERT INTO command_history "
            "(world_id,session_id,command_type,command_data,timestamp) "
            "VALUES ('world','session','CreateEventCommand','{}',1)"
        )
        conn.commit()
    service = DatabaseService(str(path))
    service.connect()
    assert service.migration_status["upgraded_from"] == version
    assert service.migration_status["history_archived"] is False
    assert (
        service._connection.execute("SELECT COUNT(*) FROM command_history").fetchone()[
            0
        ]
        == 1
    )
    service.close()


def test_new_world_stamps_current_without_replaying_migrations(db_service, monkeypatch):
    from src.services.migrations import inspect_database

    status = inspect_database(db_service.get_connection())
    assert status["pending_steps"] == []
    assert len(status["completed_entries"]) == 1
    assert status["completed_entries"][0]["migration_id"] == "created_current"
    monkeypatch.setattr(runner, "_apply", Mock(side_effect=AssertionError))
    trace = []
    db_service.get_connection().set_trace_callback(trace.append)
    prepare_database(db_service.get_connection(), ":memory:")
    assert not any(
        sql.lstrip()
        .upper()
        .startswith(
            (
                "CREATE",
                "ALTER",
                "DROP",
                "INSERT",
                "UPDATE",
                "DELETE",
            )
        )
        for sql in trace
    )


def test_ambiguous_relation_endpoint_blocks_upgrade(tmp_path):
    path = legacy_world(tmp_path)
    with closing(sqlite3.connect(path)) as conn:
        conn.execute(
            "INSERT INTO entities (id,type,name) VALUES ('duplicate','Place','Source')"
        )
        conn.execute(
            "INSERT INTO relations (id,source_id,target_id,rel_type) "
            "VALUES ('ambiguous','Source',?,'ally')",
            (TARGET_ID,),
        )
        conn.commit()
    before = database_dump(path)
    with pytest.raises(MigrationError, match="Ambiguous"):
        DatabaseService(str(path)).connect()
    assert database_dump(path) == before


def test_caller_transaction_is_not_rolled_back(tmp_path):
    path = legacy_world(tmp_path)
    with closing(sqlite3.connect(path)) as conn:
        conn.execute("UPDATE events SET name='Uncommitted caller edit'")
        with pytest.raises(MigrationError, match="existing transaction"):
            prepare_database(conn, str(path))
        assert conn.in_transaction
        assert (
            conn.execute("SELECT name FROM events").fetchone()[0]
            == "Uncommitted caller edit"
        )
        conn.rollback()


def test_current_schema_contract_damage_is_rejected(tmp_path):
    path = legacy_world(tmp_path)
    with closing(sqlite3.connect(path)) as conn:
        conn.execute("DROP TABLE tags")
        conn.execute("CREATE TABLE tags (id TEXT,name TEXT,color TEXT,created_at REAL)")
        conn.commit()
    before = path.read_bytes()
    with pytest.raises(MigrationError, match="constraint layout"):
        DatabaseService(str(path)).connect()
    assert path.read_bytes() == before


def test_flush_failure_leaves_bundle_incomplete(
    tmp_path, monkeypatch, recovery_directory
):
    path = legacy_world(tmp_path)
    before = database_dump(path)
    monkeypatch.setattr(recovery.os, "fsync", Mock(side_effect=OSError("flush failed")))
    with pytest.raises(MigrationError, match="flush failed"):
        DatabaseService(str(path)).connect()
    bundles = list((recovery_directory / "migrations").iterdir())
    assert bundles and not (bundles[0] / "recovery.json").exists()
    assert database_dump(path) == before


def test_attachment_undo_trash_is_verified_and_archived(tmp_path):
    path = legacy_world(tmp_path)
    trash = tmp_path / "assets/.trash/deleted/image.png"
    trash.parent.mkdir(parents=True)
    trash.write_bytes(b"deleted attachment needed by undo")
    with closing(sqlite3.connect(path)) as conn:
        conn.execute(
            "INSERT INTO command_history "
            "(world_id,session_id,command_type,command_data,timestamp) "
            "VALUES ('world','session','DeleteImageCommand',?,1)",
            (
                json.dumps(
                    {
                        "trash_info": {
                            "img_trash_path": "assets/.trash/deleted/image.png"
                        }
                    }
                ),
            ),
        )
        conn.commit()
    service = DatabaseService(str(path))
    service.connect()
    bundle = Path(service.migration_status["recovery_path"])
    assert (
        bundle / "trashed_assets/deleted/image.png"
    ).read_bytes() == trash.read_bytes()
    assert service.migration_status["history_archived"] is True
    service.close()
