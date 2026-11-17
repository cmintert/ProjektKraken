"""Restart, branching and atomicity through real worker/coordinator boundaries."""

import json
import sqlite3
from types import SimpleNamespace

import pytest

from src.app.command_coordinator import CommandCoordinator
from src.commands.base_command import BaseCommand, CommandResult
from src.commands.map_crud_commands import CreateMapCommand, UpdateMapCommand
from src.commands.map_hierarchy_commands import ChangeMapParentCommand
from src.commands.map_reparent_commands import PreserveMapPlacementCommand
from src.commands.registry import get_command_types
from src.core.map import Map
from src.services.command_artifact_store import CommandArtifactStore
from src.services.command_execution import execute_with_history
from src.services.command_transactions import after_command, command_transaction
from src.services.db_service import DatabaseService
from src.services.history_service import HistoryService
from src.services.history_store import HistoryStore
from src.services.map_reparenting import plan_preserved_reparent
from src.services.migrations.schema import HISTORY_COMMAND_ID_EXPRESSION
from src.services.raster_asset_service import RasterAssetService
from src.services.worker import DatabaseWorker

pytestmark = [pytest.mark.integration, pytest.mark.ci_fast]


def registration():
    return {
        "mode": "aspect_locked_affine",
        "version": 1,
        "master_center_norm": {"x": 0.3, "y": 0.4},
        "scale_norm": 0.2,
        "aspect_ratio": 1.5,
        "rotation_deg": 20,
    }


def open_session(path):
    db = DatabaseService(str(path))
    db.connect()
    worker = DatabaseWorker(str(path), get_command_types())
    worker.db_service = db
    coordinator = CommandCoordinator(SimpleNamespace(current_world=None))
    worker.history_loaded.connect(coordinator.load_history_payloads)
    worker.initialize_history("world")
    worker.command_finished.connect(coordinator.on_command_result)
    coordinator.command_requested.connect(worker.run_command)
    coordinator.undo_requested.connect(worker.run_undo)
    coordinator.redo_requested.connect(worker.run_redo)
    results = []
    worker.command_finished.connect(results.append)
    return db, worker, coordinator, results


def close_session(db, worker):
    worker.db_service = None
    worker.history_service = None
    db.close()


def test_attach_subtree_reopen_undo_reopen_redo(tmp_path, qapp):
    path = tmp_path / "world.kraken"
    db, worker, coordinator, results = open_session(path)
    records = [
        Map("A", "a.png", id="a", attributes={"notes": "retain"}),
        Map(
            "A1",
            "a1.png",
            id="a1",
            attributes={"parent_map_id": "a", "registration": registration()},
        ),
        Map(
            "A2",
            "a2.png",
            id="a2",
            attributes={"parent_map_id": "a", "registration": registration()},
        ),
        Map("B", "b.png", id="b"),
        Map(
            "B1",
            "b1.png",
            id="b1",
            attributes={"parent_map_id": "b", "registration": registration()},
        ),
    ]
    for record in records:
        db.insert_map(record)
    before = db.get_map("a1").to_dict()
    coordinator.execute_command(ChangeMapParentCommand("a", "b1", registration()))
    assert results[-1].success
    close_session(db, worker)
    db, worker, coordinator, results = open_session(path)
    assert len(coordinator.undo_stack) == 1
    coordinator.undo()
    assert results[-1].success
    assert db.get_map("a").attributes == {"notes": "retain"}
    close_session(db, worker)
    db, worker, coordinator, results = open_session(path)
    assert not coordinator.undo_stack and len(coordinator.redo_stack) == 1
    coordinator.redo()
    assert results[-1].success
    assert db.get_map("a").attributes["parent_map_id"] == "b1"
    assert db.get_map("a1").to_dict() == before
    close_session(db, worker)


def test_preserve_placement_reopen_undo_reopen_redo(tmp_path, qapp):
    from tests.unit.test_map_reparenting import assert_invariant, records

    path = tmp_path / "preserved.kraken"
    db, worker, coordinator, results = open_session(path)
    original = records()
    for record in original:
        db.insert_map(record)
    plan = plan_preserved_reparent(original, "move", "new")
    coordinator.execute_command(
        PreserveMapPlacementCommand("move", "new", plan.expected_context)
    )
    assert results[-1].success
    saved = db.get_map("move").to_dict()
    assert_invariant(original, db.get_all_maps())
    close_session(db, worker)
    db, worker, coordinator, results = open_session(path)
    try:
        assert len(coordinator.undo_stack) == 1
        coordinator.undo()
        assert results[-1].success
        assert db.get_map("move").to_dict() == original[3].to_dict()
    finally:
        close_session(db, worker)
    db, worker, coordinator, results = open_session(path)
    try:
        assert len(coordinator.redo_stack) == 1
        coordinator.redo()
        assert results[-1].success
        assert db.get_map("move").to_dict() == saved
        assert_invariant(original, db.get_all_maps())
    finally:
        close_session(db, worker)


def test_multiple_undos_and_divergence_never_resurrect_redo(tmp_path, qapp):
    path = tmp_path / "world.kraken"
    db, worker, coordinator, results = open_session(path)
    for key in "abc":
        db.insert_map(Map(key, f"{key}.png", id=key))
    coordinator.execute_command(ChangeMapParentCommand("a", "b", registration()))
    coordinator.execute_command(ChangeMapParentCommand("a", "c", registration()))
    coordinator.undo()
    coordinator.undo()
    assert all(r.success for r in results)
    close_session(db, worker)
    db, worker, coordinator, results = open_session(path)
    assert len(coordinator.redo_stack) == 2
    coordinator.redo()
    assert db.get_map("a").attributes["parent_map_id"] == "b"
    coordinator.execute_command(ChangeMapParentCommand("a", None, None))
    close_session(db, worker)
    db, worker, coordinator, results = open_session(path)
    assert len(coordinator.undo_stack) == 2 and not coordinator.redo_stack
    close_session(db, worker)


@pytest.mark.parametrize("action", ["execute", "undo", "redo"])
def test_history_failure_rolls_back_effects_and_stack(db_service, monkeypatch, action):
    for key in "ab":
        db_service.insert_map(Map(key, f"{key}.png", id=key))
    history = HistoryService(db_service, "world")
    command = ChangeMapParentCommand("a", "b", registration())
    if action != "execute":
        assert execute_with_history(db_service, history, command, "execute").success
    if action == "redo":
        assert execute_with_history(db_service, history, command, "undo").success
    before = db_service.get_map("a").to_dict()
    manifest = HistoryStore(db_service.require_connection(), "world").read()
    executed = command.is_executed

    def fail(*args):
        raise sqlite3.OperationalError("injected manifest failure")

    monkeypatch.setattr(HistoryStore, "write", fail)
    with pytest.raises(sqlite3.OperationalError):
        execute_with_history(db_service, history, command, action)
    assert db_service.get_map("a").to_dict() == before
    assert HistoryStore(db_service.require_connection(), "world").read() == manifest
    assert command.is_executed == executed


def test_invalid_active_history_is_not_partially_loaded(tmp_path, qapp):
    db, worker, coordinator, _ = open_session(tmp_path / "world.kraken")
    for key in "ab":
        db.insert_map(Map(key, f"{key}.png", id=key))
    coordinator.execute_command(ChangeMapParentCommand("a", "b", registration()))
    with db.transaction() as conn:
        conn.execute("UPDATE command_history SET command_type='Unsupported'")
    errors = []
    worker.error_occurred.connect(errors.append)
    worker.initialize_history("world")
    assert not coordinator.undo_stack and not coordinator.redo_stack
    assert errors and db.get_map("a").attributes["parent_map_id"] == "b"
    close_session(db, worker)


class SessionCommand(BaseCommand):
    """A session-only action provides a conservative restart boundary."""

    @property
    def persist_to_history(self):
        return False

    def execute(self, db_service):
        self._is_executed = True
        return CommandResult(True)

    def undo(self, db_service):
        self._is_executed = False

    def to_dict(self):
        return {}

    @classmethod
    def from_dict(cls, data):
        return cls()


def test_session_only_boundary_and_safe_newer_suffix(db_service):
    for key in "abc":
        db_service.insert_map(Map(key, f"{key}.png", id=key))
    history = HistoryService(db_service, "world")
    history.register_command_type("ChangeMapParentCommand", ChangeMapParentCommand)
    old = ChangeMapParentCommand("a", "b", registration())
    assert execute_with_history(db_service, history, old, "execute").success
    session = SessionCommand()
    assert execute_with_history(db_service, history, session, "execute").success
    assert history.load_stacks() == {"undo": [], "redo": []}
    new = ChangeMapParentCommand("a", "c", registration())
    assert execute_with_history(db_service, history, new, "execute").success
    assert len(history.load_stacks()["undo"]) == 1
    assert execute_with_history(db_service, history, new, "undo").success
    assert execute_with_history(db_service, history, session, "undo").success
    assert execute_with_history(db_service, history, old, "undo").success
    assert history.load_stacks() == {"undo": [], "redo": []}


def test_compensation_waits_for_history_commit(db_service, monkeypatch):
    history = HistoryService(db_service, "world")
    command = SessionCommand()
    calls = []
    command.on_transaction_committed = lambda: calls.append("committed")
    command.on_transaction_rolled_back = lambda: calls.append("rolled back")

    def fail(*args):
        assert calls == []
        raise RuntimeError("history failed")

    monkeypatch.setattr(history, "record_transition", fail)
    with pytest.raises(RuntimeError):
        execute_with_history(db_service, history, command, "execute")
    assert calls == ["rolled back"]


def test_stack_limit_and_clear(db_service):
    history = HistoryService(db_service, "world")
    history.register_command_type("ChangeMapParentCommand", ChangeMapParentCommand)
    db_service.insert_map(Map("A", "a.png", id="a"))
    commands = [ChangeMapParentCommand("a", None, None) for _ in range(105)]
    for command in commands:
        assert execute_with_history(db_service, history, command, "execute").success
    assert len(history.load_stacks()["undo"]) == 100
    assert history.clear_all_history() == 105
    assert history.load_stacks() == {"undo": [], "redo": []}


def test_failed_history_restores_map_asset_and_retry_state(tmp_path, monkeypatch):
    db = DatabaseService(str(tmp_path / "world.kraken"))
    db.connect()
    source = tmp_path / "source.png"
    source.write_bytes(b"authored image")
    history = HistoryService(db, "world")
    command = CreateMapCommand(
        {"name": "Map", "image_path": "assets/map.png"}, str(source)
    )
    original = history.record_transition

    def fail(*args):
        raise RuntimeError("injected history failure")

    monkeypatch.setattr(history, "record_transition", fail)
    with pytest.raises(RuntimeError):
        execute_with_history(db, history, command, "execute")
    assert not (tmp_path / "assets/map.png").exists()
    assert source.read_bytes() == b"authored image"
    assert not command.is_executed
    monkeypatch.setattr(history, "record_transition", original)
    assert execute_with_history(db, history, command, "execute").success
    assert (tmp_path / "assets/map.png").read_bytes() == b"authored image"
    db.close()


def test_outer_failure_restores_replaced_and_stashed_files(tmp_path, db_service):
    target = tmp_path / "rasters/old.bin"
    target.parent.mkdir()
    target.write_bytes(b"original")
    with pytest.raises(RuntimeError):
        with command_transaction(db_service):
            artifacts = CommandArtifactStore(tmp_path)
            artifacts.stash("test-command", ["rasters/old.bin"])
            RasterAssetService(tmp_path).atomic_write_bytes("rasters/old.bin", b"new")
            raise RuntimeError("history failure")
    assert target.read_bytes() == b"original"
    assert not list((tmp_path / "assets/.history").rglob("*.bin"))


def test_pruning_keeps_only_reachable_recent_suffix(db_service):
    history = HistoryService(db_service, "world")
    history.register_command_type("ChangeMapParentCommand", ChangeMapParentCommand)
    db_service.insert_map(Map("A", "a.png", id="a"))
    execute_with_history(
        db_service, history, ChangeMapParentCommand("a", None, None), "execute"
    )
    recent = HistoryService(db_service, "world")
    recent.register_command_type("ChangeMapParentCommand", ChangeMapParentCommand)
    execute_with_history(
        db_service, recent, ChangeMapParentCommand("a", None, None), "execute"
    )
    assert recent.clear_history(keep_sessions=1) == 1
    assert len(recent.load_stacks()["undo"]) == 1


def test_foreign_world_snapshot_cannot_replace_history(qapp):
    coordinator = CommandCoordinator(
        SimpleNamespace(current_world=SimpleNamespace(id="current"))
    )
    command = ChangeMapParentCommand("a", None, None)
    coordinator.undo_stack.append(command)
    coordinator.load_history_payloads({"world_id": "previous", "undo": [], "redo": []})
    assert coordinator.undo_stack == [command]


def test_missing_manifest_is_visible_failure_not_silent_history_loss(db_service):
    history = HistoryService(db_service, "world")
    db_service.insert_map(Map("A", "a.png", id="a"))
    execute_with_history(
        db_service, history, ChangeMapParentCommand("a", None, None), "execute"
    )
    with db_service.transaction() as conn:
        conn.execute(
            "DELETE FROM system_meta WHERE key LIKE 'command_history_stacks_v2:%'"
        )
    with pytest.raises(ValueError, match="manifest is missing"):
        history.load_stacks()


def test_mixed_map_commands_restore_both_stacks_after_reopening(tmp_path, qapp):
    path = tmp_path / "mixed.kraken"
    db, worker, coordinator, results = open_session(path)
    db.insert_map(Map("B", "b.png", id="b"))
    coordinator.execute_command(
        CreateMapCommand({"name": "A", "image_path": "a.png", "id": "a"})
    )
    coordinator.execute_command(ChangeMapParentCommand("a", "b", registration()))
    coordinator.execute_command(
        UpdateMapCommand("a", {"name": "Renamed", "attributes": {"notes": "authored"}})
    )
    assert all(r.success for r in results)
    close_session(db, worker)

    db, worker, coordinator, results = open_session(path)
    coordinator.undo()
    assert results[-1].success and db.get_map("a").name == "A"
    assert db.get_map("a").attributes["parent_map_id"] == "b"
    coordinator.undo()
    coordinator.undo()
    assert results[-1].success and db.get_map("a") is None
    close_session(db, worker)
    db, worker, coordinator, results = open_session(path)
    assert len(coordinator.redo_stack) == 3
    for _ in range(3):
        coordinator.redo()
        assert results[-1].success
    assert db.get_map("a").name == "Renamed"
    assert db.get_map("a").attributes["notes"] == "authored"
    assert db.get_map("a").attributes["parent_map_id"] == "b"
    close_session(db, worker)


@pytest.mark.parametrize("independent_replacement", [False, True])
def test_hook_failure_still_recovers_safe_files(
    db_service, tmp_path, monkeypatch, independent_replacement
):
    import src.services.command_transactions as transactions

    make_temporary = transactions.tempfile.mkdtemp
    monkeypatch.setattr(
        transactions.tempfile,
        "mkdtemp",
        lambda **kwargs: make_temporary(dir=tmp_path, **kwargs),
    )
    assets = RasterAssetService(tmp_path)
    for name in ("a", "b"):
        assets.atomic_write_bytes(f"{name}.bin", f"original {name}".encode())

    def fail_hook():
        raise OSError("rollback hook failed")

    with pytest.raises(OSError, match="rollback hook failed"):
        with command_transaction(db_service):
            after_command(lambda: None, fail_hook)
            for name in ("a", "b"):
                assets.atomic_write_bytes(f"{name}.bin", b"owned change")
            if independent_replacement:
                (tmp_path / "a.bin").write_bytes(b"independent replacement")
            raise RuntimeError("history failed")
    assert (tmp_path / "b.bin").read_bytes() == b"original b"
    expected = b"independent replacement" if independent_replacement else b"original a"
    assert (tmp_path / "a.bin").read_bytes() == expected
    assert list(tmp_path.glob("kraken-command-*/recovery.json"))


def test_rollback_hook_failure_restores_command_retry_state(db_service):
    class FailingCompensation(CreateMapCommand):
        def on_transaction_rolled_back(self):
            raise OSError("rollback hook failed")

    command = FailingCompensation(
        {"name": "Retry", "image_path": "retry.png", "id": "retry"}
    )
    with pytest.raises(OSError, match="rollback hook failed"):
        with command_transaction(db_service, restore_retry_state=True):
            assert command.execute(db_service).success
            assert command.is_executed
            raise RuntimeError("history failed")
    assert not command.is_executed
    assert db_service.get_map("retry") is None


@pytest.mark.parametrize("operation", ["stash", "restore"])
def test_failed_artifact_compensation_keeps_outer_rollback_consistent(
    db_service, tmp_path, operation
):
    assets = RasterAssetService(tmp_path)
    store = CommandArtifactStore(tmp_path)
    relative_path = "maps/raster.bin"
    target = tmp_path / relative_path
    assets.atomic_write_bytes(relative_path, b"original")
    manifest = {}
    if operation == "restore":
        manifest = store.stash("command", [relative_path])
        assert not target.exists()
    if operation == "stash":
        with pytest.raises(ValueError, match="Path escapes world root"):
            with command_transaction(db_service):
                assets.atomic_write_bytes(relative_path, b"replacement")
                store.stash("command", [relative_path, "../escape"])
        assert target.read_bytes() == b"original"
    else:
        artifact_path = tmp_path / manifest[relative_path]
        with pytest.raises(ValueError, match="Path escapes world root"):
            with command_transaction(db_service):
                assets.atomic_write_bytes(manifest[relative_path], b"replacement")
                store.restore({**manifest, "../escape": manifest[relative_path]})
        assert not target.exists()
        assert artifact_path.read_bytes() == b"original"


def test_active_history_lookup_is_indexed_and_decoding_is_bounded(
    db_service, monkeypatch
):
    import src.services.history_store as history_module

    history = HistoryService(db_service, "world")
    db_service.insert_map(Map("A", "a.png", id="a"))
    command = ChangeMapParentCommand("a", None, None)
    assert execute_with_history(db_service, history, command, "execute").success
    with db_service.transaction() as conn:
        conn.executemany(
            "INSERT INTO command_history (world_id,session_id,command_type,command_data,timestamp) "
            "VALUES ('world',?,'Archived',?,0)",
            [
                (
                    history.session_id,
                    json.dumps({"_command_base": {"command_id": f"old-{i}"}}),
                )
                for i in range(3000)
            ],
        )
    decoded = []
    original_loads = json.loads

    def counted_loads(value):
        decoded.append(value)
        return original_loads(value)

    monkeypatch.setattr(
        history_module, "json", SimpleNamespace(loads=counted_loads, dumps=json.dumps)
    )
    conn = db_service.require_connection()
    rows = HistoryStore(conn, "world").rows()
    assert list(rows) == [command.command_id]
    assert len(decoded) == 2  # One manifest and the one active payload.
    plan = conn.execute(
        f"EXPLAIN QUERY PLAN SELECT * FROM command_history WHERE world_id=? "
        f"AND {HISTORY_COMMAND_ID_EXPRESSION} IN (?)",
        ("world", command.command_id),
    ).fetchall()
    assert any("idx_ch_world_identity" in row[3] for row in plan)
