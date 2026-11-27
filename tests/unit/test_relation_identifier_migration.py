"""Verify exact key changes, history boundaries, and checkpoint recovery."""

import json
from pathlib import Path

import pytest

from src.commands.remove_relation_definition_command import (
    RemoveRelationDefinitionCommand,
)
from src.core.entities import Entity
from src.core.relation_dictionary import edit_document
from src.core.relation_vocabulary import VOCABULARY_KEY
from src.services.database_restore_service import DatabaseRestoreService
from src.services.db_service import DatabaseService
from src.services.history_store import HistoryStore
from src.services.relation_dictionary import usage
from src.services.relation_identifier_migration import (
    MIGRATION_LOG,
    migrate_identifier,
    preview_migration,
)
from src.services.repositories.settings_repository import SettingsRepository
from src.services.world_transfer import export_world, import_world

pytestmark = pytest.mark.ci_fast

WORLD_ID = "migration-world"
OLD = "sworn_to"
NEW = "owes_allegiance"


def _rows(connection):
    return [
        dict(row) for row in connection.execute("SELECT * FROM relations ORDER BY id")
    ]


@pytest.fixture
def migration_world(tmp_path):
    root = tmp_path / "world"
    root.mkdir()
    database = DatabaseService(str(root / "world.kraken"))
    database.connect()
    for identifier in ("a", "b", "c", "d"):
        database.insert_entity(Entity(id=identifier, name=identifier, type="person"))
    definition = {
        "key": OLD,
        "forward_label": "Sworn to",
        "reverse_label": "Sworn members",
        "description": "Sworn allegiance",
        "forward_template": "{source} swore to {target}.",
        "enabled": False,
    }
    with database.transaction() as conn:
        conn.executemany(
            "INSERT INTO relations (id, source_id, target_id, rel_type, attributes) VALUES (?,?,?,?,?)",
            [
                ("first", "a", "b", OLD, '{"notes":"First","valid_from":10}'),
                ("second", "b", "a", OLD, '{"notes":"Reciprocal","valid_until":20}'),
                ("third", "a", "b", "member_of", "{}"),
            ],
        )
        repository = SettingsRepository(conn)
        repository.restore(VOCABULARY_KEY, edit_document(None, definition, None))
        repository.restore(
            "graph_lexicon_config", '{"edges":{"sworn_to":{"color":"#333333"}}}'
        )
    try:
        yield database
    finally:
        database.close()


def test_removal_undo_redo_changes_only_the_definition(migration_world):
    database = migration_world
    connection = database.require_connection()
    repository = SettingsRepository(connection)
    rows = _rows(connection)
    raw = repository.raw(VOCABULARY_KEY)
    command = RemoveRelationDefinitionCommand(
        database.db_path, raw, OLD, usage(connection, OLD)
    )
    assert command.execute(database).success
    assert json.loads(repository.raw(VOCABULARY_KEY))["definitions"] == []
    assert _rows(connection) == rows
    restored = RemoveRelationDefinitionCommand.from_dict(command.to_dict())
    restored.undo(database)
    assert repository.raw(VOCABULARY_KEY) == raw
    assert restored.execute(database).success
    assert _rows(connection) == rows


def test_exact_migration_reopens_transfers_and_restores(migration_world, tmp_path):
    database = migration_world
    connection = database.require_connection()
    rows = _rows(connection)
    history = HistoryStore(connection, WORLD_ID)
    with database.transaction():
        history.boundary()
        connection.execute(
            "INSERT INTO edit_sessions (session_id, world_id, started_at, app_version) VALUES ('session', ?, 0, 'test')",
            (WORLD_ID,),
        )
        columns = (
            "world_id, session_id, command_type, command_data, timestamp, is_executed"
        )
        connection.execute(
            f"INSERT INTO command_history ({columns}) VALUES (?, 'session', 'test', ?, 0, 1)",
            (WORLD_ID, json.dumps({"_command_base": {"command_id": "previous"}})),
        )
        history.append("previous")
    review = preview_migration(connection, WORLD_ID, OLD, NEW)
    assert review["count"] == 2
    assert review["history"]["undo"] == ["previous"]
    backups = tmp_path / "backups"
    checkpoint = migrate_identifier(database, WORLD_ID, OLD, NEW, review, backups)
    expected = [
        row | {"rel_type": NEW} if row["rel_type"] == OLD else row for row in rows
    ]
    assert _rows(connection) == expected
    assert history.read()["undo"] == []
    assert connection.execute("SELECT count(*) FROM command_history").fetchone()[0] == 1
    repo = SettingsRepository(connection)
    assert json.loads(repo.raw(VOCABULARY_KEY))["definitions"][0]["key"] == NEW
    assert json.loads(repo.raw("graph_lexicon_config"))["edges"] == {
        NEW: {"color": "#333333"}
    }
    assert json.loads(repo.raw(MIGRATION_LOG))[0]["checkpoint"] == checkpoint.name

    package = tmp_path / "world.krakenworld"
    home = Path(database.db_path).parent
    export_world(
        connection,
        {"path": str(home), "manifest": {"id": WORLD_ID, "name": "World"}},
        package,
        lambda: False,
    )
    imported = import_world(package, tmp_path / "imported", "Imported", lambda: False)
    for file in (Path(database.db_path), imported / "world.kraken"):
        reopened = DatabaseService(str(file), read_only=True)
        reopened.connect()
        try:
            reopened_conn = reopened.require_connection()
            assert _rows(reopened_conn) == expected
            assert SettingsRepository(reopened_conn).raw(MIGRATION_LOG) == repo.raw(
                MIGRATION_LOG
            )
        finally:
            reopened.close()

    restored_file = tmp_path / "restored.kraken"
    restored = DatabaseRestoreService().restore(checkpoint, restored_file, backups)
    assert restored.success
    reopened = DatabaseService(str(restored_file), read_only=True)
    reopened.connect()
    try:
        restored_connection = reopened.require_connection()
        assert _rows(restored_connection) == rows
        assert HistoryStore(restored_connection, WORLD_ID).read()["undo"] == [
            "previous"
        ]
        assert SettingsRepository(restored_connection).raw(MIGRATION_LOG) is None
    finally:
        reopened.close()


def test_migration_rejects_protected_colliding_stale_and_unsupported_keys(
    migration_world, tmp_path
):
    connection = migration_world.require_connection()
    with pytest.raises(ValueError, match="built-in"):
        preview_migration(connection, WORLD_ID, "member_of", NEW)
    with pytest.raises(ValueError, match="built-in"):
        preview_migration(connection, WORLD_ID, OLD, "Located_At")
    with migration_world.transaction():
        connection.execute(
            "INSERT INTO relations (id, source_id, target_id, rel_type) VALUES ('collision','c','d','OWES_ALLEGIANCE')"
        )
    with pytest.raises(ValueError, match="conflicting"):
        preview_migration(connection, WORLD_ID, OLD, NEW)
    with migration_world.transaction():
        connection.execute("DELETE FROM relations WHERE id='collision'")
        connection.execute(
            "INSERT INTO system_meta (key, value) VALUES ('plugin_filters', ?)",
            ('{"rel_types":{"include":["sworn_to"]}}',),
        )
    with pytest.raises(ValueError, match="plugin_filters"):
        preview_migration(connection, WORLD_ID, OLD, NEW)
    with migration_world.transaction():
        connection.execute("DELETE FROM system_meta WHERE key='plugin_filters'")
    review = preview_migration(connection, WORLD_ID, OLD, NEW)
    with migration_world.transaction():
        connection.execute("UPDATE relations SET attributes='{}' WHERE id='first'")
    rows = _rows(connection)
    with pytest.raises(ValueError, match="impact changed"):
        migrate_identifier(
            migration_world, WORLD_ID, OLD, NEW, review, tmp_path / "backups"
        )
    assert _rows(connection) == rows


@pytest.mark.parametrize("stage", ["backup", "transaction"])
def test_migration_failure_preserves_data_and_history(
    migration_world, tmp_path, monkeypatch, stage
):
    from src.services import relation_identifier_migration as migration

    connection = migration_world.require_connection()
    review = preview_migration(connection, WORLD_ID, OLD, NEW)
    snapshot = connection.execute("SELECT * FROM system_meta ORDER BY key").fetchall()
    rows = _rows(connection)
    original_write = migration._write_migration

    def fail(*_args):
        raise OSError("Injected failure")

    def fail_after_write(*args):
        original_write(*args)
        fail()

    if stage == "backup":
        monkeypatch.setattr(migration, "snapshot_database", fail)
    else:
        monkeypatch.setattr(migration, "_write_migration", fail_after_write)
    with pytest.raises(OSError, match="Injected"):
        migrate_identifier(
            migration_world, WORLD_ID, OLD, NEW, review, tmp_path / "backups"
        )
    assert _rows(connection) == rows
    assert (
        connection.execute("SELECT * FROM system_meta ORDER BY key").fetchall()
        == snapshot
    )
