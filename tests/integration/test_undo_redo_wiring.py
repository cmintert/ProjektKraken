"""
Integration tests for Undo/Redo signal wiring.

Verifies that the CommandCoordinator is correctly connected to the Worker
and that the UI actions respond to history changes.
"""

from unittest.mock import MagicMock, patch

from src.app.main_window import MainWindow
from src.commands.base_command import CommandResult

# Patches to prevent full UI/DB spinup
MAIN_WINDOW_PATCHES = [
    patch("src.app.worker_manager.DatabaseWorker"),
    patch("src.app.worker_manager.QThread"),
    # We allow QTimer to run so _complete_initialization fires
    # patch("src.app.main_window.QTimer"),
    patch("src.app.ui_manager.UIManager.create_timeline_menu"),
    patch("src.app.ui_manager.UIManager.create_settings_menu"),
    patch("src.app.ui_manager.UIManager.create_file_menu"),
    patch("src.app.ui_manager.UIManager.create_view_menu"),
    patch("src.app.ui_manager.UIManager.create_layouts_menu"),
    patch("src.app.ui_manager.UIManager.create_help_menu"),
]


def _start_patches():
    """Start all common patches."""
    for p in MAIN_WINDOW_PATCHES:
        p.start()


def _stop_patches():
    """Stop all common patches."""
    for p in MAIN_WINDOW_PATCHES:
        p.stop()


def test_undo_stack_populates_from_worker(qtbot):
    """Verify worker command_finished signal populates coordinator undo stack."""
    _start_patches()
    try:
        # 1. Initialize Window
        window = MainWindow()
        qtbot.addWidget(window)

        # We need to manually trigger completion or wait for timer
        # Since we didn't patch QTimer, it should fire.
        # But for determinism, let's call it directly if needed,
        # or wait using qtbot.

        # Wait for initialization to complete (Phase 3)
        # The QTimer is set to UI_INIT_DELAY_MS (usually small)
        qtbot.wait(200)

        # Ensure Phase 3 ran
        if not hasattr(window, "command_coordinator"):
            window._complete_initialization()

        coordinator = window.command_coordinator
        worker = window.worker

        # Verify initial state
        assert len(coordinator.undo_stack) == 0
        assert not coordinator.can_undo()

        # 2. Verify Wiring (Connection was made)
        # Since worker is a Mock, connect() is a method call we can verify
        # We use ANY for the connection type argument as it might be QueuedConnection
        from unittest.mock import ANY

        worker.command_finished.connect.assert_any_call(
            coordinator.on_command_result, ANY
        )

        # 3. Verify Logic (Simulate signal reception)
        # Create a dummy success result
        cmd_mock = MagicMock()
        cmd_mock.get_description.return_value = "Test Command"

        result = CommandResult(
            success=True,
            message="Command succeeded",
            command_name="TestCommand",
            data={"command": cmd_mock},
        )

        # Manually invoke the slot (since the signal connection is mocked)
        coordinator.on_command_result(result)

        # 4. Verify Coordinator updated
        assert len(coordinator.undo_stack) == 1
        assert coordinator.undo_stack[0] == cmd_mock
        assert coordinator.can_undo()

    finally:
        _stop_patches()


def test_undo_redo_actions_state(qtbot):
    """Verify UI actions update enabled state when history changes."""
    _start_patches()
    try:
        window = MainWindow()
        qtbot.addWidget(window)
        qtbot.wait(200)

        if not hasattr(window, "command_coordinator"):
            window._complete_initialization()

        ui_manager = window.ui_manager
        coordinator = window.command_coordinator

        # Verify actions exist
        assert hasattr(ui_manager, "undo_action")
        assert len(coordinator.undo_stack) == 0

        # Initial state should be disabled
        assert not ui_manager.undo_action.isEnabled()

        # Manually enable to test the signal (simulation)
        # Note: We can't easily check if the signal IS connected
        # without emitting and checking side effects.

        # Simulate history change
        cmd_mock = MagicMock()
        coordinator.undo_stack.append(cmd_mock)

        # Emit history_changed (coordinator does this internally usually)
        coordinator.history_changed.emit()

        # Check if UI updated
        assert ui_manager.undo_action.isEnabled()

        # Clear history
        coordinator.undo_stack.clear()
        coordinator.history_changed.emit()

        assert not ui_manager.undo_action.isEnabled()

    finally:
        _stop_patches()


def test_deferred_connection_logic(qtbot):
    """Verify connecting actions doesn't crash effectively."""
    _start_patches()
    try:
        window = MainWindow()
        qtbot.addWidget(window)

        # At this point (Phase 2), actions exist but are not connected to coordinator
        # merely because coordinator might not exist yet if timer hasn't fired.

        ui_manager = window.ui_manager
        assert hasattr(ui_manager, "undo_action")

        # Force complete init
        window._complete_initialization()

        # Now coordinator exists
        assert hasattr(window, "coordinator")

        # Verify no crash on re-connection or if we call it manually
        ui_manager.connect_undo_redo_actions()

        # All good if we got here
        assert True

    finally:
        _stop_patches()
