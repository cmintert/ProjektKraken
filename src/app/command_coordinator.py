"""Command Coordinator.

Handles command execution, undo/redo stack management, and communication with the
database worker thread.
"""

import logging
from typing import TYPE_CHECKING, Dict, List, Optional, cast

from PySide6.QtCore import QObject, Signal, Slot

if TYPE_CHECKING:
    from src.commands.base_command import BaseCommand, CommandResult
    from src.core.protocols import MainWindowProtocol

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
    clear_persistent_history_requested = Signal()
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
        self._undo_redo_in_progress = False
        self._pending_history_action: Optional[tuple[str, "BaseCommand"]] = None
        self._pending_commands: Dict[str, "BaseCommand"] = {}
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

    @staticmethod
    def _serialize_command(command: "BaseCommand") -> dict[str, object]:
        """Create a worker-safe command intent without sharing a live object."""
        return {
            "type": command.__class__.__name__,
            "data": command.to_dict(),
            "base": command.base_state_dict(),
        }

    @staticmethod
    def _restore_command(
        payload: object,
        fallback: Optional["BaseCommand"] = None,
    ) -> Optional["BaseCommand"]:
        """Reconstruct canonical worker state on the Qt main thread."""
        if not isinstance(payload, dict):
            return fallback
        data = payload.get("data", {})
        base = payload.get("base", {})
        if not isinstance(data, dict) or not isinstance(base, dict):
            return fallback
        command_class = fallback.__class__ if fallback is not None else None
        if command_class is None:
            from src.commands.registry import get_command_types

            command_class = get_command_types().get(str(payload.get("type", "")))
        if command_class is None:
            return fallback
        try:
            command = command_class.from_dict(data)
            command.restore_base_state(base)
            return command
        except Exception:
            logger.exception(
                "Could not restore canonical command state for %s",
                payload.get("type", ""),
            )
            return fallback

    @Slot(list)
    def load_history_payloads(self, payloads: list[dict[str, object]]) -> None:
        """Rebuild the undo stack from worker-produced serializable payloads."""
        try:
            from src.commands.registry import get_command_types

            command_types = get_command_types()
            commands: List["BaseCommand"] = []
            for payload in payloads[-self.max_stack_size :]:
                command_type = str(payload.get("type", ""))
                command_class = command_types.get(command_type)
                if command_class is None:
                    logger.warning("Unknown persisted command type: %s", command_type)
                    continue
                data = payload.get("data", {})
                base = payload.get("base", {})
                if not isinstance(data, dict) or not isinstance(base, dict):
                    logger.warning(
                        "Invalid persisted command payload: %s",
                        command_type,
                    )
                    continue
                command = command_class.from_dict(data)
                command.restore_base_state(base)
                commands.append(command)
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
        self.track_command(command)
        self.command_requested.emit(self._serialize_command(command))

    @Slot(object)
    def track_command(self, command: "BaseCommand") -> None:
        """Retain a main-thread command by ID until its worker result arrives."""
        self._pending_commands[command.command_id] = command

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
        command = self.undo_stack[-1]
        self._pending_history_action = ("undo", command)
        logger.debug(f"Undoing command: {command.__class__.__name__}")
        self.undo_requested.emit(self._serialize_command(command))

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
        command = self.redo_stack[-1]
        self._pending_history_action = ("redo", command)
        logger.debug(f"Redoing command: {command.__class__.__name__}")
        self.redo_requested.emit(self._serialize_command(command))

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
        self._pending_commands.clear()
        self.clear_persistent_history_requested.emit()
        self._emit_history_changed()

    @Slot(object)
    def on_command_result(self, result: "CommandResult") -> None:
        """Handle command execution result from worker thread.

        This slot runs on the **main thread** (connected via
        ``QueuedConnection``).  It updates the in-memory undo/redo
        stacks, builds lightweight snapshots, emits
        ``history_changed(undo_snapshots, redo_snapshots)``. Persistent
        history is owned and updated by the database worker.

        Args:
            result: CommandResult object containing execution status.

        """
        is_undo_redo = result.command_name.startswith(
            (
                "Undo_",
                "Redo_",
            )
        )
        if is_undo_redo:
            self._undo_redo_in_progress = False
            pending = self._pending_history_action
            self._pending_history_action = None
            if result.success and pending is not None:
                action, pending_command = pending
                canonical = self._restore_command(
                    result.data.get("command_state"),
                    pending_command,
                )
                if canonical is None:
                    canonical = pending_command
                if action == "undo" and self.undo_stack[-1:] == [pending_command]:
                    self.undo_stack.pop()
                    self.redo_stack.append(canonical)
                elif action == "redo" and self.redo_stack[-1:] == [pending_command]:
                    self.redo_stack.pop()
                    self.undo_stack.append(canonical)
                self._emit_history_changed()
                self.log_stack_state()

        command_id = str(result.data.get("command_id", ""))
        tracked_command = (
            self._pending_commands.pop(command_id, None)
            if command_id and not is_undo_redo
            else None
        )

        if result.success:
            logger.info(f"Command succeeded: {result.message}")

            # Add command to undo stack if it was successful
            # The command object should be in result.data
            command = self._restore_command(
                result.data.get("command_state"),
                tracked_command,
            )
            if command is None:
                legacy_command = result.data.get("command")
                if legacy_command is not None:
                    command = cast("BaseCommand", legacy_command)
            if (
                not is_undo_redo
                and command is not None
                and getattr(command, "is_undoable", True)
            ):
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

    def _refresh_after_command(self, result: "CommandResult") -> None:
        """Refresh UI data after successful command execution.

        Args:
            result: CommandResult object.

        """
        # Raster paint commands already return immutable patch effects that the
        # MapHandler applies directly to the active buffer.  Reloading all data
        # after every stroke is redundant and can make the timeline re-emit its
        # unchanged playhead.  A playhead event deliberately invalidates raster
        # edit targets, so that generic refresh used to stop Paint after each
        # successful stroke.
        if result.command_name in {
            "PaintRasterCommand",
            "StrokeRasterCommand",
        }:
            return

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
        from PySide6.QtWidgets import QMessageBox, QWidget

        QMessageBox.critical(
            cast(QWidget, self.window), "Command Error", f"Operation failed:\n{message}"
        )
