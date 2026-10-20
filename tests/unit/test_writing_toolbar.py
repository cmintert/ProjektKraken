"""Protect command identity and author state across the new chrome."""

import pytest
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QToolButton

from src.core.theme_manager import ThemeManager
from src.gui.widgets.wiki_text_edit import WikiTextEdit

pytestmark = [
    pytest.mark.ci_fast,
    pytest.mark.usefixtures("isolated_theme_manager"),
]


@pytest.mark.parametrize("source", [False, True])
def test_opening_writing_menus_preserves_draft_selection_and_undo(qtbot, source):
    widget = WikiTextEdit()
    qtbot.addWidget(widget)
    widget.set_adaptive_width(True)
    widget.resize(760, 400)
    if source:
        widget.action_toggle_mode.trigger()
    widget.set_wiki_text("A **draft** with [[id:alpha|Alpha]]")
    widget.show()
    view = widget.editor
    view.moveCursor(QTextCursor.MoveOperation.End)
    view.insertPlainText("!")
    cursor = view.textCursor()
    cursor.setPosition(2)
    cursor.setPosition(7, QTextCursor.MoveMode.KeepAnchor)
    view.setTextCursor(cursor)
    snapshot = (
        widget.get_wiki_text(),
        cursor.anchor(),
        cursor.position(),
        view.document().revision(),
        view.document().isUndoAvailable(),
    )
    row = widget.toolbar_presentation.menu_row
    buttons = [
        button for button in row.findChildren(QToolButton) if button.text() == "Format"
    ]
    button = buttons[0]
    opened = []
    button.menu().aboutToShow.connect(lambda: opened.append(True))
    QTimer.singleShot(30, button.menu().close)
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
    assert opened
    cursor = view.textCursor()
    assert snapshot == (
        widget.get_wiki_text(),
        cursor.anchor(),
        cursor.position(),
        view.document().revision(),
        view.document().isUndoAvailable(),
    )


def test_format_menu_reuses_existing_shortcut_actions(qtbot):
    widget = WikiTextEdit()
    qtbot.addWidget(widget)
    view = widget.editor
    presentation = widget.toolbar_presentation
    assert presentation._menus["Headings"].actions() == [
        view.action_h1,
        view.action_h2,
        view.action_h3,
    ]
    for action in (view.action_bold, view.action_italic, view.action_body):
        assert action in presentation._menus["Format"].actions()
    widget.action_toggle_mode.trigger()
    view.setPlainText("**Keep existing clear behavior**")
    cursor = view.textCursor()
    cursor.select(QTextCursor.SelectionType.Document)
    view.setTextCursor(cursor)
    view.action_body.trigger()
    assert widget.toPlainText() == "Keep existing clear behavior"


def test_edit_menu_uses_native_editor_undo_and_redo(qtbot):
    widget = WikiTextEdit()
    qtbot.addWidget(widget)
    widget.action_toggle_mode.trigger()
    initial = widget.toPlainText()
    widget.editor.insertPlainText("draft")
    drafted = widget.toPlainText()
    presentation = widget.toolbar_presentation
    presentation._refresh_edit_menu()
    menu = presentation._menus["Edit"]
    undo = next(
        action
        for action in menu.actions()
        if action.text().replace("&", "").startswith("Undo")
    )
    assert undo.isEnabled()
    undo.trigger()
    assert widget.toPlainText() == initial
    presentation._refresh_edit_menu()
    redo = next(
        action
        for action in menu.actions()
        if action.text().replace("&", "").startswith("Redo")
    )
    assert redo.isEnabled()
    redo.trigger()
    assert widget.toPlainText() == drafted


@pytest.mark.parametrize(
    "theme",
    [
        "dark_mode",
        "light_mode",
        "fantasy_mode",
        "imperial_mode",
        "cyberpunk_mode",
        "muted_light_mode",
    ],
)
def test_theme_switch_preserves_authoring_history_and_recolors_icons(
    qtbot, theme, qapp, monkeypatch
):
    widget = WikiTextEdit()
    qtbot.addWidget(widget)
    monkeypatch.setattr(qapp, "setStyleSheet", widget.setStyleSheet)
    monkeypatch.setattr(qapp, "setPalette", widget.setPalette)
    widget.set_wiki_text("A [[id:alpha|linked]] **draft**")
    view = widget.editor
    view.moveCursor(QTextCursor.MoveOperation.End)
    initial = widget.get_wiki_text()
    view.insertPlainText("!")
    before = (
        widget.get_wiki_text(),
        view.textCursor().anchor(),
        view.textCursor().position(),
    )
    manager = ThemeManager()
    previous = manager.current_theme_name
    try:
        manager.set_theme(theme)
        assert before == (
            widget.get_wiki_text(),
            view.textCursor().anchor(),
            view.textCursor().position(),
        )
        assert not view.action_bold.icon().isNull()
        assert not view.action_italic.icon().isNull()
        assert not view.action_body.icon().isNull()
        view.undo()
        assert widget.get_wiki_text() == initial
    finally:
        manager.set_theme(previous)


def test_narrow_secondary_overflow_keeps_disabled_link_routes(qtbot):
    widget = WikiTextEdit()
    qtbot.addWidget(widget)
    widget.set_adaptive_width(True)
    widget.resize(300, 400)
    widget.show()
    qtbot.wait(20)
    assert not widget.action_open_link.isEnabled()
    assert not widget.action_peek_link.isEnabled()
    row = widget.link_toolbar
    routes = [
        button.text() for button in row.findChildren(QToolButton) if button.isVisible()
    ]
    routes += [
        action.text() for action in row.overflow_menu.actions() if action.isVisible()
    ]
    assert "Open link" in routes
    assert "Peek link" in routes
    assert widget.editor.horizontalScrollBar().maximum() == 0


def test_compact_selector_and_button_tooltips(qtbot):
    """Keep compact chrome readable and explain every formatting icon."""
    widget = WikiTextEdit()
    qtbot.addWidget(widget)
    widget.set_adaptive_width(True)
    widget.resize(760, 400)
    widget.show()
    qtbot.wait(20)
    assert widget.toolbar_presentation.heading_button.width() < widget.width() // 2
    for action in (
        widget.editor.action_bold,
        widget.editor.action_italic,
        widget.editor.action_body,
    ):
        assert action.text() in action.toolTip()
        assert action.shortcut().toString() in action.toolTip()
    assert widget.toolbar_presentation.heading_button.toolTip()


def test_narrow_formatting_strip_retains_full_menu_commands(qtbot):
    """Never leave partially clipped icons at the smallest supported widths."""
    widget = WikiTextEdit()
    qtbot.addWidget(widget)
    widget.set_adaptive_width(True)
    widget.resize(240, 400)
    widget.show()
    qtbot.wait(30)
    toolbar = widget.toolbar
    menu = widget.toolbar_presentation._menus["Format"]
    for action in (
        widget.editor.action_bold,
        widget.editor.action_italic,
        widget.editor.action_body,
    ):
        assert action in menu.actions()
        if action in toolbar.actions():
            button = toolbar.widgetForAction(action)
            assert toolbar.rect().contains(button.geometry())
