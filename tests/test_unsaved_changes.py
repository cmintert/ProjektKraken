from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QMessageBox, QWidget

from src.core.entities import Entity
from src.core.events import Event
from src.gui.widgets.entity_editor import EntityEditorWidget
from src.gui.widgets.event_editor import EventEditorWidget


@pytest.fixture
def event_editor(qtbot):
    from unittest.mock import MagicMock

    # Use QWidget as parent
    mock_parent = QWidget()
    mock_parent.worker = MagicMock()
    widget = EventEditorWidget(parent=mock_parent)
    qtbot.addWidget(widget)
    return widget


@pytest.fixture
def entity_editor(qtbot):
    from unittest.mock import MagicMock

    # Use QWidget as parent
    mock_parent = QWidget()
    mock_parent.worker = MagicMock()
    widget = EntityEditorWidget(parent=mock_parent)
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

    # The worker acknowledges the save by reloading the persisted snapshot.
    event_editor.load_event(Event(id="e1", name="Modified Name", lore_date=100.0))
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

    # NOTE: In the real app, save triggers a reload which clears the dirty flag.
    # We must simulate that here to verify the flag is cleared.
    entity_editor.load_entity(entity)

    assert not entity_editor.has_unsaved_changes()


class MockEditor(QWidget):
    """Minimal editor for the unsaved-change decision boundary."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.unsaved = False

    def has_unsaved_changes(self):
        return self.unsaved

    def _on_save(self):
        pass


def test_mainwindow_check_unsaved_changes(qtbot):
    """The window facade preserves the coordinator's clean/save/discard decisions."""
    from src.app.coordinators.editor_coordinator import EditorCoordinator
    from src.app.main_window import MainWindow

    window = QWidget()
    qtbot.addWidget(window)
    window.event_editor = MockEditor(window)
    window.entity_editor = MockEditor(window)
    window.editor_coordinator = EditorCoordinator(window)
    editor = window.event_editor

    with patch(
        "src.app.coordinators.editor_coordinator.QMessageBox.warning"
    ) as warning:
        assert MainWindow.check_unsaved_changes(window, editor)
        warning.assert_not_called()

        editor.unsaved = True
        for decision, safe_to_leave, saves in (
            (QMessageBox.StandardButton.Save, False, 1),
            (QMessageBox.StandardButton.Discard, True, 0),
            (QMessageBox.StandardButton.Cancel, False, 0),
        ):
            warning.return_value = decision
            with patch.object(editor, "_on_save") as save:
                assert MainWindow.check_unsaved_changes(window, editor) is safe_to_leave
                assert save.call_count == saves


def test_editor_init_not_dirty(qtbot):
    """Regression test: Editor should not be dirty on init or when no item loaded."""
    from unittest.mock import MagicMock

    from src.gui.widgets.entity_editor import EntityEditorWidget
    from src.gui.widgets.event_editor import EventEditorWidget

    # Mock parent
    mock_parent = QWidget()
    mock_parent.worker = MagicMock()

    # Check Event Editor
    event_editor = EventEditorWidget(parent=mock_parent)
    qtbot.addWidget(event_editor)
    assert not event_editor.has_unsaved_changes()

    # Simulate a signal that would normally cause dirty (e.g. text changed)
    # But without an event loaded, it should be ignored
    event_editor.name_edit.setText("Changed")
    assert not event_editor.has_unsaved_changes()

    # Check Entity Editor
    entity_editor = EntityEditorWidget(parent=mock_parent)
    qtbot.addWidget(entity_editor)
    assert not entity_editor.has_unsaved_changes()

    # Simulate signal
    entity_editor.name_edit.setText("Changed")
    assert not entity_editor.has_unsaved_changes()
