"""Exact Longform undo/history and transaction-safe refresh regressions."""

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from unittest.mock import patch

import pytest

from src.commands.longform_commands import (
    DemoteLongformEntryCommand,
    MoveLongformEntryCommand,
    PromoteLongformEntryCommand,
    RemoveLongformEntryCommand,
)
from src.core.entities import Entity
from src.services import longform_builder as longform
from src.services.history_service import HistoryService

pytestmark = pytest.mark.ci_fast

COMMANDS = {
    "move": MoveLongformEntryCommand,
    "promote": PromoteLongformEntryCommand,
    "demote": DemoteLongformEntryCommand,
    "remove": RemoveLongformEntryCommand,
}


def _file_backed(service, path):
    """Reuse the shared DB fixture, reopening a snapshot as a real WAL world."""
    with closing(sqlite3.connect(path)) as destination:
        service.require_connection().backup(destination)
    service.close()
    service.db_path = str(path)
    service.connect()


def _command(operation, row_id, old_meta=None):
    arguments = ["entities", row_id, old_meta if old_meta is not None else {}]
    if operation == "move":
        arguments.append({"position": 500, "parent_id": None, "depth": 0})
    return COMMANDS[operation](*arguments)


@pytest.mark.parametrize("operation", COMMANDS)
@pytest.mark.parametrize(
    "state", ["absent", "empty_container", "other_document", "empty_document", "full"]
)
def test_exact_undo_survives_history_and_restart(
    db_service, tmp_path, operation, state
):
    parent = Entity(
        name="Parent",
        type="test",
        attributes={"_longform": {"default": {"position": 100, "depth": 0}}},
    )
    db_service.insert_entity(parent)
    attrs = {"user": {"keep": [1, 2]}}
    if state != "absent":
        attrs["_longform"] = {}
    if state in {"other_document", "empty_document", "full"}:
        attrs["_longform"]["other"] = {"position": 42, "custom": ["retain"]}
    if state == "empty_document":
        attrs["_longform"]["default"] = {}
    elif state == "full":
        attrs["_longform"]["default"] = {
            "position": 200,
            "depth": 1 if operation == "promote" else 0,
            "parent_id": parent.id if operation == "promote" else None,
            "custom": {"nested": ["authored"]},
            "title_override": "Exact heading",
        }
    target = Entity(name="Target", type="test", attributes=attrs)
    db_service.insert_entity(target)
    _file_backed(db_service, tmp_path / "history.kraken")
    history = HistoryService(db_service, "snapshot-world")
    history.register_command_type(COMMANDS[operation].__name__, COMMANDS[operation])
    # A stale UI draft must not define the authoritative undo snapshot.
    command = _command(operation, target.id, {"position": -999, "depth": 7})
    assert "metadata_before" not in command.to_dict()
    assert command.execute(db_service).success
    after = db_service.get_entity(target.id).attributes
    history.save_command(command)
    history.end_session()
    db_service.close()
    db_service.connect()
    history = HistoryService(db_service, "snapshot-world")
    history.register_command_type(COMMANDS[operation].__name__, COMMANDS[operation])
    restored = history.load_recent_history()
    assert len(restored) == 1
    command = restored[0]
    command.undo(db_service)
    assert db_service.get_entity(target.id).attributes == attrs
    assert not db_service.require_connection().in_transaction
    # The first-addition regression previously crashed during heading generation.
    assert isinstance(
        longform.build_longform_sequence(db_service.require_connection()), list
    )
    assert command.execute(db_service).success
    assert db_service.get_entity(target.id).attributes == after
    command.undo(db_service)
    assert db_service.get_entity(target.id).attributes == attrs


def test_undo_preserves_other_documents_and_later_unrelated_attributes(db_service):
    attrs = {"_longform": {"default": {"position": 100, "extra": [1]}}}
    target = Entity(name="Target", type="test", attributes=attrs)
    db_service.insert_entity(target)
    command = _command("remove", target.id)
    assert command.execute(db_service).success
    with db_service.transaction() as conn:
        conn.execute(
            "UPDATE entities SET attributes=? WHERE id=?",
            (
                json.dumps({"later": True, "_longform": {"other": {"extra": [2]}}}),
                target.id,
            ),
        )
    command.undo(db_service)
    assert db_service.get_entity(target.id).attributes == {
        "later": True,
        "_longform": {
            "default": {"position": 100, "extra": [1]},
            "other": {"extra": [2]},
        },
    }


@pytest.mark.parametrize("operation", COMMANDS)
def test_legacy_history_undo_restores_supplied_metadata(db_service, operation):
    target = Entity(name="Legacy", type="test")
    db_service.insert_entity(target)
    supplied = {"position": 100, "depth": 0, "extra": {"keep": [1]}}
    payload = _command(operation, target.id, supplied).to_dict()
    payload["is_executed"] = True
    assert "metadata_before" not in payload
    command = COMMANDS[operation].from_dict(json.loads(json.dumps(payload)))
    command.undo(db_service)
    assert (
        longform.get_longform_meta(
            db_service.require_connection(), "entities", target.id
        )
        == supplied
    )


@pytest.mark.parametrize(
    "raw", ["{broken", "[]", '{"_longform":[]}', '{"_longform":{"default":null}}']
)
def test_invalid_metadata_is_rejected_without_mutation(db_service, raw):
    target = Entity(name="Malformed", type="test")
    db_service.insert_entity(target)
    with db_service.transaction() as conn:
        conn.execute("UPDATE entities SET attributes=? WHERE id=?", (raw, target.id))
    command = _command("move", target.id)
    assert not command.execute(db_service).success
    assert "metadata_before" not in command.to_dict()
    assert (
        db_service.require_connection()
        .execute("SELECT attributes FROM entities WHERE id=?", (target.id,))
        .fetchone()[0]
        == raw
    )


def test_failed_execution_does_not_freeze_snapshot_for_retry(db_service):
    target = Entity(name="Retry", type="test")
    db_service.insert_entity(target)
    command = _command("move", target.id)
    with patch.object(
        longform, "insert_or_update_longform_meta", side_effect=ValueError
    ):
        assert not command.execute(db_service).success
    with db_service.transaction() as conn:
        longform.insert_or_update_longform_meta(
            conn, "entities", target.id, position=300, depth=0
        )
    before = db_service.get_entity(target.id).attributes
    assert command.execute(db_service).success
    command.undo(db_service)
    assert db_service.get_entity(target.id).attributes == before


def test_refresh_preserves_outer_write_rollback(db_service):
    target = Entity(name="Committed", type="test")
    db_service.insert_entity(target)
    with pytest.raises(RuntimeError, match="later failure"):
        with db_service.transaction() as conn:
            conn.execute("UPDATE entities SET name='Pending' WHERE id=?", (target.id,))
            statements = []
            conn.set_trace_callback(statements.append)
            try:
                db_service.ensure_fresh_view()
                assert statements == []
                assert conn.in_transaction
            finally:
                conn.set_trace_callback(None)
            raise RuntimeError("later failure")
    assert db_service.get_entity(target.id).name == "Committed"


def test_refresh_retains_read_snapshot_until_owner_finishes(db_service, tmp_path):
    target = Entity(name="Before", type="test")
    db_service.insert_entity(target)
    _file_backed(db_service, tmp_path / "wal.kraken")
    with db_service.transaction() as reader:
        assert db_service.get_entity(target.id).name == "Before"
        with closing(sqlite3.connect(db_service.db_path)) as writer:
            writer.execute("UPDATE entities SET name='After' WHERE id=?", (target.id,))
            writer.commit()
        db_service.ensure_fresh_view()
        assert reader.in_transaction
        assert db_service.get_entity(target.id).name == "Before"
    db_service.ensure_fresh_view()
    assert db_service.get_entity(target.id).name == "After"


def test_refresh_does_not_connect_or_use_a_foreign_thread(db_service):
    with ThreadPoolExecutor(max_workers=1) as executor:
        with pytest.raises(RuntimeError, match="another thread"):
            executor.submit(db_service.ensure_fresh_view).result()
    db_service.close()
    with patch.object(db_service, "connect") as connect:
        db_service.ensure_fresh_view()
        connect.assert_not_called()
