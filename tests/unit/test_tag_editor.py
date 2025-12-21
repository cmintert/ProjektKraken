"""
Unit tests for TagEditorWidget.
"""

from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import Qt


@pytest.fixture
def tag_editor(qtbot):
    """Creates a TagEditorWidget instance for testing."""
    from src.gui.widgets.tag_editor import TagEditorWidget

    widget = TagEditorWidget()
    qtbot.addWidget(widget)
    return widget


class TestTagEditorWidget:
    """Tests for TagEditorWidget component."""

    def test_initial_state(self, tag_editor):
        """Test widget initializes with empty tag list."""
        assert tag_editor.get_tags() == []
        assert tag_editor.tag_list.count() == 0

    def test_add_tag(self, tag_editor, qtbot):
        """Test adding a tag updates the list."""
        tag_editor.tag_input.setText("important")
        qtbot.mouseClick(tag_editor.btn_add, Qt.LeftButton)

        assert "important" in tag_editor.get_tags()
        assert tag_editor.tag_list.count() == 1
        assert tag_editor.tag_input.text() == ""  # Input cleared

    def test_add_tag_via_enter(self, tag_editor, qtbot):
        """Test adding a tag via Enter key."""
        tag_editor.tag_input.setText("urgent")
        qtbot.keyPress(tag_editor.tag_input, Qt.Key_Return)

        assert "urgent" in tag_editor.get_tags()

    def test_remove_tag(self, tag_editor, qtbot):
        """Test removing a tag updates the list."""
        tag_editor.load_tags(["tag1", "tag2", "tag3"])
        assert tag_editor.tag_list.count() == 3

        # Select and remove the second tag
        tag_editor.tag_list.setCurrentRow(1)
        qtbot.mouseClick(tag_editor.btn_remove, Qt.LeftButton)

        tags = tag_editor.get_tags()
        assert len(tags) == 2
        assert "tag2" not in tags
        assert "tag1" in tags
        assert "tag3" in tags

    def test_duplicate_tag_rejected(self, tag_editor, qtbot):
        """Test that duplicate tags are not added."""
        tag_editor.load_tags(["existing"])
        tag_editor.tag_input.setText("existing")
        qtbot.mouseClick(tag_editor.btn_add, Qt.LeftButton)

        assert tag_editor.get_tags() == ["existing"]
        assert tag_editor.tag_list.count() == 1

    def test_empty_tag_rejected(self, tag_editor, qtbot):
        """Test that empty tags are not added."""
        tag_editor.tag_input.setText("   ")
        qtbot.mouseClick(tag_editor.btn_add, Qt.LeftButton)

        assert tag_editor.get_tags() == []
        assert tag_editor.tag_list.count() == 0

    def test_load_tags(self, tag_editor):
        """Test loading tags populates the widget."""
        tags = ["fantasy", "medieval", "main-plot"]
        tag_editor.load_tags(tags)

        assert tag_editor.get_tags() == tags
        assert tag_editor.tag_list.count() == 3

    def test_load_tags_clears_previous(self, tag_editor):
        """Test loading new tags clears previous ones."""
        tag_editor.load_tags(["old1", "old2"])
        tag_editor.load_tags(["new1"])

        assert tag_editor.get_tags() == ["new1"]
        assert tag_editor.tag_list.count() == 1

    def test_get_tags(self, tag_editor):
        """Test getting tags returns the current list."""
        tag_editor.load_tags(["alpha", "beta", "gamma"])
        result = tag_editor.get_tags()

        assert result == ["alpha", "beta", "gamma"]
        assert isinstance(result, list)

    def test_tags_changed_signal_on_add(self, tag_editor, qtbot):
        """Test signal emitted when adding a tag."""
        signal_spy = MagicMock()
        tag_editor.tags_changed.connect(signal_spy)

        tag_editor.tag_input.setText("new-tag")
        qtbot.mouseClick(tag_editor.btn_add, Qt.LeftButton)

        signal_spy.assert_called_once()

    def test_tags_changed_signal_on_remove(self, tag_editor, qtbot):
        """Test signal emitted when removing a tag."""
        tag_editor.load_tags(["to-remove"])

        signal_spy = MagicMock()
        tag_editor.tags_changed.connect(signal_spy)

        tag_editor.tag_list.setCurrentRow(0)
        qtbot.mouseClick(tag_editor.btn_remove, Qt.LeftButton)

        signal_spy.assert_called_once()

    def test_tag_normalization(self, tag_editor, qtbot):
        """Test that tags are trimmed of whitespace."""
        tag_editor.tag_input.setText("  spaced  ")
        qtbot.mouseClick(tag_editor.btn_add, Qt.LeftButton)

        assert "spaced" in tag_editor.get_tags()

    def test_case_sensitive_tags(self, tag_editor, qtbot):
        """Test that tags are case-sensitive."""
        tag_editor.load_tags(["Important"])
        tag_editor.tag_input.setText("important")
        qtbot.mouseClick(tag_editor.btn_add, Qt.LeftButton)

        tags = tag_editor.get_tags()
        assert len(tags) == 2
        assert "Important" in tags
        assert "important" in tags
