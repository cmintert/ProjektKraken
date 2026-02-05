from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QObject

from src.app.command_coordinator import CommandCoordinator
from src.commands.base_command import BaseCommand, CommandResult
from src.services.db_service import DatabaseService


class MockCommand(BaseCommand):
    """Mock command for testing."""

    def __init__(self, name="MockCommand"):
        super().__init__()
        self.name = name
        self.executed_count = 0
        self.undone_count = 0

    def execute(self, db_service: DatabaseService):
        self.executed_count += 1
        self._is_executed = True
        return CommandResult(
            success=True,
            message=f"{self.name} executed",
            command_name=self.name,
            data={"command": self},
        )

    def undo(self, db_service: DatabaseService):
        self.undone_count += 1
        self._is_executed = False

    def get_description(self):
        return f"Mock: {self.name}"


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
    assert len(coordinator.undo_stack) == 0
    assert len(coordinator.redo_stack) == 0
    assert coordinator.max_stack_size == 100


def test_execute_command(coordinator):
    mock_command = MagicMock()
    mock_command.__class__.__name__ = "MockCommand"

    # Connect to the signal to verify emission
    signal_spy = MagicMock()
    coordinator.command_requested.connect(signal_spy)

    coordinator.execute_command(mock_command)

    signal_spy.assert_called_once_with(mock_command)


def test_on_command_result_success_adds_to_undo_stack(coordinator, main_window):
    """Test that successful command execution adds command to undo stack."""
    mock_command = MockCommand("TestCmd")
    mock_result = CommandResult(
        success=True,
        message="Success",
        command_name="TestCmd",
        data={"command": mock_command},
    )

    # Initially empty
    assert len(coordinator.undo_stack) == 0
    assert len(coordinator.redo_stack) == 0

    coordinator.on_command_result(mock_result)

    # Command should be in undo stack
    assert len(coordinator.undo_stack) == 1
    assert coordinator.undo_stack[0] == mock_command
    assert len(coordinator.redo_stack) == 0

    # Should trigger load_data on window
    main_window.load_data.assert_called_once()


def test_on_command_result_clears_redo_stack(coordinator, main_window):
    """Test that new command execution clears redo stack."""
    cmd1 = MockCommand("Cmd1")
    cmd2 = MockCommand("Cmd2")

    # Add cmd1 to redo stack manually
    coordinator.redo_stack.append(cmd1)

    # Execute cmd2
    result = CommandResult(
        success=True, message="Success", data={"command": cmd2}
    )
    coordinator.on_command_result(result)

    # Redo stack should be cleared
    assert len(coordinator.redo_stack) == 0
    assert len(coordinator.undo_stack) == 1


def test_stack_size_limit(coordinator, main_window):
    """Test that undo stack is limited to max_stack_size."""
    coordinator.max_stack_size = 3

    for i in range(5):
        cmd = MockCommand(f"Cmd{i}")
        result = CommandResult(
            success=True, message="Success", data={"command": cmd}
        )
        coordinator.on_command_result(result)

    # Should only keep last 3
    assert len(coordinator.undo_stack) == 3
    assert coordinator.undo_stack[0].name == "Cmd2"
    assert coordinator.undo_stack[1].name == "Cmd3"
    assert coordinator.undo_stack[2].name == "Cmd4"


def test_undo_moves_to_redo_stack(coordinator):
    """Test that undo pops from undo stack and pushes to redo stack."""
    cmd = MockCommand("TestUndo")
    coordinator.undo_stack.append(cmd)

    # Connect signal spy
    signal_spy = MagicMock()
    coordinator.undo_requested.connect(signal_spy)

    coordinator.undo()

    # Should move from undo to redo
    assert len(coordinator.undo_stack) == 0
    assert len(coordinator.redo_stack) == 1
    assert coordinator.redo_stack[0] == cmd

    # Should emit undo_requested signal
    signal_spy.assert_called_once_with(cmd)


def test_redo_moves_to_undo_stack(coordinator):
    """Test that redo pops from redo stack and pushes to undo stack."""
    cmd = MockCommand("TestRedo")
    coordinator.redo_stack.append(cmd)

    # Connect signal spy
    signal_spy = MagicMock()
    coordinator.redo_requested.connect(signal_spy)

    coordinator.redo()

    # Should move from redo to undo
    assert len(coordinator.redo_stack) == 0
    assert len(coordinator.undo_stack) == 1
    assert coordinator.undo_stack[0] == cmd

    # Should emit redo_requested signal
    signal_spy.assert_called_once_with(cmd)


def test_can_undo(coordinator):
    """Test can_undo returns correct state."""
    assert not coordinator.can_undo()

    cmd = MockCommand()
    coordinator.undo_stack.append(cmd)

    assert coordinator.can_undo()


def test_can_redo(coordinator):
    """Test can_redo returns correct state."""
    assert not coordinator.can_redo()

    cmd = MockCommand()
    coordinator.redo_stack.append(cmd)

    assert coordinator.can_redo()


def test_clear_history(coordinator):
    """Test clear_history empties both stacks."""
    coordinator.undo_stack.extend([MockCommand("1"), MockCommand("2")])
    coordinator.redo_stack.extend([MockCommand("3")])

    # Connect signal spy
    signal_spy = MagicMock()
    coordinator.history_changed.connect(signal_spy)

    coordinator.clear_history()

    assert len(coordinator.undo_stack) == 0
    assert len(coordinator.redo_stack) == 0
    signal_spy.assert_called_once()


def test_undo_on_empty_stack_does_nothing(coordinator):
    """Test that undo on empty stack doesn't crash."""
    assert not coordinator.can_undo()
    
    # Should not raise
    coordinator.undo()
    
    assert len(coordinator.undo_stack) == 0
    assert len(coordinator.redo_stack) == 0


def test_redo_on_empty_stack_does_nothing(coordinator):
    """Test that redo on empty stack doesn't crash."""
    assert not coordinator.can_redo()
    
    # Should not raise
    coordinator.redo()
    
    assert len(coordinator.undo_stack) == 0
    assert len(coordinator.redo_stack) == 0


def test_history_changed_signal_on_undo(coordinator):
    """Test that history_changed signal is emitted on undo."""
    cmd = MockCommand()
    coordinator.undo_stack.append(cmd)

    signal_spy = MagicMock()
    coordinator.history_changed.connect(signal_spy)

    coordinator.undo()

    signal_spy.assert_called_once()


def test_history_changed_signal_on_redo(coordinator):
    """Test that history_changed signal is emitted on redo."""
    cmd = MockCommand()
    coordinator.redo_stack.append(cmd)

    signal_spy = MagicMock()
    coordinator.history_changed.connect(signal_spy)

    coordinator.redo()

    signal_spy.assert_called_once()


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
    
    # Should NOT add to undo stack
    assert len(coordinator.undo_stack) == 0
