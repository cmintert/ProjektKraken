from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QDockWidget

from src.app.main import MainWindow


@pytest.fixture
def main_window(qtbot):
    with (
        patch("src.app.main_window.DatabaseWorker") as MockWorker,
        patch("src.app.main_window.QTimer"),
        patch("src.app.main_window.QThread"),
    ):
        mock_worker = MockWorker.return_value
        mock_db = mock_worker.db_service
        mock_db.get_all_events.return_value = []
        window = MainWindow()
        qtbot.addWidget(window)
        return window


def test_timeline_is_dockable(main_window):
    # Verify Timeline Dock existence
    assert hasattr(main_window, "timeline_dock")
    assert isinstance(main_window.timeline_dock, QDockWidget)
    assert main_window.timeline_dock.windowTitle() == "Timeline"

    # Verify Timeline Widget is inside the Dock
    assert main_window.timeline_dock.widget() == main_window.timeline

    # Verify Central Widget is NOT the timeline (it's a dummy or hidden)
    central = main_window.centralWidget()
    assert central != main_window.timeline
    # Optional: ensure central is hidden or empty
    # assert central.isHidden() or ...


def test_view_menu_includes_timeline(main_window):
    # Check View Menu actions
    menu_bar = main_window.menuBar()
    view_menu = None
    for action in menu_bar.actions():
        if action.text() == "View":
            view_menu = action.menu()
            break

    assert view_menu is not None

    # Find Timeline toggle action
    actions = view_menu.actions()
    timeline_action = None
    for act in actions:
        if "Timeline" in act.text():  # Action text usually matches Dock Title
            timeline_action = act
            break

    assert timeline_action is not None
    # Verify it controls the dock
    assert timeline_action == main_window.timeline_dock.toggleViewAction()


def test_dock_features_enabled(main_window):
    """Verify that all dock widgets have floating and moving enabled."""
    from PySide6.QtWidgets import QDockWidget

    docks = [main_window.list_dock, main_window.editor_dock, main_window.timeline_dock]

    for dock in docks:
        features = dock.features()
        assert features & QDockWidget.DockWidgetMovable, (
            f"{dock.objectName()} is not movable"
        )
        assert features & QDockWidget.DockWidgetFloatable, (
            f"{dock.objectName()} is not floatable"
        )
        assert features & QDockWidget.DockWidgetClosable, (
            f"{dock.objectName()} is not closable"
        )
