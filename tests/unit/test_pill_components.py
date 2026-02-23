"""
Unit tests for TagPill and FlowLayout components.
"""

import pytest
from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import QLabel, QWidget


@pytest.fixture
def tag_pill(qtbot):
    """
    Create a TagPill widget with text "test-tag" and register it with qtbot.
    
    Returns:
        TagPill: The created TagPill instance.
    """
    from src.gui.widgets.tag_pill import TagPill

    pill = TagPill("test-tag")
    qtbot.addWidget(pill)
    return pill


class TestTagPill:
    """Tests for TagPill component."""

    def test_pill_text(self, tag_pill):
        """Test pill displays correct text."""
        assert tag_pill.text == "test-tag"
        assert tag_pill.label.text() == "test-tag"

    def test_delete_signal(self, tag_pill, qtbot):
        """
        Verify that clicking the pill's delete button emits the `deleted` signal carrying the pill's text.
        
        The test clicks the pill's delete button and asserts the emitted signal's argument equals "test-tag".
        """
        with qtbot.waitSignal(tag_pill.deleted) as blocker:
            qtbot.mouseClick(tag_pill.btn_delete, Qt.LeftButton)
        assert blocker.args == ["test-tag"]


class TestFlowLayout:
    """Tests for FlowLayout component."""

    @pytest.fixture
    def container(self, qtbot):
        """
        Create and register a QWidget to serve as a test container.
        
        Returns:
            widget (QWidget): The created QWidget registered with the provided qtbot fixture.
        """
        widget = QWidget()
        qtbot.addWidget(widget)
        return widget

    def test_add_items(self, container):
        from src.gui.widgets.flow_layout import FlowLayout

        layout = FlowLayout(container)

        w1 = QWidget()
        w2 = QWidget()
        layout.addWidget(w1)
        layout.addWidget(w2)

        assert layout.count() == 2
        assert layout.itemAt(0).widget() == w1
        assert layout.itemAt(1).widget() == w2

    def test_minimum_size(self, container):
        from src.gui.widgets.flow_layout import FlowLayout

        layout = FlowLayout(container)

        w1 = QWidget()
        w1.setMinimumSize(100, 50)
        layout.addWidget(w1)

        min_size = layout.minimumSize()
        assert min_size.width() >= 100
        assert min_size.height() >= 50
