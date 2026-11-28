"""Command Coordinator.

Handles command execution, undo/redo stack management, and communication with the
database worker thread.
"""

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Dict, List, Optional, cast

from PySide6.QtCore import QObject, Signal, Slot

from src.app.command_feedback import present_deletion_feedback
from src.core.operation_trace import event as trace_event
from src.core.operation_trace import new_trace, safe_id

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
    command_preparing = Signal(object)  # Main-thread intent enrichment only
    graph_command_finished = Signal(object)

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
        self._history_epoch = 0
        self.mutations_suspended = False
        self.defer_command: Callable[["BaseCommand"], bool] | None = None
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

    def _serialize_command(
        self, command: "BaseCommand", action: str = "save"
    ) -> dict[str, object]:
        """Create a worker-safe command intent without sharing a live object."""
        world = getattr(self.window, "current_world", None)
        world_id = getattr(world, "id", "") if world is not None else ""
        payload: dict[str, object] = {
            "type": command.__class__.__name__,
            "data": command.to_dict(),
            "base": command.base_state_dict(),
        }
        trace = new_trace(command, action, str(world_id), self._history_epoch)
        payload["trace"] = trace
        trace_event(trace, "requested")
        return payload

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

    @Slot(object)
    def load_history_payloads(self, payloads: object) -> None:
        """Restore both ordered stacks, or expose no unsafe partial history."""
        from src.app.history_payloads import restore_stacks

        world = getattr(self.window, "current_world", None)
        if isinstance(payloads, dict) and payloads.get("world_id") is not None:
            if world is not None and payloads["world_id"] != world.id:
                return
        try:
            undo, redo = restore_stacks(payloads, self.max_stack_size)
        except Exception:
            logger.exception("Could not restore command history")
            undo, redo = [], []
        self.undo_stack, self.redo_stack = undo, redo
        self._emit_history_changed()

    def begin_exclusive_mutation(self) -> bool:
        """Reserve mutation dispatch after earlier commands have settled."""
        if (
            self.mutations_suspended
            or self._pending_commands
            or self._undo_redo_in_progress
        ):
            return False
        self.mutations_suspended = True
        return True

    def execute_command(self, command: "BaseCommand") -> None:
        """Execute a command via the worker thread.

        Args:
            command: The command object to execute.

        """
        if self.mutations_suspended:
            logger.warning("Command rejected during database shutdown")
            return
        if self.defer_command is not None and self.defer_command(command):
            return
        logger.debug(f"Executing command: {command.__class__.__name__}")
        self.command_preparing.emit(command)
        payload = self._serialize_command(command)
        self.track_command(command)
        self.command_requested.emit(payload)

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
        if self.mutations_suspended or not self.can_undo():
            logger.warning("Undo called with empty undo stack")
            return

        if self._undo_redo_in_progress or self._pending_commands:
            logger.debug("Undo skipped — previous operation in progress")
            return

        self._undo_redo_in_progress = True
        command = self.undo_stack[-1]
        self.command_preparing.emit(command)
        self._pending_history_action = ("undo", command)
        logger.debug(f"Undoing command: {command.__class__.__name__}")
        self.undo_requested.emit(self._serialize_command(command, "undo"))

    @Slot()
    def redo(self) -> None:
        """Redo the last undone command.

        Pops a command from the redo stack, requests its re-execution,
        and pushes it to the undo stack.

        Guarded: only one undo/redo can be in-flight at a time.
        """
        if self.mutations_suspended or not self.can_redo():
            logger.warning("Redo called with empty redo stack")
            return

        if self._undo_redo_in_progress or self._pending_commands:
            logger.debug("Redo skipped — previous operation in progress")
            return

        self._undo_redo_in_progress = True
        command = self.redo_stack[-1]
        self.command_preparing.emit(command)
        self._pending_history_action = ("redo", command)
        logger.debug(f"Redoing command: {command.__class__.__name__}")
        self.redo_requested.emit(self._serialize_command(command, "redo"))

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
        self._pending_history_action = None
        self._undo_redo_in_progress = False
        self._history_epoch += 1
        self.clear_persistent_history_requested.emit()
        self._emit_history_changed()

    def _accept_result_trace(self, result: "CommandResult") -> bool:
        """Reject results from an earlier history or world context."""
        trace = result.data.get("operation_trace")
        if not isinstance(trace, dict):
            return True
        if trace.get("epoch") != self._history_epoch:
            trace_event(trace, "discarded", reason="history_reset")
            return False
        world = getattr(self.window, "current_world", None)
        current_world_id = getattr(world, "id", "") if world is not None else ""
        if trace.get("world_id") != safe_id(current_world_id):
            trace_event(trace, "discarded", reason="world_changed")
            self._pending_commands.pop(str(trace.get("command_id", "")), None)
            if trace.get("action") in {"undo", "redo"}:
                self._pending_history_action = None
                self._undo_redo_in_progress = False
            return False
        trace_event(
            trace, "received", outcome="succeeded" if result.success else "failed"
        )
        return True

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
        if not self._accept_result_trace(result):
            return
        from src.core.command import is_graph_connection_result

        graph_result = is_graph_connection_result(result)
        is_undo_redo = result.command_name.startswith(
            (
                "Undo_",
                "Redo_",
            )
        )
        if is_undo_redo:
            self._apply_history_transition(result)

        command_id = str(result.data.get("command_id", ""))
        tracked_command = (
            self._pending_commands.pop(command_id, None)
            if command_id and not is_undo_redo
            else None
        )

        if result.success:
            logger.debug("Command result succeeded: %s", result.command_name)

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

            if graph_result:
                self.graph_command_finished.emit(result)
            else:
                present_deletion_feedback(result, self.window)

        else:
            if graph_result:
                self.graph_command_finished.emit(result)
                if not is_undo_redo:
                    return
            if not is_undo_redo and "temporal_dependencies" in result.data:
                from PySide6.QtWidgets import QWidget

                from src.app.coordinators.temporal_deletion import (
                    confirm_temporal_deletion,
                )

                retry = confirm_temporal_deletion(
                    result.data,
                    self.window if isinstance(self.window, QWidget) else None,
                )
                if retry is not None:
                    self.execute_command(retry)
                return
            logger.debug("Command result failed: %s", result.command_name)
            self._show_error(result.message)

    @Slot(object)
    def on_graph_preflight_failure(self, result: "CommandResult") -> None:
        """Return a timing preparation failure to its still-open graph draft."""
        from src.core.command import is_graph_connection_result

        if is_graph_connection_result(result):
            self.graph_command_finished.emit(result)

    def _apply_history_transition(self, result: "CommandResult") -> None:
        self._undo_redo_in_progress = False
        pending = self._pending_history_action
        self._pending_history_action = None
        if not result.success or pending is None:
            return
        action, pending_command = pending
        canonical = (
            self._restore_command(result.data.get("command_state"), pending_command)
            or pending_command
        )
        if action == "undo" and self.undo_stack[-1:] == [pending_command]:
            self.undo_stack.pop()
            self.redo_stack.append(canonical)
        elif action == "redo" and self.redo_stack[-1:] == [pending_command]:
            self.redo_stack.pop()
            self.undo_stack.append(canonical)
        self._emit_history_changed()
        self.log_stack_state()

    def log_stack_state(self) -> None:
        """Log a compact summary of the undo/redo stacks."""
        next_undo = self.undo_stack[-1].get_description() if self.undo_stack else "none"
        next_redo = self.redo_stack[-1].get_description() if self.redo_stack else "none"
        logger.debug(
            "Command stacks: undo=%d (next=%s), redo=%d (next=%s)",
            len(self.undo_stack),
            next_undo,
            len(self.redo_stack),
            next_redo,
        )

    def _show_error(self, message: str) -> None:
        """Display error message to user.

        Args:
            message: Error message to display.

        """
        from PySide6.QtWidgets import QMessageBox, QWidget

        QMessageBox.critical(
            cast(QWidget, self.window), "Command Error", f"Operation failed:\n{message}"
        )
