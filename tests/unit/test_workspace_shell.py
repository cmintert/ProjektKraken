"""Tests for the fixed-zone workspace primitives."""

from __future__ import annotations

from PySide6.QtCore import QMimeData, QPointF, Qt
from PySide6.QtGui import QDropEvent
from PySide6.QtWidgets import QLabel

from src.gui.workspace import (
    DEFAULT_WORKSPACE_LAYOUT,
    PaneContainer,
    PanelDefinition,
    PanelRegistry,
    WorkspaceShell,
    normalize_layout,
)
from src.gui.workspace.pane_container import PANEL_MIME_TYPE


def _registry() -> PanelRegistry:
    registry = PanelRegistry()
    defaults = {
        "project": "left",
        "entity": "center",
        "event": "center",
        "map": "center",
        "timeline": "bottom",
        "graph": "center",
        "longform": "center",
        "analysis": "right",
        "ai_search": "right",
        "history": "bottom",
    }
    for panel_id, zone in defaults.items():
        registry.register(
            PanelDefinition(panel_id, panel_id.title(), QLabel(), zone)
        )
    return registry


def _shell(qtbot) -> WorkspaceShell:
    shell = WorkspaceShell()
    qtbot.addWidget(shell)
    registry = _registry()
    for definition in registry.definitions():
        shell.register_panel(
            definition.id,
            definition.title,
            definition.widget,
            definition.default_zone,
        )
    shell.reset_layout()
    return shell


def test_workspace_has_exactly_four_generic_panes(qtbot) -> None:
    shell = _shell(qtbot)

    assert set(shell.panes) == {"left", "center", "right", "bottom"}
    assert all(isinstance(pane, PaneContainer) for pane in shell.panes.values())
    assert shell.vertical_splitter.widget(0) is shell.horizontal_splitter
    assert shell.vertical_splitter.widget(1) is shell.panes["bottom"]


def test_move_panel_reuses_widget_and_updates_registry(qtbot) -> None:
    shell = _shell(qtbot)
    widget = shell.panel("map")

    for zone in ("left", "right", "bottom", "center"):
        shell.move_panel("map", zone)
        assert shell.panel("map") is widget
        assert shell.panel_zone("map") == zone
        assert shell.panes[zone].contains_panel("map")
        assert shell.active_panel(zone) == "map"


def test_drop_tab_on_another_pane_moves_the_same_panel(qtbot) -> None:
    shell = _shell(qtbot)
    widget = shell.panel("map")
    mime_data = QMimeData()
    mime_data.setData(PANEL_MIME_TYPE, b"map")
    event = QDropEvent(
        QPointF(4, 4),
        Qt.DropAction.MoveAction,
        mime_data,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )

    shell.panes["right"].tabs.tabBar().dropEvent(event)

    assert event.isAccepted()
    assert shell.panel("map") is widget
    assert shell.panel_zone("map") == "right"
    assert shell.active_panel("right") == "map"


def test_empty_zone_becomes_temporary_drop_target(qtbot) -> None:
    shell = _shell(qtbot)
    shell.resize(1200, 800)
    shell.show()
    shell.move_panel("project", "center")
    assert shell.panes["left"].isHidden()

    shell._begin_panel_drag("map")
    qtbot.wait(1)

    assert not shell.panes["left"].isHidden()
    assert shell.panes["left"].empty_drop_hint.isVisible()
    assert shell.panes["left"].empty_drop_hint.width() > 0
    assert shell.panes["left"].empty_drop_hint.height() > 0

    shell._finish_panel_drag()

    assert shell.panes["left"].isHidden()


def test_drop_into_temporary_empty_zone_keeps_it_open(qtbot) -> None:
    shell = _shell(qtbot)
    widget = shell.panel("map")
    shell.move_panel("project", "center")
    shell._begin_panel_drag("map")
    mime_data = QMimeData()
    mime_data.setData(PANEL_MIME_TYPE, b"map")
    event = QDropEvent(
        QPointF(4, 4),
        Qt.DropAction.MoveAction,
        mime_data,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )

    shell.panes["left"].dropEvent(event)
    shell._finish_panel_drag()

    assert event.isAccepted()
    assert not shell.panes["left"].isHidden()
    assert shell.panel("map") is widget
    assert shell.panel_zone("map") == "left"
    assert shell.panes["left"].empty_drop_hint.isHidden()


def test_show_panel_reopens_hidden_zone(qtbot) -> None:
    shell = _shell(qtbot)
    shell.hide_zone("bottom")
    assert not shell.zone_visible("bottom")

    shell.show_panel("timeline")

    assert shell.zone_visible("bottom")
    assert shell.active_panel("bottom") == "timeline"


def test_empty_peripheral_zone_collapses_and_reopens_on_move(qtbot) -> None:
    shell = _shell(qtbot)
    shell.move_panel("project", "center")
    assert not shell.zone_visible("left")

    shell.move_panel("project", "left")

    assert shell.zone_visible("left")
    assert shell.panes["left"].panel_ids() == ["project"]


def test_capture_and_apply_layout_preserves_order_and_active_tabs(qtbot) -> None:
    shell = _shell(qtbot)
    shell.move_panel("graph", "left")
    shell.move_panel("longform", "bottom")
    shell.show_panel("graph")
    shell.show_panel("longform")
    captured = shell.capture_layout()

    shell.reset_layout()
    shell.apply_layout(captured)

    assert shell.panes["left"].panel_ids() == ["project", "graph"]
    assert shell.panes["bottom"].panel_ids() == [
        "timeline",
        "history",
        "longform",
    ]
    assert shell.active_panel("left") == "graph"
    assert shell.active_panel("bottom") == "longform"


def test_normalize_layout_repairs_unknown_duplicate_and_new_panels() -> None:
    registry = _registry()
    malformed = {
        "layout_version": 2,
        "zones": {
            "left": {
                "visible": True,
                "size": -50,
                "panels": ["project", "map", "unknown"],
                "active": "unknown",
            },
            "center": {
                "visible": False,
                "size": "bad",
                "panels": ["map", "entity"],
                "active": "map",
            },
            "invalid": {"panels": ["timeline"]},
        },
    }

    result = normalize_layout(malformed, registry)
    zones = result["zones"]
    all_panels = [
        panel_id
        for zone in ("left", "center", "right", "bottom")
        for panel_id in zones[zone]["panels"]
    ]

    assert len(all_panels) == len(set(all_panels)) == 10
    assert "unknown" not in all_panels
    assert zones["left"]["panels"] == ["project", "map"]
    assert zones["left"]["active"] == "project"
    assert zones["left"]["size"] >= 80
    assert zones["center"]["visible"] is True
    assert "timeline" in zones["bottom"]["panels"]


def test_incompatible_version_uses_factory_layout() -> None:
    registry = _registry()
    result = normalize_layout(
        {"layout_version": 999, "zones": {"left": {"panels": ["map"]}}},
        registry,
    )

    assert result["zones"]["left"]["panels"] == ["project"]
    assert result["zones"]["center"]["panels"] == DEFAULT_WORKSPACE_LAYOUT[
        "zones"
    ]["center"]["panels"]


def test_repeated_window_resize_keeps_center_available(qtbot) -> None:
    shell = _shell(qtbot)
    shell.show()

    for width, height in (
        (2560, 1440),
        (1024, 768),
        (1920, 1080),
        (1280, 720),
        (1366, 768),
        (1024, 768),
        (2560, 1440),
    ):
        shell.resize(width, height)
        qtbot.wait(1)
        assert shell.zone_visible("center")
        assert not shell.panes["center"].isHidden()
        assert shell.horizontal_splitter.handle(1).isEnabled()
        assert shell.vertical_splitter.handle(1).isEnabled()


def test_hidden_zone_restores_last_nonzero_size(qtbot) -> None:
    shell = _shell(qtbot)
    shell.resize(1600, 900)
    shell.show()
    shell.horizontal_splitter.setSizes([315, 900, 300])
    qtbot.wait(1)

    shell.hide_zone("left")
    shell.show_zone("left")
    qtbot.wait(1)

    assert shell.horizontal_splitter.sizes()[0] > 0
    assert shell._last_nonzero_size["left"] >= 300
