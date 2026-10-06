"""Rendered presentation roles refresh without changing creative state."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCharFormat

from src.core.theme_manager import ThemeManager
from src.gui.widgets.wiki_text_edit import WikiTextEdit

pytestmark = pytest.mark.ci_fast


def layout_formats(view):
    result = []
    block = view.document().begin()
    while block.isValid():
        result.extend(block.layout().formats())
        block = block.next()
    return result


@pytest.mark.parametrize("theme", ThemeManager().get_available_themes())
def test_theme_link_refresh_preserves_history_and_semantics(qtbot, theme):
    manager = ThemeManager()
    original = manager.current_theme_name
    widget = WikiTextEdit()
    qtbot.addWidget(widget)
    widget.set_completer(items=[("ent", "Entry", "entity"), ("evt", "Moment", "event")])
    widget.set_wiki_text("[[id:ent|Entry]] [[Moment]] [[Gone]]")
    view = widget.editor
    view.moveCursor(view.textCursor().MoveOperation.End)
    view.insertPlainText(" draft")
    qtbot.wait(1)
    text = widget.get_wiki_text()
    cursor = view.textCursor()
    steps = view.document().availableUndoSteps()
    modified = view.document().isModified()
    signals = []
    view.textChanged.connect(lambda: signals.append(True))
    try:
        manager.set_theme(theme)
        mapping = manager.get_theme()
        formats = layout_formats(view)
        colors = {f.format.foreground().color().name() for f in formats}
        for role in ("link_entity", "link_event", "link_unresolved"):
            assert mapping[role].lower() in colors
        assert any(
            f.format.underlineStyle() == QTextCharFormat.UnderlineStyle.DotLine
            for f in formats
        )
        assert widget.get_wiki_text() == text
        assert view.document().availableUndoSteps() == steps
        assert view.document().isModified() == modified
        assert view.textCursor().position() == cursor.position()
        assert signals == []
        widget.set_completer(items=[("ent", "Renamed", "entity")])
        assert widget.get_wiki_text() == text
        assert view.document().availableUndoSteps() == steps
        view.undo()
        assert " draft" not in widget.get_wiki_text()
    finally:
        manager.set_theme(original)


def test_disabled_link_geometry_and_overflow(qtbot):
    widget = WikiTextEdit()
    qtbot.addWidget(widget)
    widget.set_adaptive_width(True)
    widget.resize(900, 400)
    widget.show()
    widget.set_wiki_text("[[Entry]] plain text")
    qtbot.wait(1)
    action = widget.action_open_link
    buttons = [
        item.button
        for item in widget.link_toolbar._items
        if item.button.defaultAction() is action
    ]
    button = buttons[0]
    cursor = widget.textCursor()
    cursor.setPosition(1)
    widget.setTextCursor(cursor)
    qtbot.wait(1)
    assert button.isEnabled()
    size = button.size()
    cursor.movePosition(cursor.MoveOperation.End)
    widget.setTextCursor(cursor)
    qtbot.wait(1)
    assert not button.isEnabled()
    assert button.size() == size
    assert not button.isHidden()
    assert "Place the cursor" in button.toolTip()
    assert button.focusPolicy() == Qt.FocusPolicy.StrongFocus
    widget.resize(360, 400)
    qtbot.wait(1)
    overflow = [
        item.action
        for item in widget.link_toolbar._items
        if item.button.defaultAction() is action
    ][0]
    assert overflow.isVisible()
    assert not overflow.isEnabled()


def test_return_label_width_can_shrink_after_destination_change(qtbot):
    widget = WikiTextEdit()
    qtbot.addWidget(widget)
    widget.set_return_available(True)
    action = widget.action_return_writing
    action.setText("Back to a destination with a long name")
    widget.link_toolbar.refresh()
    wide = widget._return_button.minimumWidth()
    action.setText("Back to Home")
    widget.link_toolbar.refresh()
    assert widget._return_button.minimumWidth() < wide
