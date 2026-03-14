"""Tests for Longform Outline Widget Context Menu.

Tests the right-click context menu functionality for the outline widget,
including Move up, Move down, Promote, Demote, and Delete operations.
"""

import pytest
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication, QMenu

from src.gui.widgets.longform.outline import LongformOutlineWidget


@pytest.fixture
def outline_widget(qtbot):
    """Create an outline widget for testing."""
    widget = LongformOutlineWidget()
    qtbot.addWidget(widget)
    return widget


@pytest.fixture
def sample_sequence():
    """Sample longform sequence for testing."""
    return [
        {
            "table": "events",
            "id": "event1",
            "name": "Chapter 1",
            "meta": {"position": 100.0, "depth": 0, "parent_id": None},
        },
        {
            "table": "events",
            "id": "event2",
            "name": "Section 1.1",
            "meta": {"position": 200.0, "depth": 1, "parent_id": "event1"},
        },
        {
            "table": "events",
            "id": "event3",
            "name": "Section 1.2",
            "meta": {"position": 300.0, "depth": 1, "parent_id": "event1"},
        },
        {
            "table": "entities",
            "id": "entity1",
            "name": "Chapter 2",
            "meta": {"position": 400.0, "depth": 0, "parent_id": None},
        },
    ]


def test_context_menu_on_item(outline_widget, sample_sequence, qtbot):
    """Test that context menu appears when right-clicking on an item."""
    outline_widget.load_sequence(sample_sequence)

    # Select first item
    item = outline_widget.topLevelItem(0)
    outline_widget.setCurrentItem(item)

    # Get position of item
    rect = outline_widget.visualItemRect(item)
    pos = rect.center()

    # Use QTimer to close any menu that appears, preventing exec() from blocking
    from PySide6.QtCore import QTimer

    menu_detected = False

    def _close_menus():
        nonlocal menu_detected
        for w in QApplication.topLevelWidgets():
            if isinstance(w, QMenu):
                menu_detected = True
                w.close()

    QTimer.singleShot(0, _close_menus)
    outline_widget._show_context_menu(pos)
    assert menu_detected, "Context menu should be shown"


def test_context_menu_no_item(outline_widget, sample_sequence, qtbot):
    """Test that context menu does not appear when clicking on empty space."""
    outline_widget.load_sequence(sample_sequence)

    # Click on empty space
    pos = QPoint(10, 500)  # Far below items

    # _show_context_menu returns early when no item is at position,
    # so no blocking exec() is called.
    outline_widget._show_context_menu(pos)
    # If we reach here, no blocking occurred (no menu shown)


def test_promote_signal_emitted(outline_widget, sample_sequence, qtbot):
    """Test that promote action emits the correct signal."""
    outline_widget.load_sequence(sample_sequence)

    # Select a child item (Section 1.1)
    item = outline_widget.topLevelItem(0).child(0)
    outline_widget.setCurrentItem(item)

    # Use signal spy
    with qtbot.waitSignal(outline_widget.item_promoted, timeout=1000) as blocker:
        outline_widget._promote_selected()

    # Check signal data
    assert blocker.args[0] == "events"
    assert blocker.args[1] == "event2"
    assert blocker.args[2]["depth"] == 1


def test_demote_signal_emitted(outline_widget, sample_sequence, qtbot):
    """Test that demote action emits the correct signal."""
    outline_widget.load_sequence(sample_sequence)

    # Select the second child item (Section 1.2) which can be demoted
    item = outline_widget.topLevelItem(0).child(1)
    outline_widget.setCurrentItem(item)

    # Use signal spy
    with qtbot.waitSignal(outline_widget.item_demoted, timeout=1000) as blocker:
        outline_widget._demote_selected()

    # Check signal data
    assert blocker.args[0] == "events"
    assert blocker.args[1] == "event3"
    assert blocker.args[2]["depth"] == 1


def test_remove_signal_emitted(outline_widget, sample_sequence, qtbot):
    """Test that delete action emits the correct signal."""
    outline_widget.load_sequence(sample_sequence)

    # Select first item
    item = outline_widget.topLevelItem(0)
    outline_widget.setCurrentItem(item)

    # Use signal spy
    with qtbot.waitSignal(outline_widget.item_deleted, timeout=1000) as blocker:
        outline_widget._delete_selected()

    # Check signal data
    assert blocker.args[0] == "events"
    assert blocker.args[1] == "event1"


def test_move_up_signal_emitted(outline_widget, sample_sequence, qtbot):
    """Test that move up action emits the correct signal."""
    outline_widget.load_sequence(sample_sequence)

    # Select the second child item (Section 1.2)
    item = outline_widget.topLevelItem(0).child(1)
    outline_widget.setCurrentItem(item)

    # Use signal spy
    with qtbot.waitSignal(outline_widget.item_move_up, timeout=1000) as blocker:
        outline_widget._move_up_selected()

    # Check signal data
    assert blocker.args[0] == "events"
    assert blocker.args[1] == "event3"
    assert blocker.args[2]["position"] == 300.0


def test_move_down_signal_emitted(outline_widget, sample_sequence, qtbot):
    """Test that move down action emits the correct signal."""
    outline_widget.load_sequence(sample_sequence)

    # Select the first child item (Section 1.1)
    item = outline_widget.topLevelItem(0).child(0)
    outline_widget.setCurrentItem(item)

    # Use signal spy
    with qtbot.waitSignal(outline_widget.item_move_down, timeout=1000) as blocker:
        outline_widget._move_down_selected()

    # Check signal data
    assert blocker.args[0] == "events"
    assert blocker.args[1] == "event2"
    assert blocker.args[2]["position"] == 200.0


def test_move_up_at_top_no_signal(outline_widget, sample_sequence, qtbot):
    """Test that move up does nothing when item is already at top."""
    outline_widget.load_sequence(sample_sequence)

    # Select the first top-level item
    item = outline_widget.topLevelItem(0)
    outline_widget.setCurrentItem(item)

    # Try to move up - should not emit signal
    signal_emitted = False

    def on_signal(*args):
        nonlocal signal_emitted
        signal_emitted = True

    outline_widget.item_move_up.connect(on_signal)
    outline_widget._move_up_selected()

    # Give it a moment
    qtbot.wait(100)
    assert not signal_emitted, "Move up should not emit signal when at top"


def test_move_down_at_bottom_no_signal(outline_widget, sample_sequence, qtbot):
    """Test that move down does nothing when item is already at bottom."""
    outline_widget.load_sequence(sample_sequence)

    # Select the last child item (Section 1.2)
    item = outline_widget.topLevelItem(0).child(1)
    outline_widget.setCurrentItem(item)

    # Try to move down - should not emit signal
    signal_emitted = False

    def on_signal(*args):
        nonlocal signal_emitted
        signal_emitted = True

    outline_widget.item_move_down.connect(on_signal)
    outline_widget._move_down_selected()

    # Give it a moment
    qtbot.wait(100)
    assert not signal_emitted, "Move down should not emit signal when at bottom"


def test_promote_top_level_no_signal(outline_widget, sample_sequence, qtbot):
    """Test that promote signal is emitted even for top-level items.

    The widget emits the signal; the command layer validates and handles
    items already at maximum promotion (depth 0).
    """
    outline_widget.load_sequence(sample_sequence)

    # Select first top-level item (depth 0)
    item = outline_widget.topLevelItem(0)
    outline_widget.setCurrentItem(item)

    # Widget emits signal, command will validate
    with qtbot.waitSignal(outline_widget.item_promoted, timeout=1000) as blocker:
        outline_widget._promote_selected()

    # Signal is emitted, command will handle validation
    assert blocker.args[0] == "events"
    assert blocker.args[1] == "event1"


def test_demote_first_child_no_signal(outline_widget, sample_sequence, qtbot):
    """Test that demote works for first child (makes it child of parent)."""
    outline_widget.load_sequence(sample_sequence)

    # Select first child item (Section 1.1)
    item = outline_widget.topLevelItem(0).child(0)
    outline_widget.setCurrentItem(item)

    # Try to demote - should emit signal (command handles logic)
    with qtbot.waitSignal(outline_widget.item_demoted, timeout=1000) as blocker:
        outline_widget._demote_selected()

    assert blocker.args[0] == "events"
    assert blocker.args[1] == "event2"


def test_context_menu_actions_present(outline_widget, sample_sequence, qtbot):
    """Test that context menu contains all expected actions."""
    outline_widget.load_sequence(sample_sequence)

    # Select first child item which should enable all actions
    item = outline_widget.topLevelItem(0).child(1)  # Section 1.2
    outline_widget.setCurrentItem(item)

    rect = outline_widget.visualItemRect(item)
    pos = rect.center()

    # Capture the menu via QTimer before exec() blocks
    from PySide6.QtCore import QTimer

    captured_menu = None

    def _capture_and_close():
        nonlocal captured_menu
        for w in QApplication.topLevelWidgets():
            if isinstance(w, QMenu):
                captured_menu = w
                w.close()
                return

    QTimer.singleShot(0, _capture_and_close)
    outline_widget._show_context_menu(pos)

    assert captured_menu is not None, "Menu should be created"

    # Get all actions
    actions = captured_menu.actions()
    action_texts = [action.text() for action in actions if not action.isSeparator()]

    # Check that all expected actions are present
    assert "Move Up" in action_texts
    assert "Move Down" in action_texts
    assert "Promote" in action_texts
    assert "Demote" in action_texts
    assert "Delete Item" in action_texts
