"""Command Coordinator.

Handles command execution, undo/redo stack management, and communication with the
database worker thread.
"""

import logging
from typing import TYPE_CHECKING, Dict, List, Optional

from PySide6.QtCore import QObject, QTimer, Signal, Slot

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
            Carries two lists of snapshot dicts (undo, redo) so that
            receivers never need to touch live command objects.

    """

    # Signals
    command_requested = Signal(object)
    undo_requested = Signal(object)  # Emits the command to undo
    redo_requested = Signal(object)  # Emits the command to redo
    history_changed = Signal(list, list)  # (undo_snapshots, redo_snapshots)

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
        self._undo_redo_in_progress = False
        logger.debug("CommandCoordinator initialized with undo/redo support")

    # ------------------------------------------------------------------
    # Snapshot helpers
    # ------------------------------------------------------------------

    def _snapshot_cmd(self, cmd: "BaseCommand") -> Dict[str, object]:
        """Create a lightweight, thread-safe snapshot dict from a command.

        The snapshot is a plain dict with only serialisable values so it
        can safely be passed across signal/slot boundaries without
        touching the live command object again.

        Args:
            cmd: The command to snapshot.

        Returns:
            Dict with ``description`` and ``timestamp`` keys.
        """
        try:
            desc = cmd.get_description()
        except Exception:
            desc = cmd.__class__.__name__
        return {
            "description": desc,
            "timestamp": getattr(cmd, "timestamp", None),
        }

    def _build_snapshots(self) -> tuple:
        """Build (undo_snapshots, redo_snapshots) from the current stacks.

        Returns:
            Tuple of two lists of snapshot dicts.
        """
        undo = [self._snapshot_cmd(c) for c in self.undo_stack]
        redo = [self._snapshot_cmd(c) for c in self.redo_stack]
        return undo, redo

    def _emit_history_changed(self) -> None:
        """Emit ``history_changed`` with pre-built snapshot lists.

        All callers should use this helper instead of emitting the signal
        directly so that snapshot creation and signal emission are atomic
        from the perspective of the main-thread event loop.
        """
        undo, redo = self._build_snapshots()
        self.history_changed.emit(undo, redo)

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
            self._emit_history_changed()
            logger.info(f"Loaded {len(commands)} commands from history")
            self.log_stack_state()
        except Exception as e:
            logger.error(f"Failed to load command history: {e}")

    def execute_command(self, command: "BaseCommand") -> None:
        """Execute a command via the worker thread.

        Args:
            command: The command object to execute.

        """
        logger.debug(f"Executing command: {command.__class__.__name__}")
        self.command_requested.emit(command)

    @Slot()
    def undo(self) -> None:
        """Undo the last executed command.

        Pops a command from the undo stack, requests its undo execution,
        and pushes it to the redo stack.

        Guarded: only one undo/redo can be in-flight at a time to
        prevent overlapping UI rebuilds that crash Qt.
        """
        if not self.can_undo():
            logger.warning("Undo called with empty undo stack")
            return

        if self._undo_redo_in_progress:
            logger.debug("Undo skipped — previous operation in progress")
            return

        self._undo_redo_in_progress = True
        command = self.undo_stack.pop()
        logger.debug(f"Undoing command: {command.__class__.__name__}")
        # Optimistically move to redo stack to keep UI responsive
        if command.has_history:
            self.redo_stack.append(command)

        # Build and emit snapshots BEFORE dispatching to worker, so the
        # history panel finishes reading command attributes before the
        # worker thread starts mutating them during undo.
        self._emit_history_changed()

        # Now dispatch to the worker thread (QueuedConnection)
        self.undo_requested.emit(command)

    @Slot()
    def redo(self) -> None:
        """Redo the last undone command.

        Pops a command from the redo stack, requests its re-execution,
        and pushes it to the undo stack.

        Guarded: only one undo/redo can be in-flight at a time.
        """
        if not self.can_redo():
            logger.warning("Redo called with empty redo stack")
            return

        if self._undo_redo_in_progress:
            logger.debug("Redo skipped — previous operation in progress")
            return

        self._undo_redo_in_progress = True
        command = self.redo_stack.pop()
        logger.debug(f"Redoing command: {command.__class__.__name__}")
        self.undo_stack.append(command)

        # Build and emit snapshots BEFORE dispatching to worker
        self._emit_history_changed()

        # Now dispatch to the worker thread (QueuedConnection)
        self.redo_requested.emit(command)

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

        self._emit_history_changed()

    @Slot(object)
    def on_command_result(self, result: "CommandResult") -> None:
        """Handle command execution result from worker thread.

        This slot runs on the **main thread** (connected via
        ``QueuedConnection``).  It updates the in-memory undo/redo
        stacks, builds lightweight snapshots, emits
        ``history_changed(undo_snapshots, redo_snapshots)``, and then
        defers database persistence to a ``QTimer.singleShot(0)`` so
        that the UI update completes before any blocking I/O.

        Args:
            result: CommandResult object containing execution status.

        """
        # Clear the undo/redo guard when the worker result arrives
        is_undo_redo = result.command_name.startswith(
            (
                "Undo_",
                "Redo_",
            )
        )
        if is_undo_redo:
            self._undo_redo_in_progress = False

        if result.success:
            logger.info(f"Command succeeded: {result.message}")

            # Add command to undo stack if it was successful
            # The command object should be in result.data
            command = result.data.get("command")
            if command is not None and getattr(command, "has_history", True):
                self.undo_stack.append(command)
                self.redo_stack.clear()  # Clear redo stack on new action

                # Limit stack size to prevent memory bloat
                if len(self.undo_stack) > self.max_stack_size:
                    removed = self.undo_stack.pop(0)
                    logger.debug(
                        f"Removed oldest command from stack: "
                        f"{removed.__class__.__name__}"
                    )

                # Emit snapshots for UI (fast, no I/O)
                self._emit_history_changed()
                self.log_stack_state()

                # Defer persistent DB save so the UI can finish
                # refreshing without blocking on SQLite I/O.
                if self.history_service:
                    # Capture a reference; the lambda closure is safe
                    # because the command object is in the undo stack.
                    svc = self.history_service
                    QTimer.singleShot(0, lambda: self._save_command_safe(svc, command))

            # Trigger data refresh based on command type.
            # Skip for Undo/Redo results — DataHandler already handles
            # those reloads via its own command_finished connection.
            is_undo_redo = result.command_name.startswith(
                (
                    "Undo_",
                    "Redo_",
                )
            )
            if not is_undo_redo:
                self._refresh_after_command(result)
        else:
            logger.error(f"Command failed: {result.message}")
            self._show_error(result.message)

    @staticmethod
    def _save_command_safe(
        history_service: "HistoryService", command: "BaseCommand"
    ) -> None:
        """Persist *command* to the history database, swallowing errors.

        Called from a deferred ``QTimer.singleShot(0)`` so that the UI
        refresh triggered by ``history_changed`` completes first.

        Args:
            history_service: The active HistoryService instance.
            command: The command to persist.
        """
        try:
            history_service.save_command(command)
        except Exception as e:
            logger.error(f"Failed to save command to history: {e}")

    def _refresh_after_command(self, result: "CommandResult") -> None:
        """Refresh UI data after successful command execution.

        Args:
            result: CommandResult object.

        """
        # Determine what needs refreshing based on command type
        # This could be enhanced to be more specific per command
        if hasattr(self.window, "data_coordinator"):
            self.window.data_coordinator.load_data()

    def log_stack_state(self) -> None:
        """Logs the current state of the undo/redo stacks."""
        logger.info(f"=== UNDO STACK ({len(self.undo_stack)} items) ===")
        for i, cmd in enumerate(reversed(self.undo_stack)):
            logger.info(f"  [{i}] {cmd.get_description()}")

        if self.redo_stack:
            logger.info(f"=== REDO STACK ({len(self.redo_stack)} items) ===")
            for i, cmd in enumerate(reversed(self.redo_stack)):
                logger.info(f"  [{i}] {cmd.get_description()}")
        else:
            logger.info("=== REDO STACK (Empty) ===")

    def _show_error(self, message: str) -> None:
        """Display error message to user.

        Args:
            message: Error message to display.

        """
        from PySide6.QtWidgets import QMessageBox

        QMessageBox.critical(
            self.window, "Command Error", f"Operation failed:\n{message}"
        )
