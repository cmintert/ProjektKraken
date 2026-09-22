"""Tests for the responsive overflow action row."""

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QPushButton,
    QStyle,
    QStyleOptionButton,
)

from src.core.theme_manager import ThemeManager
from src.gui.utils.style_helper import StyleHelper
from src.gui.widgets.attribute_editor import AttributeEditorWidget
from src.gui.widgets.editor_presentation import EditorPresentation
from src.gui.widgets.overflow_toolbar import OverflowToolBar


def test_narrow_toolbar_overflows_low_priority_without_clipping(qtbot) -> None:
    toolbar = OverflowToolBar()
    primary = QPushButton("Primary Action")
    secondary = QPushButton("Secondary Action")
    option = QCheckBox("Optional checks")
    toolbar.add_button(primary, priority=100, pinned=True)
    toolbar.add_button(secondary, priority=50)
    toolbar.add_button(option, priority=10)
    toolbar.resize(210, toolbar.sizeHint().height())
    qtbot.addWidget(toolbar)
    toolbar.show()
    toolbar.resize(210, toolbar.sizeHint().height())
    qtbot.wait(1)

    assert not primary.isHidden()
    assert primary.width() >= primary.sizeHint().width()
    assert option in toolbar.overflowed_buttons()
    assert not toolbar.overflow_button.isHidden()
    assert primary.text() == "Primary Action"


def test_attribute_toolbar_keeps_add_action_visible_without_clipping(
    qapp, qtbot
) -> None:
    template = Path("src/resources/main.qss").read_text(encoding="utf-8")
    previous_style = qapp.styleSheet()
    qapp.setStyleSheet(template.format(**ThemeManager().get_theme()))
    try:
        editor = AttributeEditorWidget()
        toolbar = EditorPresentation._overflow_row(
            editor,
            [editor.btn_add, editor.btn_remove],
            pin_primary=True,
        )
        qtbot.addWidget(toolbar)
        toolbar.resize(150, toolbar.sizeHint().height())
        toolbar.show()
        qtbot.wait(1)

        text_width = editor.btn_add.fontMetrics().horizontalAdvance(
            editor.btn_add.text()
        )
        option = QStyleOptionButton()
        option.initFrom(editor.btn_add)
        content_rect = editor.btn_add.style().subElementRect(
            QStyle.SubElement.SE_PushButtonContents,
            option,
            editor.btn_add,
        )
        assert not editor.btn_add.isHidden()
        assert content_rect.width() >= text_width
        assert editor.btn_add.width() >= text_width + 48
        assert editor.btn_remove in toolbar.overflowed_buttons()
    finally:
        qapp.setStyleSheet(previous_style)


def test_wide_toolbar_keeps_actions_packed_left(qtbot) -> None:
    toolbar = OverflowToolBar()
    buttons = [QPushButton(label) for label in ("One", "Two", "Three")]
    for button in buttons:
        toolbar.add_button(button)
    toolbar.resize(800, toolbar.sizeHint().height())
    qtbot.addWidget(toolbar)
    toolbar.show()
    qtbot.wait(1)

    assert buttons[0].geometry().left() == 0
    for previous, current in zip(buttons, buttons[1:]):
        gap = current.geometry().left() - previous.geometry().right() - 1
        assert gap == toolbar._layout.spacing()


def test_wide_toolbar_keeps_checkbox_at_right(qtbot) -> None:
    toolbar = OverflowToolBar()
    action = QPushButton("Action")
    option = QCheckBox("Optional checks")
    toolbar.add_button(action, priority=100)
    toolbar.add_button(option, priority=10)
    toolbar.resize(800, toolbar.sizeHint().height())
    qtbot.addWidget(toolbar)
    toolbar.show()
    qtbot.wait(1)

    assert action.geometry().left() == 0
    assert option.geometry().right() == toolbar.contentsRect().right()


def test_overflow_menu_action_uses_original_button_signal(qtbot) -> None:
    toolbar = OverflowToolBar()
    primary = QPushButton("Primary")
    secondary = QPushButton("Secondary")
    toolbar.add_button(primary, priority=100, pinned=True)
    toolbar.add_button(secondary, priority=10)
    toolbar.resize(120, toolbar.sizeHint().height())
    qtbot.addWidget(toolbar)
    toolbar.show()
    toolbar.resize(120, toolbar.sizeHint().height())
    qtbot.wait(1)
    clicked: list[bool] = []
    secondary.clicked.connect(lambda checked=False: clicked.append(checked))

    action = next(
        action
        for action in toolbar.overflow_menu.actions()
        if action.text() == "Secondary"
    )
    action.trigger()

    assert clicked == [False]


def test_checkbox_state_is_shared_with_overflow_action(qtbot) -> None:
    toolbar = OverflowToolBar()
    primary = QPushButton("Primary")
    option = QCheckBox("Editorial checks")
    toolbar.add_button(primary, priority=100, pinned=True)
    toolbar.add_button(option, priority=0)
    toolbar.resize(115, toolbar.sizeHint().height())
    qtbot.addWidget(toolbar)
    toolbar.show()
    toolbar.resize(115, toolbar.sizeHint().height())
    qtbot.wait(1)

    action = next(
        action
        for action in toolbar.overflow_menu.actions()
        if action.text() == "Editorial checks"
    )
    action.trigger()

    assert option.isChecked()
    assert action.isChecked()


def test_unavailable_context_action_is_absent_from_toolbar_and_menu(qtbot) -> None:
    toolbar = OverflowToolBar()
    primary = QPushButton("Primary")
    contextual = QPushButton("Context only")
    toolbar.add_button(primary, priority=100, pinned=True)
    toolbar.add_button(contextual, priority=50, available=False)
    qtbot.addWidget(toolbar)
    toolbar.show()
    toolbar.resize(500, toolbar.sizeHint().height())

    assert contextual.isHidden()
    assert contextual not in toolbar.overflowed_buttons()
    assert not toolbar.overflow_menu.actions()[1].isVisible()

    toolbar.set_button_available(contextual, True)

    assert not contextual.isHidden()


def test_overflow_button_is_spacious_and_theme_aware(qtbot, monkeypatch) -> None:
    toolbar = OverflowToolBar()
    qtbot.addWidget(toolbar)
    theme = ThemeManager().get_theme()

    assert toolbar.overflow_button.text() == "..."
    assert toolbar.overflow_button.size().width() == 40
    assert toolbar.overflow_button.size().height() == 32
    assert theme["surface"] in toolbar.overflow_button.styleSheet()
    assert theme["text_main"] in toolbar.overflow_button.styleSheet()
    assert "::menu-indicator" in toolbar.overflow_button.styleSheet()

    monkeypatch.setattr(
        StyleHelper,
        "get_overflow_button_style",
        staticmethod(lambda: "QToolButton { color: magenta; }"),
    )
    toolbar._apply_theme({})

    assert toolbar.overflow_button.styleSheet() == (
        "QToolButton { color: magenta; }"
    )
