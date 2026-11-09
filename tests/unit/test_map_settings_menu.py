"""Map-level configuration shares one visible, overflow-safe menu."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QMessageBox, QToolButton

from src.core.map import Map
from src.core.theme_manager import ThemeManager
from tests.unit.test_map_feature_actions import (
    add_feature,
    click_feature,
)
from tests.unit.test_map_feature_actions import (
    feature_map as _feature_map,
)

pytestmark = pytest.mark.ci_fast
feature_map = _feature_map


def settings_actions(widget):
    widget.map_settings_menu.aboutToShow.emit()
    return {
        action.text(): action
        for action in widget.map_settings_menu.actions()
        if not action.isSeparator() and not action.property("menuSection")
    }


def test_one_settings_route_and_grouped_contents(feature_map):
    widget = feature_map
    assert not hasattr(widget, "btn_map_overflow")
    assert widget.btn_settings.text() == "Map settings"
    assert widget.map_settings_action.menu() is widget.map_settings_menu
    assert widget.map_settings_action in widget.toolbar.actions()
    assert widget.btn_fit_view.text() == "Fit to View"
    assert list(settings_actions(widget)) == [
        "Scale and distance calibration…",
        "Set as Master Map",
        "Register as Detail Map…",
        "Show Footprints",
        "Edit Footprint…",
        "Delete map…",
    ]
    actions = widget.map_settings_menu.actions()
    assert [a.text() for a in actions if a.property("menuSection")] == [
        "Scale",
        "Map hierarchy",
        "Detail-map footprints",
    ]
    assert all(
        not a.isEnabled() and a.defaultWidget().text() == a.text()
        for a in actions
        if a.property("menuSection")
    )
    assert actions[-2].isSeparator() and actions[-1].text() == "Delete map…"
    assert "Fit to View" not in settings_actions(widget)


@pytest.mark.parametrize(
    "label,handler",
    [
        ("Scale and distance calibration…", "_configure_map_width"),
        ("Set as Master Map", "_on_set_master_map_clicked"),
        ("Register as Detail Map…", "_on_register_detail_map_clicked"),
        ("Edit Footprint…", "_on_edit_footprint_clicked"),
        ("Delete map…", "_on_delete_map_clicked"),
    ],
)
def test_menu_dispatches_existing_handler(feature_map, monkeypatch, label, handler):
    widget = feature_map
    widget.maps_data[0].attributes["map_role"] = "detail"
    widget.maps_data.append(
        Map(name="World", image_path="unused.png", attributes={"map_role": "master"})
    )
    calls = []
    monkeypatch.setattr(widget, handler, lambda: calls.append(label))
    actions = settings_actions(widget)
    assert actions[label].isEnabled()
    actions[label].trigger()
    assert calls == [label]


def test_menu_refreshes_role_and_footprint_prerequisites(feature_map):
    widget = feature_map
    actions = settings_actions(widget)
    assert not actions["Register as Detail Map…"].isEnabled()
    assert actions["Register as Detail Map…"].toolTip()
    assert not actions["Set as Master Map"].isChecked()
    assert not actions["Edit Footprint…"].isEnabled()
    widget.maps_data[0].attributes["map_role"] = "master"
    actions = settings_actions(widget)
    assert actions["Set as Master Map"].isChecked()
    assert not actions["Register as Detail Map…"].isEnabled()
    widget.maps_data[0].attributes["map_role"] = "detail"
    actions = settings_actions(widget)
    assert actions["Edit Footprint…"].isEnabled()
    actions["Show Footprints"].trigger()
    assert not widget.view.footprints_visible
    actions = settings_actions(widget)
    assert not actions["Show Footprints"].isChecked()
    assert not actions["Edit Footprint…"].isEnabled()


@pytest.mark.parametrize(
    "answer", [QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes]
)
def test_delete_map_retains_confirmation(feature_map, monkeypatch, answer):
    questions = []

    def confirm(*args):
        questions.append(args[1])
        return answer

    monkeypatch.setattr(QMessageBox, "question", confirm)
    deleted = []
    feature_map.map_deleted.connect(deleted.append)
    settings_actions(feature_map)["Delete map…"].trigger()
    assert questions == ["Delete Map"]
    assert deleted == (
        [feature_map.get_selected_map_id()]
        if answer == QMessageBox.StandardButton.Yes
        else []
    )


@pytest.mark.parametrize(
    "theme", list(json.loads(Path("themes.json").read_text("utf-8")))
)
@pytest.mark.parametrize("width", [1400, 520])
def test_map_settings_keyboard_overflow_and_context(
    feature_map, qtbot, qapp, theme, width, request
):
    # Production QSS/native menu teardown owns a process, like other map renders.
    if os.environ.get("KRT_MAP_SETTINGS_RENDER_CHILD") != "1":
        result = subprocess.run(
            [sys.executable, "-m", "pytest", request.node.nodeid, "-q", "--tb=short"],
            env=dict(os.environ, KRT_MAP_SETTINGS_RENDER_CHILD="1"),
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
    widget = feature_map
    manager = ThemeManager()
    manager.set_theme(theme)
    widget.setStyleSheet(
        manager.format_stylesheet(Path("src/resources/main.qss").read_text("utf-8"))
    )
    marker = add_feature(widget)
    click_feature(widget, marker)
    widget.view.start_marker_appearance_edit(marker.marker_id)
    widget.resize(width, 760)
    qtbot.wait(0)
    transform = widget.view.transform()
    center = widget.view.mapToScene(widget.view.viewport().rect().center())
    target = widget.feature_actions.target
    playhead = widget.view._playhead_time
    menu = widget.map_settings_menu
    if width == 520:
        extension = widget.toolbar.findChild(QToolButton, "qt_toolbar_ext_button")
        assert extension.isVisible()
        QTimer.singleShot(20, extension.menu().close)
        QTest.mouseClick(extension, Qt.MouseButton.LeftButton)
        overflow = extension.menu()
        assert widget.map_settings_action in overflow.actions()
        overflow.popup(extension.mapToGlobal(QPoint()))
        overflow.setActiveAction(widget.map_settings_action)
        QTest.keyClick(overflow, Qt.Key.Key_Right)
    else:
        assert widget.btn_fit_view.isVisible()
        widget.activateWindow()
        widget.btn_settings.setFocus(Qt.FocusReason.TabFocusReason)
        qtbot.waitUntil(widget.btn_settings.hasFocus)
        QTimer.singleShot(20, menu.close)
        QTest.keyClick(widget.btn_settings, Qt.Key.Key_Space)
        menu.popup(widget.btn_settings.mapToGlobal(QPoint()))
    qtbot.waitUntil(menu.isVisible)
    assert all(
        a.defaultWidget().isVisible()
        for a in menu.actions()
        if a.property("menuSection")
    )
    assert not next(
        a for a in menu.actions() if a.text() == "Register as Detail Map…"
    ).isEnabled()
    for action in menu.actions():
        if not action.isSeparator():
            assert menu.actionGeometry(
                action
            ).width() >= menu.fontMetrics().horizontalAdvance(action.text())
    evidence = os.environ.get("KRT_MAP_SETTINGS_EVIDENCE_DIR")
    if evidence:
        directory = Path(evidence)
        directory.mkdir(parents=True, exist_ok=True)
        assert menu.grab().save(str(directory / f"{theme}-{width}-menu.png"))
        assert widget.grab().save(str(directory / f"{theme}-{width}-toolbar.png"))
    QTest.keyClick(menu, Qt.Key.Key_Escape)
    assert not menu.isVisible()
    assert widget.view.is_editing_marker_appearance
    assert widget.feature_actions.target == target
    assert widget.view._playhead_time == playhead
    assert widget.view.transform() == transform
    assert widget.view.mapToScene(widget.view.viewport().rect().center()) == center
    widget.view.cancel_marker_appearance_edit()
