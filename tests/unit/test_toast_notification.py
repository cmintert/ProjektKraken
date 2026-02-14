"""Tests for Toast Notification widget."""

import pytest
from PySide6.QtCore import QPoint
from src.gui.widgets.toast_notification import ToastNotification


@pytest.fixture
def toast(qtbot):
    """Create a basic toast notification."""
    widget = ToastNotification("Test message", duration_ms=1000, show_undo=False)
    qtbot.addWidget(widget)
    return widget


@pytest.fixture
def toast_with_undo(qtbot):
    """Create a toast notification with undo button."""
    widget = ToastNotification("Test message", duration_ms=1000, show_undo=True)
    qtbot.addWidget(widget)
    return widget


def test_toast_init(toast):
    """Test toast notification initializes correctly."""
    assert toast.message_label.text() == "Test message"
    assert toast.duration_ms == 1000
    assert toast.undo_button is None


def test_toast_with_undo_init(toast_with_undo):
    """Test toast with undo button initializes correctly."""
    assert toast_with_undo.undo_button is not None
    assert toast_with_undo.undo_button.text() == "Undo"


def test_toast_show_at_bottom_right(toast, qtbot):
    """Test toast appears at bottom-right corner."""
    toast.show_at_bottom_right()
    assert toast.isVisible()
    # Timer should be running
    assert toast.dismiss_timer.isActive()


def test_toast_auto_dismiss(toast, qtbot):
    """Test toast auto-dismisses after timeout."""
    toast.show_at_bottom_right()
    
    # Wait for auto-dismiss (1 second + buffer)
    with qtbot.waitSignal(toast.dismissed, timeout=2000):
        pass
    
    assert not toast.isVisible()


def test_toast_undo_clicked(toast_with_undo, qtbot):
    """Test undo button emits signal and dismisses toast."""
    toast_with_undo.show_at_bottom_right()
    
    with qtbot.waitSignal(toast_with_undo.undo_clicked, timeout=1000):
        toast_with_undo.undo_button.click()
    
    assert not toast_with_undo.isVisible()


def test_toast_manual_dismiss(toast, qtbot):
    """Test manually dismissing toast."""
    toast.show_at_bottom_right()
    
    with qtbot.waitSignal(toast.dismissed, timeout=1000):
        toast.dismiss()
    
    assert not toast.isVisible()
    assert not toast.dismiss_timer.isActive()


def test_toast_error_style(toast):
    """Test setting error style changes appearance."""
    toast.set_error_style()
    # Check that stylesheet contains error color
    assert "#E74C3C" in toast.styleSheet()


def test_toast_warning_style(toast):
    """Test setting warning style changes appearance."""
    toast.set_warning_style()
    # Check that stylesheet contains warning color
    assert "#FFB84D" in toast.styleSheet()


def test_toast_position_with_offset(toast, qtbot):
    """Test toast positioning with custom offset."""
    offset = QPoint(50, 50)
    toast.show_at_bottom_right(offset)
    
    # Toast should be visible
    assert toast.isVisible()
    # Position should be adjusted by offset
    # (exact position depends on screen size, so we just verify it doesn't crash)
