"""Authored relation ownership, forward validation, and exact history replay."""

import sqlite3
import uuid
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from unittest.mock import MagicMock, patch

import pytest

from src.commands.relation_commands import AddRelationCommand, UpdateRelationCommand
from src.core.entities import Entity
from src.core.events import Event
from src.services.authored_relation_service import AuthoredRelationService
from src.services.db_service import DatabaseService
from src.services.repositories import (
    EntityRepository,
    EventRepository,
    RelationRepository,
)

pytestmark = pytest.mark.ci_fast


@pytest.fixture
def endpoints(db_service):
    source = Entity(name="Source", type="Person")
    target = Event(name="Target", lore_date=1.0)
    db_service.insert_entity(source)
    db_service.insert_event(target)
    return source, target


@pytest.mark.parametrize("source_kind", ["entity", "event"])
@pytest.mark.parametrize("target_kind", ["entity", "event"])
def test_create_update_and_reverse_all_endpoint_kinds(
    db_service, source_kind, target_kind
):
    def persist(kind, name):
        if kind == "entity":
            item = Entity(name=name, type="Person")
            db_service.insert_entity(item)
        else:
            item = Event(name=name, lore_date=1.0)
            db_service.insert_event(item)
        return item

    source, target = persist(source_kind, "Source"), persist(target_kind, "Target")
    service = AuthoredRelationService.from_connection(db_service.require_connection())
    attributes = {"notes": "Authored", "timing": {"start": 12.5}, "tags": ["keep"]}
    rel_id = service.create(source.id, target.id, "related", attributes)
    saved = db_service.get_relation(rel_id)
    assert saved["attributes"] == attributes
    assert str(uuid.UUID(rel_id)) == rel_id
    assert isinstance(saved["created_at"], float)
    assert not db_service.require_connection().in_transaction

    service.update(rel_id, source.id, "reversed", attributes, source_id=target.id)
    reversed_row = db_service.get_relation(rel_id)
    assert reversed_row == {
        **saved,
        "source_id": target.id,
        "target_id": source.id,
        "rel_type": "reversed",
    }
    service.update(rel_id, target.id, "refined")
    assert db_service.get_relation(rel_id)["attributes"] == {}


def test_supplied_identity_and_zero_timestamp_are_not_reallocated(
    db_service, endpoints
):
    source, target = endpoints
    service = AuthoredRelationService.from_connection(db_service.require_connection())
    rel_id = str(uuid.uuid4())
    with (
        patch("src.services.authored_relation_service.uuid.uuid4") as allocate_id,
        patch("src.services.authored_relation_service.time.time") as allocate_time,
    ):
        assert (
            service.create(
                source.id, target.id, "related", relation_id=rel_id, created_at=0.0
            )
            == rel_id
        )
    allocate_id.assert_not_called()
    allocate_time.assert_not_called()
    assert db_service.get_relation(rel_id)["created_at"] == 0.0


@pytest.mark.parametrize(
    "bad_id", ["name", "", None, 42, "{00000000-0000-0000-0000-000000000000}"]
)
def test_invalid_uuid_does_not_invoke_lookup_or_open_facade(bad_id):
    db = DatabaseService()
    with patch.object(db, "connect") as connect:
        with pytest.raises(ValueError, match="source must be a canonical UUID"):
            db.insert_relation(bad_id, str(uuid.uuid4()), "related")
        with pytest.raises(ValueError, match="system-managed"):
            db.insert_relation(str(uuid.uuid4()), str(uuid.uuid4()), "mentions")
    connect.assert_not_called()
    assert not db.is_connected()


def test_invalid_service_endpoint_and_type_do_not_call_dependencies():
    repository = MagicMock(spec=RelationRepository)
    entity_lookup, event_lookup = MagicMock(), MagicMock()
    service = AuthoredRelationService(repository, entity_lookup, event_lookup)
    with pytest.raises(ValueError, match="canonical UUID"):
        service.create("not-a-uuid", str(uuid.uuid4()), "related")
    with pytest.raises(ValueError, match="system-managed"):
        service.create(str(uuid.uuid4()), str(uuid.uuid4()), "mentions")
    entity_lookup.assert_not_called()
    event_lookup.assert_not_called()
    repository.insert.assert_not_called()


def test_facade_honors_injected_repository_and_lookup_precedence():
    entity_repo = MagicMock(spec=EntityRepository)
    event_repo = MagicMock(spec=EventRepository)
    relation_repo = MagicMock(spec=RelationRepository)
    source = Entity(name="Source", type="Person")
    target = Event(name="Target", lore_date=1.0)
    entity_repo.get.side_effect = (
        lambda item_id: source if item_id == source.id else None
    )
    event_repo.get.return_value = target
    db = DatabaseService(
        entity_repo=entity_repo, event_repo=event_repo, relation_repo=relation_repo
    )
    try:
        rel_id = db.insert_relation(source.id, target.id, "related")
        args = relation_repo.insert.call_args.args
        assert args[:5] == (rel_id, source.id, target.id, "related", {})
        assert isinstance(args[5], float)
        event_repo.get.assert_called_once_with(target.id)
        relation_repo.set_connection.assert_called_once_with(db.require_connection())
        db.update_relation(rel_id, target.id, "changed", {"keep": True})
        relation_repo.update.assert_called_once_with(
            rel_id, "changed", {"keep": True}, target_id=target.id, source_id=None
        )
    finally:
        db.close()


@pytest.mark.parametrize("operation", ["create", "update"])
def test_standalone_serialization_failure_rolls_back(db_service, endpoints, operation):
    source, target = endpoints
    service = AuthoredRelationService.from_connection(db_service.require_connection())
    rel_id = service.create(source.id, target.id, "before")
    before = db_service.get_all_relations()
    with pytest.raises(TypeError):
        if operation == "create":
            service.create(source.id, target.id, "after", {"invalid": object()})
        else:
            service.update(rel_id, target.id, "after", {"invalid": object()})
    assert db_service.get_all_relations() == before
    assert not db_service.require_connection().in_transaction


@pytest.mark.parametrize("operation", ["create", "update", "restore"])
def test_service_joins_caller_transaction_and_preserves_rollback(
    db_service, endpoints, operation
):
    source, target = endpoints
    connection = db_service.require_connection()
    service = AuthoredRelationService.from_connection(connection)
    rel_id = service.create(source.id, target.id, "before")
    before = db_service.get_all_relations()
    with pytest.raises(RuntimeError, match="later failure"):
        with db_service.transaction():
            connection.execute(
                "INSERT INTO system_meta(key, value) VALUES ('unrelated', 'pending')"
            )
            if operation == "create":
                service.create(source.id, target.id, "after")
            elif operation == "update":
                service.update(rel_id, source.id, "after", source_id=target.id)
            else:
                service.restore_snapshot(
                    rel_id,
                    {**before[0], "source_id": target.id, "target_id": source.id},
                )
            assert connection.in_transaction
            raise RuntimeError("later failure")
    assert db_service.get_all_relations() == before
    assert (
        connection.execute(
            "SELECT value FROM system_meta WHERE key='unrelated'"
        ).fetchone()
        is None
    )


def test_failed_snapshot_restoration_rolls_back_outer_write(db_service, endpoints):
    source, target = endpoints
    connection = db_service.require_connection()
    service = AuthoredRelationService.from_connection(connection)
    rel_id = service.create(source.id, target.id, "before")
    before = db_service.get_relation(rel_id)
    with pytest.raises(sqlite3.IntegrityError):
        with db_service.transaction():
            connection.execute(
                "UPDATE entities SET name='Changed' WHERE id=?", (source.id,)
            )
            service.restore_snapshot(rel_id, {**before, "target_id": str(uuid.uuid4())})
    assert db_service.get_relation(rel_id) == before
    assert db_service.get_entity(source.id).name == "Source"


@pytest.mark.parametrize(
    "operation",
    ["add-source", "add-target", "update", "reverse-source", "reverse-target"],
)
@pytest.mark.parametrize("bad_kind", ["legacy", "missing"])
def test_commands_reject_bad_replacement_endpoints_without_writes(
    db_service, endpoints, operation, bad_kind
):
    source, target = endpoints
    bad = Entity(name="Bad", type="Person", id="legacy-id")
    db_service.insert_entity(bad)
    bad_id = bad.id if bad_kind == "legacy" else str(uuid.uuid4())
    rel_id = db_service.insert_relation(source.id, target.id, "before")
    before = db_service.get_all_relations()
    if operation == "add-source":
        command = AddRelationCommand(bad_id, target.id, "after", bidirectional=True)
    elif operation == "add-target":
        command = AddRelationCommand(source.id, bad_id, "after", bidirectional=True)
    elif operation == "update":
        command = UpdateRelationCommand(rel_id, bad_id, "after")
    elif operation == "reverse-source":
        command = UpdateRelationCommand(rel_id, target.id, "after", source_id=bad_id)
    else:
        command = UpdateRelationCommand(rel_id, bad_id, "after", source_id=target.id)
    result = command.execute(db_service)
    assert not result.success
    assert (
        "canonical UUID" if bad_kind == "legacy" else "does not exist"
    ) in result.message
    assert db_service.get_all_relations() == before
    assert not command.is_executed


@pytest.mark.parametrize(
    "encoding", ["upper", "compact", "braces", "prefix", "whitespace"]
)
def test_existing_noncanonical_uuid_encodings_are_rejected(
    db_service, endpoints, encoding
):
    _, target = endpoints
    canonical = "abcdefab-1234-4567-89ab-abcdefabcdef"
    encoded = {
        "upper": canonical.upper(),
        "compact": canonical.replace("-", ""),
        "braces": "{" + canonical + "}",
        "prefix": "id:" + canonical,
        "whitespace": " " + canonical + " ",
    }[encoding]
    db_service.insert_entity(Entity(id=encoded, name="Legacy", type="Person"))
    result = AddRelationCommand(encoded, target.id, "related").execute(db_service)
    assert not result.success
    assert "canonical UUID" in result.message
    assert db_service.get_all_relations() == []


def test_legacy_serialized_update_is_rejected_without_rewriting_snapshot(
    db_service, endpoints
):
    source, target = endpoints
    legacy = Entity(name="Legacy", type="Person", id="legacy-id")
    db_service.insert_entity(legacy)
    rel_id = db_service.insert_relation(source.id, target.id, "before")
    original_row = db_service.get_relation(rel_id)
    command = UpdateRelationCommand(rel_id, legacy.id, "after", {"notes": "legacy"})
    history = command.to_dict()
    history["previous_state"] = deepcopy(original_row)
    original_history = deepcopy(history)
    replay = UpdateRelationCommand.from_dict(history)
    result = replay.execute(db_service)
    assert not result.success
    assert "canonical UUID" in result.message
    assert replay.to_dict() == original_history
    assert history == original_history
    assert db_service.get_relation(rel_id) == original_row


def test_legacy_serialized_add_is_rejected_without_rewriting_history(
    db_service, endpoints
):
    _, target = endpoints
    legacy = Entity(name="Legacy", type="Person", id="legacy-id")
    db_service.insert_entity(legacy)
    history = {
        "source_id": legacy.id,
        "target_id": target.id,
        "rel_type": "related",
        "attributes": {"notes": "legacy"},
        "bidirectional": False,
        "created_rel_ids": [str(uuid.uuid4())],
        "created_at": 12.5,
        "is_executed": False,
    }
    original = deepcopy(history)
    command = AddRelationCommand.from_dict(history)
    result = command.execute(db_service)
    assert not result.success
    assert "canonical UUID" in result.message
    assert command.to_dict() == original
    assert history == original
    assert db_service.get_all_relations() == []


def test_serialized_undo_restores_noncanonical_snapshot_exactly(db_service, endpoints):
    source, target = endpoints
    legacy = Entity(name="Legacy", type="Person", id="legacy-id")
    db_service.insert_entity(legacy)
    rel_id = str(uuid.uuid4())
    RelationRepository(db_service.require_connection()).insert(
        rel_id, legacy.id, target.id, "before", {"extra": {"keep": [1, 2]}}, 12.5
    )
    original = db_service.get_relation(rel_id)
    command = UpdateRelationCommand(
        rel_id,
        source.id,
        "after",
        {"notes": "edited"},
        source_id=target.id,
        expected=original,
    )
    assert command.execute(db_service).success
    changed = db_service.get_relation(rel_id)
    command = UpdateRelationCommand.from_dict(command.to_dict())
    command.undo(db_service)
    assert db_service.get_relation(rel_id) == original
    assert command.execute(db_service).success
    assert db_service.get_relation(rel_id) == changed
    assert len(db_service.get_all_relations()) == 1


def test_missing_endpoint_feedback_remains_compatible(db_service, endpoints):
    source, target = endpoints
    missing = str(uuid.uuid4())
    result = AddRelationCommand(source.id, missing, "related").execute(db_service)
    assert result.message == f"Relation endpoint does not exist: {missing}"
    with pytest.raises(ValueError) as error:
        db_service.insert_relation(source.id, missing, "related")
    assert str(error.value) == f"Relation target endpoint does not exist: {missing}"
    rel_id = db_service.insert_relation(source.id, target.id, "related")
    result = UpdateRelationCommand(rel_id, missing, "changed").execute(db_service)
    assert result.message == f"Relation target endpoint does not exist: {missing}"


def test_facade_reopens_file_connection_without_replacing_service(
    db_service, endpoints, tmp_path
):
    source, target = endpoints
    path = tmp_path / "world.kraken"
    with sqlite3.connect(path) as copy:
        db_service.require_connection().backup(copy)
    db = DatabaseService(str(path))
    try:
        rel_id = db.insert_relation(source.id, target.id, "before")
        db.close()
        db.update_relation(rel_id, target.id, "after")
        assert db.get_relation(rel_id)["rel_type"] == "after"
        db.close()
        second_id = db.insert_relation(source.id, target.id, "new")
        assert db.get_relation(second_id)["source_id"] == source.id
    finally:
        db.close()


@pytest.mark.parametrize("operation", ["create", "update", "restore"])
def test_readonly_rejects_mutations_without_altering_rows(
    db_service, endpoints, tmp_path, operation
):
    source, target = endpoints
    rel_id = db_service.insert_relation(source.id, target.id, "before")
    before = db_service.get_relation(rel_id)
    path = tmp_path / "readonly.kraken"
    with sqlite3.connect(path) as copy:
        db_service.require_connection().backup(copy)
    db = DatabaseService(str(path), read_only=True)
    db.connect()
    try:
        service = AuthoredRelationService.from_connection(db.require_connection())
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            if operation == "create":
                service.create(source.id, target.id, "after")
            elif operation == "update":
                db.update_relation(rel_id, target.id, "after")
            else:
                service.restore_snapshot(rel_id, {**before, "rel_type": "after"})
        assert db.get_all_relations() == [before]
        assert not db.require_connection().in_transaction
    finally:
        db.close()


def test_command_factory_rejects_foreign_thread_before_binding(db_service):
    with ThreadPoolExecutor(max_workers=1) as executor:
        with pytest.raises(RuntimeError, match="another thread"):
            executor.submit(
                lambda: AuthoredRelationService.from_connection(
                    db_service.require_connection()
                )
            ).result()


def test_service_and_facade_cannot_write_from_foreign_thread(db_service, endpoints):
    source, target = endpoints
    service = AuthoredRelationService.from_connection(db_service.require_connection())
    before = db_service.get_all_relations()
    with ThreadPoolExecutor(max_workers=1) as executor:
        for operation in (service.create, db_service.insert_relation):
            with pytest.raises(sqlite3.ProgrammingError, match="same thread"):
                executor.submit(operation, source.id, target.id, "related").result()
    assert db_service.get_all_relations() == before
