import pytest
from PySide6.QtWidgets import QMessageBox
from unittest.mock import MagicMock, patch

from src.gui.widgets.event_editor import EventEditorWidget
from src.gui.widgets.entity_editor import EntityEditorWidget
from src.core.events import Event
from src.core.entities import Entity


@pytest.fixture
def event_editor(qtbot):
    widget = EventEditorWidget()
    qtbot.addWidget(widget)
    return widget


@pytest.fixture
def entity_editor(qtbot):
    widget = EntityEditorWidget()
    qtbot.addWidget(widget)
    return widget


def test_event_editor_dirty_tracking(event_editor):
    # Setup
    event = Event(id="e1", name="Test Event", lore_date=100.0)
    event_editor.load_event(event)

    # 1. Initially clean
    assert not event_editor.has_unsaved_changes()
    assert not event_editor.btn_save.isEnabled()

    # 2. Modify field
    event_editor.name_edit.setText("Modified Name")
    assert event_editor.has_unsaved_changes()
    assert event_editor.btn_save.isEnabled()
    assert "Modified Name" in event_editor.name_edit.text()

    # 3. Simulate Save
    # We can invoke _on_save directly
    with patch.object(event_editor, "save_requested") as mock_save:
        event_editor._on_save()
        mock_save.emit.assert_called_once()

    # After save, should be clean
    assert not event_editor.has_unsaved_changes()
    assert not event_editor.btn_save.isEnabled()


def test_entity_editor_dirty_tracking(entity_editor):
    # Setup
    entity = Entity(id="en1", name="Test Entity", type="Character")
    entity_editor.load_entity(entity)

    # 1. Clean
    assert not entity_editor.has_unsaved_changes()

    # 2. Modify type
    entity_editor.type_edit.setCurrentText("Location")
    assert entity_editor.has_unsaved_changes()

    # 3. Save
    with patch.object(entity_editor, "save_requested") as mock_save:
        entity_editor._on_save()
        mock_save.emit.assert_called_once()

    assert not entity_editor.has_unsaved_changes()


from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Signal


class MockEditor(QWidget):
    save_requested = Signal(dict)
    discard_requested = Signal(str)  # Added to match interface
    add_relation_requested = Signal(str, str, str, bool)
    remove_relation_requested = Signal(str)
    update_relation_requested = Signal(str, str, str)
    link_clicked = Signal(str)
    dirty_changed = Signal(bool)
    current_data_changed = Signal(dict)  # Added for live preview support

    def __init__(self):
        super().__init__()
        self.unsaved = False

    def has_unsaved_changes(self):
        return self.unsaved

    def _on_save(self):
        pass


def test_mainwindow_check_unsaved_changes(qtbot):
    # We need to test the logic of check_unsaved_changes logic specifically.

    from src.app.main import MainWindow

    # Create mock editors that are actual QWidgets to satisfy setWidget logic
    mock_event_editor = MockEditor()
    mock_entity_editor = MockEditor()

    # We'll use a real instance but mock internal components to avoid side effects
    with patch("src.app.main.DatabaseWorker"), patch(
        "src.app.main.UnifiedListWidget"
    ), patch("src.app.main.EventEditorWidget", return_value=mock_event_editor), patch(
        "src.app.main.EntityEditorWidget", return_value=mock_entity_editor
    ), patch(
        "src.app.main.TimelineWidget"
    ), patch(
        "src.app.main.MapWidget"
    ), patch(
        "src.app.main.ThemeManager"
    ), patch(
        "src.app.ui_manager.UIManager.setup_docks"
    ):

        window = MainWindow()

        # 1. Clean Editor -> Returns True, no prompt
        mock_event_editor.unsaved = False
        assert window.check_unsaved_changes(window.event_editor)

        # 2. Dirty Editor, User selects Save
        mock_event_editor.unsaved = True

        with patch(
            "PySide6.QtWidgets.QMessageBox.warning", return_value=QMessageBox.Save
        ) as mock_msg:
            # We mock _on_save on the instance
            with patch.object(mock_event_editor, "_on_save") as mock_on_save:
                assert window.check_unsaved_changes(window.event_editor)
                mock_on_save.assert_called_once()

        # 3. Dirty Editor, User selects Discard
        with patch(
            "PySide6.QtWidgets.QMessageBox.warning", return_value=QMessageBox.Discard
        ) as mock_msg:
            with patch.object(mock_event_editor, "_on_save") as mock_on_save:
                assert window.check_unsaved_changes(window.event_editor)
                mock_on_save.assert_not_called()

        # 4. Dirty Editor, User selects Cancel
        with patch(
            "PySide6.QtWidgets.QMessageBox.warning", return_value=QMessageBox.Cancel
        ) as mock_msg:
            with patch.object(mock_event_editor, "_on_save") as mock_on_save:
                assert not window.check_unsaved_changes(window.event_editor)
                mock_on_save.assert_not_called()


def test_editor_init_not_dirty(qtbot):
    """Regression test: Editor should not be dirty on init or when no item loaded."""
    from src.gui.widgets.event_editor import EventEditorWidget
    from src.gui.widgets.entity_editor import EntityEditorWidget

    # Check Event Editor
    event_editor = EventEditorWidget()
    qtbot.addWidget(event_editor)
    assert not event_editor.has_unsaved_changes()

    # Simulate a signal that would normally cause dirty (e.g. text changed)
    # But without an event loaded, it should be ignored
    event_editor.name_edit.setText("Changed")
    assert not event_editor.has_unsaved_changes()

    # Check Entity Editor
    entity_editor = EntityEditorWidget()
    qtbot.addWidget(entity_editor)
    assert not entity_editor.has_unsaved_changes()

    # Simulate signal
    entity_editor.name_edit.setText("Changed")
    assert not entity_editor.has_unsaved_changes()
