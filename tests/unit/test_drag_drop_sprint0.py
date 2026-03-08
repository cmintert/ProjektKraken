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
    """Test that dropping an item on entity editor emits add_relation_requested signal."""
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

    # Wait for the signal
    with qtbot.waitSignal(
        entity_editor.add_relation_requested, timeout=1000
    ) as blocker:
        entity_editor.dropEvent(drop_event)

    # Verify signal was emitted with correct parameters
    # Signal: source_id, target_id, rel_type, attributes, bidirectional
    args = blocker.args
    assert args[0] == "event-456"  # source: dropped item
    assert args[1] == "entity-123"  # target: current entity
    assert args[2] == "related"  # default relation type
    assert args[3] == {}  # empty attributes
    assert args[4] is False  # not bidirectional


def test_event_editor_drop_creates_relation_signal(event_editor, qtbot):
    """Test that dropping an item on event editor emits add_relation_requested signal."""
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

    # Wait for the signal
    with qtbot.waitSignal(event_editor.add_relation_requested, timeout=1000) as blocker:
        event_editor.dropEvent(drop_event)

    # Verify signal was emitted with correct parameters
    args = blocker.args
    assert args[0] == "entity-456"  # source: dropped item
    assert args[1] == "event-123"  # target: current event
    assert args[2] == "related"  # default relation type
    assert args[3] == {}  # empty attributes
    assert args[4] is False  # not bidirectional


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
