"""Scope, compatibility and composed presentation checks for KRT-140."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication, QLabel

from src.commands.layer_commands import UpdateLayerPropertiesCommand
from src.core.map import Map, MapLayerNode
from src.core.theme_manager import ThemeManager
from src.gui.dialogs.layer_properties_dialog import LayerPropertiesDialog
from src.gui.dialogs.temporal_validity_dialog import TemporalValidityDialog
from src.gui.widgets.map.map_layer_model import MapLayerModel
from src.gui.widgets.map.map_layer_panel import MapLayerPanel
from src.gui.widgets.map.settings_scope import settings_scope

pytestmark = pytest.mark.ci_fast


@pytest.mark.parametrize(
    "kind,label",
    [
        ("marker", "Feature"),
        ("path", "Feature"),
        ("region", "Feature"),
        ("group", "Group"),
        ("raster", "Raster layer"),
        ("basemap", "Base map"),
    ],
)
def test_target_names_and_nested_scope(kind, label):
    target = MapLayerNode(name="Same", layer_type=kind)
    inner = MapLayerNode(name="Same", children=[target], opacity=0.5)
    outer = MapLayerNode(name="Locations", children=[inner], visible=False)
    root = MapLayerNode(name="Root", children=[outer])
    before = root.to_dict()
    scope = settings_scope(target, root)
    assert scope.properties_label == f"{label} properties…"
    assert scope.location == "In: Locations / Same"
    assert "Same: 50%" in scope.opacity
    assert "Locations: hidden" in scope.visibility
    assert "absolute view scale (legacy)" in scope.zoom
    assert root.to_dict() == before


@pytest.mark.parametrize("count", [0, 1, 3])
def test_group_scope_includes_hidden_descendants_and_future_items(count):
    group = MapLayerNode(
        name="Cities",
        children=[
            MapLayerNode(
                name="Nested",
                children=[
                    MapLayerNode(name=str(i), layer_type="marker", visible=False)
                    for i in range(count)
                ],
            ),
            MapLayerNode(name="Overlay", layer_type="raster"),
            MapLayerNode(name="Snapshot", layer_type="raster_snapshot", virtual=True),
        ],
    )
    scope = settings_scope(group)
    feature_word = "feature" if count == 1 else "features"
    assert f"Contains {count} {feature_word} and 1 map layer" in scope.description
    assert "including items added later" in scope.description


def test_properties_preserve_untouched_legacy_zoom_and_cancel(
    qtbot, init_theme_manager
):
    node = MapLayerNode(name="Fort", layer_type="marker", min_zoom=0.0)
    before = node.to_dict()
    dialog = LayerPropertiesDialog(node)
    qtbot.addWidget(dialog)
    dialog._name.setText("New Fort")
    properties = dialog.properties()
    assert not {"min_zoom", "max_zoom", "zoom_basis"} & properties.keys()
    dialog._min_zoom.setValue(2)
    assert dialog.properties()["min_zoom"] == 2
    assert dialog.properties()["zoom_basis"] is None
    dialog.reject()
    assert node.to_dict() == before


def test_properties_show_ancestor_values_and_keep_draft(qtbot, init_theme_manager):
    node = MapLayerNode(name="Fort", layer_type="marker")
    group = MapLayerNode(name="Cities", children=[node], opacity=0.5)
    root = MapLayerNode(name="Root", children=[group])
    dialog = LayerPropertiesDialog(node, root=root)
    qtbot.addWidget(dialog)
    dialog._name.setText("Draft")
    group.opacity = 0.25
    dialog.set_scope(node, root)
    assert dialog._name.text() == "Draft"
    assert "Cities: 25%" in dialog._opacity_hint.text()
    assert "Cities" in dialog._zoom_hint.text()


def test_group_menu_and_opacity_target(qtbot, init_theme_manager):
    child = MapLayerNode(name="Fort", layer_type="marker")
    group = MapLayerNode(name="Cities", children=[child])
    root = MapLayerNode(name="Root", children=[group])
    panel = MapLayerPanel()
    qtbot.addWidget(panel)
    panel.set_model(MapLayerModel(root))
    panel.select_node(group.id)
    assert panel.btn_feature_actions.text() == "Group actions"
    assert panel.btn_feature_actions.isEnabled()
    assert panel._opacity_label.text() == "Group opacity:"
    assert "including items added later" in panel._opacity_scope.text()
    menus = []

    def capture_menu():
        menu = QApplication.activePopupWidget()
        menus.append(menu)
        menu.close()

    QTimer.singleShot(0, capture_menu)
    panel._show_feature_actions()
    assert [a.text() for a in menus[0].actions()] == [
        "Group properties…",
        "Group visibility dates…",
    ]
    menus[0].actions()[0].trigger()
    dialog = panel._properties_dialog
    assert dialog.windowTitle() == "Group properties"
    changed = []
    panel.layer_properties_changed.connect(lambda *args: changed.append(args))
    panel.select_node(child.id)
    dialog.accept()
    assert changed == []  # A modeless result cannot edit an abandoned target.
    assert panel._opacity_label.text() == "Feature opacity:"
    child.locked = True
    panel.refresh_settings_scope()
    assert not panel._opacity_slider.isEnabled()
    panel._selected_node_id = None
    panel.refresh_settings_scope()
    assert not panel._opacity_slider.isEnabled()


def test_group_date_caption_names_values(qtbot, init_theme_manager):
    child = MapLayerNode(name="Fort", layer_type="marker")
    dialog = TemporalValidityDialog(
        child, ancestor_windows=(("Cities", {"valid_from": 10.0, "valid_to": 20.0}),)
    )
    qtbot.addWidget(dialog)
    assert "Cities: from 10, until 20" in dialog._temporal_summary.text()
    assert any(
        "Group and feature dates apply together" in label.text()
        for label in dialog.findChildren(QLabel)
    )


@pytest.mark.parametrize(
    "kind", ["marker", "path", "region", "group", "raster", "basemap"]
)
def test_scope_is_plain_text(qtbot, init_theme_manager, kind):
    node = MapLayerNode(name="<b>Authored name</b>", layer_type=kind)
    dialog = LayerPropertiesDialog(node)
    qtbot.addWidget(dialog)
    assert dialog._scope_label.textFormat() == Qt.TextFormat.PlainText
    assert node.name in dialog._scope_label.text()


@pytest.mark.parametrize("target_kind", ["marker", "group"])
def test_scoped_properties_persist_undo_redo_and_rehydrate(
    qtbot, db_service, init_theme_manager, target_kind
):
    first = MapLayerNode(name="Fort", layer_type="marker", min_zoom=0.123456)
    second = MapLayerNode(name="Port", layer_type="marker")
    group = MapLayerNode(name="Cities", children=[first, second], opacity=0.5)
    root = MapLayerNode(name="Root", children=[group])
    world_map = Map(name="Scope test", image_path="unused.png", layers=root)
    db_service.insert_map(world_map)
    before = root.to_dict()
    target = first if target_kind == "marker" else group
    dialog = LayerPropertiesDialog(target, root=root)
    qtbot.addWidget(dialog)
    dialog._opacity.setValue(0.4)
    command = UpdateLayerPropertiesCommand(world_map.id, target.id, dialog.properties())
    assert command.execute(db_service).success

    def saved_group():
        saved = db_service.map_repo.get_map(world_map.id)
        # Portable serialization and a fresh repository read retain the same scope.
        return Map.from_dict(saved.to_dict()).layers.children[0]

    saved = saved_group()
    assert saved.children[1].opacity == 1.0
    assert saved.children[0].min_zoom == 0.123456
    if target_kind == "marker":
        assert saved.opacity == 0.5
        assert saved.children[0].effective_opacity(saved.opacity) == 0.2
    else:
        assert saved.opacity == 0.4
        assert saved.children[0].opacity == 1.0
    command.undo(db_service)
    assert db_service.map_repo.get_map(world_map.id).layers.to_dict() == before
    assert command.execute(db_service).success
    assert saved_group().opacity == saved.opacity


def test_group_editor_snapshot_refresh_and_abandoned_target(qtbot, init_theme_manager):
    child = MapLayerNode(name="Fort", layer_type="marker")
    group = MapLayerNode(name="Cities", children=[child])
    root = MapLayerNode(name="Root", children=[group])
    panel = MapLayerPanel()
    qtbot.addWidget(panel)
    panel.set_model(MapLayerModel(root))
    panel.select_node(group.id)
    panel.edit_properties(group.id)
    dialog = panel._properties_dialog
    dialog._notes.setPlainText("Unfinished notes")
    panel.set_model(MapLayerModel(MapLayerNode.from_dict(root.to_dict())))
    assert panel._properties_guard()
    assert dialog._notes.toPlainText() == "Unfinished notes"
    panel.select_node(child.id)
    panel.select_node(group.id)
    assert not panel._properties_guard()


@pytest.mark.parametrize(
    "theme", list(json.loads(Path("themes.json").read_text("utf-8")))
)
@pytest.mark.parametrize("width", [420, 760])
def test_settings_theme_narrow_focus_and_draft(
    qtbot, qapp, init_theme_manager, theme, width, request
):
    # Own production QSS and native Qt teardown in a child, as map render tests do.
    if os.environ.get("KRT140_RENDER_CHILD") != "1":
        result = subprocess.run(
            [sys.executable, "-m", "pytest", request.node.nodeid, "-q", "--tb=short"],
            env=dict(os.environ, KRT140_RENDER_CHILD="1"),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=45,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        return
    font_path = Path("C:/Windows/Fonts/segoeui.ttf")
    if font_path.exists():
        assert QFontDatabase.addApplicationFont(str(font_path)) >= 0
        qapp.setFont(QFont("Segoe UI", 10))
    manager = ThemeManager()
    manager.set_theme(theme)
    qss = Path("src/resources/main.qss").read_text("utf-8")
    qapp.setStyleSheet(manager.format_stylesheet(qss))
    child = MapLayerNode(name="Old fortress", layer_type="marker")
    group = MapLayerNode(name="Northern settlements", children=[child], opacity=0.5)
    root = MapLayerNode(name="Root", children=[group])
    dialog = LayerPropertiesDialog(child, root=root)
    qtbot.addWidget(dialog)
    dialog.resize(width, 680)
    dialog.show()
    dialog.activateWindow()
    qtbot.waitExposed(dialog)
    qapp.setActiveWindow(dialog)
    dialog._name.setText("Unsaved fortress name")
    dialog._name.setSelection(0, 7)
    dialog._name.setFocus()
    qtbot.wait(0)
    assert dialog._name.hasFocus()
    assert dialog._scope_label.height() >= dialog._scope_label.heightForWidth(
        dialog._scope_label.width()
    )
    assert dialog._buttons.geometry().bottom() <= dialog.height()
    panel = MapLayerPanel()
    qtbot.addWidget(panel)
    panel.set_model(MapLayerModel(root))
    panel.select_node(group.id)
    panel.resize(300 if width == 420 else 480, 700)
    panel.show()
    qtbot.wait(0)
    evidence = os.environ.get("KRT140_EVIDENCE_DIR")
    if evidence:
        directory = Path(evidence)
        directory.mkdir(parents=True, exist_ok=True)
        assert dialog.grab().save(str(directory / f"{theme}-{width}-properties.png"))
        assert panel.grab().save(str(directory / f"{theme}-{width}-group.png"))
    child.locked = True
    panel.select_node(child.id)
    assert not panel._opacity_slider.isEnabled()
    if evidence:
        assert panel.grab().save(str(directory / f"{theme}-{width}-disabled.png"))
    # Theme refresh is presentation only; active editor text and selection survive.
    manager.set_theme("light_mode" if theme != "light_mode" else "dark_mode")
    qapp.setStyleSheet(manager.format_stylesheet(qss))
    qtbot.wait(0)
    assert dialog._name.text() == "Unsaved fortress name"
    assert dialog._name.selectedText() == "Unsaved"
