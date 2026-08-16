import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QTextBlockFormat, QTextCursor

from src.core.theme_manager import ThemeManager
from src.gui.editor_typography import EditorTypography
from src.gui.widgets.wiki_text_edit import WikiTextEdit


def _first_character_format(block):
    cursor = QTextCursor(block)
    cursor.movePosition(QTextCursor.MoveOperation.Right)
    return cursor.charFormat()


def test_editor_typography_uses_editor_tokens_not_application_sizes():
    typography = EditorTypography.from_theme(
        {
            "font_size_body": "7pt",
            "font_size_h1": "9pt",
            "editor_body_size": "12pt",
            "editor_h1_size": 18,
            "text_main": "#dddddd",
            "accent_secondary": "#336699",
            "error": "#aa2233",
        }
    )

    assert typography.body_size == 12
    assert typography.h1_size == 18
    assert typography.line_height == 1.38
    assert typography.line_length == 72
    assert typography.document_margin == 34
    assert typography.link_color != "#336699"
    assert typography.broken_link_color != "#aa2233"


def test_default_heading_sizes_have_clear_visual_separation():
    typography = EditorTypography.from_theme({})

    assert typography.h1_size == 20.0
    assert typography.h2_size == 16.0
    assert typography.h3_size == 13.0
    assert typography.h1_size - typography.h2_size >= 4.0
    assert typography.h2_size - typography.h3_size >= 3.0


def test_loaded_and_live_headings_share_typography(qtbot):
    widget = WikiTextEdit()
    qtbot.addWidget(widget)
    typography = widget.editor._typography

    widget.set_wiki_text("# Loaded heading\n\nBody paragraph")
    loaded_heading = widget.document().firstBlock()
    loaded_heading_format = _first_character_format(loaded_heading)
    loaded_block_format = loaded_heading.blockFormat()

    body = loaded_heading.next()
    body_format = _first_character_format(body)
    body_block_format = body.blockFormat()

    assert loaded_heading_format.fontPointSize() == typography.h1_size
    assert loaded_heading_format.fontWeight() == QFont.Weight.DemiBold
    assert loaded_block_format.topMargin() == pytest.approx(
        typography.block_margins(1)[0]
    )
    assert loaded_block_format.bottomMargin() == pytest.approx(
        typography.block_margins(1)[1]
    )
    assert body_format.fontPointSize() == typography.body_size
    assert body_block_format.bottomMargin() == pytest.approx(
        typography.block_margins(0)[1]
    )
    assert body_block_format.lineHeight() == typography.line_height_percent
    assert (
        body_block_format.lineHeightType()
        == QTextBlockFormat.LineHeightTypes.ProportionalHeight.value
    )

    cursor = QTextCursor(body)
    widget.setTextCursor(cursor)
    widget._set_heading(1)
    live_heading_format = _first_character_format(body)
    live_block_format = body.blockFormat()

    assert live_heading_format.fontPointSize() == loaded_heading_format.fontPointSize()
    assert live_heading_format.fontWeight() == loaded_heading_format.fontWeight()
    assert live_block_format.topMargin() == loaded_block_format.topMargin()
    assert live_block_format.bottomMargin() == loaded_block_format.bottomMargin()
    assert live_block_format.lineHeight() == loaded_block_format.lineHeight()


def test_clearing_heading_restores_body_rhythm(qtbot):
    widget = WikiTextEdit()
    qtbot.addWidget(widget)
    typography = widget.editor._typography
    widget.set_wiki_text("# Heading")

    widget._set_heading(0)

    block = widget.document().firstBlock()
    block_format = block.blockFormat()
    character_format = _first_character_format(block)
    assert block_format.headingLevel() == 0
    assert block_format.topMargin() == 0
    assert block_format.bottomMargin() == pytest.approx(
        typography.block_margins(0)[1]
    )
    assert block_format.lineHeight() == typography.line_height_percent
    assert character_format.fontPointSize() == typography.body_size


def test_live_heading_update_replaces_fragment_sizes_and_preserves_links(qtbot):
    widget = WikiTextEdit()
    qtbot.addWidget(widget)
    widget.set_completer(names=["Known Place"])
    widget.set_wiki_text("# Visit [[Known Place]] now")
    typography = widget.editor._typography
    cursor = widget.textCursor()
    cursor.setPosition(3)
    widget.setTextCursor(cursor)

    widget.editor.action_h2.trigger()

    block = widget.document().firstBlock()
    assert block.blockFormat().headingLevel() == 2
    iterator = block.begin()
    saw_anchor = False
    while not iterator.atEnd():
        fragment = iterator.fragment()
        if fragment.isValid():
            fragment_format = fragment.charFormat()
            assert fragment_format.fontPointSize() == typography.h2_size
            assert fragment_format.fontWeight() == QFont.Weight.DemiBold
            saw_anchor = saw_anchor or fragment_format.isAnchor()
        iterator += 1
    assert saw_anchor is True
    assert widget.get_wiki_text() == "## Visit [[Known Place]] now"


def test_toolbar_changes_rendered_size_of_existing_heading(qtbot):
    """Changing an existing heading updates the live layout immediately."""
    widget = WikiTextEdit()
    qtbot.addWidget(widget)
    widget.show()
    widget.set_wiki_text("# Existing heading")
    cursor = widget.textCursor()
    cursor.setPosition(4)
    widget.setTextCursor(cursor)
    qtbot.waitForWindowShown(widget)
    document_layout = widget.document().documentLayout()
    h1_height = document_layout.blockBoundingRect(
        widget.document().firstBlock()
    ).height()

    button = widget.toolbar.widgetForAction(widget.editor.action_h3)
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
    qtbot.wait(10)

    block = widget.document().firstBlock()
    h3_height = document_layout.blockBoundingRect(block).height()
    assert block.blockFormat().headingLevel() == 3
    assert (
        _first_character_format(block).fontPointSize()
        == widget.editor._typography.h3_size
    )
    assert h3_height < h1_height
    assert widget.get_wiki_text() == "### Existing heading"


def test_theme_change_reapplies_editor_tokens_to_existing_text(qtbot):
    widget = WikiTextEdit()
    qtbot.addWidget(widget)
    widget.set_wiki_text("# Heading\n\nBody")
    theme = dict(ThemeManager().get_theme())
    theme.update(
        {
            "editor_body_size": 12.0,
            "editor_h1_size": 18.0,
            "editor_line_height": 1.45,
            "editor_paragraph_spacing": 0.5,
        }
    )

    widget.editor._on_theme_changed(theme)

    heading = widget.document().firstBlock()
    body = heading.next()
    assert _first_character_format(heading).fontPointSize() == 18.0
    assert _first_character_format(body).fontPointSize() == 12.0
    assert body.blockFormat().lineHeight() == 145
    assert body.blockFormat().bottomMargin() == pytest.approx(8.0)
    assert widget.document().documentMargin() == 34


def test_theme_change_rerenders_live_text_when_source_cache_is_empty(qtbot):
    widget = WikiTextEdit()
    qtbot.addWidget(widget)
    widget.set_wiki_text("")
    widget.insertPlainText("Unsaved live text")
    cursor = widget.textCursor()
    cursor.setPosition(6)
    widget.setTextCursor(cursor)
    theme = dict(ThemeManager().get_theme())
    theme["editor_body_size"] = 13.0

    widget.editor._on_theme_changed(theme)

    assert widget.toPlainText() == "Unsaved live text"
    assert widget.textCursor().position() == 6
    assert widget.editor._typography.body_size == 13.0
    assert _first_character_format(widget.document().firstBlock()).fontPointSize() == 13
    assert "font-size:13pt" in widget.toHtml().replace(" ", "")


def test_section_gutter_is_disabled_by_default(qtbot):
    widget = WikiTextEdit()
    qtbot.addWidget(widget)

    assert widget.editor._typography.show_section_gutter is False
