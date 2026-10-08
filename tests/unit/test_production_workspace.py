"""Production-window architecture checks for the unified workspace shell."""

from unittest.mock import Mock, patch

import pytest
from PySide6.QtWidgets import QDockWidget

from src.app.main_window import MainWindow
from src.gui.workspace import WorkspaceShell


@pytest.fixture
def main_window(qtbot):
    with (
        patch("src.app.worker_manager.DatabaseWorker"),
        patch("src.app.worker_manager.QThread"),
        patch("src.app.main_window.QTimer"),
    ):
        window = MainWindow()
        qtbot.addWidget(window)
        yield window


def test_production_window_uses_visible_central_workspace(main_window) -> None:
    assert isinstance(main_window.centralWidget(), WorkspaceShell)
    assert main_window.centralWidget() is main_window.workspace
    assert not main_window.centralWidget().isHidden()
    assert main_window.findChildren(QDockWidget) == []


def test_production_window_registers_reused_feature_widgets(main_window) -> None:
    expected = {
        "project": main_window.unified_list,
        "entity": main_window.entity_editor,
        "event": main_window.event_editor,
        "map": main_window.map_widget,
        "timeline": main_window.timeline,
        "graph": main_window.graph_widget,
        "longform": main_window.longform_editor,
        "analysis": main_window.analysis_panel,
        "ai_search": main_window.ai_search_panel,
        "wiki_peek": main_window.wiki_peek_panel,
        "history": main_window.history_panel,
    }

    assert set(main_window.workspace.panel_ids()) == set(expected)
    for panel_id, widget in expected.items():
        assert main_window.workspace.panel(panel_id) is widget


def test_factory_layout_matches_workspace_contract(main_window) -> None:
    panes = main_window.workspace.panes
    assert panes["left"].panel_ids() == ["project"]
    assert panes["center"].panel_ids() == [
        "entity",
        "event",
        "map",
        "graph",
        "longform",
    ]
    assert panes["right"].panel_ids() == ["analysis", "ai_search", "wiki_peek"]
    assert panes["bottom"].panel_ids() == ["timeline", "history"]


@pytest.mark.parametrize("kind", ["entity", "event"])
def test_production_map_click_keeps_shared_workspace_active(
    main_window, qtbot, kind
) -> None:
    main_window.show()
    qtbot.waitExposed(main_window)
    main_window.workspace.show_panel("map")
    main_window.navigation_coordinator.selected_id = "prior"
    main_window.navigation_coordinator.selected_type = "entity"
    loader = Mock()
    setattr(main_window.data_coordinator, f"load_{kind}_details", loader)

    main_window.map_widget.view.marker_clicked.emit("target", kind)

    assert main_window.workspace.active_panel("center") == "map"
    assert main_window.navigation_coordinator.selected_id == "prior"
    loader.assert_not_called()


def test_activity_action_follows_moved_panel(main_window) -> None:
    main_window.workspace.move_panel("map", "right")

    main_window.workspace._activity_actions["map"].trigger()

    assert main_window.workspace.panel_zone("map") == "right"
    assert main_window.workspace.active_panel("right") == "map"


def test_reset_layout_preserves_outer_window_geometry(main_window) -> None:
    main_window.setGeometry(140, 110, 1110, 730)
    before = main_window.geometry()
    main_window.workspace.move_panel("timeline", "left")
    main_window.workspace.move_panel("project", "right")

    main_window.ui_manager.reset_layout()

    assert main_window.geometry() == before
    assert main_window.workspace.panel_zone("timeline") == "bottom"
    assert main_window.workspace.panel_zone("project") == "left"
