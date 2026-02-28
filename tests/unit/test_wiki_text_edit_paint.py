"""
Tests for the paintEvent overide in WikiTextEditView.
"""

from unittest.mock import MagicMock, patch

from PySide6.QtGui import QPaintEvent
from PySide6.QtCore import QRect

from src.gui.widgets.wiki_text_edit import WikiTextEdit, SectionData


def test_wiki_text_edit_paint_event_does_not_crash(qtbot):
    """Test that the overridden paintEvent executes without crashing."""
    widget = WikiTextEdit()
    qtbot.addWidget(widget)

    # Add a heading to ensure SectionData is generated
    widget.set_wiki_text("# Chapter 1\n\nSome text")

    # Wait for the debounced section manager to finish
    qtbot.wait(400)

    # Trigger a paint event manually
    event = QPaintEvent(QRect(0, 0, 800, 600))
    # It shouldn't raise any exceptions
    widget.editor.paintEvent(event)


def test_paint_event_draws_rect_for_sections(qtbot):
    """Test that paintEvent completes successfully when sections exist."""
    widget = WikiTextEdit()
    qtbot.addWidget(widget)

    # Force the view mode to rich so it attempts to draw
    widget.editor._view_mode = "rich"

    # Add text and force parsing
    widget.set_wiki_text("# My Heading Output")

    # Wait for debouncer
    qtbot.wait(400)

    # Assert section data exists
    block = widget.document().firstBlock()
    assert isinstance(block.userData(), SectionData)

    # Trigger paint
    # If the logic is correct, traversing the blocks and resolving colors
    # will execute without any AttributeErrors or NameErrors.
    event = QPaintEvent(QRect(0, 0, 800, 600))
    widget.editor.paintEvent(event)
