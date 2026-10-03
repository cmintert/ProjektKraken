"""Integration regressions for world-owned icon metadata and reversible files."""

import copy
import json
import shutil
from contextlib import contextmanager
from pathlib import Path

import pytest
from PIL import Image

from src.commands.icon_library_commands import IconLibraryCommand
from src.core.entities import Entity
from src.core.map import Map
from src.core.marker import Marker
from src.core.marker_appearance import MARKER_ICON_ANCHOR_ATTRIBUTE
from src.core.marker_sizing import (
    MARKER_SIZING_ATTRIBUTE,
    MARKER_SIZING_SOURCE_ATTRIBUTE,
    MarkerSizingSettings,
)
from src.services.db_service import DatabaseService
from src.services.history_service import HistoryService
from src.services.icon_library_service import IconLibraryService
from src.services.marker_icon_catalog import MarkerIconCatalog
from src.services.repositories.icon_library_repository import IconLibraryRepository

pytestmark = pytest.mark.ci_fast


@pytest.fixture
def library(db_service, tmp_path):
    db_service.world_root = tmp_path
    return IconLibraryService(db_service, str(tmp_path))


def artwork(tmp_path, name="Watchtower.png", color="red"):
    source = tmp_path / name
    Image.new("RGBA", (40, 60), color).save(source)
    return source


def request(library, operation, **kwargs):
    return IconLibraryCommand(str(library.root), "world", operation, **kwargs)


def imported(library, db_service, tmp_path):
    command = request(library, "import", source_paths=[str(artwork(tmp_path))])
    assert command.execute(db_service).success
    return command, command.added[0]["id"]


def marker(db_service, tmp_path, icon_id, *, custom=False, name="Atlas"):
    path = artwork(tmp_path, f"{name}.png")
    image_map = Map(name, str(path))
    db_service.insert_map(image_map)
    entity = Entity("Tower", "Location")
    db_service.insert_entity(entity)
    attrs = {
        "_v_marker_icon_id": icon_id,
        MARKER_SIZING_SOURCE_ATTRIBUTE: "custom" if custom else "icon_default",
        MARKER_SIZING_ATTRIBUTE: MarkerSizingSettings.for_map_image_width(40).to_dict(),
        "unrelated": "keep",
    }
    if custom:
        attrs[MARKER_ICON_ANCHOR_ATTRIBUTE] = {"x": 0.1, "y": 0.2}
    point = Marker(
        image_map.id, entity.id, "entity", 0.5, 0.5, label="Tower", attributes=attrs
    )
    db_service.insert_marker(point)
    return point, path


def test_batch_preserves_names_reuses_bytes_and_keeps_successes(
    library, db_service, tmp_path
):
    source = artwork(tmp_path)
    duplicate = tmp_path / "Different name.png"
    duplicate.write_bytes(source.read_bytes())
    second = artwork(tmp_path, "Harbour.png", "blue")
    invalid = tmp_path / "Broken.svg"
    invalid.write_text("broken")
    command = request(
        library,
        "import",
        source_paths=list(
            map(
                str,
                [
                    source,
                    duplicate,
                    second,
                    invalid,
                    tmp_path / "Missing.png",
                ],
            )
        ),
    )
    result = command.execute(db_service)
    assert result.success
    assert len(command.added) == 2
    assert len(command.report["reused"]) == 1
    assert len(command.report["failed"]) == 2
    assert {d.name for d in library.catalog().custom()} == {"Watchtower", "Harbour"}
    assert len(library.repository.read()) == 2
    assert command.is_undoable
    assert all(d["source_filename"].endswith(".png") for d in command.added)


def test_duplicate_only_and_invalid_batches_have_no_history(
    library, db_service, tmp_path
):
    original, _ = imported(library, db_service, tmp_path)
    before = library.repository.read()
    command = request(library, "import", source_paths=original.source_paths)
    assert command.execute(db_service).success
    assert not command.is_undoable
    assert library.repository.read() == before
    invalid = request(library, "import", source_paths=[str(tmp_path / "none.svg")])
    assert invalid.execute(db_service).success
    assert not invalid.is_undoable
    assert library.repository.read() == before


def test_canonical_discovery_is_read_only_and_duplicate_order_is_stable(
    library, db_service, tmp_path
):
    source = artwork(tmp_path)
    images = tmp_path / "assets" / "images"
    images.mkdir(parents=True)
    ids = ["0" * 32, "1" * 32]
    for icon_id in reversed(ids):
        (images / f"icon_{icon_id}.png").write_bytes(source.read_bytes())
    (images / "icon_short.png").write_bytes(source.read_bytes())
    assert len(library.catalog().custom()) == 2
    assert not library.repository.exists()

    edit = request(
        library,
        "edit",
        icon_id=f"custom.{ids[0]}",
        changes={"name": "Old Watchtower", "category": "Ruins"},
    )
    assert edit.execute(db_service).success
    assert library.catalog().resolve_id(f"custom.{ids[0]}").name == "Old Watchtower"
    assert edit.undo(db_service).success
    assert not library.repository.exists()
    command = request(library, "import", source_paths=[str(source)])
    assert command.execute(db_service).success
    assert command.report["reused"][0]["id"] == f"custom.{ids[0]}"
    assert not library.repository.exists()


def test_import_undo_redo_does_not_need_original_files(library, db_service, tmp_path):
    command, icon_id = imported(library, db_service, tmp_path)
    definition = library.catalog().resolve_id(icon_id)
    path = tmp_path / definition.asset_path
    original_bytes = path.read_bytes()
    Path(command.source_paths[0]).unlink()
    assert command.undo(db_service).success
    assert not path.exists()
    assert not library.repository.exists()
    restored = IconLibraryCommand.from_dict(json.loads(json.dumps(command.to_dict())))
    restored.restore_base_state(command.base_state_dict())
    assert restored.execute(db_service).success
    assert path.read_bytes() == original_bytes
    assert library.catalog().resolve_id(icon_id) == definition


def test_rename_defaults_and_exact_undo_preserve_overrides(
    library, db_service, tmp_path
):
    _, icon_id = imported(library, db_service, tmp_path)
    before = library.catalog().resolve_id(icon_id)
    inheriting, _ = marker(db_service, tmp_path, icon_id)
    overridden, _ = marker(db_service, tmp_path, icon_id, custom=True, name="Detail")
    original_attrs = copy.deepcopy(inheriting.attributes)
    command = request(
        library,
        "edit",
        icon_id=icon_id,
        changes={
            "name": "Lookout",
            "category": "Fortifications",
            "default_native_diameter_px": 20,
            "anchor": {"x": 0.5, "y": 1},
        },
    )
    assert command.execute(db_service).success
    edited = library.catalog().resolve_id(icon_id)
    assert edited.asset_path == before.asset_path and edited.id == before.id
    assert edited.name == "Lookout" and edited.anchor.y == 1
    assert (
        db_service.get_marker(inheriting.id).attributes[MARKER_SIZING_ATTRIBUTE][
            "map_value"
        ]
        == 50
    )
    assert db_service.get_marker(overridden.id).attributes == overridden.attributes
    assert command.undo(db_service).success
    assert library.catalog().resolve_id(icon_id) == before
    assert db_service.get_marker(inheriting.id).attributes == original_attrs
    assert command.execute(db_service).success
    assert library.catalog().resolve_id(icon_id) == edited


def test_unreadable_map_blocks_default_size_change(library, db_service, tmp_path):
    _, icon_id = imported(library, db_service, tmp_path)
    point, image = marker(db_service, tmp_path, icon_id)
    image.unlink()
    before = library.repository.read()
    command = request(
        library, "edit", icon_id=icon_id, changes={"default_native_diameter_px": 25}
    )
    result = command.execute(db_service)
    assert not result.success and "Atlas" in result.message
    assert library.repository.read() == before
    assert db_service.get_marker(point.id).attributes == point.attributes


@pytest.mark.parametrize(
    "changes",
    [
        {"name": " "},
        {"default_native_diameter_px": 0},
        {"default_native_diameter_px": float("nan")},
        {"anchor": {"x": 2, "y": 0}},
        {"id": "other"},
        {"asset_path": "../outside.png"},
    ],
)
def test_invalid_edits_leave_metadata_unchanged(library, db_service, tmp_path, changes):
    _, icon_id = imported(library, db_service, tmp_path)
    before = library.repository.read()
    assert (
        not request(library, "edit", icon_id=icon_id, changes=changes)
        .execute(db_service)
        .success
    )
    assert library.repository.read() == before


def test_bundled_icons_are_immutable(library, db_service):
    for operation in ("delete", "edit"):
        result = request(library, operation, icon_id="map.pin").execute(db_service)
        assert not result.success
    assert not library.repository.exists()


def test_usage_blocks_delete_and_import_undo_across_consumers(
    library, db_service, tmp_path
):
    imported_command, icon_id = imported(library, db_service, tmp_path)
    point, _ = marker(db_service, tmp_path, icon_id)
    db_service.set_graph_lexicon(
        {"nodes": {"Location": {"icon_id": icon_id}}, "edges": {}}
    )
    command = request(library, "delete", icon_id=icon_id)
    result = command.execute(db_service)
    assert not result.success
    assert "Atlas" in result.message and "Visual Lexicon: Location" in result.message
    assert not imported_command.undo(db_service).success
    assert library.catalog().resolve_id(icon_id) is not None
    db_service.delete_marker(point.id)
    db_service.set_graph_lexicon({"nodes": {}, "edges": {}})
    command.protected = {icon_id: ["Open Visual Lexicon draft: Tower"]}
    result = command.execute(db_service)
    assert not result.success and "draft" in result.message


def test_delete_restores_artwork_and_metadata_after_database_reopen(tmp_path, qapp):
    db_path = tmp_path / "world.kraken"
    db = DatabaseService(str(db_path), world_root=tmp_path)
    db.connect()
    library = IconLibraryService(db, str(tmp_path))
    _, icon_id = imported(library, db, tmp_path)
    definition = library.catalog().resolve_id(icon_id)
    path = tmp_path / definition.asset_path
    original = path.read_bytes()
    command = request(library, "delete", icon_id=icon_id)
    assert command.execute(db).success
    payload = json.loads(json.dumps(command.to_dict()))
    base = command.base_state_dict()
    db.close()
    db = DatabaseService(str(db_path), world_root=tmp_path)
    db.connect()
    command = IconLibraryCommand.from_dict(payload)
    command.restore_base_state(base)
    assert command.undo(db).success
    assert path.read_bytes() == original
    assert (
        IconLibraryService(db, str(tmp_path)).catalog().resolve_id(icon_id)
        == definition
    )
    assert command.execute(db).success and not path.exists()
    db.close()


@pytest.mark.parametrize("failure", ["missing", "collision"])
def test_restore_failure_retains_metadata_and_recovery(
    library, db_service, tmp_path, failure
):
    _, icon_id = imported(library, db_service, tmp_path)
    command = request(library, "delete", icon_id=icon_id)
    assert command.execute(db_service).success
    target_rel, artifact_rel = next(iter(command.artifact_manifest.items()))
    if failure == "missing":
        (tmp_path / artifact_rel).unlink()
    else:
        (tmp_path / target_rel).write_bytes(b"unrelated")
    assert not command.undo(db_service).success
    assert icon_id not in library.repository.read()
    assert command.is_executed
    if failure == "collision":
        assert (tmp_path / target_rel).read_bytes() == b"unrelated"
        assert (tmp_path / artifact_rel).exists()


def test_database_write_failure_compensates_import_and_delete(
    library, db_service, tmp_path, monkeypatch
):
    imported_command, icon_id = imported(library, db_service, tmp_path)
    path = tmp_path / imported_command.added[0]["asset_path"]
    before = library.repository.read()

    def fail(*args):
        raise RuntimeError("injected write failure")

    monkeypatch.setattr(IconLibraryRepository, "write", fail)
    command = request(library, "delete", icon_id=icon_id)
    assert not command.execute(db_service).success
    assert path.exists() and library.repository.read() == before
    source = artwork(tmp_path, "Another.png", "green")
    command = request(library, "import", source_paths=[str(source)])
    assert not command.execute(db_service).success
    assert len(list((tmp_path / "assets" / "images").glob("icon_*"))) == 1


def test_commit_failure_compensates_files(library, db_service, tmp_path, monkeypatch):
    _, icon_id = imported(library, db_service, tmp_path)
    path = library.catalog().asset_file(library.catalog().resolve_id(icon_id))
    before = library.repository.read()
    original_transaction = db_service.transaction

    @contextmanager
    def failing_commit():
        with original_transaction():
            yield
            raise RuntimeError("commit failed")

    monkeypatch.setattr(db_service, "transaction", failing_commit)
    command = request(library, "delete", icon_id=icon_id)
    with pytest.raises(RuntimeError, match="commit failed"):
        command.execute(db_service)
    assert path.exists()
    assert library.repository.read() == before
    assert not command.is_executed


def test_external_database_uses_explicit_world_root(library, db_service, tmp_path):
    wrong = request(library, "load")
    wrong.world_root = str(tmp_path / "external_database_parent")
    assert not wrong.execute(db_service).success
    assert not library.repository.exists()


def test_catalog_metadata_cannot_redirect_stable_identity(
    library, db_service, tmp_path
):
    _, icon_id = imported(library, db_service, tmp_path)
    metadata = library.repository.read()
    metadata[icon_id]["asset_path"] = "assets/images/icon_" + "f" * 32 + ".png"
    with pytest.raises(ValueError, match="identity"):
        MarkerIconCatalog.load(tmp_path, metadata)


def test_defaults_use_each_maps_image_width(library, db_service, tmp_path):
    _, icon_id = imported(library, db_service, tmp_path)
    first, _ = marker(db_service, tmp_path, icon_id)
    second, image = marker(db_service, tmp_path, icon_id, name="Continent")
    Image.new("RGB", (400, 200), "white").save(image)
    command = request(
        library, "edit", icon_id=icon_id, changes={"default_native_diameter_px": 20}
    )
    assert command.execute(db_service).success
    assert (
        db_service.get_marker(first.id).attributes[MARKER_SIZING_ATTRIBUTE]["map_value"]
        == 50
    )
    assert (
        db_service.get_marker(second.id).attributes[MARKER_SIZING_ATTRIBUTE][
            "map_value"
        ]
        == 5
    )


@pytest.mark.parametrize("present", [False, True])
def test_default_undo_restores_absent_and_null_fields_exactly(
    library, db_service, tmp_path, present
):
    _, icon_id = imported(library, db_service, tmp_path)
    point, _ = marker(db_service, tmp_path, icon_id)
    point.attributes.pop(MARKER_SIZING_ATTRIBUTE)
    if present:
        point.attributes[MARKER_SIZING_ATTRIBUTE] = None
    with db_service.transaction() as connection:
        connection.execute(
            "UPDATE markers SET attributes = ? WHERE id = ?",
            (json.dumps(point.attributes), point.id),
        )
    command = request(
        library, "edit", icon_id=icon_id, changes={"default_native_diameter_px": 20}
    )
    assert command.execute(db_service).success
    assert command.undo(db_service).success
    assert db_service.get_marker(point.id).attributes == point.attributes


def test_interrupted_batch_stash_and_restore_are_atomic(
    library, db_service, tmp_path, monkeypatch
):
    command = request(
        library,
        "import",
        source_paths=[
            str(artwork(tmp_path)),
            str(artwork(tmp_path, "Harbour.png", "blue")),
        ],
    )
    assert command.execute(db_service).success
    paths = [tmp_path / d["asset_path"] for d in command.added]
    before = library.repository.read()
    icon_id = command.added[1]["id"]
    assert (
        not request(library, "usage", icon_id=icon_id)
        .execute(db_service)
        .data["report"]["usage"]
    )
    point, _ = marker(db_service, tmp_path, icon_id)
    assert not request(library, "delete", icon_id=icon_id).execute(db_service).success
    assert not command.undo(db_service).success
    assert all(p.exists() for p in paths) and library.repository.read() == before
    db_service.delete_marker(point.id)
    original_move = shutil.move
    calls = 0

    def fail_second_move(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected file failure")
        return original_move(*args, **kwargs)

    monkeypatch.setattr(shutil, "move", fail_second_move)
    assert not command.undo(db_service).success
    assert all(p.exists() for p in paths)
    assert library.repository.read() == before
    monkeypatch.setattr(shutil, "move", original_move)
    assert command.undo(db_service).success
    calls = 0
    monkeypatch.setattr(shutil, "move", fail_second_move)
    assert not command.execute(db_service).success
    assert not any(p.exists() for p in paths)
    assert all((tmp_path / p).exists() for p in command.artifact_manifest.values())
    assert not library.repository.exists()


def test_failed_compensation_retains_artifact_and_never_overwrites(
    library, db_service, tmp_path, monkeypatch
):
    original, icon_id = imported(library, db_service, tmp_path)
    target = tmp_path / original.added[0]["asset_path"]
    original_bytes = target.read_bytes()

    def fail_with_collision(*args):
        target.write_bytes(b"independent replacement")
        raise RuntimeError("injected database failure")

    monkeypatch.setattr(IconLibraryRepository, "write", fail_with_collision)
    command = request(library, "delete", icon_id=icon_id)
    with pytest.raises(FileExistsError):
        command.execute(db_service)
    assert target.read_bytes() == b"independent replacement"
    assert (tmp_path / next(iter(command.artifact_manifest.values()))).read_bytes() == (
        original_bytes
    )
    assert icon_id in library.repository.read()


def test_persisted_delete_history_and_pruning_use_external_world_root(
    tmp_path, qapp, monkeypatch
):
    from src.services.migrations import recovery

    monkeypatch.setattr(recovery, "get_backup_directory", lambda: tmp_path / "backups")
    world = tmp_path / "portable-world"
    world.mkdir()
    db_path = tmp_path / "externally-linked.kraken"
    db = DatabaseService(str(db_path), world_root=world)
    db.connect()
    library = IconLibraryService(db, str(world))
    _, icon_id = imported(library, db, world)
    deletion = request(library, "delete", icon_id=icon_id)
    assert deletion.execute(db).success
    history = HistoryService(db, "world")
    history.register_command_type("IconLibraryCommand", IconLibraryCommand)
    history.save_command(deletion)
    connection = db.require_connection()
    connection.execute("BEGIN IMMEDIATE")
    bundle = recovery.create_recovery_bundle(connection, str(db_path), world, {})
    connection.rollback()
    artifact_rel = next(iter(deletion.artifact_manifest.values()))
    assert (
        bundle / "command_artifacts" / artifact_rel.removeprefix("assets/.history/")
    ).exists()
    db.close()
    db = DatabaseService(str(db_path), world_root=world)
    db.connect()
    history = HistoryService(db, "world")
    history.register_command_type("IconLibraryCommand", IconLibraryCommand)
    restored = history.load_recent_history()[0]
    assert restored.undo(db).success
    history.set_command_executed(restored.command_id, False)
    connection = db.require_connection()
    connection.execute("BEGIN IMMEDIATE")
    recovery.create_recovery_bundle(connection, str(db_path), world, {})
    connection.rollback()
    assert restored.execute(db).success
    artifact = world / next(iter(restored.artifact_manifest.values()))
    assert artifact.exists()
    history.clear_all_history()
    assert not artifact.exists()
    db.close()
