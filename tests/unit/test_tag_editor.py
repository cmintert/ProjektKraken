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
        # Flow layout should contain exactly 1 item (the QLineEdit)
        assert tag_editor.flow_layout.count() == 1

    def test_add_tag_via_enter(self, tag_editor, qtbot):
        """Test adding a tag via Enter key."""
        tag_editor.tag_input.setText("urgent")
        qtbot.keyPress(tag_editor.tag_input, Qt.Key_Return)

        assert "urgent" in tag_editor.get_tags()
        # Pills + Input
        assert tag_editor.flow_layout.count() == 2
        assert tag_editor.tag_input.text() == ""

    def test_remove_tag(self, tag_editor, qtbot):
        """Test removing a tag updates the list."""
        tag_editor.load_tags(["tag1", "tag2", "tag3"])
        assert tag_editor.flow_layout.count() == 4  # 3 pills + 1 input

        # Find the second pill's delete button
        pills = [
            tag_editor.flow_layout.itemAt(i).widget()
            for i in range(tag_editor.flow_layout.count())
        ]
        from src.gui.widgets.tag_pill import TagPill

        target_pill = next(
            p for p in pills if isinstance(p, TagPill) and p.text == "tag2"
        )

        qtbot.mouseClick(target_pill.btn_delete, Qt.LeftButton)

        tags = tag_editor.get_tags()
        assert len(tags) == 2
        assert "tag2" not in tags
        assert "tag1" in tags
        assert "tag3" in tags

    def test_duplicate_tag_rejected(self, tag_editor, qtbot):
        """Test that duplicate tags are not added."""
        tag_editor.load_tags(["existing"])
        tag_editor.tag_input.setText("existing")
        qtbot.keyPress(tag_editor.tag_input, Qt.Key_Return)

        assert tag_editor.get_tags() == ["existing"]
        assert tag_editor.flow_layout.count() == 2

    def test_empty_tag_rejected(self, tag_editor, qtbot):
        """Test that empty tags are not added."""
        tag_editor.tag_input.setText("   ")
        qtbot.keyPress(tag_editor.tag_input, Qt.Key_Return)

        assert tag_editor.get_tags() == []
        assert tag_editor.flow_layout.count() == 1

    def test_load_tags(self, tag_editor):
        """Test loading tags populates the widget."""
        tags = ["fantasy", "medieval", "main-plot"]
        tag_editor.load_tags(tags)

        assert tag_editor.get_tags() == tags
        assert tag_editor.flow_layout.count() == 4

    def test_load_tags_clears_previous(self, tag_editor):
        """Test loading new tags clears previous ones."""
        tag_editor.load_tags(["old1", "old2"])
        tag_editor.load_tags(["new1"])

        assert tag_editor.get_tags() == ["new1"]
        assert tag_editor.flow_layout.count() == 2

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
        qtbot.keyPress(tag_editor.tag_input, Qt.Key_Return)

        signal_spy.assert_called_once()

    def test_tags_changed_signal_on_remove(self, tag_editor, qtbot):
        """Test signal emitted when removing a tag."""
        tag_editor.load_tags(["to-remove"])
        from src.gui.widgets.tag_pill import TagPill

        pill = tag_editor.flow_layout.itemAt(0).widget()
        assert isinstance(pill, TagPill)

        signal_spy = MagicMock()
        tag_editor.tags_changed.connect(signal_spy)

        qtbot.mouseClick(pill.btn_delete, Qt.LeftButton)

        signal_spy.assert_called_once()

    def test_tag_normalization(self, tag_editor, qtbot):
        """Test that tags are trimmed of whitespace."""
        tag_editor.tag_input.setText("  spaced  ")
        qtbot.keyPress(tag_editor.tag_input, Qt.Key_Return)

        assert "spaced" in tag_editor.get_tags()

    def test_case_sensitive_tags(self, tag_editor, qtbot):
        """Test that tags are case-sensitive."""
        tag_editor.load_tags(["Important"])
        tag_editor.tag_input.setText("important")
        qtbot.keyPress(tag_editor.tag_input, Qt.Key_Return)

        tags = tag_editor.get_tags()
        assert len(tags) == 2
        assert "Important" in tags
        assert "important" in tags
