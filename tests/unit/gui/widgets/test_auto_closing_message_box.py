"""Tests for AutoClosingMessageBox."""

import pytest
from PySide6.QtWidgets import QMessageBox
from src.gui.widgets.auto_closing_message_box import AutoClosingMessageBox


@pytest.fixture
def auto_closing_box(qtbot):
    """Create a basic AutoClosingMessageBox."""
    widget = AutoClosingMessageBox("Test Title", "Test Message", timeout_ms=500)
    qtbot.addWidget(widget)
    return widget


def test_initialization(auto_closing_box):
    """Test standard initialization."""
    assert auto_closing_box.windowTitle() == "Test Title"
    assert auto_closing_box.text() == "Test Message"
    assert auto_closing_box._timeout_ms == 500


def test_auto_close(auto_closing_box, qtbot):
    """Test that the box closes automatically after timeout."""
    # We need to show the box to start the timer (showEvent)
    auto_closing_box.show()

    # Check that timer is active
    assert auto_closing_box.timer.isActive()

    # Wait for the timeout (plus a buffer)
    with qtbot.waitSignal(auto_closing_box.finished, timeout=1000):
        pass

    # Verify it finished (closed)
    assert not auto_closing_box.isVisible()
