from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QObject

from src.app.command_coordinator import CommandCoordinator


class MockMainWindow(QObject):
    def __init__(self):
        super().__init__()
        self.load_data = MagicMock()


@pytest.fixture
def main_window():
    return MockMainWindow()


@pytest.fixture
def coordinator(main_window):
    return CommandCoordinator(main_window)


def test_initialization(coordinator, main_window):
    assert coordinator.window == main_window


def test_execute_command(coordinator):
    mock_command = MagicMock()
    mock_command.__class__.__name__ = "MockCommand"

    # Connect to the signal to verify emission
    signal_spy = MagicMock()
    coordinator.command_requested.connect(signal_spy)

    coordinator.execute_command(mock_command)

    signal_spy.assert_called_once_with(mock_command)


def test_on_command_result_success(coordinator, main_window):
    mock_result = MagicMock()
    mock_result.success = True
    mock_result.message = "Success"

    coordinator.on_command_result(mock_result)

    # Should trigger load_data on window
    main_window.load_data.assert_called_once()


@patch("PySide6.QtWidgets.QMessageBox")
def test_on_command_result_failure(mock_msg_box, coordinator, main_window):
    mock_result = MagicMock()
    mock_result.success = False
    mock_result.message = "Failed"

    coordinator.on_command_result(mock_result)

    # Should show error message
    mock_msg_box.critical.assert_called_once()
    args = mock_msg_box.critical.call_args[0]
    assert args[0] == main_window
    assert "Command Error" in args[1]
    assert "Failed" in args[2]

    # Should NOT trigger load_data
    main_window.load_data.assert_not_called()
