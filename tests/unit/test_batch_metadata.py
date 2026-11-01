"""Batch patches retain saved metadata and fail atomically on stale assumptions."""

import json
from copy import deepcopy

import pytest

from src.app.data_handler import DataHandler
from src.commands.batch_metadata_command import BatchMetadataCommand
from src.commands.registry import get_command_types
from src.core.batch_metadata import CORE_KEYS, MetadataOperation, normalize_targets
from src.core.entities import Entity
from src.core.events import Event
from src.services.batch_metadata_service import prepare_metadata
from src.services.history_service import HistoryService

pytestmark = pytest.mark.ci_fast


@pytest.fixture
def records(db_service):
    attrs = {
        "_temporal_v2": {"opaque": [1, 2]},
        "_sheet_layout": {"rows": []},
        "_summary_data": {"text": "retained"},
        "_other": None,
        "custom": {"nested": [True, None]},
        "nullable": None,
    }
    entity = Entity("Person", "character", attributes=deepcopy(attrs), id="same")
    event = Event("Council", 12.5, attributes=deepcopy(attrs), id="same")
    db_service.insert_entity(entity)
    db_service.insert_event(event)
    return [("entity", entity.id), ("event", event.id)]


def prepared(db, targets, **intent):
    operation = MetadataOperation(**intent)
    preview = prepare_metadata(db, targets, operation)
    command = BatchMetadataCommand(targets, operation.to_dict(), preview["rows"])
    return command, preview


def attrs(db):
    return [db.get_entity("same").attributes, db.get_event("same").attributes]


@pytest.mark.parametrize(
    "intent,expected",
    [
        ({"action": "set", "key": "title", "value": "Lord"}, "Lord"),
        (
            {"action": "set", "key": "title", "value_type": "Number", "value": 3.5},
            3.5,
        ),
        (
            {"action": "set", "key": "title", "value_type": "Boolean", "value": True},
            True,
        ),
        ({"action": "set_missing", "key": "title", "value": "Lord"}, "Lord"),
    ],
)
def test_mixed_typed_set_undo_redo(db_service, records, intent, expected):
    before = deepcopy(attrs(db_service))
    command, preview = prepared(db_service, records, **intent)
    assert (preview["changed"], preview["unchanged"], preview["overwritten"]) == (
        2,
        0,
        0,
    )
    result = command.execute(db_service)
    assert result.success
    assert len(result.data["lore_effects"]) == 2
    assert all(a["title"] == expected for a in attrs(db_service))
    assert command.undo(db_service).success
    assert attrs(db_service) == before
    restored = BatchMetadataCommand.from_dict(json.loads(json.dumps(command.to_dict())))
    assert restored.execute(db_service).success
    assert all(a["title"] == expected for a in attrs(db_service))
    assert restored.undo(db_service).success
    assert attrs(db_service) == before
    assert db_service.get_event("same").lore_date == 12.5


def test_missing_is_distinct_from_null_and_overwrite_counts(db_service, records):
    command, preview = prepared(
        db_service, records, action="set_missing", key="nullable", value="filled"
    )
    assert preview["changed"] == 0
    assert command.execute(db_service).success
    assert not command.is_undoable and not command.persist_to_history
    assert not command.changes
    command, preview = prepared(
        db_service, records, action="set", key="nullable", value="filled"
    )
    assert preview["overwritten"] == 2
    assert command.execute(db_service).success
    assert command.undo(db_service).success
    assert all(a["nullable"] is None for a in attrs(db_service))


def test_remove_and_noop_preserve_metadata(db_service, records):
    before = deepcopy(attrs(db_service))
    command, preview = prepared(db_service, records, action="remove", key="custom")
    assert preview["changed"] == 2 and preview["overwritten"] == 0
    assert command.execute(db_service).success
    for original, updated in zip(before, attrs(db_service), strict=True):
        assert updated == {k: v for k, v in original.items() if k != "custom"}
    assert command.undo(db_service).success
    assert attrs(db_service) == before
    noop, preview = prepared(db_service, records, action="remove", key="missing")
    timestamps = (
        db_service.get_entity("same").modified_at,
        db_service.get_event("same").modified_at,
    )
    assert noop.execute(db_service).success and not noop.is_undoable
    assert timestamps == (
        db_service.get_entity("same").modified_at,
        db_service.get_event("same").modified_at,
    )


def test_tags_normalized_rows_and_absence_restore(db_service, records):
    before = deepcopy(attrs(db_service))
    command, _ = prepared(
        db_service, records, action="add_tags", tags=["z", " a ", "z", "a"]
    )
    assert command.execute(db_service).success
    assert all(a["_tags"] == ["a", "z"] for a in attrs(db_service))
    for getter in (db_service.get_tags_for_entity, db_service.get_tags_for_event):
        assert {t["name"] for t in getter("same")} == {"a", "z"}
    remove, _ = prepared(
        db_service, records, action="remove_tags", tags=["z", "absent"]
    )
    assert remove.execute(db_service).success
    assert all(a["_tags"] == ["a"] for a in attrs(db_service))
    assert remove.undo(db_service).success
    assert command.undo(db_service).success
    assert attrs(db_service) == before
    assert db_service.get_tags_for_entity("same") == []
    assert db_service.get_tags_for_event("same") == []


@pytest.mark.parametrize(
    "key", sorted(CORE_KEYS) + ["_tags", "_other", "_temporal_v2", " "]
)
@pytest.mark.parametrize("action", ["set", "set_missing", "remove"])
def test_protected_keys_rejected(key, action):
    with pytest.raises(ValueError):
        MetadataOperation(action, key=key)


@pytest.mark.parametrize(
    "value_type,value",
    [
        ("Boolean", 1),
        ("Number", True),
        ("Number", float("nan")),
        ("Number", float("inf")),
        ("String", None),
    ],
)
def test_invalid_typed_values_rejected(value_type, value):
    with pytest.raises(ValueError):
        MetadataOperation("set", key="value", value_type=value_type, value=value)


def test_boolean_numeric_distinction_and_numeric_equivalence(db_service, records):
    entity = db_service.get_entity("same")
    entity.attributes["score"] = 1
    db_service.insert_entity(entity)
    _, preview = prepared(
        db_service,
        records[:1],
        action="set",
        key="score",
        value_type="Number",
        value=1.0,
    )
    assert preview["changed"] == 0
    _, preview = prepared(
        db_service,
        records[:1],
        action="set",
        key="score",
        value_type="Boolean",
        value=True,
    )
    assert preview["changed"] == 1 and preview["overwritten"] == 1


def test_mixed_changed_unchanged_and_overwritten_counts(db_service, records):
    entity = db_service.get_entity("same")
    entity.attributes["title"] = "Lord"
    db_service.insert_entity(entity)
    event = db_service.get_event("same")
    event.attributes["title"] = "Council"
    db_service.insert_event(event)
    timestamp = entity.modified_at
    command, preview = prepared(
        db_service, records, action="set", key="title", value="Lord"
    )
    assert (preview["changed"], preview["unchanged"], preview["overwritten"]) == (
        1,
        1,
        1,
    )
    result = command.execute(db_service)
    assert result.success
    assert [effect["object_type"] for effect in result.data["lore_effects"]] == [
        "event"
    ]
    assert db_service.get_entity("same").modified_at == timestamp
    assert command.undo(db_service).success
    assert db_service.get_event("same").attributes["title"] == "Council"


def test_tag_preview_conflict_and_malformed_tags_block_batch(db_service, records):
    command, _ = prepared(db_service, records, action="add_tags", tags=["new"])
    event = db_service.get_event("same")
    event.tags = ["concurrent"]
    db_service.insert_event(event)
    assert not command.execute(db_service).success
    assert "_tags" not in db_service.get_entity("same").attributes
    event.attributes["_tags"] = None
    db_service.insert_event(event)
    with pytest.raises(ValueError, match="malformed"):
        prepare_metadata(db_service, records, command.operation)


def test_stale_preview_checks_unchanged_targets_too(db_service, records):
    command, _ = prepared(db_service, records, action="remove", key="missing")
    event = db_service.get_event("same")
    event.attributes["missing"] = None
    db_service.insert_event(event)
    assert not command.execute(db_service).success
    assert not command.is_undoable
    assert db_service.get_event("same").attributes["missing"] is None


def test_unrelated_changes_survive_execute_and_undo(db_service, records):
    command, _ = prepared(db_service, records, action="set", key="title", value="Lord")
    entity = db_service.get_entity("same")
    entity.name = "New name"
    entity.attributes["unrelated"] = [3, 4]
    db_service.insert_entity(entity)
    assert command.execute(db_service).success
    assert command.undo(db_service).success
    assert db_service.get_entity("same").name == "New name"
    assert db_service.get_entity("same").attributes["unrelated"] == [3, 4]


@pytest.mark.parametrize("phase", ["preview", "execute", "undo", "redo"])
def test_deleted_targets_block_entire_batch(db_service, records, phase):
    command, _ = prepared(db_service, records, action="set", key="title", value="Lord")
    if phase in ("undo", "redo"):
        assert command.execute(db_service).success
    if phase == "redo":
        assert command.undo(db_service).success
    before_entity = deepcopy(db_service.get_entity("same").to_dict())
    db_service.delete_event("same")
    if phase == "preview":
        with pytest.raises(ValueError, match="no longer exists"):
            prepare_metadata(db_service, records, command.operation)
    else:
        result = (
            command.undo(db_service) if phase == "undo" else command.execute(db_service)
        )
        assert not result.success
    assert db_service.get_entity("same").to_dict() == before_entity


@pytest.mark.parametrize("phase", ["execute", "undo", "redo"])
def test_write_failure_rolls_back_rows_and_tags(
    db_service, records, monkeypatch, phase
):
    command, _ = prepared(db_service, records, action="add_tags", tags=["new"])
    if phase in ("undo", "redo"):
        assert command.execute(db_service).success
    if phase == "redo":
        assert command.undo(db_service).success
    before = deepcopy(attrs(db_service))
    before_tags = db_service.get_tags_for_entity("same")

    def fail(*_args):
        raise RuntimeError("injected failure")

    monkeypatch.setattr(db_service, "insert_event", fail)
    result = (
        command.undo(db_service) if phase == "undo" else command.execute(db_service)
    )
    assert not result.success
    assert attrs(db_service) == before
    assert db_service.get_tags_for_entity("same") == before_tags
    if phase == "execute":
        assert not command.changes and not command.is_executed


def test_undo_conflict_blocks_all_records(db_service, records):
    command, _ = prepared(db_service, records, action="set", key="title", value="Lord")
    assert command.execute(db_service).success
    event = db_service.get_event("same")
    event.attributes["title"] = "Lady"
    db_service.insert_event(event)
    assert not command.undo(db_service).success
    assert db_service.get_entity("same").attributes["title"] == "Lord"


def test_all_effects_refresh_and_index_checked_identities(db_service, records, qapp):
    from src.gui.widgets.unified_list import UnifiedListWidget

    widget = UnifiedListWidget()
    handler = DataHandler()
    widget.set_data([db_service.get_event("same")], [db_service.get_entity("same")])
    from PySide6.QtCore import Qt

    for row in range(2):
        widget._model.setData(
            widget._model.index(row, 0),
            Qt.CheckState.Checked,
            Qt.ItemDataRole.CheckStateRole,
        )
    checks = widget.get_checked_items()
    assert widget.btn_batch_edit.isEnabled()
    indices = []
    handler.index_object_requested.connect(lambda *identity: indices.append(identity))
    handler.lore_mutation_ready.connect(widget.apply_lore_effects)
    command, _ = prepared(db_service, records, action="add_tags", tags=["batch"])
    result = command.execute(db_service)
    result.command_name = "BatchMetadataCommand"
    handler.on_command_finished(result)
    assert sorted(indices) == records
    assert widget.get_checked_items() == checks
    assert all(obj.tags == ["batch"] for _, obj in widget._model._items)
    widget.deleteLater()


def test_hidden_checked_objects_survive_batch_effects(db_service, records, qtbot):
    from PySide6.QtCore import Qt

    from src.gui.widgets.unified_list import UnifiedListWidget

    widget = UnifiedListWidget()
    qtbot.addWidget(widget)
    widget.set_data([db_service.get_event("same")], [db_service.get_entity("same")])
    for row in range(2):
        widget._model.setData(
            widget._model.index(row, 0),
            Qt.CheckState.Checked,
            Qt.ItemDataRole.CheckStateRole,
        )
    widget.filter_combo.setCurrentText("Entities Only")
    assert widget.get_checked_items() == records
    command, _ = prepared(db_service, records, action="add_tags", tags=["batch"])
    result = command.execute(db_service)
    assert result.success
    widget.apply_lore_effects(result.data["lore_effects"])
    assert widget.get_checked_items() == records
    widget.filter_combo.setCurrentText("All Items")
    assert widget.get_checked_items() == records


def test_serialized_command_registered_and_history_restored(db_service, records):
    command, _ = prepared(db_service, records, action="remove", key="nullable")
    assert command.execute(db_service).success
    history = HistoryService(db_service, "test-world")
    history.register_command_type("BatchMetadataCommand", BatchMetadataCommand)
    history.save_command(command)
    assert get_command_types()["BatchMetadataCommand"] is BatchMetadataCommand
    (restored,) = history.load_recent_history()
    assert restored.command_id == command.command_id
    assert restored.undo(db_service).success
    assert all(a["nullable"] is None for a in attrs(db_service))
    assert normalize_targets([*records, records[0]]) == records
