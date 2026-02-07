"""Tests for Drag Cursor Pixmap implementation (TDD)."""

from unittest.mock import patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap

from src.core.events import Event
from src.gui.widgets.unified_list import UnifiedListWidget


@pytest.fixture
def unified_list(qtbot):
    """Fixture for UnifiedListWidget."""
    widget = UnifiedListWidget()
    qtbot.addWidget(widget)
    return widget


def test_start_drag_uses_pixmap(unified_list, qtbot):
    """Test that startDrag uses QDrag.setPixmap with a rendered DragPill."""
    # Setup data
    event = Event(id="e1", name="Test Drag Event", lore_date=10.0)
    unified_list.set_data([event], [])

    # Select the item
    model = unified_list._proxy_model
    index = model.index(0, 0)
    unified_list.list_widget.setCurrentIndex(index)

    # Mock QDrag to intercept setPixmap calls
    with patch("src.gui.widgets.unified_list.QDrag") as MockQDrag:
        mock_drag_instance = MockQDrag.return_value
        mock_drag_instance.exec.return_value = Qt.DropAction.CopyAction

        # Call startDrag
        unified_list.list_widget.startDrag(Qt.DropAction.CopyAction)

        # VERIFY: QDrag was instantiated
        assert MockQDrag.called

        # VERIFY: setPixmap was called
        # This is the core requirement for 60FPS smooth drag
        assert mock_drag_instance.setPixmap.called, "QDrag.setPixmap() was not called"

        # VERIFY: The pixmap passed is valid and has reasonable size
        args, _ = mock_drag_instance.setPixmap.call_args
        pixmap = args[0]
        assert isinstance(pixmap, QPixmap)
        assert not pixmap.isNull()
        assert pixmap.width() > 0
        assert pixmap.height() > 0

        # VERIFY: Hotspot is set
        assert mock_drag_instance.setHotSpot.called


def test_drag_pill_cleanup(unified_list):
    """Test that no separate DragPill window is left lingering."""
    # Setup data
    event = Event(id="e1", name="Test Drag Event", lore_date=10.0)
    unified_list.set_data([event], [])
    unified_list.list_widget.setCurrentIndex(unified_list._proxy_model.index(0, 0))

    with patch("src.gui.widgets.unified_list.QDrag") as MockQDrag:
        mock_drag_instance = MockQDrag.return_value
        mock_drag_instance.exec.return_value = Qt.DropAction.CopyAction

        unified_list.list_widget.startDrag(Qt.DropAction.CopyAction)

        # In the old implementation, _drag_pill was stored on the instance.
        # In the new one, it should likely be cleaned up or invalid.
        # Check if _drag_pill exists and is visible (it shouldn't be)
        if (
            hasattr(unified_list.list_widget, "_drag_pill")
            and unified_list.list_widget._drag_pill
        ):
            assert not unified_list.list_widget._drag_pill.isVisible()
