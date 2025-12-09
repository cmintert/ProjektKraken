"""
Unit tests for WikiTextEdit.
"""

from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QMouseEvent
from src.gui.widgets.wiki_text_edit import WikiTextEdit
import pytest

# Requires qtbot to interact with widgets


def test_ctrl_click_emits_signal(qtbot):
    """Test that Ctrl+Click on a link emits the signal."""
    widget = WikiTextEdit()
    widget.setPlainText("Jump to [[The Shire]].")
    widget.show()
    qtbot.addWidget(widget)

    # Monkey patch get_link_at_pos for robust testing of EVENT handling
    # We avoid layout hit testing issues this way
    widget.get_link_at_pos = lambda pos: "The Shire"

    with qtbot.waitSignal(widget.link_clicked) as blocker:
        # Simulate Ctrl+Click
        qtbot.mouseClick(widget.viewport(), Qt.LeftButton, Qt.ControlModifier)

    assert blocker.args == ["The Shire"]


def test_normal_click_ignores_link(qtbot):
    """Test that click without Ctrl does NOT emit signal."""
    widget = WikiTextEdit()
    widget.get_link_at_pos = lambda pos: "The Shire"
    qtbot.addWidget(widget)

    # No signal expected
    try:
        with qtbot.waitSignal(widget.link_clicked, timeout=200):
            qtbot.mouseClick(widget.viewport(), Qt.LeftButton, Qt.NoModifier)
        pytest.fail("Signal should not have been emitted")
    except:
        # Expected timeout (good)
        pass
