import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLineEdit, QMainWindow, QTextEdit

from src.gui.widgets.unified_list import UnifiedListWidget


@pytest.fixture
def window(qtbot):
    win = QMainWindow()
    win.resize(800, 600)
    qtbot.addWidget(win)
    return win


@pytest.fixture
def setup_gui(window, qtbot):
    unified_list = UnifiedListWidget()
    text_edit = QTextEdit()
    line_edit = QLineEdit()

    window.setCentralWidget(unified_list)
    # Add other widgets to window layout? unified_list is central.
    # We can just create them as children or independent windows for focus test.
    # UnifiedListWidget actions require them to be in the window.
    # Actually, unified_list adds actions to itself. With WindowShortcut, they work if unified_list is in the active window.

    text_edit.setParent(window)
    text_edit.setGeometry(0, 0, 100, 100)
    text_edit.show()

    line_edit.setParent(window)
    line_edit.setGeometry(0, 110, 100, 30)
    line_edit.show()

    # Populate list so it is visible and focusable
    from src.core.entities import Entity

    dummy_entity = Entity(
        id="1", name="Test Entity", type="Character", description="Desc"
    )
    unified_list.set_data(events=[], entities=[dummy_entity])

    window.show()
    qtbot.waitForWindowShown(window)

    return unified_list, text_edit, line_edit


def test_create_blocked_when_text_focused(setup_gui, qtbot):
    """Test that Create shortcuts are blocked when text input is focused."""
    unified_list, text_edit, line_edit = setup_gui

    # Spy on the signal
    with qtbot.waitSignal(
        unified_list.create_entity_requested, timeout=1000, raising=False
    ) as blocker:
        # Focus text edit
        text_edit.setFocus()
        qtbot.waitUntil(lambda: text_edit.hasFocus())

        # Trigger create entity trigger (simulating shortcut trigger)
        # Note: We can call the slot directly to test the logic, or simulate key press.
        # Calling slot _create_entity_trigger tests the _should_trigger_shortcut logic directly.
        unified_list._create_entity_trigger()

    # Verify signal NOT emitted
    assert not blocker.signal_triggered


def test_create_blocked_when_line_edit_focused(setup_gui, qtbot):
    """Test that Create shortcuts are blocked when QLineEdit is focused."""
    unified_list, text_edit, line_edit = setup_gui

    with qtbot.waitSignal(
        unified_list.create_event_requested, timeout=1000, raising=False
    ) as blocker:
        line_edit.setFocus()
        qtbot.waitUntil(lambda: line_edit.hasFocus())

        unified_list._create_event_trigger()

    assert not blocker.signal_triggered


def test_create_allowed_when_list_focused(setup_gui, qtbot):
    """Test that Create shortcuts work when list (non-text) is focused."""
    unified_list, text_edit, line_edit = setup_gui

    # Ensure window is active
    unified_list.window().activateWindow()
    unified_list.list_widget.setFocus()
    qtbot.waitUntil(lambda: unified_list.list_widget.hasFocus())

    with qtbot.waitSignal(unified_list.create_map_requested, timeout=2000) as blocker:
        unified_list._create_map_trigger()

    assert blocker.signal_triggered


def test_shortcut_context_is_window(setup_gui):
    """Verify actions are set to WindowShortcut."""
    unified_list, _, _ = setup_gui
    assert (
        unified_list.action_create_event.shortcutContext()
        == Qt.ShortcutContext.WindowShortcut
    )
    assert (
        unified_list.action_create_entity.shortcutContext()
        == Qt.ShortcutContext.WindowShortcut
    )
    assert (
        unified_list.action_create_map.shortcutContext()
        == Qt.ShortcutContext.WindowShortcut
    )
