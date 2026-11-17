"""Hierarchy integrity and durable structural-command snapshot regressions."""

import json
from copy import deepcopy
from dataclasses import replace

import pytest

from src.commands.map_crud_commands import (
    DeleteMapCommand,
    RegisterDetailMapCommand,
    SetMasterMapCommand,
)
from src.commands.map_hierarchy_commands import ChangeMapParentCommand
from src.core.map import Map
from src.core.map_hierarchy import (
    HierarchyError,
    MapHierarchy,
    hierarchy_attributes,
    restore_hierarchy_attributes,
)

pytestmark = pytest.mark.ci_fast


def map_record(key, parent=None, **attributes):
    if parent:
        attributes["parent_map_id"] = parent
    return Map(id=key, name=key, image_path=f"{key}.png", attributes=attributes)


def registration():
    return {
        "mode": "aspect_locked_affine",
        "version": 1,
        "master_center_norm": {"x": 0.5, "y": 0.5},
        "scale_norm": 0.2,
        "aspect_ratio": 1.5,
        "rotation_deg": 0,
    }


def test_role_independent_detached_snapshot():
    maps = [map_record("a"), map_record("b", "a", map_role="master")]
    hierarchy = MapHierarchy(maps)
    maps[1].attributes.clear()
    assert [m.id for m in hierarchy.children("a")] == ["b"]
    hierarchy.children("a")[0].attributes.clear()
    assert [m.id for m in hierarchy.descendants("a")] == ["b"]
    assert "b" in hierarchy.diagnostics()


def test_subtree_depth_and_unrelated_corruption():
    maps = [
        map_record("a"),
        map_record("b", "a"),
        map_record("c", "b"),
        map_record("d"),
        map_record("e", "d"),
        map_record("f", "e"),
        map_record("broken", "missing"),
    ]
    hierarchy = MapHierarchy(maps)
    with pytest.raises(HierarchyError, match="cap"):
        hierarchy.validate_change_parent("a", "f")
    hierarchy.validate_change_parent("a", "e")
    with pytest.raises(HierarchyError, match="cycle"):
        hierarchy.validate_change_parent("a", "c")
    hierarchy.validate_change_parent("broken", None)


def test_invalid_parent_metadata_is_diagnostic_not_global_block():
    hierarchy = MapHierarchy([map_record("a"), map_record("bad", parent_map_id=4)])
    assert "bad" in hierarchy.diagnostics()
    hierarchy.validate_change_parent("a", None)


def test_cycles_never_return_source_as_its_descendant():
    hierarchy = MapHierarchy([map_record("a", "b"), map_record("b", "a")])
    assert [m.id for m in hierarchy.descendants("a")] == ["b"]
    with pytest.raises(HierarchyError):
        hierarchy.subtree_height("a")
    hierarchy.validate_change_parent("a", None)


def test_command_serialization_preserves_exact_keys_and_unrelated_data(db_service):
    source = map_record("source", map_role=None, notes={"text": "authored"})
    child = map_record("child", "source", registration=registration())
    for record in [source, child, map_record("parent")]:
        db_service.insert_map(record)
    child_before = deepcopy(db_service.get_map("child").to_dict())
    payload = registration()
    command = ChangeMapParentCommand("source", "parent", payload)
    payload["master_center_norm"]["x"] = 0.9
    assert command.execute(db_service).success
    assert (
        db_service.get_map("source").attributes["registration"]["master_center_norm"][
            "x"
        ]
        == 0.5
    )
    command = ChangeMapParentCommand.from_dict(
        json.loads(json.dumps(command.to_dict()))
    )
    current = db_service.get_map("source")
    db_service.insert_map(
        replace(current, attributes={**current.attributes, "extra": 7})
    )
    assert command.undo(db_service).success
    assert db_service.get_map("source").attributes == {**source.attributes, "extra": 7}
    assert command.execute(db_service).success
    assert db_service.get_map("child").to_dict() == child_before


def test_delete_guard_sees_role_mismatch(db_service):
    for record in [map_record("a"), map_record("b", "a", map_role="master")]:
        db_service.insert_map(record)
    assert not DeleteMapCommand("a").execute(db_service).success
    assert db_service.get_map("a") is not None


def test_invalid_command_leaves_data_untouched(db_service):
    source = map_record("a")
    db_service.insert_map(source)
    assert (
        not ChangeMapParentCommand("a", "a", registration()).execute(db_service).success
    )
    assert db_service.get_map("a").attributes == {}


def test_command_write_failure_rolls_back(db_service, monkeypatch):
    for record in [map_record("a"), map_record("b")]:
        db_service.insert_map(record)
    insert = db_service.insert_map

    def fail_after_write(record):
        insert(record)
        raise RuntimeError("Injected failure after write")

    monkeypatch.setattr(db_service, "insert_map", fail_after_write)
    command = ChangeMapParentCommand("a", "b", registration())
    with pytest.raises(RuntimeError, match="Injected"):
        command.execute(db_service)
    assert db_service.get_map("a").attributes == {}
    assert not command.is_executed


def test_detach_roundtrip_restores_explicit_nulls(db_service):
    source = map_record("a", "b", map_role=None, registration=registration())
    for record in [source, map_record("b")]:
        db_service.insert_map(record)
    command = ChangeMapParentCommand("a", None, None)
    assert command.execute(db_service).success
    assert db_service.get_map("a").attributes == {}
    command = ChangeMapParentCommand.from_dict(command.to_dict())
    assert command.undo(db_service).success
    assert db_service.get_map("a").attributes == source.attributes


@pytest.mark.parametrize("scale,aspect", [(1e-300, 1e300), (1e300, 1e-300)])
def test_noninvertible_numeric_scale_rejected(db_service, scale, aspect):
    for record in [map_record("a"), map_record("b")]:
        db_service.insert_map(record)
    payload = {**registration(), "scale_norm": scale, "aspect_ratio": aspect}
    assert not ChangeMapParentCommand("a", "b", payload).execute(db_service).success
    assert db_service.get_map("a").attributes == {}


def test_stale_proposal_and_undo_do_not_overwrite_hierarchy(db_service):
    for record in [map_record("a"), map_record("b"), map_record("c")]:
        db_service.insert_map(record)
    stale = ChangeMapParentCommand("a", "b", registration(), expected_hierarchy={})
    first = ChangeMapParentCommand("a", "c", registration())
    assert first.execute(db_service).success
    assert not stale.execute(db_service).success
    second = ChangeMapParentCommand("a", "b", registration())
    assert second.execute(db_service).success
    assert not first.undo(db_service).success
    assert db_service.get_map("a").attributes["parent_map_id"] == "b"


def test_invalid_descendant_registration_rejects_attachment(db_service):
    for record in [map_record("a"), map_record("child", "a"), map_record("b")]:
        db_service.insert_map(record)
    command = ChangeMapParentCommand("a", "b", registration())
    assert not command.execute(db_service).success
    assert db_service.get_map("a").attributes == {}


@pytest.mark.parametrize("kind", [SetMasterMapCommand, RegisterDetailMapCommand])
def test_legacy_ui_commands_keep_exact_undo_after_serialization(db_service, kind):
    root = map_record("root", map_role="master")
    source = map_record(
        "source", "root", map_role="detail", registration=registration()
    )
    for record in [root, source]:
        db_service.insert_map(record)
    command = (
        kind("source")
        if kind is SetMasterMapCommand
        else kind("source", "root", {**registration(), "scale_norm": 0.4})
    )
    assert command.execute(db_service).success
    restored = kind.from_dict(json.loads(json.dumps(command.to_dict())))
    current = db_service.get_map("source")
    db_service.insert_map(
        replace(current, attributes={**current.attributes, "extra": 3})
    )
    restored.undo(db_service)
    assert db_service.get_map("source").attributes == {**source.attributes, "extra": 3}
    assert db_service.get_map("root").attributes == root.attributes


def test_null_attributes_do_not_block_unrelated_maps_or_parent_changes(db_service):
    for key in ("source", "parent", "unrelated", "delete"):
        db_service.insert_map(map_record(key))
    with db_service.transaction() as conn:
        conn.execute("UPDATE maps SET attributes=NULL WHERE id != 'delete'")
    maps = db_service.get_all_maps()
    hierarchy = MapHierarchy(maps)
    assert len(hierarchy.roots()) == 4
    assert hierarchy.diagnostics() == {}
    assert all(m.attributes is None for m in maps if m.id != "delete")
    assert hierarchy_attributes(None) == {}
    assert restore_hierarchy_attributes(None, None) == {}
    command = ChangeMapParentCommand("source", "parent", registration())
    assert command.execute(db_service).success
    assert command.undo(db_service).success
    assert db_service.get_map("unrelated").attributes is None
    assert DeleteMapCommand("delete").execute(db_service).success
