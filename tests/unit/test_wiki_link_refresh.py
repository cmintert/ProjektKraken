from unittest.mock import Mock

import pytest

from src.core.theme_manager import ThemeManager
from src.gui.editor_typography import EditorTypography
from src.gui.widgets.wiki_text_edit import WikiTextEdit


@pytest.fixture
def editor(qtbot):
    widget = WikiTextEdit()
    qtbot.addWidget(widget)
    return widget


def test_link_validation_updates_on_completer_load(editor):
    """Test that existing wiki links re-validate when completer data arrives."""
    view = editor.editor

    # 1. Set text with a link before any completer is set
    # Fallback behavior: if no _valid_targets_lower exists, links are NOT marked red.
    view.set_wiki_text("[[MissingItem]]")

    # Check that it's NOT red initially (fallback)
    html = view.toHtml()
    assert "color: red" not in html

    # 2. Set completer WITHOUT the item
    # This should trigger re-render and turn it red because 'MissingItem' is not in the list
    view.set_completer(names=["OtherItem"])
    html = view.toHtml().lower()
    broken_color = EditorTypography.from_theme(
        ThemeManager().get_theme()
    ).broken_link_color
    assert broken_color in html

    # 3. Set completer WITH the item
    # This should trigger re-render and turn it back to blue (normal link color)
    view.set_completer(names=["MissingItem", "OtherItem"])
    html = view.toHtml().lower()
    assert broken_color not in html


def test_cursor_preservation_on_completer_refresh(editor):
    """Test that cursor position is preserved when completer triggers a refresh."""
    view = editor.editor
    view.set_wiki_text("Line 1\nLine 2\nLine 3")

    # Place cursor at the end of Line 2
    cursor = view.textCursor()
    cursor.setPosition(13)  # End of 'Line 1\nLine 2'
    view.setTextCursor(cursor)

    # Update completer
    view.set_completer(names=["Test"])

    # Verify cursor is still at 13
    assert view.textCursor().position() == 13


def test_link_refresh_updates_all_fragments_and_invalidates_layout(editor):
    """Revalidation updates every anchor before requesting a repaint."""
    view = editor.editor
    view.set_wiki_text("[[Known]] and [[Missing]]")
    refresh = Mock(wraps=view._refresh_document_layout)
    view._refresh_document_layout = refresh

    view.set_completer(names=["Known"])

    link_color = view._typography.link_color.lower()
    broken_color = view._typography.broken_link_color.lower()
    anchor_colors = {}
    block = view.document().begin()
    while block.isValid():
        iterator = block.begin()
        while not iterator.atEnd():
            fragment = iterator.fragment()
            if fragment.isValid() and fragment.charFormat().isAnchor():
                anchor_colors[fragment.charFormat().anchorHref()] = (
                    fragment.charFormat().foreground().color().name().lower()
                )
            iterator += 1
        block = block.next()

    assert anchor_colors == {"Known": link_color, "Missing": broken_color}
    refresh.assert_called_once_with()
