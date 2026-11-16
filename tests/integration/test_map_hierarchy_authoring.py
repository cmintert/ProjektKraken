"""Exercise hierarchy authoring through real widgets, guards and commands."""

from dataclasses import replace
from pathlib import Path

import pytest
from PySide6.QtCore import QObject, Qt, Slot
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication, QStyleOptionGraphicsItem, QWidget

from src.app.coordinators.map_edit_transition_coordinator import (
    MapEditTransitionCoordinator,
)
from src.app.map_handler import MapHandler
from src.commands.base_command import CommandResult
from src.commands.map_hierarchy_commands import ChangeMapParentCommand
from src.core.feature_geometry_state import FeatureGeometryState
from src.core.map import Map, MapLayerNode
from src.core.marker import Marker
from src.core.region_geometry import RegionPolygon
from src.core.trajectory import Keyframe
from src.gui.dialogs.map_hierarchy_dialog import MapHierarchyDialog
from src.gui.dialogs.register_detail_map_dialog import RegisterDetailMapDialog
from src.gui.widgets.map.detail_map_footprint_item import DetailMapFootprintItem
from src.gui.widgets.map_widget import MapWidget
from src.services.map_hierarchy_options import candidate_parents
from src.services.map_nesting_service import MapNestingService

pytestmark = pytest.mark.ci_fast


class ReadWorker(QObject):
    @Slot(str)
    def load_markers(self, map_id):
        pass

    @Slot(str)
    def load_trajectories(self, map_id):
        pass

    @Slot(str)
    def load_feature_geometry_states(self, map_id):
        pass


def registration():
    return {
        "mode": "aspect_locked_affine",
        "version": 1,
        "master_center_norm": {"x": 0.4, "y": 0.6},
        "scale_norm": 0.3,
        "rotation_deg": 25.0,
        "aspect_ratio": 1.0,
        "confidence": "suggested",
    }


@pytest.fixture
def authoring(qtbot, tmp_path, db_service):
    records = []
    for key, size in (
        ("source", (400, 200)),
        ("parent", (600, 400)),
        ("child", (100, 100)),
    ):
        image = QImage(*size, QImage.Format.Format_RGB32)
        image.fill(Qt.GlobalColor.gray)
        path = tmp_path / f"{key}.png"
        assert image.save(str(path))
        attributes = {"width_meters": 1000, "authored": {"text": "unchanged"}}
        if key == "child":
            attributes.update(
                parent_map_id="source", map_role="master", registration=registration()
            )
        if key == "source":
            attributes["map_role"] = "master"
        record = Map(id=key, name=key, image_path=str(path), attributes=attributes)
        db_service.insert_map(record)
        records.append(record)
    widget = MapWidget()
    if QApplication.platformName() == "offscreen":
        widget.view.setViewport(QWidget())
    qtbot.addWidget(widget)
    worker = ReadWorker()
    handler = MapHandler(
        widget, worker, lambda: str(tmp_path / "world.kraken"), lambda *_: None
    )
    widget.map_selected.connect(handler.on_map_selected)
    widget.view.footprint_edit_confirmed.connect(handler.on_footprint_edit_confirmed)
    handler.on_maps_ready(records)
    widget.resize(960, 720)
    widget.show()
    commands = []
    handler.command_requested.connect(commands.append)
    return widget, handler, commands, db_service, worker


def test_candidates_include_roots_and_exclude_self_descendants_and_depth():
    maps = [Map(id=str(i), name=str(i), image_path="") for i in range(7)]
    for i in range(1, 5):
        maps[i].attributes["parent_map_id"] = str(i - 1)
    assert [m.id for m in candidate_parents(maps, "0")] == []
    assert "0" in [m.id for m in candidate_parents(maps, "6")]
    assert "4" not in [m.id for m in candidate_parents(maps, "6")]


def test_preview_cancel_preserves_database_descendants_and_origin(authoring):
    widget, handler, commands, db, _ = authoring
    before = [record.to_dict() for record in db.get_all_maps()]
    widget.view.scale(1.4, 1.4)
    transform = widget.view.transform()
    handler.on_register_detail_map_requested("source", "parent", registration())
    assert widget.get_selected_map_id() == "parent"
    assert widget.view.is_editing_footprint
    assert "source" in widget.view.footprint_names()
    assert widget.footprint_controls.isVisible()
    assert not commands
    assert before == [record.to_dict() for record in db.get_all_maps()]
    widget.view.cancel_footprint_edit()
    assert widget.get_selected_map_id() == "source"
    assert widget.view.transform() == transform
    assert not commands
    assert before == [record.to_dict() for record in db.get_all_maps()]
    assert "child" in widget.view.footprint_names()  # role mismatch remains traversable


def test_apply_is_one_command_and_serialized_undo_preserves_local_content(authoring):
    widget, handler, commands, db, _ = authoring
    before = [record.to_dict() for record in db.get_all_maps()]
    handler.on_register_detail_map_requested("source", "parent", registration())
    widget.footprint_controls.reset.click()
    widget.view.finish_footprint_edit()
    assert len(commands) == 1
    command = commands[0]
    assert isinstance(command, ChangeMapParentCommand)
    assert command.registration["rotation_deg"] == 0
    assert command.registration["confidence"] == "user_confirmed"
    result = command.execute(db)
    assert result.success
    handler.hierarchy_coordinator.on_command_finished(
        CommandResult(success=True, data={"command_id": command.command_id})
    )
    handler.on_maps_ready(db.get_all_maps())
    assert "source" in widget.view.footprint_names()
    source = db.get_map("source")
    assert source.attributes["parent_map_id"] == "parent"
    assert source.attributes["width_meters"] == 1000
    assert source.attributes["authored"] == {"text": "unchanged"}
    restored = ChangeMapParentCommand.from_dict(command.to_dict())
    assert restored.undo(db).success
    handler.on_maps_ready(db.get_all_maps())
    widget.select_map("source")
    assert not widget.btn_parent.isVisible()
    assert before == [record.to_dict() for record in db.get_all_maps()]


@pytest.mark.parametrize("decision", ["keep", "discard", "apply"])
def test_preview_uses_protected_navigation_and_waits_for_ack(authoring, decision):
    widget, handler, commands, db, _ = authoring
    owner = handler.hierarchy_coordinator
    guard = MapEditTransitionCoordinator(
        [owner], lambda: "world", lambda *_: decision, lambda _: None
    )
    widget.edit_transition_handler = guard.request_transition
    handler.on_register_detail_map_requested("source", "parent", registration())
    widget.select_map("child")
    if decision == "keep":
        assert widget.get_selected_map_id() == "parent"
        assert widget.view.is_editing_footprint
    elif decision == "discard":
        assert widget.get_selected_map_id() == "child"
        assert not commands
    else:
        assert widget.get_selected_map_id() == "parent"
        assert guard.is_waiting
        assert len(commands) == 1
        assert commands[0].execute(db).success
        owner.on_command_finished(
            CommandResult(success=True, data={"command_id": commands[0].command_id})
        )
        assert widget.get_selected_map_id() == "child"
        assert not guard.is_waiting


def test_failed_ack_retains_preview_and_rejects_other_command_results(authoring):
    widget, handler, commands, _, _ = authoring
    owner = handler.hierarchy_coordinator
    handler.on_register_detail_map_requested("source", "parent", registration())
    widget.view.finish_footprint_edit()
    owner.on_command_finished(CommandResult(success=True, data={"command_id": "other"}))
    assert owner.edit_status()["pending"]
    owner.on_command_finished(
        CommandResult(
            success=False,
            message="Save rejected",
            data={"command_id": commands[0].command_id},
        )
    )
    assert widget.view.is_editing_footprint
    assert not owner.edit_status()["pending"]
    assert widget.footprint_controls.status.text() == "Save rejected"


def test_lock_reset_opacity_and_hierarchy_dialog_are_presentation_only(authoring):
    widget, handler, commands, _, _ = authoring
    picker = RegisterDetailMapDialog(
        widget.maps_data[0], widget.maps_data[1:], parent=widget
    )
    assert picker._parent_combo.itemText(0).endswith("(Independent)")
    assert picker._parent_combo.itemText(1).endswith("(Detail map)")
    picker._accept()
    assert picker.registration()["confidence"] == "suggested"
    hierarchy = MapHierarchyDialog(widget.maps_data, "source", widget)
    assert hierarchy.tree.topLevelItemCount() == 2
    assert hierarchy.tree.currentItem().childCount() == 1
    handler.on_register_detail_map_requested("source", "parent", registration())
    controls = widget.footprint_controls
    controls.opacity.setValue(0)
    controls.lock.setChecked(True)
    assert not controls.reset.isEnabled()
    controls.lock.setChecked(False)
    controls.reset.click()
    widget.view.finish_footprint_edit()
    assert commands[0].registration["rotation_deg"] == 0


def test_guard_can_retain_unrelated_edit_before_beginning_preview(authoring):
    widget, handler, commands, _, _ = authoring
    original = widget.get_selected_map_id()
    callbacks = []
    widget.edit_transition_handler = lambda reason, callback: callbacks.append(callback)
    handler.on_register_detail_map_requested("source", "parent", registration())
    assert widget.get_selected_map_id() == original
    assert not widget.view.is_editing_footprint
    assert not commands
    assert len(callbacks) == 1


def test_detach_action_is_guarded_and_refreshes_breadcrumb_after_undo(authoring):
    widget, handler, commands, db, _ = authoring
    widget.select_map("child")
    assert widget.btn_parent.isVisible()
    child_before = db.get_map("child").to_dict()
    widget.make_map_independent_requested.emit("child")
    assert len(commands) == 1
    assert commands[0].execute(db).success
    handler.on_maps_ready(db.get_all_maps())
    assert widget.get_selected_map_id() == "child"
    assert not widget.btn_parent.isVisible()
    assert db.get_map("child").attributes["width_meters"] == 1000
    assert commands[0].undo(db).success
    handler.on_maps_ready(db.get_all_maps())
    assert widget.btn_parent.isVisible()
    assert db.get_map("child").to_dict() == child_before


def test_reparent_preview_and_cancel_restore_original_saved_footprint(authoring):
    widget, handler, commands, _, _ = authoring
    widget.select_map("child")
    before = widget.maps_data[2].to_dict()
    handler.on_register_detail_map_requested("child", "parent", registration())
    assert widget.get_selected_map_id() == "parent"
    widget.view.cancel_footprint_edit()
    assert widget.get_selected_map_id() == "child"
    assert widget.maps_data[2].to_dict() == before
    assert not commands
    widget.placement_requested.emit("child")
    assert widget.get_selected_map_id() == "source"
    widget.view.cancel_footprint_edit()
    assert widget.get_selected_map_id() == "child"


def test_unreadable_parent_image_does_not_preview_on_previous_map(
    authoring, monkeypatch
):
    widget, handler, commands, _, _ = authoring
    widget.maps_data[1].image_path = "missing-parent-image.png"
    messages = []
    monkeypatch.setattr(
        "src.gui.mixins.map_nesting_mixin.QMessageBox.warning",
        lambda *args: messages.append(args[-1]),
    )
    handler.on_register_detail_map_requested("source", "parent", registration())
    assert not widget.view.is_editing_footprint
    assert widget.get_selected_map_id() == "source"
    assert not commands
    assert messages


def test_breadcrumb_escapes_authored_names(authoring):
    widget, _, _, _, _ = authoring
    widget.set_breadcrumb([("source", "<A & B>"), ("child", "<em>child</em>")])
    text = widget.breadcrumb_label.text()
    assert "&lt;A &amp; B&gt;" in text
    assert "&lt;em&gt;child&lt;/em&gt;" in text


def test_external_hierarchy_change_retains_preview_until_explicit_cancel(authoring):
    widget, handler, commands, _, _ = authoring
    handler.on_register_detail_map_requested("source", "parent", registration())
    widget.maps_data[0].attributes["parent_map_id"] = "parent"
    handler.on_maps_ready(widget.maps_data)
    assert widget.view.is_editing_footprint
    assert not widget.btn_confirm_map_edit.isEnabled()
    assert not handler.hierarchy_coordinator.edit_status()["can_apply"]
    widget.view.finish_footprint_edit()
    assert not commands
    widget.view.cancel_footprint_edit()
    assert not widget.view.is_editing_footprint


def test_cancel_placement_on_current_parent_restores_its_viewport(authoring):
    widget, handler, _, _, _ = authoring
    transform = widget.view.transform()
    handler.hierarchy_coordinator.edit_placement("child")
    assert widget.get_selected_map_id() == "source"
    assert widget.view.is_editing_footprint
    widget.view.cancel_footprint_edit()
    assert widget.view.transform() == transform


def test_attach_detach_and_undo_preserve_authored_spatial_and_temporal_data(authoring):
    widget, handler, commands, db, _ = authoring
    polygon = RegionPolygon(
        outer=((0.1, 0.1), (0.9, 0.1), (0.9, 0.9), (0.1, 0.9)),
        holes=(((0.3, 0.3), (0.3, 0.6), (0.6, 0.6), (0.6, 0.3)),),
    ).to_geometry()
    region = Marker(
        "child",
        "territory",
        "entity",
        0.5,
        0.5,
        id="region",
        feature_type="region",
        geometry=polygon,
    )
    point = Marker("source", "traveller", "entity", 0.2, 0.3, id="point")
    db.insert_marker(region)
    db.insert_marker(point)
    db.feature_geometry_repo.replace_marker_states(
        region.id,
        [
            FeatureGeometryState(region.id, 25.0, polygon, 0.5, 0.5),
        ],
    )
    db.trajectory_repo.insert(
        point.id, [Keyframe(1.0, 0.2, 0.3), Keyframe(50.0, 0.7, 0.8)]
    )
    source = db.get_map("source")
    layer_tree = MapLayerNode(
        "Layers",
        children=[
            MapLayerNode(
                "Raster",
                layer_type="raster",
                attributes={
                    "file_path": source.image_path,
                    "notes": "Preserve image metadata",
                },
                start_date=12.0,
                end_date=80.0,
            )
        ],
    )
    db.insert_map(replace(source, layers=layer_tree))
    handler.on_maps_ready(db.get_all_maps())
    source_before = db.get_map("source").to_dict()
    child_before = db.get_map("child").to_dict()
    connection = db.require_connection()

    def local_rows():
        return {
            table: [
                tuple(row)
                for row in connection.execute(f"SELECT * FROM {table} ORDER BY id")
            ]
            for table in ("markers", "moving_features", "feature_geometry_states")
        }

    before = local_rows()
    image_bytes = Path(source.image_path).read_bytes()
    handler.on_register_detail_map_requested("source", "parent", registration())
    widget.view.finish_footprint_edit()
    assert len(commands) == 1
    attach = commands[0]
    assert attach.execute(db).success
    assert local_rows() == before
    assert db.get_map("child").to_dict() == child_before
    assert db.get_map("source").layers.to_dict() == layer_tree.to_dict()
    detach = ChangeMapParentCommand("source", None, None)
    assert detach.execute(db).success
    assert detach.undo(db).success
    assert attach.undo(db).success
    assert db.get_map("source").to_dict() == source_before
    assert db.get_map("child").to_dict() == child_before
    assert local_rows() == before
    assert Path(source.image_path).read_bytes() == image_bytes


def test_rotated_preview_image_matches_registered_points_on_non_square_parent(
    qapp, tmp_path
):
    child = QImage(80, 40, QImage.Format.Format_RGB32)
    painter = QPainter(child)
    for x in range(8):
        for y in range(4):
            painter.fillRect(
                x * 10, y * 10, 10, 10, QColor(20 + 25 * x, 20 + 50 * y, 10)
            )
    painter.end()
    path = tmp_path / "alignment.png"
    assert child.save(str(path))
    reg = {
        **registration(),
        "aspect_ratio": 0.5,
        "rotation_deg": 30,
        "master_center_norm": {"x": 0.5, "y": 0.5},
        "scale_norm": 0.4,
    }
    item = DetailMapFootprintItem(
        "child", "Alignment", "parent", reg, 400, 100, str(path)
    )
    item.set_image_opacity(1.0)
    output = QImage(400, 100, QImage.Format.Format_RGB32)
    output.fill(Qt.GlobalColor.white)
    painter = QPainter(output)
    item.paint(painter, QStyleOptionGraphicsItem())
    painter.end()
    for x in range(8):
        for y in range(4):
            u, v = (x + 0.5) / 8, (y + 0.5) / 4
            px, py = MapNestingService.detail_to_parent((u, v), reg)
            assert output.pixelColor(
                round(px * 400), round(py * 100)
            ) == child.pixelColor(x * 10 + 5, y * 10 + 5)
