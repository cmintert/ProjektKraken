"""Tests for the responsive overflow action row."""

from PySide6.QtWidgets import QCheckBox, QPushButton

from src.core.theme_manager import ThemeManager
from src.gui.utils.style_helper import StyleHelper
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
