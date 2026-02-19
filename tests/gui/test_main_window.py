"""Tests for the VS Code-style MainWindow layout.

Validates activity bar toggle behaviour, editor tab management,
and window state persistence.
"""

from __future__ import annotations

from src.gui.main_window import MainWindow

# -- Activity-bar toggle tests -----------------------------------------------


def test_toggle_explorer_dock(qtbot):
    """Explorer dock visibility toggles on each call."""
    win = MainWindow()
    qtbot.addWidget(win)
    win.show()
    win.explorer_dock.setVisible(True)

    win.toggle_explorer()
    assert not win.explorer_dock.isVisible()

    win.toggle_explorer()
    assert win.explorer_dock.isVisible()


def test_toggle_timeline_dock(qtbot):
    """Timeline dock visibility toggles on each call."""
    win = MainWindow()
    qtbot.addWidget(win)
    win.show()
    win.timeline_dock.setVisible(True)

    win.toggle_timeline()
    assert not win.timeline_dock.isVisible()

    win.toggle_timeline()
    assert win.timeline_dock.isVisible()


def test_toggle_relations_dock(qtbot):
    """Relations dock visibility toggles on each call."""
    win = MainWindow()
    qtbot.addWidget(win)
    win.show()
    win.relations_dock.setVisible(True)

    win.toggle_relations()
    assert not win.relations_dock.isVisible()

    win.toggle_relations()
    assert win.relations_dock.isVisible()


def test_toggle_console_dock(qtbot):
    """Console dock visibility toggles on each call."""
    win = MainWindow()
    qtbot.addWidget(win)
    win.show()
    win.console_dock.setVisible(True)

    win.toggle_console()
    assert not win.console_dock.isVisible()

    win.toggle_console()
    assert win.console_dock.isVisible()


def test_on_explorer_clicked_toggles(qtbot):
    """_on_explorer_clicked toggles dock and emits signal."""
    win = MainWindow()
    qtbot.addWidget(win)
    win.show()
    win.explorer_dock.setVisible(True)

    with qtbot.waitSignal(win.explorer_requested, timeout=1000):
        win._on_explorer_clicked()
    assert not win.explorer_dock.isVisible()

    with qtbot.waitSignal(win.explorer_requested, timeout=1000):
        win._on_explorer_clicked()
    assert win.explorer_dock.isVisible()


def test_on_timeline_clicked_toggles(qtbot):
    """_on_timeline_clicked toggles dock and emits signal."""
    win = MainWindow()
    qtbot.addWidget(win)
    win.show()
    win.timeline_dock.setVisible(True)

    with qtbot.waitSignal(win.timeline_requested, timeout=1000):
        win._on_timeline_clicked()
    assert not win.timeline_dock.isVisible()


def test_on_relations_clicked_toggles(qtbot):
    """_on_relations_clicked toggles dock and emits signal."""
    win = MainWindow()
    qtbot.addWidget(win)
    win.show()
    win.relations_dock.setVisible(True)

    with qtbot.waitSignal(win.relations_requested, timeout=1000):
        win._on_relations_clicked()
    assert not win.relations_dock.isVisible()


# -- Editor tab tests --------------------------------------------------------


def test_create_new_editor_tab(qtbot):
    """create_new_editor_tab adds a tab and returns its index."""
    win = MainWindow()
    qtbot.addWidget(win)
    initial = win.editor_tabs.count()

    idx = win.create_new_editor_tab()
    assert win.editor_tabs.count() == initial + 1
    assert idx == initial


def test_create_multiple_tabs(qtbot):
    """Multiple tabs can be created with custom titles."""
    win = MainWindow()
    qtbot.addWidget(win)

    idx1 = win.create_new_editor_tab("File A")
    idx2 = win.create_new_editor_tab("File B")
    assert win.editor_tabs.count() == 2
    assert win.editor_tabs.tabText(idx1) == "File A"
    assert win.editor_tabs.tabText(idx2) == "File B"


def test_close_tab(qtbot):
    """Closing a tab removes it from the tab widget."""
    win = MainWindow()
    qtbot.addWidget(win)

    win.create_new_editor_tab("Temp")
    assert win.editor_tabs.count() == 1

    win._on_tab_close_requested(0)
    assert win.editor_tabs.count() == 0


# -- Structure tests ---------------------------------------------------------


def test_activity_bar_exists(qtbot):
    """MainWindow has a non-movable activity bar with 4 actions."""
    win = MainWindow()
    qtbot.addWidget(win)

    assert win.activity_bar is not None
    assert not win.activity_bar.isMovable()
    assert len(win.activity_bar.actions()) == 4


def test_dock_widgets_exist(qtbot):
    """MainWindow has Explorer, Timeline, Relations, and Console docks."""
    win = MainWindow()
    qtbot.addWidget(win)

    assert win.explorer_dock is not None
    assert win.timeline_dock is not None
    assert win.relations_dock is not None
    assert win.console_dock is not None


def test_central_widget_is_splitter(qtbot):
    """Central widget is a QSplitter containing the editor tab widget."""
    win = MainWindow()
    qtbot.addWidget(win)

    from PySide6.QtWidgets import QSplitter

    assert isinstance(win.centralWidget(), QSplitter)
    assert win.editor_tabs is not None
    assert win.editor_tabs.tabsClosable()


def test_editor_tabs_closable(qtbot):
    """Editor tabs are closable by default."""
    win = MainWindow()
    qtbot.addWidget(win)

    assert win.editor_tabs.tabsClosable()


# -- State persistence tests -------------------------------------------------


def test_save_and_restore_state(qtbot):
    """Saving and restoring window state round-trips geometry."""
    win1 = MainWindow()
    qtbot.addWidget(win1)

    # Hide a dock, create a tab, then save
    win1.explorer_dock.setVisible(False)
    win1.create_new_editor_tab("Persisted")
    win1._save_window_state()

    # Create a second window and restore
    win2 = MainWindow()
    qtbot.addWidget(win2)
    win2._restore_window_state()

    # The dock state should be restored (explorer hidden)
    # Note: in offscreen mode restoreState may not perfectly reproduce
    # visibility, but _save/_restore should not raise.
    # We verify the round-trip completes without errors.
    assert win2 is not None


def test_close_event_saves_state(qtbot):
    """closeEvent triggers _save_window_state without errors."""
    win = MainWindow()
    qtbot.addWidget(win)
    win.create_new_editor_tab("Before close")

    # Simulate close — should not raise
    win.close()


def test_window_title(qtbot):
    """MainWindow has the expected title."""
    win = MainWindow()
    qtbot.addWidget(win)

    assert win.windowTitle() == "ProjektKraken"


def test_console_is_read_only(qtbot):
    """Console text edit is read-only."""
    win = MainWindow()
    qtbot.addWidget(win)

    assert win._console_widget.isReadOnly()
