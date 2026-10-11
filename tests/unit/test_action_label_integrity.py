"""UI-GATE-01 detector and production-layout behavior regressions."""

import json
from pathlib import Path

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QFont, QFontDatabase, QIcon, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QMenu,
    QPushButton,
    QRadioButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from scripts.action_label_audit import audit_widget, button_failures, menu_failures
from src.core.theme_manager import ThemeManager
from src.gui.utils.action_label_metrics import (
    action_label_geometry,
    intrinsic_action_size,
)
from src.gui.widgets.action_flow_layout import ActionFlowLayout
from src.gui.widgets.overflow_toolbar import OverflowToolBar

pytestmark = pytest.mark.ci_fast


def styled_host(qtbot):
    font_path = Path("C:/Windows/Fonts/segoeui.ttf")
    if font_path.exists():
        QFontDatabase.addApplicationFont(str(font_path))
    root = QWidget()
    qtbot.addWidget(root)
    root.setFont(QFont("Segoe UI", 10))
    root.setStyleSheet(
        ThemeManager().format_stylesheet(
            Path("src/resources/main.qss").read_text("utf-8")
        )
    )
    root.resize(500, 300)
    return root


@pytest.mark.smoke
def test_deliberately_small_geometry_proves_gate_fails(qtbot):
    root = styled_host(qtbot)
    button = QPushButton("Create an entity", root)
    button.setStyleSheet("QPushButton { min-height: 0; }")
    button.setFixedSize(35, 10)
    root.show()
    kinds = {failure.kind for failure in audit_widget(root)}
    assert "horizontal_clipping" in kinds
    assert "vertical_clipping" in kinds
    button.setFixedSize(intrinsic_action_size(button))
    assert not button_failures(button, root)


def test_populated_explorer_keeps_filter_row_compact_and_list_expansive(qtbot):
    from src.core.events import Event
    from src.gui.widgets.unified_list import UnifiedListWidget

    root = styled_host(qtbot)
    layout = QVBoxLayout(root)
    panel = UnifiedListWidget()
    layout.addWidget(panel)
    panel.set_data([Event(id="audit", name="Draft event", lore_date=0)], [])
    root.resize(480, 1100)
    root.show()
    qtbot.wait(10)
    filters = panel.filter_combo.parentWidget()
    more = panel.filter_action_toolbar.overflow_button
    assert more.label_geometry().required.height() == more.fontMetrics().height()
    assert filters.height() == filters.layout().heightForWidth(filters.width())
    assert panel.list_widget.height() > panel.height() * 0.7
    assert not audit_widget(root)


def test_gate_catches_ancestor_clipping_and_sibling_overlap(qtbot):
    root = styled_host(qtbot)
    first = QPushButton("First action", root)
    first.resize(intrinsic_action_size(first))
    first.move(root.width() - 15, 20)
    second = QPushButton("Second action", root)
    third = QPushButton("Third action", root)
    for button in (second, third):
        button.resize(intrinsic_action_size(button))
        button.move(20, 100)
    root.show()
    failures = audit_widget(root)
    assert any(failure.kind == "ancestor_clipping" for failure in failures)
    assert any(failure.kind.startswith("overlap:") for failure in failures)


@pytest.mark.parametrize("factory", [QPushButton, QToolButton, QCheckBox, QRadioButton])
def test_intrinsic_dimensions_fit_actual_font_and_style(qtbot, factory):
    root = styled_host(qtbot)
    button = factory(root)
    button.setText("Complete action wording")
    if isinstance(button, QToolButton):
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
    for point_size in (10, 12.5, 15, 20):
        font = QFont(button.font())
        font.setPointSizeF(point_size)
        button.setFont(font)
        button.resize(intrinsic_action_size(button))
        assert action_label_geometry(button).fits


def test_multiline_push_button_requires_complete_height(qtbot):
    root = styled_host(qtbot)
    button = QPushButton("Apply changes\nand continue writing", root)
    button.resize(intrinsic_action_size(button))
    assert action_label_geometry(button).fits
    button.resize(button.width(), button.fontMetrics().height())
    assert any(
        failure.kind == "vertical_clipping" for failure in button_failures(button, root)
    )


def test_mixed_icon_text_and_split_button_include_decoration(qtbot):
    root = styled_host(qtbot)
    icon = QPixmap(24, 24)
    icon.fill(Qt.GlobalColor.black)
    for button in (QPushButton("Create entity", root), QToolButton(root)):
        button.setText("Create entity")
        button.setIcon(QIcon(icon))
        button.setIconSize(icon.size())
        if isinstance(button, QToolButton):
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        menu = QMenu(button)
        menu.addAction("Create event")
        button.setMenu(menu)
        button.resize(intrinsic_action_size(button))
        assert action_label_geometry(button).fits
        button.resize(button.width() - 40, button.height())
        assert button_failures(button, root)


def test_menu_detects_changed_wording_and_constrained_geometry(qtbot):
    menu = QMenu()
    qtbot.addWidget(menu)
    menu.addAction("Create Entit…")
    failures = menu_failures(menu, ["Create Entity…"])
    assert any(failure.kind == "changed_wording" for failure in failures)
    menu.setFixedWidth(25)
    assert any(failure.kind == "horizontal_clipping" for failure in menu_failures(menu))


def test_pinned_actions_and_overflow_stack_without_collision(qtbot):
    root = styled_host(qtbot)
    layout = QVBoxLayout(root)
    toolbar = OverflowToolBar()
    primary = QPushButton("Apply")
    secondary = QPushButton("Manage secondary actions")
    toolbar.add_button(primary, pinned=True)
    toolbar.add_button(secondary)
    layout.addWidget(toolbar)
    layout.addStretch()
    root.resize(170, 300)
    root.show()
    qtbot.waitUntil(lambda: toolbar.overflow_button.isVisible())
    qtbot.wait(10)
    assert primary.isVisible()
    assert toolbar.overflow_button.y() > primary.y()
    assert not audit_widget(root)


def test_overflow_tracks_dynamic_text_focus_and_single_toggle(qtbot):
    toolbar = OverflowToolBar()
    qtbot.addWidget(toolbar)
    primary = QPushButton("Create")
    option = QCheckBox("Option")
    toolbar.add_button(primary, pinned=True)
    toolbar.add_button(option)
    toolbar.resize(500, 150)
    toolbar.show()
    toolbar.activateWindow()
    qtbot.wait(10)
    option.setFocus()
    assert option.hasFocus()
    option.setText("Long editorial option requiring more space than this toolbar")
    toolbar.resize(180, 150)
    qtbot.waitUntil(lambda: option in toolbar.overflowed_buttons())
    assert toolbar.overflow_button.hasFocus()
    changes = []
    option.toggled.connect(changes.append)
    action = toolbar.overflow_menu.actions()[1]
    assert action.text() == option.text()
    action.trigger()
    assert option.isChecked() and changes == [True]
    action.trigger()
    assert not option.isChecked() and changes == [True, False]


def test_flow_repositions_original_widgets_without_authoring_signals(qtbot):
    root = styled_host(qtbot)
    layout = ActionFlowLayout(root)
    buttons = [
        QPushButton(text)
        for text in ("Create an entity", "Create an event", "Apply changes")
    ]
    calls = []
    for button in buttons:
        button.clicked.connect(lambda: calls.append(True))
        layout.addWidget(button)
    root.resize(230, 300)
    root.show()
    qtbot.wait(1)
    assert buttons[1].y() > buttons[0].y()
    assert not audit_widget(root)
    root.resize(800, 300)
    qtbot.wait(1)
    assert len({button.y() for button in buttons}) == 1
    assert not calls


@pytest.mark.parametrize("kind", ["push", "tool", "checkbox", "radio", "combo"])
def test_wrapping_controls_use_complete_painted_label_geometry(qtbot, kind):
    from src.gui.widgets.wrapping_buttons import WrappingPushButton, WrappingToolButton
    from src.gui.widgets.wrapping_choices import WrappingCheckBox, WrappingRadioButton
    from src.gui.widgets.wrapping_combo_box import WrappingComboBox

    root = styled_host(qtbot)
    layout = QVBoxLayout(root)
    wording = "Enable automated checks and preserve the complete action wording"
    factories = {
        "push": WrappingPushButton,
        "checkbox": WrappingCheckBox,
        "radio": WrappingRadioButton,
    }
    if kind == "combo":
        control = WrappingComboBox()
        control.addItem(wording)
    elif kind == "tool":
        control = WrappingToolButton()
        control.setText(wording)
        control.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
    else:
        control = factories[kind](wording)
    layout.addWidget(control)
    layout.addStretch()
    root.resize(220, 350)
    root.show()
    qtbot.waitUntil(lambda: control.label_geometry().fits)
    assert control.label_geometry().required.height() > control.fontMetrics().height()
    assert (
        control.text() == wording
        if kind != "combo"
        else control.currentText() == wording
    )
    assert not audit_widget(root)


def test_responsive_dialog_actions_stack_and_preserve_accept_role(qtbot):
    from PySide6.QtWidgets import QDialog, QDialogButtonBox

    from src.gui.widgets.responsive_dialog_buttons import ResponsiveDialogButtonBox

    dialog = QDialog()
    qtbot.addWidget(dialog)
    layout = QVBoxLayout(dialog)
    box = ResponsiveDialogButtonBox(
        QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
    )
    layout.addWidget(box)
    apply = box.button(QDialogButtonBox.StandardButton.Ok)
    cancel = box.button(QDialogButtonBox.StandardButton.Cancel)
    apply.setText("Apply the reviewed changes")
    cancel.setText("Keep editing this draft")
    dialog.resize(250, 220)
    dialog.show()
    qtbot.waitUntil(lambda: box.orientation() == Qt.Orientation.Vertical)
    assert not audit_widget(dialog)
    with qtbot.waitSignal(box.accepted):
        qtbot.mouseClick(apply, Qt.MouseButton.LeftButton)
    assert box.buttonRole(apply) == QDialogButtonBox.ButtonRole.AcceptRole


@pytest.mark.parametrize(
    "theme", list(json.loads(Path("themes.json").read_text("utf-8")))
)
def test_shared_label_geometry_survives_interaction_states(qtbot, theme, monkeypatch):
    from src.gui.widgets.wrapping_buttons import WrappingPrimaryButton

    monkeypatch.setattr(ThemeManager(), "current_theme_name", theme)
    root = styled_host(qtbot)
    root.setStyleSheet(
        Path("src/resources/main.qss")
        .read_text("utf-8")
        .format(**ThemeManager().themes[theme])
    )
    layout = QVBoxLayout(root)
    action = WrappingPrimaryButton("Apply reviewed changes and continue writing")
    layout.addWidget(action)
    root.resize(240, 220)
    root.show()
    action.setFocus()
    qtbot.mouseMove(action, action.rect().center())
    for enabled, pressed in ((True, False), (True, True), (False, False)):
        action.setEnabled(enabled)
        action.setDown(pressed)
        qtbot.wait(1)
        assert action.label_geometry().fits


def test_wrapped_choice_has_one_keyboard_and_full_label_click_target(qtbot):
    from src.gui.widgets.wrapping_choices import WrappingCheckBox

    root = styled_host(qtbot)
    layout = QVBoxLayout(root)
    option = WrappingCheckBox(
        "Enable automated checks for every current authoring action"
    )
    layout.addWidget(option)
    root.resize(220, 220)
    root.show()
    option.setFocus()
    qtbot.keyClick(option, Qt.Key.Key_Space)
    assert option.isChecked()
    qtbot.mouseClick(
        option,
        Qt.MouseButton.LeftButton,
        pos=option.rect().bottomRight() - QPoint(5, 5),
    )
    assert not option.isChecked()


def test_missing_source_owner_and_unknown_adapter_fail_closed(qtbot):
    from PySide6.QtWidgets import QAbstractButton

    from scripts.action_label_coverage import coverage_records
    from scripts.action_label_fixtures import SURFACES

    assert (
        coverage_records([{"source": "src/gui/new_action_surface.py"}], SURFACES)[0][
            "status"
        ]
        == "missing_fixture"
    )

    class UnknownButton(QAbstractButton):
        def paintEvent(self, event):
            pass

    root = styled_host(qtbot)
    unknown = UnknownButton(root)
    unknown.setText("A complete action")
    unknown.resize(200, 50)
    root.show()
    assert any(failure.kind == "unknown_adapter" for failure in audit_widget(root))


@pytest.mark.parametrize(
    "theme", list(json.loads(Path("themes.json").read_text("utf-8")))
)
def test_scrollable_panel_background_follows_app_theme(qtbot, theme, monkeypatch):
    from PySide6.QtGui import QColor

    from src.gui.widgets.responsive_form import scrollable_form_page

    manager = ThemeManager()
    monkeypatch.setattr(manager, "current_theme_name", theme)
    root = styled_host(qtbot)
    layout = QVBoxLayout(root)
    page = QWidget()
    scroll = scrollable_form_page(page)
    layout.addWidget(scroll)
    root.show()
    qtbot.wait(1)
    expected = QColor(manager.get_theme()["app_bg"])
    assert page.grab().toImage().pixelColor(10, 10) == expected
    assert scroll.viewport().grab().toImage().pixelColor(10, 10) == expected


def test_generation_grid_and_prompt_remain_separate_at_enlarged_text(qtbot):
    import re

    from src.gui.widgets.llm_generation_widget import LLMGenerationWidget

    root = styled_host(qtbot)
    root.setStyleSheet(
        re.sub(
            r"(font-size\s*:\s*)([\d.]+)(px|pt)",
            lambda match: f"{match[1]}{float(match[2]) * 2:g}{match[3]}",
            root.styleSheet(),
        )
    )
    layout = QVBoxLayout(root)
    generator = LLMGenerationWidget()
    layout.addWidget(generator)
    generator.custom_prompt_edit.setPlainText("An unfinished authoring prompt")
    root.resize(360, 720)
    root.show()
    qtbot.wait(10)
    assert not audit_widget(root)
    assert (
        generator.custom_prompt_edit.toPlainText() == "An unfinished authoring prompt"
    )
    assert generator.generate_btn.isVisibleTo(root)


@pytest.mark.parametrize(
    "theme", list(json.loads(Path("themes.json").read_text("utf-8")))
)
def test_native_panel_fill_and_live_theme_switch_use_theme_tokens(
    qapp, qtbot, theme, monkeypatch
):
    from PySide6.QtGui import QColor

    manager = ThemeManager()
    monkeypatch.setattr(manager, "current_theme_name", theme)
    monkeypatch.setattr(manager, "_qss_template", manager._qss_template)
    old_palette, old_stylesheet = qapp.palette(), qapp.styleSheet()
    panel = QWidget()
    panel.setAutoFillBackground(True)
    qtbot.addWidget(panel)
    panel.resize(120, 120)
    panel.show()
    try:
        template = Path("src/resources/main.qss").read_text("utf-8")
        manager.apply_theme(qapp, template)
        qtbot.wait(1)
        expected = QColor(manager.get_theme()["app_bg"])
        assert panel.grab().toImage().pixelColor(20, 20) == expected
        alternate = "light_mode" if theme != "light_mode" else "dark_mode"
        monkeypatch.setattr(manager, "current_theme_name", alternate)
        manager.apply_theme(qapp, template)
        qtbot.wait(1)
        assert panel.grab().toImage().pixelColor(20, 20) == QColor(
            manager.get_theme()["app_bg"]
        )
    finally:
        qapp.setPalette(old_palette)
        qapp.setStyleSheet(old_stylesheet)
