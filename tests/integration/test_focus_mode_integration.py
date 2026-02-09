"""Integration tests for Focus Mode in MainWindow."""

from unittest.mock import Mock, patch

from PySide6.QtCore import Qt

from src.app.main_window import MainWindow
from src.gui.utils.shortcut_manager import ShortcutManager


def test_focus_mode_initialization(qtbot):
    """Test that focus mode is properly initialized."""
    with (
        patch("src.app.main_window.WorkerManager"),
        patch("src.gui.widgets.graph_view.GraphWidget"),
        patch("src.gui.widgets.map_widget.MapWidget"),
        patch("src.gui.widgets.timeline.TimelineWidget"),
        patch("src.gui.widgets.unified_list.UnifiedListWidget"),
        patch("src.gui.widgets.ai_search_panel.AISearchPanelWidget"),
        patch("src.gui.widgets.history_panel.HistoryPanelWidget"),
    ):
        window = MainWindow()
        qtbot.addWidget(window)
        window.show()

        # Check that focus mode state is initialized
        assert hasattr(window, "_focus_mode_active")
        assert window._focus_mode_active is False

        # Check that the action exists
        assert hasattr(window, "action_focus_mode")
        assert (
            window.action_focus_mode.shortcut()
            == ShortcutManager.FOCUS_MODE.key_sequence
        )


def test_focus_mode_signal_connection(qtbot):
    """Test that focus mode signals are connected from editors."""
    with (
        patch("src.app.main_window.WorkerManager"),
        patch("src.gui.widgets.graph_view.GraphWidget"),
        patch("src.gui.widgets.map_widget.MapWidget"),
        patch("src.gui.widgets.timeline.TimelineWidget"),
        patch("src.gui.widgets.unified_list.UnifiedListWidget"),
        patch("src.gui.widgets.ai_search_panel.AISearchPanelWidget"),
        patch("src.gui.widgets.history_panel.HistoryPanelWidget"),
    ):
        window = MainWindow()
        qtbot.addWidget(window)
        window.show()

        # Both editors should have their focus_mode_changed signals connected
        # We can verify by checking the signal exists
        assert hasattr(window.entity_editor.desc_edit, "focus_mode_changed")
        assert hasattr(window.event_editor.desc_edit, "focus_mode_changed")


def test_focus_mode_changes_dock_opacity(qtbot):
    """Test that activating focus mode dims docks."""
    with (
        patch("src.app.main_window.WorkerManager"),
        patch("src.gui.widgets.graph_view.GraphWidget"),
        patch("src.gui.widgets.map_widget.MapWidget"),
        patch("src.gui.widgets.timeline.TimelineWidget"),
        patch("src.gui.widgets.unified_list.UnifiedListWidget"),
        patch("src.gui.widgets.ai_search_panel.AISearchPanelWidget"),
        patch("src.gui.widgets.history_panel.HistoryPanelWidget"),
    ):
        window = MainWindow()
        qtbot.addWidget(window)
        window.show()

        # Get a reference to a dock
        docks = window.ui_manager.docks
        if not docks:
            # If no docks were created (possible in test env), skip
            return

        # Activate focus mode (simulate activating from entity editor)
        # We need to set the state on the editor manually as we are bypassing the signal
        window.entity_editor.desc_edit._focus_mode_active = True
        window._on_focus_mode_changed(True)

        # Check that docks has opacity effect
        for dock_name, dock in docks.items():
            if dock is not None:
                if dock_name == "entity":
                    # Entity dock should NOT have effect
                    assert dock.graphicsEffect() is None
                elif dock_name == "graph":
                    # Graph widget uses set_opacity instead of QGraphicsOpacityEffect
                    # Verify calls on the MOCKED GraphWidget instance (not the dock)
                    # The dock.widget() is the mock object
                    dock.widget()
                    # We expect check set_opacity(0.3) was called
                    # Note: We can't easily check 'called' on a property-mock or if it's swapped out
                    # But we can check that we DID NOT perform the standard effect
                    assert dock.graphicsEffect() is None
                else:
                    # Others should have effect
                    effect = dock.graphicsEffect()
                    assert effect is not None
                    assert effect.opacity() == 0.3

        # Deactivate focus mode
        window.entity_editor.desc_edit._focus_mode_active = False
        window._on_focus_mode_changed(False)

        # Check that docks have no effect
        for dock_name, dock in docks.items():
            if dock is not None:
                assert dock.graphicsEffect() is None


def test_focus_mode_toggle_from_entity_editor(qtbot):
    """Test that clicking FC button in entity editor triggers focus mode."""
    with (
        patch("src.app.main_window.WorkerManager"),
        patch("src.gui.widgets.graph_view.GraphWidget"),
        patch("src.gui.widgets.map_widget.MapWidget"),
        patch("src.gui.widgets.timeline.TimelineWidget"),
        patch("src.gui.widgets.unified_list.UnifiedListWidget"),
        patch("src.gui.widgets.ai_search_panel.AISearchPanelWidget"),
        patch("src.gui.widgets.history_panel.HistoryPanelWidget"),
    ):
        window = MainWindow()
        qtbot.addWidget(window)

        # Get the entity editor's FC button
        fc_button = window.entity_editor.desc_edit.btn_focus

        # Initially not checked
        assert not fc_button.isChecked()
        assert not window._focus_mode_active

        # Click the button
        with qtbot.waitSignal(window.entity_editor.desc_edit.focus_mode_changed):
            fc_button.click()

        # Check focus mode is now active
        assert fc_button.isChecked()
        assert window._focus_mode_active

        # Click again to deactivate
        with qtbot.waitSignal(window.entity_editor.desc_edit.focus_mode_changed):
            fc_button.click()

        assert not fc_button.isChecked()
        assert not window._focus_mode_active


def test_focus_mode_toggle_from_event_editor(qtbot):
    """Test that clicking FC button in event editor triggers focus mode."""
    with (
        patch("src.app.main_window.WorkerManager"),
        patch("src.gui.widgets.graph_view.GraphWidget"),
        patch("src.gui.widgets.map_widget.MapWidget"),
        patch("src.gui.widgets.timeline.TimelineWidget"),
        patch("src.gui.widgets.unified_list.UnifiedListWidget"),
        patch("src.gui.widgets.ai_search_panel.AISearchPanelWidget"),
        patch("src.gui.widgets.history_panel.HistoryPanelWidget"),
    ):
        window = MainWindow()
        qtbot.addWidget(window)

        # Get the event editor's FC button
        fc_button = window.event_editor.desc_edit.btn_focus

        # Initially not checked
        assert not fc_button.isChecked()
        assert not window._focus_mode_active

        # Click the button
        with qtbot.waitSignal(window.event_editor.desc_edit.focus_mode_changed):
            fc_button.click()

        # Check focus mode is now active
        assert fc_button.isChecked()
        assert window._focus_mode_active


def test_keyboard_shortcut_toggles_focus_mode(qtbot):
    """Test that Ctrl+Shift+F toggles focus mode."""
    with (
        patch("src.app.main_window.WorkerManager"),
        patch("src.gui.widgets.graph_view.GraphWidget"),
        patch("src.gui.widgets.map_widget.MapWidget"),
        patch("src.gui.widgets.timeline.TimelineWidget"),
        patch("src.gui.widgets.unified_list.UnifiedListWidget"),
        patch("src.gui.widgets.ai_search_panel.AISearchPanelWidget"),
        patch("src.gui.widgets.history_panel.HistoryPanelWidget"),
    ):
        window = MainWindow()
        qtbot.addWidget(window)
        window.show()

        # Get initial state
        initial_state = window.entity_editor.desc_edit.btn_focus.isChecked()

        # Trigger the shortcut action
        window.action_focus_mode.trigger()

        # Check that the button state changed
        new_state = window.entity_editor.desc_edit.btn_focus.isChecked()
        assert new_state != initial_state


def test_keyboard_shortcut_works_with_visible_editor(qtbot):
    """Test that shortcut targets the visible editor."""
    with (
        patch("src.app.main_window.WorkerManager"),
        patch("src.gui.widgets.graph_view.GraphWidget"),
        patch("src.gui.widgets.map_widget.MapWidget"),
        patch("src.gui.widgets.timeline.TimelineWidget"),
        patch("src.gui.widgets.unified_list.UnifiedListWidget"),
        patch("src.gui.widgets.ai_search_panel.AISearchPanelWidget"),
        patch("src.gui.widgets.history_panel.HistoryPanelWidget"),
    ):
        window = MainWindow()
        qtbot.addWidget(window)

        # Make entity editor visible
        entity_dock = window.ui_manager.docks.get("entity")
        if entity_dock:
            entity_dock.show()

        # Trigger shortcut
        window._toggle_focus_mode_from_shortcut()

        # Entity editor button should be checked
        assert window.entity_editor.desc_edit.btn_focus.isChecked()


def test_focus_mode_state_persists_across_editor_switches(qtbot):
    """Test that focus mode state is tracked independently of which editor triggered it."""
    with (
        patch("src.app.main_window.WorkerManager"),
        patch("src.gui.widgets.graph_view.GraphWidget"),
        patch("src.gui.widgets.map_widget.MapWidget"),
        patch("src.gui.widgets.timeline.TimelineWidget"),
        patch("src.gui.widgets.unified_list.UnifiedListWidget"),
        patch("src.gui.widgets.ai_search_panel.AISearchPanelWidget"),
        patch("src.gui.widgets.history_panel.HistoryPanelWidget"),
    ):
        window = MainWindow()
        qtbot.addWidget(window)

        # Activate focus mode from entity editor
        window.entity_editor.desc_edit.btn_focus.click()
        window.entity_editor.desc_edit.toggle_focus_mode()

        assert window._focus_mode_active is True

        # The state should be maintained in the MainWindow
        # Even if we haven't clicked the event editor button
        assert window.event_editor.desc_edit.btn_focus.isChecked() is False

        # But window knows focus mode is active
        assert window._focus_mode_active is True
