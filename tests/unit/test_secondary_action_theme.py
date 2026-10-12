"""Equivalent supporting actions render consistently without flattening roles."""

import json
from pathlib import Path

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PySide6.QtWidgets import QGridLayout, QPushButton, QToolButton, QWidget

from src.core.theme_manager import ThemeManager
from src.gui.utils.style_helper import StyleHelper
from src.gui.widgets.editor_presentation import DisclosureButton
from src.gui.widgets.standard_buttons import DestructiveButton, PrimaryButton
from src.gui.widgets.wrapping_buttons import WrappingToolButton
from src.gui.workspace.activity_bar import ActivityBar

pytestmark = pytest.mark.ci_fast
THEMES = json.loads(Path("themes.json").read_text("utf-8"))


@pytest.mark.parametrize("name", THEMES)
def test_secondary_actions_share_rendered_states_and_keep_other_roles(
    qtbot, monkeypatch, tmp_path, name
):
    manager = ThemeManager()
    monkeypatch.setattr(manager, "current_theme_name", name)
    theme = manager.get_theme()
    font_path = Path("C:/Windows/Fonts/segoeui.ttf")
    if font_path.exists():
        QFontDatabase.addApplicationFont(str(font_path))
    host = QWidget()
    qtbot.addWidget(host)
    host.setFont(QFont("Segoe UI", 10))
    host.setStyleSheet(
        manager.format_stylesheet(Path("src/resources/main.qss").read_text("utf-8"))
    )
    palette = host.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(theme["app_bg"]))
    host.setPalette(palette)
    host.setAutoFillBackground(True)
    host.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    layout = QGridLayout(host)
    plain = QPushButton("Refresh")
    styled = QPushButton("Chronology…")
    styled.setStyleSheet(
        StyleHelper.get_tool_button_style() + StyleHelper.get_inspector_focus_style()
    )
    native_tool = QToolButton()
    native_tool.setText("Heading 1")
    toolbar_tool = QToolButton()
    toolbar_tool.setText("Body")
    toolbar_tool.setStyleSheet(StyleHelper.get_editor_toolbar_style())
    more = WrappingToolButton()
    more.setObjectName("OverflowToolBarMenuButton")
    more.setText("More actions")
    more.setStyleSheet(StyleHelper.get_overflow_button_style())
    controls = [plain, styled, native_tool, toolbar_tool, more]
    for index, button in enumerate(controls):
        if isinstance(button, QToolButton):
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        button.setCheckable(True)
        layout.addWidget(button, index // 3, index % 3)
    primary = PrimaryButton("Save changes")
    destructive = DestructiveButton("Delete")
    quiet = DisclosureButton("Summary")
    quiet.setObjectName("InspectorWritingAction")
    quiet._apply_theme()
    layout.addWidget(primary, 2, 0)
    layout.addWidget(destructive, 2, 1)
    layout.addWidget(quiet, 2, 2)
    host.resize(640, 200)
    host.show()
    host.activateWindow()
    host.setFocus()
    qtbot.wait(1)
    sizes = [button.size() for button in controls]
    for state in ("normal", "hover", "pressed", "checked", "disabled"):
        for button in controls:
            button.setEnabled(state != "disabled")
            button.setChecked(state == "checked")
            button.setDown(state == "pressed")
            if state == "hover":
                qtbot.mouseMove(button, button.rect().center())
            else:
                qtbot.mouseMove(host, host.rect().bottomRight())
            qtbot.wait(1)
            image = button.grab().toImage()
            assert image.pixelColor(button.width() // 2, 5) == QColor(
                theme[f"action_secondary_{state}_bg"]
            )
            assert image.pixelColor(button.width() // 2, 1) == QColor(
                theme[f"action_secondary_{state}_border"]
            )
            group = (
                QPalette.ColorGroup.Disabled
                if state == "disabled"
                else QPalette.ColorGroup.Active
            )
            assert button.palette().color(
                group, QPalette.ColorRole.ButtonText
            ) == QColor(theme[f"action_secondary_{state}_text"])
        assert [button.size() for button in controls] == sizes
    for button in controls:
        button.setEnabled(True)
        button.setChecked(False)
        button.setDown(False)
        button.setFocus()
        qtbot.wait(1)
        assert button.grab().toImage().pixelColor(button.width() // 2, 1) == QColor(
            theme["focus_ring"]
        )
    for button, role in ((primary, "primary"), (destructive, "destructive")):
        assert button.grab().toImage().pixelColor(button.width() // 2, 5) == QColor(
            theme[f"action_{role}_normal_bg"]
        )
    point = quiet.mapTo(host, QPoint(quiet.width() // 2, 5))
    assert host.grab().toImage().pixelColor(point) == QColor(theme["app_bg"])
    assert primary.palette().color(QPalette.ColorRole.ButtonText) == QColor(
        theme["action_primary_normal_text"]
    )
    assert destructive.palette().color(QPalette.ColorRole.ButtonText) == QColor(
        theme["action_destructive_normal_text"]
    )
    host.setFocus()
    qtbot.mouseMove(host, host.rect().bottomRight())
    qtbot.wait(1)
    assert host.grab().save(str(tmp_path / f"{name}.png"))


def test_activity_buttons_share_intrinsic_size_after_label_and_font_changes(qtbot):
    from src.gui.utils.action_label_metrics import action_label_geometry

    host = QWidget()
    qtbot.addWidget(host)
    host.setStyleSheet(
        ThemeManager().format_stylesheet(
            Path("src/resources/main.qss").read_text("utf-8")
        )
    )
    layout = QGridLayout(host)
    bar = ActivityBar("Activities")
    bar.setOrientation(Qt.Orientation.Vertical)
    bar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
    layout.addWidget(bar)
    actions = [
        bar.addAction(name)
        for name in ("Project", "Map", "Timeline", "Graph", "Longform", "Analysis")
    ]
    host.resize(250, 500)
    host.show()
    buttons = [bar.widgetForAction(action) for action in actions]

    def uniform_and_readable():
        return len(
            {(button.width(), button.height()) for button in buttons}
        ) == 1 and all(action_label_geometry(button).fits for button in buttons)

    qtbot.waitUntil(uniform_and_readable)
    first_width = buttons[0].width()
    actions[1].setText("World overview")
    qtbot.waitUntil(lambda: uniform_and_readable() and buttons[0].width() > first_width)
    label_size = buttons[0].size()
    host.setStyleSheet(host.styleSheet().replace("font-size: 10pt", "font-size: 15pt"))
    qtbot.waitUntil(
        lambda: uniform_and_readable() and buttons[0].height() > label_size.height()
    )
    calls = []
    actions[0].triggered.connect(lambda: calls.append(True))
    qtbot.mouseClick(buttons[0], Qt.MouseButton.LeftButton)
    assert calls == [True]
