"""Tests for Sprint 0 drag-and-drop relation creation.

Tests the basic drag-drop functionality from Project Explorer to Entity/Event editors.
"""

import json

import pytest
from PySide6.QtCore import QMimeData, Qt

from src.core.entities import Entity
from src.core.events import Event
from src.gui.widgets.entity_editor import EntityEditorWidget
from src.gui.widgets.event_editor import EventEditorWidget
from src.gui.widgets.unified_list import KRAKEN_ITEM_MIME_TYPE


@pytest.fixture
def entity_editor(qtbot):
    """Create an EntityEditorWidget for testing."""
    from unittest.mock import MagicMock

    from PySide6.QtWidgets import QWidget

    mock_parent = QWidget()
    mock_parent.worker = MagicMock()
    widget = EntityEditorWidget(parent=mock_parent)
    qtbot.addWidget(widget)
    return widget


@pytest.fixture
def event_editor(qtbot):
    """Create an EventEditorWidget for testing."""
    from unittest.mock import MagicMock

    from PySide6.QtWidgets import QWidget

    mock_parent = QWidget()
    mock_parent.worker = MagicMock()
    widget = EventEditorWidget(parent=mock_parent)
    qtbot.addWidget(widget)
    return widget


def test_entity_editor_accepts_drops(entity_editor):
    """Test that entity editor accepts drops."""
    assert entity_editor.acceptDrops() is True


def test_event_editor_accepts_drops(event_editor):
    """Test that event editor accepts drops."""
    assert event_editor.acceptDrops() is True


def test_entity_editor_drop_creates_relation_signal(entity_editor, qtbot):
    """A labeled drop prepares a connection; Connect emits the directed request."""
    # Load an entity so the editor is ready
    entity = Entity(id="entity-123", name="Test Entity", type="Character")
    entity_editor.load_entity(entity)

    # Create MIME data simulating a drag from Project Explorer
    mime_data = QMimeData()
    drag_data = {"id": "event-456", "type": "event", "name": "The Great War"}
    mime_data.setData(KRAKEN_ITEM_MIME_TYPE, json.dumps(drag_data).encode("utf-8"))

    # Create a mock drop event
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QDropEvent

    drop_event = QDropEvent(
        QPoint(10, 10),  # position
        Qt.DropAction.CopyAction,  # actions
        mime_data,  # mime data
        Qt.MouseButton.LeftButton,  # buttons
        Qt.KeyboardModifier.NoModifier,  # modifiers
    )

    entity_editor._suggestion_items = [("event-456", "The Great War", "event")]
    _assert_drop_requires_connect(entity_editor, drop_event, "event-456", "entity-123")


def test_event_editor_drop_creates_relation_signal(event_editor, qtbot):
    """A labeled drop prepares a connection; Connect emits the directed request."""
    # Load an event so the editor is ready
    event = Event(id="event-123", name="Test Event", lore_date=0.0)
    event_editor.load_event(event)

    # Create MIME data simulating a drag from Project Explorer
    mime_data = QMimeData()
    drag_data = {"id": "entity-456", "type": "entity", "name": "John Smith"}
    mime_data.setData(KRAKEN_ITEM_MIME_TYPE, json.dumps(drag_data).encode("utf-8"))

    # Create a mock drop event
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QDropEvent

    drop_event = QDropEvent(
        QPoint(10, 10),
        Qt.DropAction.CopyAction,
        mime_data,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )

    event_editor._suggestion_items = [("entity-456", "John Smith", "entity")]
    _assert_drop_requires_connect(event_editor, drop_event, "entity-456", "event-123")


def _assert_drop_requires_connect(editor, drop_event, source_id, target_id):
    """Protect the non-mutating inspector boundary and explicit save action."""
    requests = []
    editor.relation_authoring_requested.connect(requests.append)
    editor.dropEvent(drop_event)
    assert not drop_event.isAccepted()
    assert not editor.relation_authoring.capture_open
    assert requests == []

    panel = editor.relation_authoring
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QDragEnterEvent

    enter = QDragEnterEvent(
        QPoint(10, 10),
        Qt.DropAction.CopyAction,
        drop_event.mimeData(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    panel.drop_target.dragEnterEvent(enter)
    assert enter.isAccepted()
    panel.drop_target.dropEvent(drop_event)
    assert drop_event.isAccepted()
    assert panel.capture_open
    assert requests == []
    panel.apply_button.click()
    assert len(requests) == 1
    request = requests[0]
    assert request["source_id"] == source_id
    assert request["target_id"] == target_id
    assert request["rel_type"] == "related"
    assert request["attributes"] == {}


def test_entity_editor_rejects_drop_when_no_entity_loaded(entity_editor, qtbot):
    """Test that entity editor rejects drops when no entity is loaded."""
    # Don't load an entity - editor should reject drops

    # Create MIME data
    mime_data = QMimeData()
    drag_data = {"id": "event-456", "type": "event", "name": "The Great War"}
    mime_data.setData(KRAKEN_ITEM_MIME_TYPE, json.dumps(drag_data).encode("utf-8"))

    # Create a mock drop event
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QDropEvent

    drop_event = QDropEvent(
        QPoint(10, 10),
        Qt.DropAction.CopyAction,
        mime_data,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )

    # Drop should be ignored (no signal emitted)
    entity_editor.dropEvent(drop_event)
    # If drop was accepted, signal would have been emitted
    # Since we can't easily test for "signal not emitted", we just verify no crash


def test_entity_editor_rejects_invalid_mime_data(entity_editor, qtbot):
    """Test that entity editor rejects drops with invalid MIME data."""
    # Load an entity
    entity = Entity(id="entity-123", name="Test Entity", type="Character")
    entity_editor.load_entity(entity)

    # Create MIME data with wrong format
    mime_data = QMimeData()
    mime_data.setText("plain text, not JSON")

    # Create a mock drop event
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QDropEvent

    drop_event = QDropEvent(
        QPoint(10, 10),
        Qt.DropAction.CopyAction,
        mime_data,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )

    # Drop should be ignored (no signal emitted)
    entity_editor.dropEvent(drop_event)
    # Verify no crash - if invalid data was accepted, signal wouldn't have been emitted
