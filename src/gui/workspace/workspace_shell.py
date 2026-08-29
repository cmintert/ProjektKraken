"""Unified fixed-zone workspace shell."""

from __future__ import annotations

from typing import Any, cast

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QHBoxLayout,
    QSizePolicy,
    QSplitter,
    QToolBar,
    QWidget,
)

from src.gui.workspace.layout_state import normalize_layout
from src.gui.workspace.pane_container import PaneContainer
from src.gui.workspace.panel_registry import (
    ZONE_NAMES,
    PanelDefinition,
    PanelRegistry,
    ZoneName,
)

_HORIZONTAL_PANE_COUNT = 3


class WorkspaceShell(QWidget):
    """Own the activity bar, four fixed zones, and explicit workspace state."""

    layout_changed = Signal()
    zone_visibility_changed = Signal(str, bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create the fixed activity bar and splitter topology."""
        super().__init__(parent)
        self.setObjectName("WorkspaceShell")
        self.registry = PanelRegistry()
        self.panes: dict[ZoneName, PaneContainer] = {
            zone: PaneContainer(zone, self) for zone in ZONE_NAMES
        }
        self._last_nonzero_size: dict[ZoneName, int] = {
            "left": 270,
            "center": 800,
            "right": 340,
            "bottom": 210,
        }
        self._activity_actions: dict[str, QAction] = {}
        self._applying_layout = False
        self._drag_revealed_zones: set[ZoneName] = set()

        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.activity_bar = QToolBar("Activity Bar", self)
        self.activity_bar.setObjectName("ActivityBar")
        self.activity_bar.setMovable(False)
        self.activity_bar.setFloatable(False)
        self.activity_bar.setOrientation(Qt.Orientation.Vertical)
        self.activity_bar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.activity_bar.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Expanding,
        )
        root_layout.addWidget(self.activity_bar)

        self.horizontal_splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.horizontal_splitter.setObjectName("WorkspaceHorizontalSplitter")
        self.horizontal_splitter.addWidget(self.panes["left"])
        self.horizontal_splitter.addWidget(self.panes["center"])
        self.horizontal_splitter.addWidget(self.panes["right"])
        self.horizontal_splitter.setStretchFactor(0, 0)
        self.horizontal_splitter.setStretchFactor(1, 1)
        self.horizontal_splitter.setStretchFactor(2, 0)
        self.horizontal_splitter.setCollapsible(0, True)
        self.horizontal_splitter.setCollapsible(1, False)
        self.horizontal_splitter.setCollapsible(2, True)

        self.vertical_splitter = QSplitter(Qt.Orientation.Vertical, self)
        self.vertical_splitter.setObjectName("WorkspaceVerticalSplitter")
        self.vertical_splitter.addWidget(self.horizontal_splitter)
        self.vertical_splitter.addWidget(self.panes["bottom"])
        self.vertical_splitter.setStretchFactor(0, 1)
        self.vertical_splitter.setStretchFactor(1, 0)
        self.vertical_splitter.setCollapsible(0, False)
        self.vertical_splitter.setCollapsible(1, True)
        root_layout.addWidget(self.vertical_splitter, 1)

        for pane in self.panes.values():
            pane.panel_move_requested.connect(self.move_panel)
            pane.panel_drag_started.connect(self._begin_panel_drag)
            pane.panel_drag_finished.connect(self._finish_panel_drag)
        self.horizontal_splitter.splitterMoved.connect(self._remember_horizontal_sizes)
        self.vertical_splitter.splitterMoved.connect(self._remember_vertical_sizes)

    def register_panel(
        self,
        panel_id: str,
        title: str,
        widget: QWidget,
        default_zone: ZoneName,
        activity_id: str | None = None,
    ) -> None:
        """Register and place an existing feature widget."""
        definition = PanelDefinition(
            id=panel_id,
            title=title,
            widget=widget,
            default_zone=default_zone,
            activity_id=activity_id,
        )
        self.registry.register(definition)
        self.panes[default_zone].add_panel(panel_id, title, widget)
        if activity_id is not None:
            action = self.activity_bar.addAction(title)
            action.setObjectName(f"Activity_{activity_id}")
            action.setToolTip(f"Show {title}")
            action.triggered.connect(
                lambda _checked=False, target=panel_id: self.show_panel(target)
            )
            self._activity_actions[activity_id] = action

    def panel(self, panel_id: str) -> QWidget:
        """Return the registered feature widget."""
        return self.registry.panel(panel_id)

    def panel_ids(self) -> list[str]:
        """Return all registered panel IDs."""
        return self.registry.panel_ids()

    def panel_zone(self, panel_id: str) -> ZoneName:
        """Return the current zone for *panel_id*."""
        return self.registry.location(panel_id)

    def set_panel_title(self, panel_id: str, title: str) -> None:
        """Update the visible tab title wherever a panel currently lives."""
        zone = self.panel_zone(panel_id)
        if not self.panes[zone].set_panel_title(panel_id, title):
            raise RuntimeError(f"Panel missing from registered zone: {panel_id}")

    def show_panel(self, panel_id: str, *, focus: bool = False) -> None:
        """Reveal the panel's current zone and activate its tab."""
        zone = self.panel_zone(panel_id)
        self.show_zone(zone)
        self.panes[zone].activate_panel(panel_id)
        widget = self.panel(panel_id)
        widget.show()
        if focus:
            widget.setFocus(Qt.FocusReason.ShortcutFocusReason)

    def move_panel(self, panel_id: str, zone: str) -> None:
        """Move the same panel widget into one of the four fixed zones."""
        if zone not in ZONE_NAMES:
            raise ValueError(f"Unknown zone: {zone}")
        target_zone = cast(ZoneName, zone)
        source_zone = self.panel_zone(panel_id)
        if source_zone == target_zone:
            self.show_panel(panel_id)
            return

        widget = self.panes[source_zone].remove_panel(panel_id)
        if widget is None:
            raise RuntimeError(f"Panel missing from registered zone: {panel_id}")
        definition = self.registry.definition(panel_id)
        target_was_drag_revealed = target_zone in self._drag_revealed_zones
        self._drag_revealed_zones.discard(target_zone)
        self.show_zone(target_zone)
        if target_was_drag_revealed:
            self.zone_visibility_changed.emit(target_zone, True)
        self.panes[target_zone].add_panel(panel_id, definition.title, widget)
        self.registry.set_location(panel_id, target_zone)
        self.panes[target_zone].activate_panel(panel_id)

        if source_zone != "center" and not self.panes[source_zone].panel_ids():
            self.hide_zone(source_zone)
        self.layout_changed.emit()

    def _begin_panel_drag(self, _panel_id: str) -> None:
        """Temporarily expose every hidden peripheral zone as a drop target."""
        self._drag_revealed_zones.clear()
        for zone in ZONE_NAMES:
            pane = self.panes[zone]
            pane.set_drag_target_active(True)
            if zone != "center" and pane.isHidden():
                self._drag_revealed_zones.add(zone)
                pane.show()
                self._restore_zone_size(zone)

    def _finish_panel_drag(self) -> None:
        """Restore transient zones that were not chosen as the drop target."""
        for zone, pane in self.panes.items():
            pane.set_drag_target_active(False)
            if zone in self._drag_revealed_zones:
                pane.hide()
        self._drag_revealed_zones.clear()

    def hide_zone(self, zone: ZoneName) -> None:
        """Hide a peripheral zone while remembering its useful size."""
        if zone == "center":
            return
        pane = self.panes[zone]
        if pane.isHidden():
            return
        size = self._current_zone_size(zone)
        if size > 0:
            self._last_nonzero_size[zone] = size
        pane.hide()
        self.zone_visibility_changed.emit(zone, False)
        if not self._applying_layout:
            self.layout_changed.emit()

    def show_zone(self, zone: ZoneName) -> None:
        """Reveal a zone and restore its last useful splitter size."""
        pane = self.panes[zone]
        if zone == "center":
            pane.show()
            return
        was_hidden = pane.isHidden()
        pane.show()
        if was_hidden:
            self._restore_zone_size(zone)
            self.zone_visibility_changed.emit(zone, True)
            if not self._applying_layout:
                self.layout_changed.emit()

    def toggle_zone(self, zone: ZoneName) -> None:
        """Toggle a peripheral zone; Center always remains visible."""
        if zone == "center":
            self.show_zone(zone)
        elif self.panes[zone].isHidden():
            self.show_zone(zone)
        else:
            self.hide_zone(zone)

    def active_panel(self, zone: ZoneName) -> str | None:
        """Return the active panel ID for a zone."""
        return self.panes[zone].current_panel_id()

    def apply_layout(self, layout: object) -> dict[str, Any]:
        """Normalize and apply explicit workspace state."""
        normalized = normalize_layout(layout, self.registry)
        zones = normalized["zones"]
        self._applying_layout = True
        try:
            for pane in self.panes.values():
                for panel_id in list(pane.panel_ids()):
                    pane.remove_panel(panel_id)

            for zone in ZONE_NAMES:
                zone_data = zones[zone]
                for panel_id in zone_data["panels"]:
                    definition = self.registry.definition(panel_id)
                    self.panes[zone].add_panel(
                        panel_id, definition.title, definition.widget
                    )
                    self.registry.set_location(panel_id, zone)
                active = zone_data["active"]
                if isinstance(active, str):
                    self.panes[zone].activate_panel(active)
                self._last_nonzero_size[zone] = int(zone_data["size"])

            for zone in ZONE_NAMES:
                visible = bool(zones[zone]["visible"])
                self.panes[zone].setVisible(visible or zone == "center")

            self.horizontal_splitter.setSizes(
                [
                    int(zones["left"]["size"])
                    if zones["left"]["visible"]
                    else 0,
                    int(zones["center"]["size"]),
                    int(zones["right"]["size"])
                    if zones["right"]["visible"]
                    else 0,
                ]
            )
            bottom_size = (
                int(zones["bottom"]["size"])
                if zones["bottom"]["visible"]
                else 0
            )
            top_size = max(100, self.height() - bottom_size)
            self.vertical_splitter.setSizes([top_size, bottom_size])
        finally:
            self._applying_layout = False
        self.layout_changed.emit()
        return normalized

    def capture_layout(self) -> dict[str, Any]:
        """Capture explicit, machine-independent workspace state."""
        from src.gui.workspace.layout_state import WORKSPACE_LAYOUT_VERSION

        zones: dict[str, dict[str, object]] = {}
        for zone in ZONE_NAMES:
            pane = self.panes[zone]
            zones[zone] = {
                "visible": not pane.isHidden() if zone != "center" else True,
                "size": self._captured_zone_size(zone),
                "panels": pane.panel_ids(),
                "active": pane.current_panel_id(),
            }
        return {"layout_version": WORKSPACE_LAYOUT_VERSION, "zones": zones}

    def reset_layout(self) -> None:
        """Restore deterministic factory panel placement and zone geometry."""
        from src.gui.workspace.layout_state import DEFAULT_WORKSPACE_LAYOUT

        self.apply_layout(DEFAULT_WORKSPACE_LAYOUT)

    def zone_visible(self, zone: ZoneName) -> bool:
        """Return whether a zone is intentionally visible."""
        return zone == "center" or not self.panes[zone].isHidden()

    def _current_zone_size(self, zone: ZoneName) -> int:
        if zone == "bottom":
            sizes = self.vertical_splitter.sizes()
            return sizes[1] if len(sizes) > 1 else 0
        sizes = self.horizontal_splitter.sizes()
        index = {"left": 0, "center": 1, "right": 2}[zone]
        return sizes[index] if len(sizes) > index else 0

    def _captured_zone_size(self, zone: ZoneName) -> int:
        size = self._current_zone_size(zone)
        if size > 0:
            self._last_nonzero_size[zone] = size
        return self._last_nonzero_size[zone]

    def _restore_zone_size(self, zone: ZoneName) -> None:
        target = self._last_nonzero_size[zone]
        if zone == "bottom":
            sizes = self.vertical_splitter.sizes()
            total = sum(sizes) or max(self.height(), target + 100)
            self.vertical_splitter.setSizes([max(100, total - target), target])
            return

        sizes = self.horizontal_splitter.sizes()
        if len(sizes) != _HORIZONTAL_PANE_COUNT:
            sizes = [270, 800, 340]
        index = 0 if zone == "left" else 2
        sizes[index] = target
        sizes[1] = max(100, sizes[1] - target)
        self.horizontal_splitter.setSizes(sizes)

    def _remember_horizontal_sizes(self, *_args: int) -> None:
        if self._applying_layout:
            return
        sizes = self.horizontal_splitter.sizes()
        for zone, index in (("left", 0), ("center", 1), ("right", 2)):
            if len(sizes) > index and sizes[index] > 0:
                self._last_nonzero_size[cast(ZoneName, zone)] = sizes[index]
        self.layout_changed.emit()

    def _remember_vertical_sizes(self, *_args: int) -> None:
        if self._applying_layout:
            return
        sizes = self.vertical_splitter.sizes()
        if len(sizes) > 1 and sizes[1] > 0:
            self._last_nonzero_size["bottom"] = sizes[1]
        self.layout_changed.emit()
