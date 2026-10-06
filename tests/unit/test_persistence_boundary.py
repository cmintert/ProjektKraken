"""Regression coverage for strict connection access and Longform atomicity."""

import sqlite3
from argparse import Namespace
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.cli import index as index_cli
from src.commands.composite_command import CompositeCommand
from src.commands.longform_commands import MoveLongformEntryCommand
from src.core.entities import Entity
from src.services import longform_builder, tag_filter
from src.services.db_service import DatabaseService
from src.services.history_service import HistoryService
from src.services.worker import DatabaseWorker
from src.webserver.config import ServerConfig
from src.webserver.server import create_app

pytestmark = pytest.mark.ci_fast


def test_strict_connection_lifecycle(db_service):
    service = DatabaseService()
    with patch.object(service, "connect") as connect:
        with pytest.raises(RuntimeError, match="not connected"):
            service.require_connection()
        connect.assert_not_called()
    assert db_service.require_connection() is db_service.get_connection()
    db_service.close()
    with pytest.raises(RuntimeError, match="not connected"):
        db_service.require_connection()
    # Lazy compatibility access reopens, with ownership re-established.
    assert db_service.get_connection().execute("SELECT 1").fetchone()[0] == 1


def test_failed_connection_leaves_strict_access_disconnected(db_service):
    db_service.close()
    with patch("src.services.db_service.prepare_database", side_effect=ValueError):
        with pytest.raises(ValueError):
            db_service.connect()
    assert not db_service.is_connected()
    with pytest.raises(RuntimeError, match="not connected"):
        db_service.require_connection()
    db_service.connect()
    assert db_service.require_connection()


@pytest.mark.parametrize("operation", ["require", "lazy", "transaction", "connect"])
def test_connection_boundary_rejects_foreign_thread(db_service, operation):
    def access():
        if operation == "require":
            return db_service.require_connection()
        if operation == "lazy":
            return db_service.get_connection()
        if operation == "connect":
            return db_service.connect()
        with db_service.transaction():
            pass

    with ThreadPoolExecutor(max_workers=1) as executor:
        with pytest.raises(RuntimeError, match="another thread"):
            executor.submit(access).result()
    assert db_service.require_connection().execute("SELECT 1").fetchone()[0] == 1


def test_metadata_reader_is_detached_and_validates_inputs(db_service):
    entity = Entity(name="Metadata", type="test")
    db_service.insert_entity(entity)
    conn = db_service.require_connection()
    assert longform_builder.get_longform_meta(conn, "entities", entity.id) == {}
    assert longform_builder.get_longform_meta(conn, "entities", "missing") == {}
    with db_service.transaction():
        longform_builder.insert_or_update_longform_meta(
            conn, "entities", entity.id, position=123, title_override="Authored"
        )
    meta = longform_builder.get_longform_meta(conn, "entities", entity.id)
    meta["position"] = -1
    assert (
        longform_builder.get_longform_meta(conn, "entities", entity.id)["position"]
        == 123
    )
    assert (
        longform_builder.get_longform_meta(conn, "entities", entity.id, "other") == {}
    )
    with pytest.raises(ValueError, match="Invalid table"):
        longform_builder.get_longform_meta(conn, "entities; DROP TABLE entities", "x")
    with pytest.raises(ValueError, match="doc_id"):
        longform_builder.get_longform_meta(conn, "entities", "missing", "../bad")


@pytest.mark.parametrize("operation", ["update", "remove"])
def test_helpers_preserve_outer_rollback_and_unrelated_writes(db_service, operation):
    entity = Entity(name="Before", type="test")
    db_service.insert_entity(entity)
    conn = db_service.require_connection()
    with db_service.transaction():
        longform_builder.insert_or_update_longform_meta(
            conn, "entities", entity.id, position=100
        )
    before = db_service.get_entity(entity.id).to_dict()
    with pytest.raises(RuntimeError, match="later failure"):
        with db_service.transaction():
            conn.execute("UPDATE entities SET name='After' WHERE id=?", (entity.id,))
            if operation == "update":
                longform_builder.insert_or_update_longform_meta(
                    conn, "entities", entity.id, position=200
                )
            else:
                longform_builder.remove_from_longform(conn, "entities", entity.id)
            assert conn.in_transaction
            raise RuntimeError("later failure")
    assert db_service.get_entity(entity.id).to_dict() == before


def test_longform_command_undo_redo_and_composite_failure(db_service):
    entity = Entity(name="Outline", type="test")
    db_service.insert_entity(entity)
    conn = db_service.require_connection()
    old = {"position": 100, "depth": 0, "parent_id": None, "title_override": "Old"}
    with db_service.transaction():
        longform_builder.insert_or_update_longform_meta(
            conn, "entities", entity.id, **old
        )
    command = MoveLongformEntryCommand(
        "entities", entity.id, old, {**old, "position": 200}
    )
    assert command.execute(db_service).success
    assert not conn.in_transaction
    command.undo(db_service)
    assert longform_builder.get_longform_meta(conn, "entities", entity.id) == old
    assert command.execute(db_service).success
    command.undo(db_service)
    missing = MoveLongformEntryCommand("entities", "missing", {}, {"position": 300})
    result = CompositeCommand([command, missing]).execute(db_service)
    assert not result.success
    assert longform_builder.get_longform_meta(conn, "entities", entity.id) == old


def test_reindex_partial_failure_rolls_back_all_records(db_service):
    entities = [Entity(name=name, type="test") for name in ("First", "Second")]
    for entity in entities:
        db_service.insert_entity(entity)
    conn = db_service.require_connection()
    with db_service.transaction():
        for entity, position in zip(entities, (250, 750)):
            longform_builder.insert_or_update_longform_meta(
                conn, "entities", entity.id, position=position
            )
    before = [db_service.get_entity(entity.id).to_dict() for entity in entities]
    original = longform_builder.insert_or_update_longform_meta
    calls = 0

    def fail_second(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("second write failed")
        return original(*args, **kwargs)

    with patch.object(longform_builder, "insert_or_update_longform_meta", fail_second):
        with pytest.raises(RuntimeError, match="second write"):
            with db_service.transaction():
                conn.execute("UPDATE entities SET name='Temporary'")
                longform_builder.reindex_document_positions(conn)
    assert calls == 2
    assert [db_service.get_entity(entity.id).to_dict() for entity in entities] == before


def test_history_reads_do_not_reopen_disconnected_service(db_service):
    history = HistoryService(db_service, "review-world")
    db_service.close()
    with patch.object(db_service, "connect") as connect:
        assert history.load_recent_history() == []
        assert history.get_history_stats() == {}
        connect.assert_not_called()


def test_tag_filter_accepts_connection_or_service_without_reopening(db_service):
    entity = Entity(name="Tagged", type="test")
    db_service.insert_entity(entity)
    expected = [("entity", entity.id)]
    assert tag_filter.filter_object_ids(db_service) == expected
    assert tag_filter.filter_object_ids(db_service.require_connection()) == expected
    db_service.close()
    with patch.object(db_service, "connect") as connect:
        with pytest.raises(ValueError, match="not connected"):
            tag_filter.filter_object_ids(db_service)
        connect.assert_not_called()
    with pytest.raises(ValueError, match="Invalid argument"):
        tag_filter.filter_object_ids(object())


def test_explicit_indexing_commits_and_rolls_back(db_service, qapp):
    entity = Entity(name="Worker outline", type="test")
    db_service.insert_entity(entity)
    worker = DatabaseWorker(":memory:")
    worker.db_service = db_service
    results = []
    errors = []
    worker.longform_sequence_loaded.connect(results.append)
    worker.error_occurred.connect(errors.append)
    worker.load_longform_sequence("default")
    assert results == [[]]
    with db_service.transaction() as conn:
        longform_builder.ensure_all_items_indexed(conn)
    worker.load_longform_sequence("default")
    assert results and results[-1][0]["id"] == entity.id
    assert not db_service.require_connection().in_transaction
    with db_service.transaction() as conn:
        longform_builder.remove_from_longform(conn, "entities", entity.id)
    original = longform_builder.insert_or_update_longform_meta

    def fail_after_write(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("index failed")

    with patch.object(
        longform_builder, "insert_or_update_longform_meta", fail_after_write
    ):
        with pytest.raises(RuntimeError, match="index failed"):
            with db_service.transaction() as conn:
                longform_builder.ensure_all_items_indexed(conn)
    worker.load_longform_sequence("default")
    assert results[-1] == []
    assert not errors
    assert (
        longform_builder.get_longform_meta(
            db_service.require_connection(), "entities", entity.id
        )
        == {}
    )


def test_webserver_longform_reads_leave_world_unchanged(db_service, tmp_path):
    entity = Entity(name="Web outline", type="test")
    db_service.insert_entity(entity)
    path = tmp_path / "web.kraken"
    with closing(sqlite3.connect(path)) as destination:
        db_service.require_connection().backup(destination)
    before = path.read_bytes()
    app = create_app(ServerConfig(db_path=str(path)))
    with TestClient(app, headers={"host": "localhost"}) as client:
        assert client.get("/api/longform").status_code == 200
        assert client.get("/api/toc").status_code == 200
        assert client.get("/longform").status_code == 200
    assert path.read_bytes() == before


@pytest.mark.parametrize(
    "operation", ["rebuild_index", "delete_object", "index_object", "query_index"]
)
def test_index_cli_passes_owned_connection_and_closes_it(
    db_service, tmp_path, operation
):
    path = tmp_path / "index.kraken"
    with closing(sqlite3.connect(path)) as destination:
        db_service.require_connection().backup(destination)
    args = Namespace(
        database=str(path),
        type="entity",
        id="test",
        provider="mock",
        model=None,
        excluded_attributes=None,
        verbose=False,
        text="test",
        top_k=5,
        json=False,
    )
    search = MagicMock()
    search.rebuild_index.return_value.per_type = {}
    search.rebuild_index.return_value.failed = 0
    search.query.return_value = []
    connections = []

    def create_search(connection, **kwargs):
        assert connection.execute("SELECT 1").fetchone()[0] == 1
        connections.append(connection)
        return search

    with patch.object(index_cli, "create_search_service", create_search):
        assert getattr(index_cli, operation)(args) == 0
    assert len(connections) == 1
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        connections[0].execute("SELECT 1")
