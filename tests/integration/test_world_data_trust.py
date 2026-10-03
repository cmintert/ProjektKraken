"""Real output and fresh-session checks for the KRT-17 source trust gates."""

import os
import re
import sqlite3
from contextlib import closing
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PIL import Image
from PySide6.QtCore import QByteArray, QRectF, Qt, QUrl
from PySide6.QtGui import QImage, QTextDocument

from src.app.command_coordinator import CommandCoordinator
from src.app.coordinators.editor_coordinator import EditorCoordinator
from src.app.coordinators.transfer_coordinator import TransferCoordinator
from src.app.data_handler import DataHandler
from src.app.raster_controller import RasterController
from src.commands.entity_commands import DeleteEntityCommand
from src.commands.map_crud_commands import DeleteMapCommand
from src.commands.raster_commands import (
    CreateRasterLayerCommand,
    RemoveRasterSnapshotCommand,
    SetRasterSnapshotCommand,
)
from src.commands.registry import get_command_types
from src.core.entities import Entity
from src.core.feature_geometry_state import FeatureGeometryState
from src.core.image_attachment import ImageAttachment
from src.core.map import Map, MapLayerNode
from src.core.marker import Marker
from src.gui.dialogs.transfer_dialog import TransferDialog
from src.gui.widgets.longform.editor import LongformEditorWidget
from src.services.db_service import DatabaseService
from src.services.transfer_worker import TransferWorker
from src.services.worker import DatabaseWorker

pytestmark = pytest.mark.ci_fast


@pytest.mark.parametrize("extension", ["png", "webp"])
def test_longform_preview_loads_world_relative_image(qtbot, tmp_path, extension):
    """Resolve actual image resources from a world path containing spaces."""
    world = tmp_path / "Trust World"
    relative_path = f"assets/portrait.{extension}"
    image_path = world / relative_path
    image_path.parent.mkdir(parents=True)
    Image.new("RGB", (4, 4), "red").save(image_path, lossless=True)
    editor = LongformEditorWidget(db_path=str(world / "Trust World.kraken"))
    qtbot.addWidget(editor)
    editor.load_sequence([
        {
            "table": "entities", "id": "portrait", "name": "Portrait",
            "heading_level": 1, "meta": {},
            "content": f"![portrait]({relative_path})",
        }
    ])
    resource = editor.content.document().resource(
        QTextDocument.ResourceType.ImageResource, QUrl(relative_path)
    )
    assert resource is not None
    image = resource.toImage() if hasattr(resource, "toImage") else resource
    if isinstance(image, QByteArray):
        assert bytes(image) == image_path.read_bytes(), bytes(image)[:100]
        # QTextBrowser can retain encoded resources rather than decoded images.
        with Image.open(BytesIO(bytes(image))) as decoded:
            assert decoded.convert("RGB").getpixel((0, 0)) == (255, 0, 0)
        if extension == "webp":
            return
        image = QImage.fromData(image)
    assert not image.isNull()
    assert image.pixelColor(0, 0).name() == "#ff0000"


@pytest.mark.parametrize("images", [True, False])
def test_markdown_create_output_through_dialog_and_coordinator(
    trust_world, qtbot, images
):
    """Exercise the actual review-to-export request, including image choices."""
    db, root = trust_world
    assets = root / "assets"
    assets.mkdir()
    Image.new("RGB", (4, 4), "red").save(assets / "portrait.png")
    db.insert_entity(
        Entity(
            name="Portrait",
            type="Character",
            description="![portrait](assets/portrait.png)",
            attributes={"_longform": {"default": {"position": 100, "depth": 0}}},
        )
    )
    dialog = TransferDialog()
    qtbot.addWidget(dialog)
    worker = DatabaseWorker(db.db_path, get_command_types(), world_root=root)
    worker.db_service = db
    coordinator = TransferCoordinator(
        dialog, worker, lambda: {}, lambda command: None, lambda: True,
        lambda: None, lambda: [], {},
    )
    coordinator.dialog = dialog
    coordinator._world = {"db_path": db.db_path, "path": str(root)}
    dialog.review_requested.connect(coordinator._review)
    dialog.apply_requested.connect(coordinator._apply)
    dialog.tabs.setCurrentIndex(1)
    dialog.export_format.setCurrentIndex(dialog.export_format.findData("markdown"))
    dialog.images.setChecked(images)
    destination = root / "external" / "document.md"
    dialog.destination.setText(str(destination))
    dialog.show()
    qtbot.mouseClick(dialog.next, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: dialog.pages.currentIndex() == 1)
    with qtbot.waitSignal(coordinator._worker.finished):
        qtbot.mouseClick(dialog.next, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(
        lambda: dialog.pages.currentIndex() == 2 or dialog.next.isEnabled()
    )
    assert dialog.pages.currentIndex() == 2, dialog.status.text()
    content = destination.read_text(encoding="utf-8")
    assert "Portrait" in content
    copied = list(destination.with_name("document.md.assets").glob("*.png"))
    assert bool(copied) == images


@pytest.fixture
def trust_world(db_service, tmp_path):
    """Extend the shared database fixture with a real world file."""
    path = tmp_path / "Trust World.kraken"
    with closing(sqlite3.connect(path)) as target:
        db_service.get_connection().backup(target)
    service = DatabaseService(str(path), world_root=tmp_path)
    service.connect()
    yield service, tmp_path
    service.close()


@pytest.fixture
def command_pipeline(trust_world, qapp, qtbot):
    """Use real serialized command requests, queued execution, and canonical undo."""
    db, root = trust_world
    worker = DatabaseWorker(db.db_path, get_command_types(), world_root=root)
    worker.db_service = db
    coordinator = CommandCoordinator(Mock())
    coordinator.command_requested.connect(
        worker.run_command, Qt.ConnectionType.QueuedConnection
    )
    coordinator.undo_requested.connect(
        worker.run_undo, Qt.ConnectionType.QueuedConnection
    )
    coordinator.redo_requested.connect(
        worker.run_redo, Qt.ConnectionType.QueuedConnection
    )
    worker.command_finished.connect(coordinator.on_command_result)
    results = []
    worker.command_finished.connect(results.append)

    def execute(command):
        count = len(results)
        coordinator.execute_command(command)
        qtbot.waitUntil(lambda: len(results) > count)
        assert results[-1].success, results[-1].message

    def undo():
        count = len(results)
        coordinator.undo()
        qtbot.waitUntil(lambda: len(results) > count)
        assert results[-1].success, results[-1].message

    return SimpleNamespace(
        execute=execute, undo=undo, coordinator=coordinator, worker=worker
    )


def export(worker, db, root, destination, key):
    request = {
        "job_id": "trust-export",
        "operation": "prepare_export",
        "db_path": db.db_path,
        "format": key,
        "scope": "all",
        "options": {"title": "Chronique — 世界", "images": True},
        "world": {"path": str(root)},
        "destination": str(destination),
    }
    results = []
    worker.finished.connect(results.append)
    worker.run(request)
    assert results[-1]["success"], results[-1]
    prepared = results[-1]
    worker.run({**request, "operation": "export", "prepared": prepared})
    return results[-1]


@pytest.mark.parametrize("key", ["markdown", "notes"])
def test_exported_images_and_unicode_survive_outside_world(trust_world, key):
    db, root = trust_world
    assets = root / "assets"
    assets.mkdir()
    Image.new("RGB", (4, 4), "red").save(assets / "portrait.png")
    first = Entity(
        name="Étoile",
        type="person",
        description="**世界** ![portrait](assets/portrait.png) [[Harbour|Port]]",
        attributes={"_longform": {"default": {"position": 2}}},
    )
    second = Entity(
        name="Harbour",
        type="place",
        description="A safe port.",
        attributes={"_longform": {"default": {"position": 1}}},
    )
    db.insert_entity(first)
    db.insert_entity(second)
    db.insert_relation(first.id, second.id, "visits")
    destination = root / "external" / ("chronicle.md" if key == "markdown" else "vault")
    result = export(TransferWorker(lambda: db), db, root, destination, key)
    assert result["success"], result
    files = [destination] if key == "markdown" else list(destination.glob("*.md"))
    content = "\n".join(path.read_text(encoding="utf-8") for path in files)
    assert "世界" in content
    if key == "markdown":
        assert content.index("# Harbour") < content.index("# Étoile")
        assert f"[Port](#item-{second.id})" in content
    else:
        assert "[[Harbour]]" in content
    for path in files:
        for source in re.findall(r"!\[[^\]]*\]\(([^)]+)\)", path.read_text("utf-8")):
            assert (path.parent / source).is_file(), source
            assert (path.parent / source).read_bytes() == (
                assets / "portrait.png"
            ).read_bytes()


def test_relation_links_use_actual_export_filenames(trust_world):
    db, root = trust_world
    first = Entity(name="Harbour/City", type="place")
    second = Entity(name="HarbourCity", type="place")
    db.insert_entity(first)
    db.insert_entity(second)
    db.insert_relation(second.id, first.id, "linked")
    destination = root / "vault"
    assert export(TransferWorker(lambda: db), db, root, destination, "notes")["success"]
    notes = {path: path.read_text("utf-8") for path in destination.glob("*.md")}
    source = next(text for text in notes.values() if second.id in text)
    target = next(path for path, text in notes.items() if first.id in text)
    assert f"[[{target.stem}]]" in source


def test_note_filename_collisions_never_overwrite_lore(trust_world):
    db, root = trust_world
    entities = [
        Entity(name=name, type="place") for name in ["Port", "port", "Port (2)"]
    ]
    for entity in entities:
        db.insert_entity(entity)
    destination = root / "vault"
    assert export(TransferWorker(lambda: db), db, root, destination, "notes")["success"]
    contents = [path.read_text("utf-8") for path in destination.glob("*.md")]
    assert len(contents) == 3
    for entity in entities:
        assert sum(entity.id in content for content in contents) == 1


def test_entity_delete_undo_preserves_relations_and_image(
    trust_world, command_pipeline
):
    db, root = trust_world
    first = Entity(name="Étoile", type="person")
    second = Entity(name="Harbour", type="place")
    db.insert_entity(first)
    db.insert_entity(second)
    relation = db.insert_relation(first.id, second.id, "visits")
    image = root / "assets" / "images" / "portrait.png"
    image.parent.mkdir(parents=True)
    Image.new("RGB", (4, 4), "red").save(image)
    original = image.read_bytes()
    attachment = ImageAttachment(
        id="trust-image",
        owner_type="entity",
        owner_id=first.id,
        image_rel_path="assets/images/portrait.png",
    )
    db.get_attachment_repo().insert(attachment)
    command = DeleteEntityCommand(first.id)
    command_pipeline.execute(command)
    assert db.get_entity(first.id) is None
    assert db.get_relation(relation) is None
    command_pipeline.undo()
    assert db.get_entity(first.id).to_dict() == first.to_dict()
    assert db.get_relation(relation)["target_id"] == second.id
    assert db.get_attachment_repo().get(attachment.id) == attachment
    assert image.read_bytes() == original


def test_dated_raster_fresh_session_and_snapshot_undo(trust_world, qapp):
    db, root = trust_world
    map_obj = Map(
        name="Climate", image_path="map.png", layers=MapLayerNode(name="Root")
    )
    db.insert_map(map_obj)
    created = CreateRasterLayerCommand(
        map_obj.id, "Rain", 4, 4, "discrete", 0, world_root=str(root)
    ).execute(db)
    assert created.success
    node = created.data["node_id"]
    snapshots = {}
    for date, value in [(10.0, 10), (20.0, 20)]:
        import numpy as np

        from src.core.raster_grid import encode_value_png

        relative = f"rasters/state-{int(date)}.png"
        command = SetRasterSnapshotCommand(
            map_obj.id,
            node,
            date,
            relative,
            dict(snapshots),
            encode_value_png(np.full((4, 4), value, dtype=np.uint16)),
        )
        assert command.execute(db).success
        snapshots[format(date, ".17g")] = relative
    db.close()
    fresh = DatabaseService(db.db_path, world_root=root)
    fresh.connect()
    try:
        loaded = fresh.get_map(map_obj.id)
        metadata = loaded.attributes["raster_layers"][0]
        assert metadata["snapshots"] == snapshots
        item = Mock()
        widget = SimpleNamespace(
            maps_data=[loaded], view=SimpleNamespace(_raster_items={node: item})
        )
        controller = RasterController(widget, lambda: fresh.db_path)
        controller._current_map_id = map_obj.id
        for date, expected in [(0, 0), (10, 10), (15, 10), (20, 20), (25, 20)]:
            controller._current_lore_date = date
            controller._apply_temporal_rasters()
            buffer = item.swap_buffer.call_args.args[0]
            assert buffer.get_value_at(0.5, 0.5) == expected
        original = (root / snapshots["10"]).read_bytes()
        deletion = RemoveRasterSnapshotCommand(
            map_obj.id, node, 10.0, str(root), dict(snapshots)
        )
        assert deletion.execute(fresh).success
        assert not (root / snapshots["10"]).exists()
        deletion.undo(fresh)
        assert (root / snapshots["10"]).read_bytes() == original
        assert (
            fresh.get_map(map_obj.id).attributes["raster_layers"][0]["snapshots"]
            == snapshots
        )
        # Metadata reloads after deletion/undo must respect the unmoved playhead.
        widget.layer_panel = Mock()
        widget._cached_entities = []
        widget._cached_events = []
        widget.view.graphics_scene = Mock()
        widget.view.pixmap_item = Mock()
        widget.view.pixmap_item.boundingRect.return_value = QRectF(0, 0, 4, 4)
        controller._current_lore_date = 25.0
        late_deletion = RemoveRasterSnapshotCommand(
            map_obj.id, node, 20.0, str(root), dict(snapshots)
        )
        for operation, expected in [
            (lambda: None, 20),
            (lambda: late_deletion.execute(fresh), 10),
            (lambda: late_deletion.undo(fresh), 20),
            (lambda: late_deletion.execute(fresh), 10),
            (lambda: late_deletion.undo(fresh), 20),
        ]:
            operation()
            widget.maps_data = [fresh.get_map(map_obj.id)]
            controller.load_raster_layers(map_obj.id)
            displayed = widget.view._raster_items[node].buffer
            assert displayed.get_value_at(0.5, 0.5) == expected
            assert controller._current_lore_date == 25.0
    finally:
        fresh.close()


def test_map_delete_undo_restores_complete_saved_state(trust_world, command_pipeline):
    db, root = trust_world
    entity = Entity(name="Border", type="place")
    db.insert_entity(entity)
    map_obj = Map(
        name="Borders", image_path="map.png", layers=MapLayerNode(name="Root")
    )
    db.insert_map(map_obj)
    marker = Marker(
        map_id=map_obj.id,
        object_id=entity.id,
        object_type="entity",
        x=0.2,
        y=0.2,
        feature_type="region",
        geometry=[{"x": 0.1, "y": 0.1}, {"x": 0.3, "y": 0.1}, {"x": 0.2, "y": 0.3}],
    )
    db.insert_marker(marker)
    state = FeatureGeometryState(
        marker_id=marker.id,
        effective_date=10,
        geometry=marker.geometry,
        anchor_x=0.2,
        anchor_y=0.2,
    )
    db.feature_geometry_repo.replace_marker_states(marker.id, [state])
    created = CreateRasterLayerCommand(
        map_obj.id, "Rain", 4, 4, "discrete", 7, world_root=str(root)
    ).execute(db)
    raster = root / created.data["file_path"]
    image = raster.read_bytes()
    original_map = db.get_map(map_obj.id).to_dict()
    original_marker = db.get_marker(marker.id).to_dict()
    original_states = db.feature_geometry_repo.get_states(marker.id)
    command = DeleteMapCommand(map_obj.id)
    command_pipeline.execute(command)
    assert db.get_map(map_obj.id) is None
    assert db.get_marker(marker.id) is None
    assert not raster.exists()
    command_pipeline.undo()
    assert db.get_map(map_obj.id).to_dict() == original_map
    assert db.get_marker(marker.id).to_dict() == original_marker
    assert db.feature_geometry_repo.get_states(marker.id) == original_states
    assert raster.read_bytes() == image


@pytest.mark.parametrize("key", ["markdown", "notes"])
def test_failed_export_preserves_existing_output(trust_world, key, monkeypatch):
    db, root = trust_world
    entity = Entity(
        name="Author",
        type="person",
        description="New text",
        attributes={"_longform": {"default": {"position": 1}}},
    )
    db.insert_entity(entity)
    destination = root / ("document.md" if key == "markdown" else "vault")
    if key == "notes":
        destination.mkdir()
        previous = destination / "original.md"
    else:
        previous = destination
    previous.write_text("original", encoding="utf-8")
    if key == "markdown":
        assets = destination.with_name(destination.name + ".assets")
        assets.mkdir()
        (assets / "old.png").write_bytes(b"old image")
        (root / "assets").mkdir()
        Image.new("RGB", (4, 4), "red").save(root / "assets" / "new.png")
        entity.description += " ![new](assets/new.png)"
        db.insert_entity(entity)
        original_replace = os.replace

        def fail_replace(source, target):
            if str(target) == str(destination):
                raise OSError("injected publish failure")
            return original_replace(source, target)

        monkeypatch.setattr("src.services.transfer_files.os.replace", fail_replace)
    else:

        def fail_copy(*args, **kwargs):
            raise OSError("injected asset export failure")

        monkeypatch.setattr(
            "src.services.transfer_worker.copy_markdown_images", fail_copy
        )
    result = export(TransferWorker(lambda: db), db, root, destination, key)
    assert not result["success"]
    assert previous.read_text("utf-8") == "original"
    if key == "markdown":
        assert (assets / "old.png").read_bytes() == b"old image"
        assert len(list(assets.iterdir())) == 1


@pytest.mark.parametrize("action", ["cancel", "remove_and_delete", "delete_anyway"])
def test_entity_delete_keeps_or_restores_raster_mapping(
    trust_world, command_pipeline, qapp, qtbot, monkeypatch, action
):
    from PySide6.QtWidgets import QWidget

    db, root = trust_world
    entity = Entity(name="Rain", type="concept")
    db.insert_entity(entity)
    map_obj = Map(
        name="Climate",
        image_path="map.png",
        attributes={
            "raster_layers": [
                {
                    "node_id": "rain",
                    "value_entity_map": {
                        "mode": "exact",
                        "mappings": [
                            {
                                "value": 1,
                                "entity_id": entity.id,
                            }
                        ],
                    },
                }
            ]
        },
    )
    db.insert_map(map_obj)
    window = QWidget()
    window.map_handler = SimpleNamespace(
        _map_widget=SimpleNamespace(maps_data=[map_obj])
    )
    editor = EditorCoordinator(window)
    editor.command_requested.connect(command_pipeline.coordinator.execute_command)
    handler = DataHandler()
    map_reloads = []
    handler.reload_maps.connect(lambda: map_reloads.append(True))
    command_pipeline.worker.command_finished.connect(handler.on_command_finished)
    dialog = Mock(result_action=action)
    monkeypatch.setattr(
        "src.gui.dialogs.raster_orphan_warning_dialog.RasterOrphanWarningDialog",
        Mock(return_value=dialog),
    )
    editor.delete_entity(entity.id)
    assert dialog.exec.called
    if action != "cancel":
        qtbot.waitUntil(
            lambda: bool(command_pipeline.coordinator.undo_stack)
            and not command_pipeline.coordinator._pending_commands
        )
        assert db.get_entity(entity.id) is None
        mappings = db.get_map(map_obj.id).attributes["raster_layers"][0][
            "value_entity_map"
        ]["mappings"]
        assert bool(mappings) == (action == "delete_anyway")
        if action == "remove_and_delete":
            assert map_reloads, "Palette metadata must refresh after deletion"
        command_pipeline.undo()
    assert db.get_entity(entity.id).to_dict() == entity.to_dict()
    assert db.get_map(map_obj.id).to_dict() == map_obj.to_dict()
    assert not command_pipeline.coordinator.undo_stack
    if action != "cancel":
        with qtbot.waitSignal(command_pipeline.worker.command_finished):
            command_pipeline.coordinator.redo()
        assert db.get_entity(entity.id) is None
        command_pipeline.undo()
        assert db.get_entity(entity.id).to_dict() == entity.to_dict()
        assert db.get_map(map_obj.id).to_dict() == map_obj.to_dict()
        assert not command_pipeline.coordinator.undo_stack
    window.deleteLater()


def test_map_delete_cancel_keeps_saved_state(
    trust_world, command_pipeline, monkeypatch
):
    from PySide6.QtWidgets import QMessageBox, QWidget

    from src.gui.mixins.map_dialog_mixin import MapDialogMixin

    db, root = trust_world
    map_obj = Map(name="Map", image_path="map.png")
    db.insert_map(map_obj)
    window = QWidget()
    window.map_selector = Mock()
    window.map_selector.currentData.return_value = map_obj.id
    window.map_deleted = Mock()
    monkeypatch.setattr(
        "src.gui.mixins.map_dialog_mixin.QMessageBox.question",
        Mock(return_value=QMessageBox.StandardButton.No),
    )
    MapDialogMixin._on_delete_map_clicked(window)
    window.map_deleted.emit.assert_not_called()
    assert db.get_map(map_obj.id).to_dict() == map_obj.to_dict()
    assert not command_pipeline.coordinator.undo_stack
    window.deleteLater()
