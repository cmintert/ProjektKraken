"""Tests for DragPill widget (TDD approach)."""

import pytest
from PySide6.QtCore import QPoint

from src.gui.widgets.drag_pill import DragPill


@pytest.fixture
def drag_pill(qtbot):
    """Create a DragPill widget for testing."""
    widget = DragPill(item_name="Test Event", item_type="event")
    qtbot.addWidget(widget)
    return widget


def test_drag_pill_initialization(drag_pill):
    """Test that drag pill initializes with correct properties."""
    assert drag_pill.item_name == "Test Event"
    assert drag_pill.item_type == "event"
    assert not drag_pill.isVisible()  # Hidden by default


def test_drag_pill_shows_at_position(drag_pill, qtbot):
    """Test that drag pill can be shown at a specific position."""
    position = QPoint(100, 100)
    drag_pill.show_at_position(position)
    
    assert drag_pill.isVisible()
    # Check that position is offset from cursor
    actual_pos = drag_pill.pos()
    assert actual_pos.x() == position.x() + 10  # Default offset
    assert actual_pos.y() == position.y() + 10


def test_drag_pill_updates_position(drag_pill, qtbot):
    """Test that drag pill can update its position during drag."""
    drag_pill.show_at_position(QPoint(100, 100))
    
    new_position = QPoint(150, 150)
    drag_pill.update_position(new_position)
    
    actual_pos = drag_pill.pos()
    assert actual_pos.x() == new_position.x() + 10
    assert actual_pos.y() == new_position.y() + 10


def test_drag_pill_hides(drag_pill, qtbot):
    """Test that drag pill can be hidden."""
    drag_pill.show_at_position(QPoint(100, 100))
    assert drag_pill.isVisible()
    
    drag_pill.hide()
    assert not drag_pill.isVisible()


def test_drag_pill_displays_correct_text(drag_pill):
    """Test that drag pill displays the correct item name and type."""
    # Check that labels exist and contain correct text
    assert "Test Event" in drag_pill.name_label.text()
    assert "event" in drag_pill.type_label.text()


def test_drag_pill_uses_theme_colors(drag_pill):
    """Test that drag pill applies theme colors."""
    # Check that stylesheet contains theme color references
    stylesheet = drag_pill.styleSheet()
    assert len(stylesheet) > 0  # Has styling applied


def test_drag_pill_has_max_width(drag_pill):
    """Test that drag pill respects maximum width constraint."""
    # Create pill with very long name
    long_pill = DragPill(item_name="A" * 100, item_type="entity")
    
    # Width should be constrained
    assert long_pill.width() <= 200  # Max width from spec


def test_drag_pill_shows_icon_for_event_type(drag_pill):
    """Test that drag pill shows appropriate icon for event type."""
    event_pill = DragPill(item_name="Event", item_type="event")
    assert event_pill.icon_label.text() == "⚡"  # Event icon


def test_drag_pill_shows_icon_for_entity_type():
    """Test that drag pill shows appropriate icon for entity type."""
    entity_pill = DragPill(item_name="Entity", item_type="entity")
    assert entity_pill.icon_label.text() == "👤"  # Entity icon


def test_drag_pill_stays_on_top():
    """Test that drag pill stays on top of other windows."""
    pill = DragPill(item_name="Test", item_type="event")
    # Check window flags
    from PySide6.QtCore import Qt
    assert pill.windowFlags() & Qt.WindowType.WindowStaysOnTopHint


def test_drag_pill_is_frameless():
    """Test that drag pill has no window frame."""
    pill = DragPill(item_name="Test", item_type="event")
    from PySide6.QtCore import Qt
    assert pill.windowFlags() & Qt.WindowType.FramelessWindowHint


def test_drag_pill_custom_offset():
    """Test that drag pill can use custom offset from cursor."""
    pill = DragPill(item_name="Test", item_type="event", cursor_offset=QPoint(20, 30))
    position = QPoint(100, 100)
    pill.show_at_position(position)
    
    actual_pos = pill.pos()
    assert actual_pos.x() == position.x() + 20
    assert actual_pos.y() == position.y() + 30
