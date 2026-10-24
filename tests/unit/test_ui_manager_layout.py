"""Menu integration for the activity workspace coordinator and live panels."""

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QLabel, QMenuBar, QWidget

from src.app.ui_manager import UIManager
from src.gui.workspace import WorkspaceShell


@pytest.fixture
def mock_main_window():
    return MagicMock()


@pytest.fixture
def ui_manager(mock_main_window):
    return UIManager(mock_main_window)


def test_reset_delegates_to_confirmed_active_workspace(ui_manager, mock_main_window):
    ui_manager.reset_layout()
    mock_main_window.workspace_coordinator.manage.assert_called_once_with("reset")
    mock_main_window.workspace.reset_layout.assert_not_called()


def test_view_panels_menu_tracks_open_and_closed_panels(qtbot):
    shell = WorkspaceShell()
    qtbot.addWidget(shell)
    shell.register_panel("project", "Project", QLabel(), "left")
    shell.register_panel("event", "Event", QLabel(), "center")
    window = QWidget()
    qtbot.addWidget(window)
    window.workspace = shell
    manager = UIManager(window)
    menu_bar = QMenuBar()
    qtbot.addWidget(menu_bar)

    with (
        patch("src.gui.widgets.focus_writing.FocusWritingController"),
        patch.object(manager, "create_layouts_menu"),
    ):
        manager.create_view_menu(menu_bar)

    event_action = manager._panel_actions["event"]
    project_action = manager._panel_actions["project"]
    assert event_action.isChecked()
    assert project_action.isChecked()

    shell.close_panel("event")
    assert not event_action.isChecked()
    assert project_action.isChecked()

    event_action.trigger()
    assert event_action.isChecked()
    assert shell.is_panel_open("event")

    project_action.trigger()
    assert not project_action.isChecked()
    assert not shell.is_panel_open("project")


def test_settings_is_one_direct_action_without_alternative_menu_routes(
    ui_manager, qtbot, mock_main_window
):
    menu_bar = QMenuBar()
    qtbot.addWidget(menu_bar)
    ui_manager.create_file_menu(menu_bar)
    ui_manager.create_timeline_menu(menu_bar)
    ui_manager.create_settings_menu(menu_bar)
    settings = [action for action in menu_bar.actions() if action.text() == "Settings"]
    assert len(settings) == 1
    assert settings[0].menu() is None
    settings[0].trigger()
    mock_main_window.app_coordinator.settings.open_settings.assert_called_once_with()

    def labels(menu):
        result = []
        for action in menu.actions():
            result.append(action.text())
            if action.menu() is not None:
                result.extend(labels(action.menu()))
        return result

    menu_labels = labels(menu_bar)
    assert not any("Settings" in label for label in menu_labels if label != "Settings")
    assert "Configure Grouping..." not in menu_labels
    assert "Calendar Configuration..." not in menu_labels
    assert "Create Backup..." in menu_labels
    assert "Clear Grouping" in menu_labels
