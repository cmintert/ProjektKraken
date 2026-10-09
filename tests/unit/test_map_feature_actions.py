"""Real selection/menu regressions for the visible KRT-48 feature routes."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QFont, QFontDatabase, QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog, QMenu, QMessageBox, QToolButton, QWidget

from src.core.map import Map
from src.core.theme_manager import ThemeManager
from src.gui.utils.style_helper import StyleHelper
from src.gui.widgets.map.feature_actions import FeatureContext, feature_actions
from src.gui.widgets.map_widget import MapWidget

pytestmark = pytest.mark.ci_fast


@pytest.fixture
def feature_map(qtbot, tmp_path, init_theme_manager, qapp):
    # Windows offscreen Qt does not discover system fonts automatically.
    font_path = Path("C:/Windows/Fonts/segoeui.ttf")
    if os.environ.get("KRT48_EVIDENCE_DIR") and font_path.exists():
        assert QFontDatabase.addApplicationFont(str(font_path)) >= 0
        qapp.setFont(QFont("Segoe UI", 10))
    widget = MapWidget()
    widget.view.setViewport(QWidget())
    qtbot.addWidget(widget)
    image = QPixmap(600, 400)
    image.fill(Qt.GlobalColor.gray)
    image_path = tmp_path / "map.png"
    assert image.save(str(image_path))
    world_map = Map(name="Test map", image_path=str(image_path))
    widget.set_maps([world_map])
    widget.select_map(world_map.id)
    assert widget.load_map(str(image_path))
    widget.resize(1400, 800)
    widget.show()
    qtbot.waitExposed(widget)
    widget.view.fit_to_view()
    return widget


def add_feature(widget, kind="point", object_id="target", object_type="entity"):
    geometry = [{"x": 0.3, "y": 0.3}, {"x": 0.7, "y": 0.3}]
    if kind == "region":
        geometry.append({"x": 0.5, "y": 0.7})
    widget.add_marker(
        object_id,
        object_type,
        "Upper Rhine",
        0.5,
        0.5,
        feature_type=kind,
        geometry=geometry,
    )
    return widget.view.find_item_by_id(object_id)


def click_feature(widget, item):
    pos = widget.view.mapFromScene(item.sceneBoundingRect().center())
    QTest.mouseClick(widget.view.viewport(), Qt.MouseButton.LeftButton, pos=pos)


def select_layer(widget, object_id, qtbot):
    panel = widget.layer_panel
    node = panel.feature_node(object_id)
    index = panel._proxy_model.mapFromSource(panel._model.index_from_node(node))
    panel.tree_view.scrollTo(index)
    qtbot.wait(0)
    QTest.mouseClick(
        panel.tree_view.viewport(),
        Qt.MouseButton.LeftButton,
        pos=panel.tree_view.visualRect(index).center(),
    )


def menu_action(menu, action_id):
    for action in menu.actions():
        if action.data() == action_id:
            return action
        if action.menu():
            result = menu_action(action.menu(), action_id)
            if result:
                return result
    return None


def open_toolbar_menu(widget, qtbot):
    opened = []

    def dismiss():
        opened.append(widget.feature_actions_menu.isVisible())
        widget.feature_actions_menu.close()

    QTimer.singleShot(20, dismiss)
    QTest.mouseClick(widget.btn_feature_actions, Qt.MouseButton.LeftButton)
    assert opened == [True]
    widget.feature_actions_menu.popup(widget.btn_feature_actions.mapToGlobal(QPoint()))
    qtbot.waitUntil(widget.feature_actions_menu.isVisible)
    return widget.feature_actions_menu


@pytest.mark.parametrize(
    "kind,label",
    [
        ("region", "Edit border at current date"),
        ("path", "Edit path at current date"),
        ("point", "Edit appearance"),
    ],
)
@pytest.mark.parametrize("source", ["canvas", "layers"])
def test_visible_routes_dispatch_existing_intents(
    feature_map, qtbot, kind, label, source
):
    item = add_feature(feature_map, kind)
    if source == "canvas":
        click_feature(feature_map, item)
    else:
        select_layer(feature_map, "target", qtbot)
    assert feature_map.feature_actions.target.source == source
    assert feature_map.feature_actions_action.isEnabled()
    assert feature_map.layer_panel.btn_feature_actions.isEnabled()
    menu = open_toolbar_menu(feature_map, qtbot)
    action = menu_action(menu, "appearance" if kind == "point" else "geometry")
    assert action.text() == label
    if kind == "point":
        QTest.mouseClick(
            menu, Qt.MouseButton.LeftButton, pos=menu.actionGeometry(action).center()
        )
        assert feature_map.view.is_editing_marker_appearance
        feature_map.view.cancel_marker_appearance_edit()
    else:
        with qtbot.waitSignal(feature_map.feature_geometry_edit_requested) as signal:
            QTest.mouseClick(
                menu,
                Qt.MouseButton.LeftButton,
                pos=menu.actionGeometry(action).center(),
            )
        assert signal.args == ["target"]


def test_layers_button_keyboard_menu_and_tree_selection(feature_map, qtbot):
    add_feature(feature_map, "path", "first")
    add_feature(feature_map, "region", "second")
    select_layer(feature_map, "first", qtbot)
    tree = feature_map.layer_panel.tree_view
    tree.setFocus()
    QTest.keyClick(tree, Qt.Key.Key_Down)
    assert feature_map.feature_actions.target.object_id == "second"
    assert feature_map.feature_actions.target.source == "layers"
    clicked = []

    def activate():
        menu = next(
            menu
            for menu in feature_map.layer_panel.findChildren(QMenu)
            if menu.isVisible()
        )
        action = menu_action(menu, "geometry")
        menu.setActiveAction(action)
        QTest.keyClick(menu, Qt.Key.Key_Return)

    feature_map.feature_geometry_edit_requested.connect(clicked.append)
    feature_map.layer_panel.btn_feature_actions.setFocus()
    QTimer.singleShot(0, activate)
    QTest.keyClick(feature_map.layer_panel.btn_feature_actions, Qt.Key.Key_Space)
    assert clicked == ["second"]


@pytest.mark.parametrize("kind", ["point", "path", "region"])
def test_locked_layers_target_cannot_edit_previous_canvas_feature(
    feature_map, qtbot, kind
):
    first = add_feature(feature_map, object_id="first")
    add_feature(feature_map, kind, "locked")
    model = feature_map.get_layer_model()
    model.set_node_locked(model.find_node_by_id("locked"), True)
    click_feature(feature_map, first)
    select_layer(feature_map, "locked", qtbot)
    assert feature_map.feature_actions.target.object_id == "locked"
    menu = open_toolbar_menu(feature_map, qtbot)
    assert [action.text() for action in menu.actions()] == ["Unlock"]
    QTest.mouseClick(
        menu,
        Qt.MouseButton.LeftButton,
        pos=menu.actionGeometry(menu.actions()[0]).center(),
    )
    assert not model.find_node_by_id("locked").locked
    assert not model.find_node_by_id("first").locked


@pytest.mark.parametrize("state", ["hidden", "absent", "outside"])
def test_layers_management_without_available_canvas(feature_map, qtbot, state):
    add_feature(feature_map, "region")
    node = feature_map.layer_panel.feature_node("target")
    model = feature_map.get_layer_model()
    if state == "hidden":
        model.setData(
            model.index_from_node(node),
            Qt.CheckState.Unchecked,
            Qt.ItemDataRole.CheckStateRole,
        )
    elif state == "absent":
        feature_map.view.remove_marker("target")
    else:
        node.start_date = 10.0
        model.temporal_state_changed.emit()
        feature_map.view.set_playhead_time(0.0)
    select_layer(feature_map, "target", qtbot)
    menu = open_toolbar_menu(feature_map, qtbot)
    assert menu_action(menu, "validity").isEnabled()
    if state == "outside":
        assert menu_action(menu, "geometry") is None
        assert menu_action(menu, "jump").isEnabled()
    else:
        assert not menu_action(menu, "geometry").isEnabled()
        assert menu_action(menu, "geometry").toolTip()
    menu.close()


@pytest.mark.parametrize("change", ["selection", "map", "delete", "lock", "date"])
def test_open_menu_revalidates_target(feature_map, qtbot, change):
    first = add_feature(feature_map, "path", "first")
    add_feature(feature_map, "path", "second")
    click_feature(feature_map, first)
    menu = open_toolbar_menu(feature_map, qtbot)
    action = menu_action(menu, "geometry")
    requested = []
    feature_map.feature_geometry_edit_requested.connect(requested.append)
    if change == "selection":
        select_layer(feature_map, "second", qtbot)
    elif change == "map":
        feature_map._accepted_map_id = "other"
    elif change == "delete":
        feature_map.remove_marker("first")
    elif change == "lock":
        model = feature_map.get_layer_model()
        model.set_node_locked(model.find_node_by_id("first"), True)
    else:
        feature_map.view.set_playhead_time(10.0)
    action.trigger()
    assert requested == []
    menu.close()


def test_deferred_transition_rechecks_after_approval(feature_map, qtbot):
    item = add_feature(feature_map, "region")
    click_feature(feature_map, item)
    continuations = []
    feature_map.edit_transition_handler = lambda reason, resume: continuations.append(
        resume
    )
    menu = open_toolbar_menu(feature_map, qtbot)
    requested = []
    feature_map.feature_geometry_edit_requested.connect(requested.append)
    menu_action(menu, "geometry").trigger()
    assert requested == []
    assert len(continuations) == 1
    feature_map.remove_marker("target")
    continuations[0]()
    assert requested == []
    menu.close()


def test_same_map_scene_refresh_retains_layers_target(feature_map, qtbot):
    add_feature(feature_map, "region")
    select_layer(feature_map, "target", qtbot)
    target = feature_map.feature_actions.target
    feature_map.clear_markers()
    feature_map.rebuild_layer_model()
    add_feature(feature_map, "region")
    feature_map.marker_scene_updated.emit(feature_map.get_selected_map_id())
    assert feature_map.feature_actions.target == target
    assert feature_map.feature_actions_action.isEnabled()


def test_ambiguous_selection_and_group_disable_actions(feature_map, qtbot):
    first = add_feature(feature_map, object_id="first")
    second = add_feature(feature_map, object_id="second")
    first.setSelected(True)
    second.setSelected(True)
    assert not feature_map.feature_actions_action.isEnabled()
    assert feature_map.feature_actions_action.toolTip() == "Select one feature"
    model = feature_map.get_layer_model()
    group = next(node for node in model.root.children if node.layer_type == "group")
    feature_map.layer_panel._on_item_clicked(
        feature_map.layer_panel._proxy_model.mapFromSource(model.index_from_node(group))
    )
    assert feature_map.feature_actions.target is None


def test_modeless_validity_does_not_apply_after_selection_change(feature_map, qtbot):
    first = add_feature(feature_map, "region", "first")
    add_feature(feature_map, "region", "second")
    click_feature(feature_map, first)
    menu = open_toolbar_menu(feature_map, qtbot)
    menu_action(menu, "validity").trigger()
    dialog = feature_map.layer_panel._temporal_dialog
    assert dialog is not None
    changed = []
    feature_map.layer_properties_changed.connect(lambda *args: changed.append(args))
    select_layer(feature_map, "second", qtbot)
    dialog.accept()
    assert changed == []
    menu.close()


def test_returning_to_feature_reopens_valid_modeless_editor(feature_map, qtbot):
    add_feature(feature_map, "region", "first")
    add_feature(feature_map, "region", "second")
    select_layer(feature_map, "first", qtbot)
    panel = feature_map.layer_panel
    panel.edit_temporal_validity("first")
    old = panel._temporal_dialog
    select_layer(feature_map, "second", qtbot)
    select_layer(feature_map, "first", qtbot)
    panel.edit_temporal_validity("first")
    replacement = panel._temporal_dialog
    assert replacement is not old
    qtbot.wait(0)
    assert panel._temporal_dialog is replacement
    changed = []
    feature_map.layer_properties_changed.connect(lambda *args: changed.append(args))
    replacement.accept()
    assert len(changed) == 1 and changed[0][0] == "first"


def test_modal_style_rejects_recreated_scene_item(feature_map, qtbot, monkeypatch):
    item = add_feature(feature_map, "path")
    click_feature(feature_map, item)
    changed = []
    feature_map.feature_style_changed.connect(lambda *args: changed.append(args))

    def replace_during_dialog(dialog):
        feature_map.view.remove_marker("target")
        add_feature(feature_map, "path")
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(QDialog, "exec", replace_during_dialog)
    menu = open_toolbar_menu(feature_map, qtbot)
    menu_action(menu, "style").trigger()
    assert changed == []
    menu.close()


def test_map_replacement_disables_old_scene_until_matching_snapshot(feature_map):
    item = add_feature(feature_map, "region")
    replacement = Map(name="Another map", image_path="unused.png")
    feature_map.set_maps(feature_map.maps_data + [replacement])
    feature_map.select_map(replacement.id)
    item.setSelected(True)
    assert not feature_map.feature_actions_action.isEnabled()
    assert feature_map.feature_actions_action.toolTip() == "Loading map features"
    feature_map.marker_scene_updated.emit("old-map")
    assert feature_map.feature_actions.awaiting_scene
    feature_map.clear_markers()
    feature_map.rebuild_layer_model()
    add_feature(feature_map, "region", "new-target")
    feature_map.marker_scene_updated.emit(replacement.id)
    assert not feature_map.feature_actions.awaiting_scene
    feature_map.layer_panel.layer_selected.emit("new-target")
    assert feature_map.feature_actions.target.object_id == "new-target"


def test_delete_confirmation_revalidates_target(feature_map, qtbot, monkeypatch):
    item = add_feature(feature_map)
    click_feature(feature_map, item)
    deleted = []
    feature_map.marker_delete_confirmed.connect(deleted.append)

    def confirm(*args):
        feature_map.view.graphics_scene.clearSelection()
        return QMessageBox.StandardButton.Yes

    monkeypatch.setattr(QMessageBox, "question", confirm)
    menu = open_toolbar_menu(feature_map, qtbot)
    menu_action(menu, "delete").trigger()
    assert deleted == []
    menu.close()


@pytest.mark.parametrize("kind", ["path", "region", "marker"])
def test_restricted_capability_vocabulary(kind):
    assert [
        action.action_id
        for action in feature_actions(FeatureContext(kind, locked=True))
    ] == ["unlock"]
    assert [
        action.action_id
        for action in feature_actions(FeatureContext(kind, outside_date=True))
    ] == ["lock", "jump", "validity", "layers"]


def test_event_and_raster_marker_capabilities():
    actions = {
        action.action_id: action
        for action in feature_actions(
            FeatureContext("marker", is_event=True, raster_icon=True)
        )
    }
    assert "journey" not in actions
    assert actions["appearance"].enabled and actions["size"].enabled
    assert not actions["fill"].enabled and actions["fill"].reason
    assert not actions["paste"].enabled and actions["paste"].reason


@pytest.mark.parametrize(
    "theme", list(json.loads(Path("themes.json").read_text(encoding="utf-8")))
)
@pytest.mark.parametrize("width", [1400, 520])
def test_theme_layout_keyboard_and_overflow(
    feature_map, qtbot, theme, width, qapp, monkeypatch, request
):
    # Production QSS and native popup teardown can leave offscreen Qt state that
    # crashes later, unrelated widgets in a long-lived QApplication. Keep these
    # real render/keyboard checks, but own their QApplication in a child process.
    if os.environ.get("KRT48_RENDER_CHILD") != "1":
        environment = dict(os.environ, KRT48_RENDER_CHILD="1")
        result = subprocess.run(
            [sys.executable, "-m", "pytest", request.node.nodeid, "-q", "--tb=short"],
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        return
    manager = ThemeManager()
    qss = Path("src/resources/main.qss")
    monkeypatch.setattr(manager, "_qss_template", "")
    try:
        manager.set_theme(theme)
        if qss.exists():
            feature_map.setStyleSheet(
                manager.format_stylesheet(qss.read_text(encoding="utf-8"))
            )
        item = add_feature(feature_map, "region")
        click_feature(feature_map, item)
        feature_map.resize(width, 760)
        qtbot.wait(0)
        feature_map.view.fit_to_view()
        assert (
            feature_map.btn_feature_actions.styleSheet()
            == StyleHelper.get_secondary_button_style()
        )
        assert (
            feature_map.layer_panel.btn_feature_actions.styleSheet()
            == StyleHelper.get_secondary_button_style()
        )
        menu = feature_map.feature_actions_menu
        if width == 520:
            extension = feature_map.toolbar.findChild(
                QToolButton, "qt_toolbar_ext_button"
            )
            assert extension.isVisible()
            QTimer.singleShot(20, extension.menu().close)
            QTest.mouseClick(extension, Qt.MouseButton.LeftButton)
            overflow = extension.menu()
            assert feature_map.feature_actions_action in overflow.actions()
            overflow.popup(extension.mapToGlobal(QPoint()))
            overflow.setActiveAction(feature_map.feature_actions_action)
            QTest.keyClick(overflow, Qt.Key.Key_Right)
        else:
            feature_map.btn_feature_actions.setFocus()
            QTimer.singleShot(20, menu.close)
            QTest.keyClick(feature_map.btn_feature_actions, Qt.Key.Key_Space)
            qtbot.wait(25)
            menu.popup(feature_map.btn_feature_actions.mapToGlobal(QPoint()))
        qtbot.waitUntil(menu.isVisible)
        assert menu_action(menu, "geometry").isEnabled()
        evidence = os.environ.get("KRT48_EVIDENCE_DIR")
        if evidence:
            directory = Path(evidence)
            directory.mkdir(parents=True, exist_ok=True)
            assert feature_map.grab().save(str(directory / f"{theme}-{width}.png"))
            assert menu.grab().save(str(directory / f"{theme}-{width}-menu.png"))
        QTest.keyClick(menu, Qt.Key.Key_Escape)
        menu.close()
        for popup in feature_map.findChildren(QMenu):
            popup.close()
        qtbot.wait(25)
        if evidence:
            button = feature_map.layer_panel.btn_feature_actions
            feature_map.activateWindow()
            button.setFocus(Qt.FocusReason.TabFocusReason)
            QTest.mouseMove(feature_map.view.viewport())
            qtbot.waitUntil(button.hasFocus)
            assert feature_map.grab().save(
                str(directory / f"{theme}-{width}-focus.png")
            )
            feature_map.view.setFocus()
            QTest.mouseMove(button, button.rect().center())
            qtbot.wait(0)
            assert feature_map.grab().save(
                str(directory / f"{theme}-{width}-hover.png")
            )
            feature_map.view.graphics_scene.clearSelection()
            feature_map.feature_actions.reset()
            qtbot.wait(0)
            assert feature_map.grab().save(
                str(directory / f"{theme}-{width}-disabled.png")
            )
    finally:
        manager.current_theme_name = "dark_mode"
