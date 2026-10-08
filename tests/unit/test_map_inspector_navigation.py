"""Real workspace and pointer regressions for map inspection (KRT-64)."""

from unittest.mock import Mock, patch

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QMainWindow, QMessageBox, QToolButton

from src.app.coordinators.map_navigation import MapNavigationController
from src.app.coordinators.navigation_coordinator import NavigationCoordinator
from src.app.map_handler import MapHandler
from src.gui.widgets.map_widget import MapWidget
from src.gui.workspace import WorkspaceShell

pytestmark = pytest.mark.ci_fast


@pytest.fixture
def map_window(qtbot, init_theme_manager, tmp_path):
    window = QMainWindow()
    qtbot.addWidget(window)
    window.workspace = WorkspaceShell()
    window.setCentralWidget(window.workspace)
    window.map_widget = MapWidget()
    for panel_id, widget in (
        ("map", window.map_widget),
        ("entity", QLabel("Entity inspector")),
        ("event", QLabel("Event inspector")),
        ("other", QLabel("Other panel")),
    ):
        window.workspace.register_panel(panel_id, panel_id.title(), widget, "center")
    window.workspace.reset_layout()
    window.workspace.show_panel("map")
    for name in (
        "event_editor", "entity_editor", "editor_coordinator", "unified_list",
        "timeline", "data_coordinator",
    ):
        setattr(window, name, Mock())
    window.event_editor.has_unsaved_changes.return_value = False
    window.entity_editor.has_unsaved_changes.return_value = False
    window.entity_editor.current_entity_id = "prior"
    window.event_editor.current_event_id = None
    window.navigation = NavigationCoordinator(window)
    window.navigation.selected_id = "prior"
    window.navigation.selected_type = "entity"
    window.binding = MapNavigationController(window.map_widget, window.navigation)
    window.handler = MapHandler(
        window.map_widget, Mock(), lambda: "unused.kraken", window.binding.browse
    )
    window.map_widget.marker_clicked.connect(window.handler.on_marker_clicked)
    image = QPixmap(600, 400)
    image.fill(Qt.GlobalColor.gray)
    image_path = tmp_path / "map.png"
    assert image.save(str(image_path))
    assert window.map_widget.load_map(str(image_path))
    window.resize(1500, 800)
    window.show()
    qtbot.waitExposed(window)
    return window


def add_feature(window, kind="entity", feature="point"):
    widget = window.map_widget
    geometry = [{"x": 0.35, "y": 0.5}, {"x": 0.65, "y": 0.5}]
    if feature == "region":
        geometry.append({"x": 0.5, "y": 0.7})
    widget.add_marker(
        "target", kind, "Target", 0.5, 0.5,
        feature_type=feature, geometry=geometry if feature != "point" else None,
    )
    widget.view.fit_to_view()
    return widget.view.find_item_by_id("target")


def click_feature(qtbot, window, item):
    view = window.map_widget.view
    point = view.mapFromScene(item.sceneBoundingRect().center())
    qtbot.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=point)


@pytest.mark.parametrize("kind", ["entity", "event"])
@pytest.mark.parametrize("feature", ["point", "path", "region"])
def test_shared_zone_click_stays_on_map_and_explicit_open_reveals(
    map_window, qtbot, kind, feature
):
    window = map_window
    widget = window.map_widget
    assert not widget.open_inspector_action.isEnabled()
    item = add_feature(window, kind, feature)
    transform = widget.view.transform()
    click_feature(qtbot, window, item)
    assert window.workspace.active_panel("center") == "map"
    assert window.navigation.selected_id == "prior"
    assert widget._selected_marker_id == "target"
    assert widget.layer_panel.selected_node_id == "target"
    assert widget.open_inspector_action.isEnabled()
    assert widget.view.transform() == transform
    assert widget._playhead_time == 0.0
    getattr(window.data_coordinator, f"load_{kind}_details").assert_not_called()
    qtbot.mouseClick(widget.btn_open_inspector, Qt.MouseButton.LeftButton)
    assert window.workspace.active_panel("center") == kind
    getattr(window.data_coordinator, f"load_{kind}_details").assert_called_once_with(
        "target"
    )


@pytest.mark.parametrize("kind", ["entity", "event"])
@pytest.mark.parametrize("layout", ["visible", "inactive", "hidden", "moved-map"])
def test_passive_inspection_only_updates_visible_separate_target(
    map_window, qtbot, kind, layout
):
    window = map_window
    workspace = window.workspace
    workspace.move_panel(kind, "right")
    if layout == "inactive":
        workspace.move_panel("other", "right")
        workspace.show_panel("other")
    elif layout == "hidden":
        workspace.hide_zone("right")
    elif layout == "moved-map":
        workspace.move_panel("map", "left")
    item = add_feature(window, kind)
    window.map_widget.view.setFocus()
    before = workspace.capture_layout()
    click_feature(qtbot, window, item)
    assert workspace.capture_layout() == before
    assert window.map_widget.view.hasFocus()
    loaded = getattr(window.data_coordinator, f"load_{kind}_details")
    if layout in {"visible", "moved-map"}:
        loaded.assert_called_once_with("target")
    else:
        loaded.assert_not_called()


def test_same_inspected_object_can_be_opened_explicitly(map_window):
    window = map_window
    window.navigation.selected_id = "target"
    item = add_feature(window)
    item.setSelected(True)
    window.map_widget.open_inspector_action.trigger()
    assert window.workspace.active_panel("center") == "entity"
    window.data_coordinator.load_entity_details.assert_not_called()


def test_declined_inspection_retains_local_selection(map_window, qtbot):
    window = map_window
    window.workspace.move_panel("entity", "right")
    window.entity_editor.has_unsaved_changes.return_value = True
    item = add_feature(window)
    with patch(
        "src.app.coordinators.navigation_coordinator.QMessageBox.warning",
        return_value=QMessageBox.StandardButton.Cancel,
    ):
        click_feature(qtbot, window, item)
    assert window.navigation.selected_id == "prior"
    assert window.workspace.active_panel("center") == "map"
    assert item.isSelected()
    assert window.map_widget.layer_panel.selected_node_id == "target"
    assert window.map_widget.open_inspector_action.isEnabled()


@pytest.mark.parametrize("supersede", [False, True])
def test_pending_save_retains_map_origin_and_new_press_supersedes(
    map_window, qtbot, supersede
):
    window = map_window
    window.workspace.move_panel("entity", "right")
    source = window.entity_editor
    source.has_unsaved_changes.return_value = True
    source._on_save.side_effect = lambda: setattr(source, "_pending_save_revision", 7)
    item = add_feature(window)
    with patch(
        "src.app.coordinators.navigation_coordinator.QMessageBox.warning",
        return_value=QMessageBox.StandardButton.Save,
    ):
        click_feature(qtbot, window, item)
    assert window.navigation._pending_navigation_context == ("map", False)
    assert window.navigation._pending_navigation is not None
    if supersede:
        qtbot.mousePress(
            window.map_widget.view.viewport(), Qt.MouseButton.LeftButton,
            pos=QPoint(10, 10),
        )
    source.has_unsaved_changes.return_value = False
    window.navigation._on_navigation_save_finished("entity", "prior", 7, True)
    assert window.navigation.selected_id == ("prior" if supersede else "target")
    assert window.workspace.active_panel("center") == "map"
    if supersede:
        qtbot.mouseRelease(
            window.map_widget.view.viewport(), Qt.MouseButton.LeftButton,
            pos=QPoint(10, 10),
        )


def test_hold_and_drag_do_not_navigate(map_window, qtbot):
    window = map_window
    window.workspace.move_panel("entity", "right")
    item = add_feature(window)
    view = window.map_widget.view
    point = view.mapFromScene(item.sceneBoundingRect().center())
    qtbot.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=point)
    qtbot.wait(300)
    assert window.navigation.selected_id == "prior"
    qtbot.mouseMove(view.viewport(), point + QPoint(90, 0))
    qtbot.mouseRelease(
        view.viewport(), Qt.MouseButton.LeftButton, pos=point + QPoint(90, 0)
    )
    assert window.navigation.selected_id == "prior"
    window.data_coordinator.load_entity_details.assert_not_called()


def test_narrow_toolbar_keeps_labeled_open_action_in_overflow(map_window, qtbot):
    window = map_window
    add_feature(window).setSelected(True)
    window.resize(550, 700)
    qtbot.wait(30)
    extension = window.map_widget.toolbar.findChild(QToolButton, "qt_toolbar_ext_button")
    assert extension.isVisible()
    assert window.map_widget.open_inspector_action in extension.menu().actions()
    assert window.map_widget.open_inspector_action.text() == "Open in inspector"


def test_layer_selection_opens_with_focused_button_keyboard(map_window, qtbot):
    window = map_window
    widget = window.map_widget
    add_feature(window)
    widget._on_layer_panel_selected("target")
    widget.btn_open_inspector.setFocus(Qt.FocusReason.TabFocusReason)
    qtbot.keyClick(widget.btn_open_inspector, Qt.Key.Key_Space)
    assert window.workspace.active_panel("center") == "entity"
    window.data_coordinator.load_entity_details.assert_called_once_with("target")


def test_temporal_hidden_selection_disables_open_and_cannot_open_stale_target(
    map_window,
):
    window = map_window
    widget = window.map_widget
    item = add_feature(window)
    item.setSelected(True)
    assert widget.open_inspector_action.isEnabled()
    item.setVisible(False)
    widget.view.effective_visibility_changed.emit()
    assert not widget.open_inspector_action.isEnabled()
    widget._open_selected_inspector()
    assert window.workspace.active_panel("center") == "map"
    window.data_coordinator.load_entity_details.assert_not_called()


def test_explicit_open_keeps_dirty_inspector_guard(map_window, qtbot):
    window = map_window
    item = add_feature(window)
    click_feature(qtbot, window, item)
    window.entity_editor.has_unsaved_changes.return_value = True
    with patch(
        "src.app.coordinators.navigation_coordinator.QMessageBox.warning",
        return_value=QMessageBox.StandardButton.Cancel,
    ):
        window.map_widget.open_inspector_action.trigger()
    assert window.workspace.active_panel("center") == "map"
    assert item.isSelected()
    assert window.navigation.selected_id == "prior"


def test_pending_passive_save_rechecks_moved_workspace(map_window, qtbot):
    window = map_window
    window.workspace.move_panel("entity", "right")
    source = window.entity_editor
    source.has_unsaved_changes.return_value = True
    source._on_save.side_effect = lambda: setattr(source, "_pending_save_revision", 7)
    with patch(
        "src.app.coordinators.navigation_coordinator.QMessageBox.warning",
        return_value=QMessageBox.StandardButton.Save,
    ):
        click_feature(qtbot, window, add_feature(window))
    window.workspace.move_panel("entity", "center")
    window.workspace.show_panel("map")
    source.has_unsaved_changes.return_value = False
    window.navigation._on_navigation_save_finished("entity", "prior", 7, True)
    assert window.workspace.active_panel("center") == "map"
    assert window.navigation.selected_id == "prior"
    window.data_coordinator.load_entity_details.assert_not_called()
