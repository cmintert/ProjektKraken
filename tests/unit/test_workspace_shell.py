"""Tests for the fixed-zone workspace primitives."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QMimeData, QPointF, Qt
from PySide6.QtGui import QColor, QDropEvent
from PySide6.QtWidgets import QApplication, QLabel

from src.core.theme_manager import ThemeManager
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


def test_workspace_splitter_sash_renders_rounded_theme_colors(qtbot) -> None:
    shell = _shell(qtbot)
    shell.resize(1200, 800)
    shell.show()
    qtbot.wait(1)
    handle = shell.horizontal_splitter.handle(1)
    center = handle.rect().center()
    theme = ThemeManager().get_theme()

    assert handle.width() == 4
    assert handle.grab().toImage().pixelColor(center) == QColor(theme["border"])

    QApplication.sendEvent(handle, QEvent(QEvent.Type.Enter))
    assert handle.grab().toImage().pixelColor(center) == QColor(theme["primary"])

    QApplication.sendEvent(handle, QEvent(QEvent.Type.Leave))
    assert handle.grab().toImage().pixelColor(center) == QColor(theme["border"])


def test_move_panel_reuses_widget_and_updates_registry(qtbot) -> None:
    shell = _shell(qtbot)
    widget = shell.panel("map")

    for zone in ("left", "right", "bottom", "center"):
        shell.move_panel("map", zone)
        assert shell.panel("map") is widget
        assert shell.panel_zone("map") == zone
        assert shell.panes[zone].contains_panel("map")
        assert shell.active_panel(zone) == "map"


def test_pane_corners_are_mirrored_over_content_after_resize(qapp, qtbot):
    """Opaque content and tab frames cannot change one corner's curvature."""
    previous_style = qapp.styleSheet()
    pane = PaneContainer("center")
    qtbot.addWidget(pane)
    content = QLabel("Content")
    content.setStyleSheet("background: magenta; border: 1px solid blue;")
    pane.add_panel("test", "Test", content)
    try:
        ThemeManager().apply_theme(
            qapp, Path("src/resources/main.qss").read_text(encoding="utf-8")
        )
        pane.show()
        for width, height in ((320, 180), (481, 243)):
            pane.resize(width, height)
            qapp.processEvents()
            rendered = pane.grab().toImage()
            w, h = rendered.width(), rendered.height()
            radius = int(9 * rendered.devicePixelRatio())
            for x in range(radius):
                for y in range(radius):
                    colors = [
                        rendered.pixelColor(px, py)
                        for px, py in (
                            (x, y), (w - 1 - x, y),
                            (x, h - 1 - y), (w - 1 - x, h - 1 - y),
                        )
                    ]
                    for channel in ("red", "green", "blue"):
                        values = [getattr(color, channel)() for color in colors]
                        # Compare like backgrounds: top tabs and bottom content
                        # deliberately differ and must not be painted over.
                        # Qt's curve rasterizer has small coverage differences
                        # between mirrored edges (under 2% per color channel).
                        assert abs(values[0] - values[1]) <= 5
                        assert abs(values[2] - values[3]) <= 5
            border = QColor(ThemeManager().get_theme()["border"])
            for x, y in ((w // 2, 0), (w // 2, h - 1),
                         (0, h // 2), (w - 1, h // 2)):
                assert rendered.pixelColor(x, y) == border
            inset = int(8 * rendered.devicePixelRatio())
            assert rendered.pixelColor(inset, h - 1 - inset) == QColor("magenta")
    finally:
        qapp.setStyleSheet(previous_style)


def test_workspace_tabs_clear_corners_when_overflowing(qapp, qtbot):
    """Qt reserves both corner areas even when many tabs need scroll buttons."""
    previous_style = qapp.styleSheet()
    pane = PaneContainer("center")
    qtbot.addWidget(pane)
    for index in range(8):
        pane.add_panel(str(index), f"Workspace panel {index}", QLabel())
    try:
        ThemeManager().apply_theme(
            qapp, Path("src/resources/main.qss").read_text(encoding="utf-8")
        )
        pane.show()
        for width in (160, 320, 900):
            pane.resize(width, 180)
            for selected in (0, 7):
                pane.tabs.setCurrentIndex(selected)
                qapp.processEvents()
                bar = pane.tabs.tabBar()
                assert bar.geometry().left() >= 9
                assert bar.mapTo(pane, bar.rect().topLeft()).y() >= 5
                assert bar.geometry().right() < pane.width() - 9
                assert pane.tabs.currentIndex() == selected
    finally:
        qapp.setStyleSheet(previous_style)


def test_outer_frame_encloses_activity_bar_and_tracks_theme(qapp, qtbot):
    """All four outer edges remain visible through theme changes and resize."""
    manager = ThemeManager()
    previous_theme = manager.current_theme_name
    previous_style = qapp.styleSheet()
    shell = _shell(qtbot)
    try:
        shell.show()
        for theme in ("light_mode", "dark_mode", "fantasy_mode"):
            manager.current_theme_name = theme
            manager.apply_theme(
                qapp, Path("src/resources/main.qss").read_text(encoding="utf-8")
            )
            manager.theme_changed.emit(manager.get_theme())
            for width, height in ((900, 640), (1200, 800)):
                shell.resize(width, height)
                qapp.processEvents()
                image = shell.grab().toImage()
                w, h = image.width(), image.height()
                border = QColor(manager.get_theme()["border"])
                for x, y in ((0, h // 2), (w - 1, h // 2),
                             (w // 2, 0), (w // 2, h - 1)):
                    assert image.pixelColor(x, y) == border
                assert shell.activity_bar.geometry().left() == 4
                for offset in range(4):
                    assert image.pixelColor(offset, h // 2) == border
                assert shell.horizontal_splitter.handleWidth() == 4
                assert shell.vertical_splitter.handleWidth() == 4
    finally:
        manager.current_theme_name = previous_theme
        manager.theme_changed.emit(manager.get_theme())
        qapp.setStyleSheet(previous_style)


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


def test_panel_activation_emits_for_tab_changes_and_reselection(qtbot) -> None:
    shell = _shell(qtbot)
    activated: list[str] = []
    shell.panel_activated.connect(activated.append)

    shell.show_panel("graph")
    shell.show_panel("graph")

    assert activated == ["graph", "graph"]


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
