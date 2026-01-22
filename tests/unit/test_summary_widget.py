import time

import pytest
from PySide6.QtWidgets import QApplication

from src.core.summary_data import SummaryData
from src.gui.widgets.summary_widget import SummaryWidget


@pytest.fixture
def summary_widget(qtbot):
    widget = SummaryWidget()
    qtbot.addWidget(widget)
    widget.show()
    return widget


def test_initial_state_is_empty(summary_widget):
    assert summary_widget.text_display.toPlainText() == ""
    assert summary_widget.generate_btn.isEnabled()


def test_set_summary_updates_display(summary_widget):
    data = SummaryData(
        text="## Summary\nContent", hash="123", timestamp=time.time(), model="gpt-4"
    )
    summary_widget.set_summary(data)

    assert "Content" in summary_widget.text_display.toPlainText()
    assert "gpt-4" in summary_widget.metadata_label.text()


def test_set_stale_shows_warning(summary_widget):
    summary_widget.set_stale(True)
    assert summary_widget.stale_banner.isVisible()

    summary_widget.set_stale(False)
    assert not summary_widget.stale_banner.isVisible()


def test_generate_signal_emitted(summary_widget, qtbot):
    with qtbot.waitSignal(summary_widget.generate_requested, timeout=1000) as blocker:
        summary_widget.generate_btn.click()
    assert blocker.signal_triggered


def test_copy_button_copies_text(summary_widget, qtbot):
    data = SummaryData(
        text="Copy this", hash="123", timestamp=time.time(), model="gpt-4"
    )
    summary_widget.set_summary(data)

    # Mock clipboard or check functionality if possible.
    # For unit test without full GUI env, we might just check slot connection
    # or use QClipboard if available.
    clipboard = QApplication.clipboard()
    clipboard.clear()

    summary_widget.copy_btn.click()

    assert clipboard.text() == "Copy this"
