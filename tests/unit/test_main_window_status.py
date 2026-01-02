from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QApplication

from src.app.main import MainWindow


@pytest.fixture
def main_window(qtbot):
    # Ensure app exists
    _ = QApplication.instance() or QApplication([])
    from unittest.mock import patch

    with (
        patch("src.app.main_window.DatabaseWorker") as MockWorker,
        patch("src.app.main_window.QTimer"),
        patch("src.app.main_window.QThread"),
    ):
        mock_worker = MockWorker.return_value
        mock_db = mock_worker.db_service
        # Default return for get_all_events to avoid iteration errors if used during init
        mock_db.get_all_events.return_value = []

        window = MainWindow()
        qtbot.addWidget(window)
        yield window


def test_status_bar_initialization(main_window):
    """Test that status bar labels are created with correct styling."""
    assert hasattr(main_window, "lbl_world_time")
    assert hasattr(main_window, "lbl_playhead_time")

    # Check Blue for World Time
    assert "#3498db" in main_window.lbl_world_time.styleSheet()

    # Check Red for Playhead Time
    assert "#e74c3c" in main_window.lbl_playhead_time.styleSheet()


def test_status_bar_updates(main_window):
    """Test that status bar labels update correctly."""

    # World Time
    main_window.update_world_time_label(123.45)
    assert "123.45" in main_window.lbl_world_time.text()
    assert "World:" in main_window.lbl_world_time.text()

    # Playhead Time
    main_window.update_playhead_time_label(678.90)
    assert "678.90" in main_window.lbl_playhead_time.text()
    assert "Playhead:" in main_window.lbl_playhead_time.text()


def test_status_bar_formatting_with_converter(main_window):
    """Test that labels use converter if available."""
    mock_converter = MagicMock()
    mock_converter.format_date.return_value = "Year 10"

    main_window.calendar_converter = mock_converter

    main_window.update_world_time_label(100.0)
    assert "Year 10" in main_window.lbl_world_time.text()

    mock_converter.format_date.assert_called_with(100.0)
