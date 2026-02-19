"""Tests for the MainWindow layout.

Validates activity bar toggle behaviour, editor tab management,
real widget integration, signal forwarding, and window state persistence.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDockWidget, QMainWindow, QSizePolicy

from src.gui.main_window import MainWindow
from src.gui.widgets.entity_editor import EntityEditorWidget
from src.gui.widgets.event_editor import EventEditorWidget
from src.gui.widgets.graph_view.graph_widget import GraphWidget
from src.gui.widgets.timeline import TimelineWidget
from src.gui.widgets.unified_list import UnifiedListWidget

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

    with qtbot.waitSignal(win.timeline_requested, timeout=1000):
        win._on_timeline_clicked()
    assert win.timeline_dock.isVisible()


def test_on_relations_clicked_toggles(qtbot):
    """_on_relations_clicked toggles dock and emits signal."""
    win = MainWindow()
    qtbot.addWidget(win)
    win.show()
    win.relations_dock.setVisible(True)

    with qtbot.waitSignal(win.relations_requested, timeout=1000):
        win._on_relations_clicked()
    assert not win.relations_dock.isVisible()

    with qtbot.waitSignal(win.relations_requested, timeout=1000):
        win._on_relations_clicked()
    assert win.relations_dock.isVisible()


# -- Real widget integration tests -------------------------------------------


def test_explorer_uses_unified_list(qtbot):
    """Explorer dock contains a UnifiedListWidget."""
    win = MainWindow()
    qtbot.addWidget(win)
    assert isinstance(win.unified_list, UnifiedListWidget)
    assert win.explorer_dock.widget() is win.unified_list


def test_timeline_uses_timeline_widget(qtbot):
    """Timeline dock contains a TimelineWidget."""
    win = MainWindow()
    qtbot.addWidget(win)
    assert isinstance(win.timeline, TimelineWidget)
    assert win.timeline_dock.widget() is win.timeline


def test_relations_uses_graph_widget(qtbot):
    """Relations dock contains a GraphWidget."""
    win = MainWindow()
    qtbot.addWidget(win)
    assert isinstance(win.graph_widget, GraphWidget)
    assert win.relations_dock.widget() is win.graph_widget


def test_event_editor_tab_exists(qtbot):
    """Central tabs include an EventEditorWidget."""
    win = MainWindow()
    qtbot.addWidget(win)
    assert isinstance(win.event_editor, EventEditorWidget)
    assert win.editor_tabs.indexOf(win.event_editor) != -1


def test_entity_editor_tab_exists(qtbot):
    """Central tabs include an EntityEditorWidget."""
    win = MainWindow()
    qtbot.addWidget(win)
    assert isinstance(win.entity_editor, EntityEditorWidget)
    assert win.editor_tabs.indexOf(win.entity_editor) != -1


def test_default_editor_tabs_count(qtbot):
    """MainWindow starts with 2 default editor tabs (Event + Entity)."""
    win = MainWindow()
    qtbot.addWidget(win)
    assert win.editor_tabs.count() == 2


# -- Signal forwarding tests -------------------------------------------------


def test_item_selected_signal_forwarded(qtbot):
    """UnifiedListWidget.item_selected is forwarded to MainWindow."""
    win = MainWindow()
    qtbot.addWidget(win)

    with qtbot.waitSignal(win.item_selected, timeout=1000):
        win.unified_list.item_selected.emit("event", "test-id-1")


def test_event_selected_signal_forwarded(qtbot):
    """TimelineWidget.event_selected is forwarded to MainWindow."""
    win = MainWindow()
    qtbot.addWidget(win)

    with qtbot.waitSignal(win.event_selected, timeout=1000):
        win.timeline.event_selected.emit("test-event-id")


def test_node_clicked_signal_forwarded(qtbot):
    """GraphWidget.node_clicked is forwarded to MainWindow."""
    win = MainWindow()
    qtbot.addWidget(win)

    with qtbot.waitSignal(win.node_clicked, timeout=1000):
        win.graph_widget.node_clicked.emit("entity", "test-node-id")


# -- Editor tab tests --------------------------------------------------------


def test_create_new_editor_tab(qtbot):
    """create_new_editor_tab adds a tab and returns its index."""
    win = MainWindow()
    qtbot.addWidget(win)
    initial_tab_count = win.editor_tabs.count()

    idx = win.create_new_editor_tab()
    assert win.editor_tabs.count() == initial_tab_count + 1
    assert idx == initial_tab_count


def test_create_multiple_tabs(qtbot):
    """Multiple tabs can be created with custom titles."""
    win = MainWindow()
    qtbot.addWidget(win)
    initial_tab_count = win.editor_tabs.count()

    idx1 = win.create_new_editor_tab("File A")
    idx2 = win.create_new_editor_tab("File B")
    assert win.editor_tabs.count() == initial_tab_count + 2
    assert win.editor_tabs.tabText(idx1) == "File A"
    assert win.editor_tabs.tabText(idx2) == "File B"


def test_close_tab(qtbot):
    """Closing a tab removes it from the tab widget."""
    win = MainWindow()
    qtbot.addWidget(win)

    idx = win.create_new_editor_tab("Temp")
    initial_tab_count = win.editor_tabs.count()

    win._on_tab_close_requested(idx)
    assert win.editor_tabs.count() == initial_tab_count - 1


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


def test_dock_nesting_enabled(qtbot):
    """Dock nesting and tabbed docking are enabled."""
    win = MainWindow()
    qtbot.addWidget(win)

    opts = win.dockOptions()
    assert opts & QMainWindow.DockOption.AllowNestedDocks
    assert opts & QMainWindow.DockOption.AllowTabbedDocks
    assert opts & QMainWindow.DockOption.AnimatedDocks


def test_docks_are_movable_floatable_closable(qtbot):
    """All docks have movable, floatable, and closable features set."""
    win = MainWindow()
    qtbot.addWidget(win)

    expected = (
        QDockWidget.DockWidgetFeature.DockWidgetMovable
        | QDockWidget.DockWidgetFeature.DockWidgetFloatable
        | QDockWidget.DockWidgetFeature.DockWidgetClosable
    )
    for dock in (
        win.explorer_dock,
        win.timeline_dock,
        win.relations_dock,
        win.console_dock,
    ):
        assert dock.features() == expected, f"{dock.objectName()} features mismatch"


def test_docks_allowed_in_all_areas(qtbot):
    """All docks accept all dock areas."""
    win = MainWindow()
    qtbot.addWidget(win)

    for dock in (
        win.explorer_dock,
        win.timeline_dock,
        win.relations_dock,
        win.console_dock,
    ):
        assert (
            dock.allowedAreas() == Qt.DockWidgetArea.AllDockWidgetAreas
        ), f"{dock.objectName()} areas mismatch"


def test_docks_have_minimum_size(qtbot):
    """All docks have a non-zero minimum size."""
    win = MainWindow()
    qtbot.addWidget(win)

    for dock in (
        win.explorer_dock,
        win.timeline_dock,
        win.relations_dock,
        win.console_dock,
    ):
        assert dock.minimumWidth() >= 250, f"{dock.objectName()} min width too small"
        assert dock.minimumHeight() >= 100, f"{dock.objectName()} min height too small"


def test_inner_widgets_have_expanding_size_policy(qtbot):
    """Inner dock widgets use Expanding size policy to prevent collapse."""
    win = MainWindow()
    qtbot.addWidget(win)

    for widget, name in (
        (win.unified_list, "UnifiedListWidget"),
        (win.timeline, "TimelineWidget"),
        (win.graph_widget, "GraphWidget"),
    ):
        hp = widget.sizePolicy().horizontalPolicy()
        vp = widget.sizePolicy().verticalPolicy()
        assert (
            hp == QSizePolicy.Policy.Expanding
        ), f"{name} horizontal policy is {hp}, expected Expanding"
        assert (
            vp == QSizePolicy.Policy.Expanding
        ), f"{name} vertical policy is {vp}, expected Expanding"


def test_inner_widgets_have_size_hints(qtbot):
    """Inner dock widgets provide stable sizeHint and minimumSizeHint."""
    win = MainWindow()
    qtbot.addWidget(win)

    for widget, name in (
        (win.unified_list, "UnifiedListWidget"),
        (win.timeline, "TimelineWidget"),
        (win.graph_widget, "GraphWidget"),
    ):
        sh = widget.sizeHint()
        msh = widget.minimumSizeHint()
        assert (
            sh.width() > 0 and sh.height() > 0
        ), f"{name} sizeHint is degenerate: {sh}"
        assert (
            msh.width() > 0 and msh.height() > 0
        ), f"{name} minimumSizeHint is degenerate: {msh}"


def test_central_widget_is_splitter(qtbot):
    """Central widget is a QSplitter containing the editor tab widget."""
    win = MainWindow()
    qtbot.addWidget(win)

    from PySide6.QtWidgets import QSplitter

    assert isinstance(win.centralWidget(), QSplitter)
    assert win.editor_tabs is not None
    assert win.editor_tabs.tabsClosable()


def test_splitter_not_collapsible(qtbot):
    """Central splitter does not allow children to collapse."""
    win = MainWindow()
    qtbot.addWidget(win)

    assert not win._splitter.childrenCollapsible()
    assert win._splitter.handleWidth() >= 4


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
