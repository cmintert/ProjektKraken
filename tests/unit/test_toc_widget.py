"""
Unit tests for TOCWidget.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidget

from src.gui.widgets.toc_widget import TOCWidget


def test_toc_widget_initialization(qtbot):
    """Test that the TOCWidget initializes correctly and is empty."""
    widget = TOCWidget()
    qtbot.addWidget(widget)

    # Needs to have a QListWidget
    list_widget = widget.findChild(QListWidget)
    assert list_widget is not None
    assert list_widget.count() == 0


def test_toc_widget_update_headings(qtbot):
    """Test updating the TOC with a list of headings."""
    widget = TOCWidget()
    qtbot.addWidget(widget)

    # Format: (level, text, position)
    headings = [(1, "Introduction", 0), (2, "Background", 50), (1, "Conclusion", 150)]

    widget.update_headings(headings)

    list_widget = widget.findChild(QListWidget)
    assert list_widget.count() == 3

    item1 = list_widget.item(0)
    assert item1.text() == "Introduction"
    assert item1.data(Qt.ItemDataRole.UserRole) == 0  # stores position

    item2 = list_widget.item(1)
    assert item2.text() == "  Background"  # indented
    assert item2.data(Qt.ItemDataRole.UserRole) == 50

    item3 = list_widget.item(2)
    assert item3.text() == "Conclusion"
    assert item3.data(Qt.ItemDataRole.UserRole) == 150


def test_toc_widget_clicks_emit_signal(qtbot):
    """Test that clicking an item emits the header_clicked signal with the correct block position."""
    widget = TOCWidget()
    qtbot.addWidget(widget)

    headings = [(1, "Introduction", 0), (2, "Background", 50)]
    widget.update_headings(headings)
    list_widget = widget.findChild(QListWidget)

    # Get the rectangle for the second item to click on
    item_rect = list_widget.visualItemRect(list_widget.item(1))

    with qtbot.waitSignal(widget.header_clicked) as blocker:
        qtbot.mouseClick(
            list_widget.viewport(), Qt.MouseButton.LeftButton, pos=item_rect.center()
        )

    assert blocker.args == [50]  # The position we clicked
