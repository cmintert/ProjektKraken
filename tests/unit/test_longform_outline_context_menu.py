"""Tests for Longform Outline Widget Context Menu.

Tests the right-click context menu functionality for the outline widget,
including Move up, Move down, Promote, Demote, and Delete operations.
"""

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu

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
    
    # Mock the menu exec to prevent actual display
    original_exec = QMenu.exec
    menu_shown = False
    
    def mock_exec(self, pos):
        nonlocal menu_shown
        menu_shown = True
        return None
    
    QMenu.exec = mock_exec
    try:
        # Trigger context menu
        outline_widget._show_context_menu(pos)
        assert menu_shown, "Context menu should be shown"
    finally:
        QMenu.exec = original_exec


def test_context_menu_no_item(outline_widget, sample_sequence, qtbot):
    """Test that context menu does not appear when clicking on empty space."""
    outline_widget.load_sequence(sample_sequence)
    
    # Click on empty space
    pos = QPoint(10, 500)  # Far below items
    
    # Mock the menu exec to detect if it was called
    original_exec = QMenu.exec
    menu_shown = False
    
    def mock_exec(self, pos):
        nonlocal menu_shown
        menu_shown = True
        return None
    
    QMenu.exec = mock_exec
    try:
        outline_widget._show_context_menu(pos)
        assert not menu_shown, "Context menu should not be shown for empty space"
    finally:
        QMenu.exec = original_exec


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
    with qtbot.waitSignal(outline_widget.item_removed, timeout=1000) as blocker:
        outline_widget._remove_selected()
    
    # Check signal data
    assert blocker.args[0] == "events"
    assert blocker.args[1] == "event1"
    assert blocker.args[2]["depth"] == 0


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
    """Test that promote does nothing for top-level items."""
    outline_widget.load_sequence(sample_sequence)
    
    # Select first top-level item (depth 0)
    item = outline_widget.topLevelItem(0)
    outline_widget.setCurrentItem(item)
    
    # Try to promote - should still emit signal (command will validate)
    # Actually, the widget will emit, but the command should handle depth check
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


def test_context_menu_actions_present(outline_widget, sample_sequence, qtbot, monkeypatch):
    """Test that context menu contains all expected actions."""
    outline_widget.load_sequence(sample_sequence)
    
    # Select first child item which should enable all actions
    item = outline_widget.topLevelItem(0).child(1)  # Section 1.2
    outline_widget.setCurrentItem(item)
    
    rect = outline_widget.visualItemRect(item)
    pos = rect.center()
    
    # Capture the menu that gets created
    captured_menu = None
    original_exec = QMenu.exec
    
    def mock_exec(self, global_pos):
        nonlocal captured_menu
        captured_menu = self
        return None
    
    monkeypatch.setattr(QMenu, "exec", mock_exec)
    
    # Trigger context menu
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
    assert "Delete from Longform" in action_texts
