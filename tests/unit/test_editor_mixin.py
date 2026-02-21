"""Tests for BaseEditorMixin shared behavior."""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def qapp():
    """Ensure QApplication exists."""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _make_editor_widget(qapp):
    """Create a minimal editor widget using the mixin for testing."""
    from PySide6.QtCore import Signal
    from PySide6.QtWidgets import QPushButton, QWidget

    from src.gui.mixins.autosave_mixin import AutoSaveManager
    from src.gui.mixins.editor_mixin import BaseEditorMixin

    class TestEditor(BaseEditorMixin, QWidget):
        dirty_changed = Signal(bool)

        def __init__(self):
            QWidget.__init__(self)
            self._is_loading = False
            self._is_dirty = False
            self._current_id = None
            self._is_drag_over = False
            self._selected_relation_type = "related"
            self._type_picker = None
            self._hidden_attributes = {}
            self.btn_save = QPushButton("Save Changes")
            self.btn_discard = QPushButton("Discard")
            self.autosave_manager = MagicMock(spec=AutoSaveManager)

        def _get_current_item_id(self):
            return self._current_id

        def _get_editor_label(self):
            return "TestEditor"

        def _show_drop_hint(self, rel_type):
            pass

        def _hide_drop_hint(self):
            pass

    return TestEditor()


def test_set_dirty_emits_signal(qapp):
    """Test that set_dirty emits dirty_changed signal."""
    editor = _make_editor_widget(qapp)
    editor._current_id = "test-id"

    received = []
    editor.dirty_changed.connect(lambda val: received.append(val))

    editor.set_dirty(True)
    assert received == [True]
    assert editor._is_dirty is True
    assert editor.btn_save.text() == "Save Changes *"


def test_set_dirty_ignored_during_loading(qapp):
    """Test that set_dirty(True) is ignored when _is_loading is True."""
    editor = _make_editor_widget(qapp)
    editor._current_id = "test-id"
    editor._is_loading = True

    editor.set_dirty(True)
    assert editor._is_dirty is False


def test_set_dirty_ignored_when_no_item(qapp):
    """Test that set_dirty(True) is ignored when no item is loaded."""
    editor = _make_editor_widget(qapp)
    editor._current_id = None

    editor.set_dirty(True)
    assert editor._is_dirty is False


def test_set_dirty_false_resets_ui(qapp):
    """Test that set_dirty(False) resets button text."""
    editor = _make_editor_widget(qapp)
    editor._current_id = "test-id"

    editor.set_dirty(True)
    editor.set_dirty(False)
    assert editor._is_dirty is False
    assert editor.btn_save.text() == "Save Changes"


def test_has_unsaved_changes(qapp):
    """Test has_unsaved_changes returns dirty state."""
    editor = _make_editor_widget(qapp)
    editor._current_id = "test-id"

    assert editor.has_unsaved_changes() is False
    editor.set_dirty(True)
    assert editor.has_unsaved_changes() is True


def test_extract_hidden_attributes(qapp):
    """Test that hidden attributes are separated correctly."""
    editor = _make_editor_widget(qapp)

    attrs = {"name": "test", "_tags": ["a"], "_summary_data": {}, "color": "red"}
    display = editor._extract_hidden_attributes(attrs)

    assert display == {"name": "test", "color": "red"}
    assert editor._hidden_attributes == {"_tags": ["a"], "_summary_data": {}}


def test_merge_hidden_attributes(qapp):
    """Test that hidden attributes are merged back correctly."""
    editor = _make_editor_widget(qapp)
    editor._hidden_attributes = {"_tags": ["a"], "_summary_data": {"key": "val"}}

    base = {"name": "test", "_summary_data": {"new": "data"}}
    editor._merge_hidden_attributes(base)

    # _summary_data should NOT be overwritten (already in base)
    assert base["_summary_data"] == {"new": "data"}
    # _tags should be added
    assert base["_tags"] == ["a"]
