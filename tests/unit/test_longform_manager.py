"""Unit tests for LongformManager Obsidian vault export feedback."""

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication, QMessageBox

from src.app.longform_manager import LongformManager


class FakeMainWindow(QObject):
    """Minimal window dependency for LongformManager tests."""

    def __init__(self) -> None:
        super().__init__()
        self.status_bar = MagicMock()


@pytest.fixture
def qapp():
    """Provide a QApplication for the Qt-backed manager."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def fake_window(qapp):
    """Create the minimum window interface needed by the manager."""
    return FakeMainWindow()


@pytest.fixture
def manager(fake_window):
    """Create a LongformManager with its window dependency."""
    return LongformManager(fake_window)


@patch("src.app.longform_manager.AutoClosingMessageBox")
def test_successful_vault_export_shows_transient_result(
    mock_message_box, manager, fake_window
):
    """Successful vault exports should use the shared transient result modal."""
    manager.on_vault_export_finished(
        {
            "success": True,
            "files_created": 3,
            "output_dir": "C:/tmp/vault",
            "errors": [],
        }
    )

    message = "Exported 3 files to C:/tmp/vault"
    fake_window.status_bar.showMessage.assert_called_once_with(message, 5000)
    mock_message_box.assert_called_once_with(
        "Obsidian Export Complete",
        message,
        1500,
        QMessageBox.Icon.Information,
        parent=fake_window,
    )
    mock_message_box.return_value.exec.assert_called_once_with()


@patch("src.app.longform_manager.AutoClosingMessageBox")
def test_failed_vault_export_shows_transient_result(
    mock_message_box, manager, fake_window
):
    """Failed vault exports should show a concise transient error modal."""
    manager.on_vault_export_finished(
        {
            "success": False,
            "files_created": 0,
            "output_dir": "C:/tmp/vault",
            "errors": ["disk full", "permission denied"],
        }
    )

    fake_window.status_bar.showMessage.assert_called_once_with(
        "Export completed with errors: disk full; permission denied", 5000
    )
    mock_message_box.assert_called_once_with(
        "Obsidian Export Failed",
        "Vault export failed: disk full; permission denied",
        1500,
        QMessageBox.Icon.Critical,
        parent=fake_window,
    )
    mock_message_box.return_value.exec.assert_called_once_with()
