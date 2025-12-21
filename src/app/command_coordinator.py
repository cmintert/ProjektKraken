"""
Command Coordinator.

Handles command execution, undo/redo stack management,
and communication with the database worker thread.
"""

import logging

from PySide6.QtCore import QObject, Signal, Slot

logger = logging.getLogger(__name__)


class CommandCoordinator(QObject):
    """
    Coordinates command execution and worker thread communication.
    
    Manages:
    - Command submission to worker thread
    - Result handling
    - Undo/redo operations (future enhancement)
    
    Attributes:
        command_requested: Signal emitted when a command needs execution.
    """

    # Signal to send commands to worker thread
    command_requested = Signal(object)

    def __init__(self, main_window):
        """
        Initialize the command coordinator.
        
        Args:
            main_window: Reference to the MainWindow instance.
        """
        super().__init__()
        self.window = main_window
        logger.debug("CommandCoordinator initialized")

    def execute_command(self, command):
        """
        Execute a command via the worker thread.
        
        Args:
            command: The command object to execute.
        """
        logger.debug(f"Executing command: {command.__class__.__name__}")
        self.command_requested.emit(command)

    @Slot(object)
    def on_command_result(self, result):
        """
        Handle command execution result from worker thread.
        
        Args:
            result: CommandResult object containing execution status.
        """
        if result.success:
            logger.info(f"Command succeeded: {result.message}")
            # Trigger data refresh based on command type
            self._refresh_after_command(result)
        else:
            logger.error(f"Command failed: {result.message}")
            self._show_error(result.message)

    def _refresh_after_command(self, result):
        """
        Refresh UI data after successful command execution.
        
        Args:
            result: CommandResult object.
        """
        # Determine what needs refreshing based on command type
        # This could be enhanced to be more specific per command
        if hasattr(self.window, 'load_data'):
            self.window.load_data()

    def _show_error(self, message: str):
        """
        Display error message to user.
        
        Args:
            message: Error message to display.
        """
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.critical(
            self.window,
            "Command Error",
            f"Operation failed:\n{message}"
        )
