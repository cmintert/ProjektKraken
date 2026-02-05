"""Command Coordinator.

Handles command execution, undo/redo stack management, and communication with the
database worker thread.
"""

import logging
from typing import TYPE_CHECKING, List, Optional

from PySide6.QtCore import QObject, Signal, Slot

if TYPE_CHECKING:
    from src.commands.base_command import BaseCommand, CommandResult
    from src.core.protocols import MainWindowProtocol
    from src.services.history_service import HistoryService

logger = logging.getLogger(__name__)


class CommandCoordinator(QObject):
    """Coordinates command execution and worker thread communication.

    Manages:
    - Command submission to worker thread
    - Result handling
    - Undo/redo stack management
    - Command history persistence (Phase 2)

    Attributes:
        command_requested: Signal emitted when a command needs execution.
        undo_requested: Signal emitted when undo operation is requested.
        redo_requested: Signal emitted when redo operation is requested.
        history_changed: Signal emitted when undo/redo history changes.

    """

    # Signals
    command_requested = Signal(object)
    undo_requested = Signal(object)  # Emits the command to undo
    redo_requested = Signal(object)  # Emits the command to redo
    history_changed = Signal()  # For UI updates

    def __init__(self, main_window: "MainWindowProtocol") -> None:
        """Initialize the command coordinator.

        Args:
            main_window: Reference to the MainWindow instance.

        """
        super().__init__()
        self.window = main_window
        self.undo_stack: List["BaseCommand"] = []
        self.redo_stack: List["BaseCommand"] = []
        self.max_stack_size = 100  # Limit memory usage
        self.history_service: Optional["HistoryService"] = None
        logger.debug("CommandCoordinator initialized with undo/redo support")

    def set_history_service(self, history_service: "HistoryService") -> None:
        """Set the history service for persistent command storage.

        Args:
            history_service: HistoryService instance for this world
        """
        self.history_service = history_service
        logger.debug("HistoryService attached to CommandCoordinator")

    def load_history(self) -> None:
        """Load command history from database.

        Populates the undo stack with recent commands from previous sessions.
        """
        if not self.history_service:
            logger.warning("No history service available, skipping history load")
            return

        try:
            commands = self.history_service.load_recent_history(
                limit=self.max_stack_size
            )
            self.undo_stack = commands
            self.redo_stack.clear()
            self.history_changed.emit()
            logger.info(f"Loaded {len(commands)} commands from history")
        except Exception as e:
            logger.error(f"Failed to load command history: {e}")

    def execute_command(self, command: "BaseCommand") -> None:
        """Execute a command via the worker thread.

        Args:
            command: The command object to execute.

        """
        logger.debug(f"Executing command: {command.__class__.__name__}")
        self.command_requested.emit(command)

    def undo(self) -> None:
        """Undo the last executed command.

        Pops a command from the undo stack, requests its undo execution,
        and pushes it to the redo stack.
        """
        if not self.can_undo():
            logger.warning("Undo called with empty undo stack")
            return

        command = self.undo_stack.pop()
        logger.debug(f"Undoing command: {command.__class__.__name__}")
        self.undo_requested.emit(command)
        self.redo_stack.append(command)
        self.history_changed.emit()

    def redo(self) -> None:
        """Redo the last undone command.

        Pops a command from the redo stack, requests its re-execution,
        and pushes it to the undo stack.
        """
        if not self.can_redo():
            logger.warning("Redo called with empty redo stack")
            return

        command = self.redo_stack.pop()
        logger.debug(f"Redoing command: {command.__class__.__name__}")
        self.redo_requested.emit(command)
        self.undo_stack.append(command)
        self.history_changed.emit()

    def can_undo(self) -> bool:
        """Check if undo operation is available.

        Returns:
            bool: True if there are commands in the undo stack.

        """
        return len(self.undo_stack) > 0

    def can_redo(self) -> bool:
        """Check if redo operation is available.

        Returns:
            bool: True if there are commands in the redo stack.

        """
        return len(self.redo_stack) > 0

    def clear_history(self) -> None:
        """Clear all undo/redo history.

        Clears both in-memory stacks and persistent history in the database.
        Should be called when switching worlds to avoid cross-world undo.
        """
        logger.debug("Clearing undo/redo history")
        self.undo_stack.clear()
        self.redo_stack.clear()

        # Also clear persistent history from database
        if self.history_service:
            try:
                deleted_count = self.history_service.clear_all_history()
                logger.info(f"Cleared {deleted_count} commands from persistent history")
            except Exception as e:
                logger.error(f"Failed to clear persistent history: {e}")

        self.history_changed.emit()

    @Slot(object)
    def on_command_result(self, result: "CommandResult") -> None:
        """Handle command execution result from worker thread.

        Args:
            result: CommandResult object containing execution status.

        """
        if result.success:
            logger.info(f"Command succeeded: {result.message}")

            # Add command to undo stack if it was successful
            # The command object should be in result.data
            command = result.data.get("command")
            if command is not None:
                self.undo_stack.append(command)
                self.redo_stack.clear()  # Clear redo stack on new action

                # Save command to database for persistence (Phase 2)
                if self.history_service:
                    try:
                        self.history_service.save_command(command)
                    except Exception as e:
                        logger.error(f"Failed to save command to history: {e}")

                # Limit stack size to prevent memory bloat
                if len(self.undo_stack) > self.max_stack_size:
                    removed = self.undo_stack.pop(0)
                    logger.debug(
                        f"Removed oldest command from stack: {removed.__class__.__name__}"
                    )

                self.history_changed.emit()

            # Trigger data refresh based on command type
            self._refresh_after_command(result)
        else:
            logger.error(f"Command failed: {result.message}")
            self._show_error(result.message)

    def _refresh_after_command(self, result: "CommandResult") -> None:
        """Refresh UI data after successful command execution.

        Args:
            result: CommandResult object.

        """
        # Determine what needs refreshing based on command type
        # This could be enhanced to be more specific per command
        if hasattr(self.window, "load_data"):
            self.window.load_data()

    def _show_error(self, message: str) -> None:
        """Display error message to user.

        Args:
            message: Error message to display.

        """
        from PySide6.QtWidgets import QMessageBox

        QMessageBox.critical(
            self.window, "Command Error", f"Operation failed:\n{message}"
        )
