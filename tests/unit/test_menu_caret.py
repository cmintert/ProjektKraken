"""Split-menu chrome follows shared theme states without changing its actions."""

import json
from pathlib import Path

import pytest
from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QAction, QColor
from PySide6.QtWidgets import QMenu, QToolButton, QVBoxLayout, QWidget

from src.gui.widgets.menu_caret import PhosphorToolMenuButton

pytestmark = pytest.mark.ci_fast
THEMES = json.loads(Path("themes.json").read_text("utf-8"))


@pytest.mark.parametrize("name", THEMES)
def test_split_dropdown_surface_follows_theme_states(
    qtbot, isolated_theme_manager, name
):
    manager = isolated_theme_manager
    manager.set_theme(name, persist=False)
    theme = manager.get_theme()
    host = QWidget()
    qtbot.addWidget(host)
    host.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    host.setStyleSheet(
        manager.format_stylesheet(Path("src/resources/main.qss").read_text("utf-8"))
    )
    layout = QVBoxLayout(host)
    button = PhosphorToolMenuButton(host)
    button.setText("Fit View")
    button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
    button.setMenu(QMenu(button))
    button.setCheckable(True)
    layout.addWidget(button)
    host.resize(240, 100)
    host.show()
    host.activateWindow()
    host.setFocus()
    qtbot.wait(1)
    initial_size = button.size()
    for state in ("normal", "hover", "pressed", "checked", "disabled"):
        button.setEnabled(state != "disabled")
        button.setChecked(state == "checked")
        button.setDown(state == "pressed")
        if state == "hover":
            qtbot.mouseMove(button, QPoint(button.width() - 8, 6))
        else:
            qtbot.mouseMove(host, host.rect().bottomRight())
        qtbot.wait(1)
        image = button.grab().toImage()
        assert image.pixelColor(button.width() - 8, 5) == QColor(
            theme[f"action_secondary_{state}_bg"]
        ), state
        assert button.size() == initial_size

    button.setEnabled(True)
    button.setChecked(False)
    button.setDown(False)
    before_icon = button._caret.cacheKey()
    next_theme = "light_mode" if name != "light_mode" else "fantasy_mode"
    manager.set_theme(next_theme, persist=False)
    host.setStyleSheet(
        manager.format_stylesheet(Path("src/resources/main.qss").read_text("utf-8"))
    )
    qtbot.wait(1)
    assert button.grab().toImage().pixelColor(button.width() - 8, 5) == QColor(
        manager.get_theme()["action_secondary_normal_bg"]
    )
    assert button._caret.cacheKey() != before_icon


def test_split_button_keeps_primary_action_and_menu_hit_area(qtbot):
    button = PhosphorToolMenuButton()
    qtbot.addWidget(button)
    action = QAction("Fit View", button)
    button.setDefaultAction(action)
    button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
    menu = QMenu(button)
    menu.addAction("Compact lanes")
    button.setMenu(menu)
    button.show()
    with qtbot.waitSignal(action.triggered):
        qtbot.mouseClick(button, Qt.MouseButton.LeftButton, pos=QPoint(10, 10))
    with qtbot.waitSignal(menu.aboutToShow):
        QTimer.singleShot(0, menu.close)
        qtbot.mouseClick(
            button,
            Qt.MouseButton.LeftButton,
            pos=QPoint(button.width() - 8, button.height() // 2),
        )
