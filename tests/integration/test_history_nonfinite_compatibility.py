"""Unlimited zoom remains restorable without losing existing command history."""

import json
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from src.commands.layer_commands import (
    UpdateLayerPropertiesCommand,
    UpdateLayerTreeCommand,
)
from src.core.map import Map, MapLayerNode
from src.services.db_service import DatabaseService
from src.services.history_store import HistoryStore
from src.services.migrations import MigrationError, recovery, runner, steps
from src.services.migrations.command_history import upgrade_history_identity_index
from src.services.migrations.schema import (
    HISTORY_COMMAND_ID_EXPRESSION,
    LEGACY_HISTORY_COMMAND_ID_INDEX_SQL,
)
from tests.integration.test_ordered_history import close_session, open_session

pytestmark = [pytest.mark.integration, pytest.mark.ci_fast]


def legacy_world(tmp_path, monkeypatch):
    monkeypatch.setattr(recovery, "get_backup_directory", lambda: tmp_path / "backups")
    path = tmp_path / "world.kraken"
    db, worker, coordinator, results = open_session(path)
    root = MapLayerNode(
        "Layers",
        id="root",
        children=[
            MapLayerNode("A", id="a"),
            MapLayerNode("B", id="b"),
        ],
    )
    db.insert_map(Map("Map", "map.png", id="map", layers=root))
    command = UpdateLayerPropertiesCommand("map", "a", {"name": "Renamed"})
    coordinator.execute_command(command)
    assert results[-1].success
    # Reproduce the actual version-six writer's raw unlimited-zoom snapshot.
    payload = json.loads(
        db.require_connection()
        .execute("SELECT command_data FROM command_history")
        .fetchone()[0]
    )
    payload["previous"]["max_zoom"] = float("inf")
    serialized = json.dumps(payload)
    with db.transaction() as conn:
        conn.execute("UPDATE command_history SET command_data=?", (serialized,))
    close_session(db, worker)
    with closing(sqlite3.connect(path)) as conn:
        conn.execute("DROP INDEX idx_ch_world_identity")
        conn.execute(LEGACY_HISTORY_COMMAND_ID_INDEX_SQL)
        conn.execute("DELETE FROM migration_history")
        runner._stamp(conn, 6, "created_current", "created")
        conn.commit()
    return path, serialized, command.command_id


def test_new_property_snapshots_are_strict_json_and_unlimited_zoom_is_lossless(
    db_service,
):
    root = MapLayerNode("Root", id="root")
    db_service.insert_map(Map("Map", "map.png", id="map", layers=root))
    command = UpdateLayerPropertiesCommand(
        "map", "root", {"max_zoom": float("inf"), "name": "New"}
    )
    assert command.execute(db_service).success
    encoded = json.loads(json.dumps(command.to_dict(), allow_nan=False))
    assert encoded["previous"]["max_zoom"] is None
    assert encoded["properties"]["max_zoom"] is None
    restored = UpdateLayerPropertiesCommand.from_dict(encoded)
    assert restored.properties["max_zoom"] == float("inf")
    restored.undo(db_service)
    assert db_service.get_map("map").layers.max_zoom == float("inf")
    assert db_service.get_map("map").layers.name == "Root"
    assert restored.execute(db_service).success
    assert db_service.get_map("map").layers.max_zoom == float("inf")


def test_upgrade_preserves_history_then_reorder_reopen_undo_redo(
    tmp_path, monkeypatch, qapp
):
    path, payload, identity = legacy_world(tmp_path, monkeypatch)
    with closing(sqlite3.connect(path)) as conn:
        before = conn.execute("SELECT * FROM command_history").fetchall()
        manifest = conn.execute(
            "SELECT key,value FROM system_meta WHERE key LIKE 'command_history_stacks_v2:%'"
        ).fetchall()
    db, worker, coordinator, results = open_session(path)
    assert db.migration_status["upgraded_from"] == 6
    assert not db.migration_status["history_archived"]
    conn = db.require_connection()
    assert [
        tuple(row) for row in conn.execute("SELECT * FROM command_history")
    ] == before
    assert [
        tuple(row)
        for row in conn.execute(
            "SELECT key,value FROM system_meta WHERE key LIKE 'command_history_stacks_v2:%'"
        )
    ] == manifest
    assert list(HistoryStore(conn, "world").rows()) == [identity]
    assert len(coordinator.undo_stack) == 1
    plan = conn.execute(
        f"EXPLAIN QUERY PLAN SELECT * FROM command_history WHERE world_id=? AND {HISTORY_COMMAND_ID_EXPRESSION} IN (?)",
        ("world", identity),
    ).fetchall()
    assert any("idx_ch_world_identity" in row[3] and "<expr>" in row[3] for row in plan)
    recovery_path = Path(db.migration_status["recovery_path"])
    with closing(sqlite3.connect(recovery_path / "database.kraken")) as old:
        assert (
            old.execute("SELECT command_data FROM command_history").fetchone()[0]
            == payload
        )
    root = db.get_map("map").layers
    root.children.reverse()
    coordinator.execute_command(UpdateLayerTreeCommand("map", root.to_dict()))
    assert results[-1].success
    close_session(db, worker)
    db, worker, coordinator, results = open_session(path)
    assert len(coordinator.undo_stack) == 2
    coordinator.undo()
    assert results[-1].success
    assert [node.id for node in db.get_map("map").layers.children] == ["a", "b"]
    coordinator.undo()
    assert results[-1].success
    assert db.get_map("map").layers.children[0].name == "A"
    assert db.get_map("map").layers.children[0].max_zoom == float("inf")
    close_session(db, worker)
    db, worker, coordinator, results = open_session(path)
    assert len(coordinator.redo_stack) == 2
    coordinator.redo()
    coordinator.redo()
    assert all(result.success for result in results)
    assert [node.id for node in db.get_map("map").layers.children] == ["b", "a"]
    assert db.get_map("map").layers.children[1].name == "Renamed"
    close_session(db, worker)


def test_read_only_v6_lookup_preserves_file_and_history(tmp_path, monkeypatch, qapp):
    path, payload, identity = legacy_world(tmp_path, monkeypatch)
    before = path.read_bytes()
    db = DatabaseService(str(path), read_only=True)
    db.connect()
    assert list(HistoryStore(db.require_connection(), "world").rows()) == [identity]
    assert (
        db.require_connection()
        .execute("SELECT command_data FROM command_history")
        .fetchone()[0]
        == payload
    )
    db.close()
    assert path.read_bytes() == before


def test_identity_upgrade_failure_rolls_back_without_reset(tmp_path, monkeypatch, qapp):
    path, payload, identity = legacy_world(tmp_path, monkeypatch)
    stamp = runner._stamp

    def fail(conn, version, *args):
        if version == steps.HISTORY_IDENTITY_VERSION:
            raise RuntimeError("index upgrade failure")
        stamp(conn, version, *args)

    monkeypatch.setattr(runner, "_stamp", fail)
    with pytest.raises(MigrationError, match="index upgrade failure"):
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
            == "6"
        )
        assert (
            "json_valid(command_data, 2)"
            not in conn.execute(
                "SELECT sql FROM sqlite_master WHERE name='idx_ch_world_identity'"
            ).fetchone()[0]
        )
        conn.row_factory = sqlite3.Row
        assert list(HistoryStore(conn, "world").rows()) == [identity]


def test_index_handles_malformed_archive_but_still_rejects_missing_active_record(
    db_service,
):
    with db_service.transaction() as conn:
        conn.execute(
            "INSERT INTO command_history(world_id,session_id,command_type,command_data,timestamp) "
            "VALUES ('world','session','Archived','{invalid archive',0)"
        )
        upgrade_history_identity_index(conn)
        store = HistoryStore(conn, "world")
        store.boundary()
        assert store.rows() == {}
        store.write({"version": 2, "undo": ["missing"], "redo": []})
        with pytest.raises(ValueError, match="missing command records"):
            store.rows()
