"""Tests for AutoClosingMessageBox."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import QWidget

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


def test_notifications_share_window_and_restart_timeout(qtbot):
    """Rapid completions replace one notice and remain nonmodal plain text."""
    parent = QWidget()
    child = QWidget(parent)
    qtbot.addWidget(parent)
    first = AutoClosingMessageBox.notify(child, "Deleted", "Deleted <b>authored</b>.")
    assert first.parent() is parent
    assert first.windowModality() == Qt.WindowModality.NonModal
    assert first.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
    assert first.textFormat() == Qt.TextFormat.PlainText
    first.timer.start(1)
    second = AutoClosingMessageBox.notify(parent, "Exported", "Exported file.")
    assert second is first
    assert second.text() == "Exported file."
    assert second.timer.interval() == 2500
    assert len(parent.findChildren(AutoClosingMessageBox)) == 1
    second.close()
    third = AutoClosingMessageBox.notify(child, "Created", "Relation created.")
    assert third is first
    assert third.timer.isActive()


def test_repeated_show_events_do_not_extend_timeout(auto_closing_box, qtbot):
    """Window presentation updates cannot keep the same notice alive forever."""
    auto_closing_box.show()
    qtbot.wait(200)
    remaining = auto_closing_box.timer.remainingTime()
    auto_closing_box.showEvent(QShowEvent())
    assert auto_closing_box.timer.remainingTime() <= remaining
    qtbot.waitUntil(lambda: not auto_closing_box.isVisible(), timeout=500)


def test_notify_arms_timer_even_without_show_event(qtbot, monkeypatch):
    """The public notification path owns expiry independent of platform events."""
    parent = QWidget()
    qtbot.addWidget(parent)
    monkeypatch.setattr(AutoClosingMessageBox, "showEvent", lambda self, event: None)
    popup = AutoClosingMessageBox.notify(parent, "Deleted", "Deleted item.")
    assert popup.isVisible()
    assert popup.timer.isActive()
    qtbot.waitUntil(lambda: not popup.isVisible(), timeout=3500)


def test_timeout_hides_even_if_dialog_accept_does_not(
    auto_closing_box, qtbot, monkeypatch
):
    """Expiry removes the window independently of QMessageBox acceptance."""
    monkeypatch.setattr(auto_closing_box, "accept", lambda: None)
    auto_closing_box.show()
    qtbot.waitUntil(lambda: not auto_closing_box.isVisible(), timeout=1000)
