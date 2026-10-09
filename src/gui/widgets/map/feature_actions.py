"""Shared feature-action vocabulary and selection-aware map presentation.

This module consumes UI snapshots only. Mutations remain existing signal intents.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from PySide6.QtCore import QObject, QPoint
from PySide6.QtWidgets import QMenu
from shiboken6 import isValid

from src.core.marker_appearance import MarkerAppearance
from src.gui.widgets.map.feature_items import PathItem, RegionItem
from src.gui.widgets.map.marker_item import MarkerItem

if TYPE_CHECKING:
    from src.gui.widgets.map.map_graphics_view import MapGraphicsView
    from src.gui.widgets.map.map_layer_model import MapLayerModel
    from src.gui.widgets.map.map_layer_panel import MapLayerPanel

FeatureItem = MarkerItem | PathItem | RegionItem


@dataclass(frozen=True)
class FeatureTarget:
    """An explicit local selection, independent of the inspected object."""

    map_id: str | None
    object_id: str
    source: Literal["canvas", "layers"]
    revision: int


@dataclass(frozen=True)
class FeatureContext:
    """Current presentation capabilities, without a live scene-item reference."""

    kind: str
    locked: bool = False
    outside_date: bool = False
    canvas_available: bool = True
    is_event: bool = False
    raster_icon: bool = False
    has_journey: bool = False
    can_paste: bool = False
    can_reset_anchor: bool = False
    can_reset_size: bool = False


@dataclass(frozen=True)
class FeatureAction:
    """One existing intent and its visible availability explanation."""

    action_id: str
    label: str
    group: str = ""
    enabled: bool = True
    reason: str = ""


def feature_actions(context: FeatureContext) -> tuple[FeatureAction, ...]:
    """Describe the same supported operations for every feature entry point."""
    if context.locked:
        return (FeatureAction("unlock", "Unlock"),)
    common = [FeatureAction("lock", "Lock")]
    if context.outside_date:
        return tuple(
            common
            + [
                FeatureAction("jump", "Jump to valid time"),
                FeatureAction("validity", "Visibility dates…"),
                FeatureAction("layers", "Show in Layers"),
            ]
        )
    available = context.canvas_available
    reason = "Show this feature on the map to edit it" if not available else ""
    if context.kind in {"path", "region"}:
        part = "border" if context.kind == "region" else "path"
        history = "borders" if context.kind == "region" else "paths"
        primary = [
            FeatureAction(
                "geometry",
                f"Edit {part} at current date",
                enabled=available,
                reason=reason,
            ),
            FeatureAction(
                "style", "Edit appearance…", enabled=available, reason=reason
            ),
            FeatureAction(
                "history",
                f"Manage historical {history}…",
                enabled=available,
                reason=reason,
            ),
        ]
    else:
        primary = [
            FeatureAction(
                "appearance", "Edit appearance", enabled=available, reason=reason
            ),
            FeatureAction("icon", "Change icon…", enabled=available, reason=reason),
        ]
        if not context.is_event:
            label = "Edit journey" if context.has_journey else "Create journey"
            primary.append(
                FeatureAction("journey", label, enabled=available, reason=reason)
            )
        primary.extend(_appearance_actions(context))
    return tuple(
        primary
        + [FeatureAction("validity", "Visibility dates…")]
        + common
        + [
            FeatureAction(
                "delete", f"Delete {context.kind}", enabled=available, reason=reason
            ),
        ]
    )


def _appearance_actions(context: FeatureContext) -> list[FeatureAction]:
    """Keep expert appearance operations grouped and lossless."""
    availability = (
        ("copy", "Copy appearance", True, ""),
        ("paste", "Paste appearance", context.can_paste, "Copy an appearance first"),
        (
            "anchor",
            "Reset anchor to centre",
            context.can_reset_anchor,
            "The anchor is already centred",
        ),
        ("size", "Size & Zoom…", True, ""),
        (
            "reset_size",
            "Reset size to icon default",
            context.can_reset_size,
            "Choose a library icon first",
        ),
    )
    actions = [
        FeatureAction(
            key,
            label,
            "Advanced appearance",
            enabled and context.canvas_available,
            "Show this feature on the map to edit it"
            if not context.canvas_available
            else reason
            if not enabled
            else "",
        )
        for key, label, enabled, reason in availability
    ]
    vector_enabled = context.canvas_available and not context.raster_icon
    for key, label in (
        ("border", "Set border strength…"),
        ("fill", "Set fill color…"),
        ("border_color", "Set border color…"),
        ("no_fill", "No fill (transparent)"),
        ("no_border", "No border"),
    ):
        actions.append(
            FeatureAction(
                key,
                label,
                "Advanced appearance",
                vector_enabled,
                "Available for SVG and fallback markers only"
                if context.raster_icon
                else "Show this feature on the map to edit it"
                if not vector_enabled
                else "",
            )
        )
    return actions


def populate_feature_menu(
    menu: QMenu,
    actions: tuple[FeatureAction, ...],
    activate: Callable[[str], None],
) -> None:
    """Render descriptors without creating another command registry."""
    menu.clear()
    menu.setToolTipsVisible(True)
    groups: dict[str, QMenu] = {}
    for descriptor in actions:
        parent = menu
        if descriptor.group:
            if descriptor.group not in groups:
                groups[descriptor.group] = menu.addMenu(descriptor.group)
                groups[descriptor.group].setToolTipsVisible(True)
            parent = groups[descriptor.group]
        action = parent.addAction(descriptor.label)
        action.setData(descriptor.action_id)
        action.setEnabled(descriptor.enabled)
        action.setToolTip(descriptor.reason)
        action.setStatusTip(descriptor.reason)
        action.triggered.connect(
            lambda _checked=False, key=descriptor.action_id: activate(key)
        )


def item_context(item: FeatureItem, view: "MapGraphicsView") -> FeatureContext:
    """Project existing scene presentation into the shared capability vocabulary."""
    marker = isinstance(item, MarkerItem)
    kind = "marker" if marker else "path" if isinstance(item, PathItem) else "region"
    return FeatureContext(
        kind=kind,
        locked=item.is_locked,
        outside_date=item.is_temporal_ghost,
        canvas_available=item.isVisible(),
        is_event=item.object_type == "event",
        raster_icon=isinstance(item, MarkerItem) and item.is_raster_icon,
        has_journey=item.marker_id in view._trajectory_marker_ids,
        can_paste=view._interaction._copied_marker_appearance is not None,
        can_reset_anchor=isinstance(item, MarkerItem)
        and not MarkerAppearance.from_attributes(
            item._visual_attributes
        ).anchor.is_centered,
        can_reset_size=isinstance(item, MarkerItem)
        and view.marker_icon_catalog.resolve_attributes(item._visual_attributes)
        is not None,
    )


class FeatureActionPresenter(QObject):
    """Bind explicit local selection to existing UI handlers and signal intents."""

    def __init__(
        self,
        view: "MapGraphicsView",
        panel: "MapLayerPanel",
        get_map_id: Callable[[], str | None],
        transition: Callable[[str, Callable[[], None]], None],
        selection_updated: Callable[[], None],
    ) -> None:
        """Compose narrow UI dependencies; no services or persistence are owned."""
        super().__init__(view)
        self.view = view
        self.panel = panel
        self.get_map_id = get_map_id
        self.transition = transition
        self.selection_updated = selection_updated
        self.target: FeatureTarget | None = None
        self.revision = 0
        self.synchronizing = False
        self.refreshing_scene = False
        self.awaiting_scene = False
        self.ambiguous = False
        self._model: MapLayerModel | None = None
        panel.feature_menu_requested = self.show_layers_menu
        panel.feature_context_menu = self.show_layers_context_menu
        panel.capture_feature_guard = self.capture_guard
        view._interaction.feature_presenter = self
        panel.layer_selected.connect(self.layers_selected)
        view.graphics_scene.selectionChanged.connect(self.canvas_selected)
        view.marker_clicked.connect(self.canvas_clicked)
        view.effective_visibility_changed.connect(self.refresh)

    def select(
        self, object_id: str | None, source: Literal["canvas", "layers"]
    ) -> None:
        """Record explicit intent; mirrored highlight does not call this method."""
        old = self.target
        if old is not None and (old.map_id, old.object_id, old.source) == (
            self.get_map_id(),
            object_id,
            source,
        ):
            self.refresh()
            return
        self.revision += 1
        self.target = (
            FeatureTarget(self.get_map_id(), object_id, source, self.revision)
            if object_id
            else None
        )
        self.refresh()

    def canvas_selected(self) -> None:
        """Resolve single feature selections, rejecting ambiguous canvas input."""
        if (
            self.synchronizing
            or self.refreshing_scene
            or not isValid(self.view.graphics_scene)
        ):
            return
        items = [
            item
            for item in self.view.graphics_scene.selectedItems()
            if isinstance(item, (MarkerItem, PathItem, RegionItem))
        ]
        self.ambiguous = len(items) > 1
        if (
            len(items) == 1
            and self.target
            and (items[0].marker_id == self.target.object_id)
        ):
            self.refresh()
            return
        # Visibility updates may deselect an unavailable item. Keep its layer target.
        if not items and self.target:
            item = self.view.find_item_by_id(self.target.object_id)
            if (item is not None and not item.isVisible()) or (
                item is None and self.panel.feature_node(self.target.object_id)
            ):
                self.refresh()
                return
        if not items:
            self.panel.clear_feature_selection()
        self.select(items[0].marker_id if len(items) == 1 else None, "canvas")

    def canvas_clicked(self, object_id: str, _object_type: str) -> None:
        """A completed canvas click owns intent even after mirrored selection."""
        if not self.ambiguous:
            self.select(object_id, "canvas")

    def layers_selected(self, node_id: str) -> None:
        """Select by layer identity even when the canvas item is locked/hidden."""
        if self.synchronizing:
            return
        self.ambiguous = False
        node = self.panel.feature_node(node_id)
        self.select(node_id if node is not None else None, "layers")

    def context(self, target: FeatureTarget | None = None) -> FeatureContext | None:
        """Resolve current capabilities afresh; never retain graphics pointers."""
        target = target or self.target
        if self.awaiting_scene or target is None or target.map_id != self.get_map_id():
            return None
        node = self.panel.feature_node(target.object_id)
        item = self.view.find_item_by_id(target.object_id)
        if not isinstance(item, (MarkerItem, PathItem, RegionItem)):
            if node is None:
                return None
            return FeatureContext(
                node.layer_type,
                locked=node.locked,
                outside_date=not self.panel.feature_valid(node.id),
                canvas_available=False,
            )
        context = item_context(item, self.view)
        if node is not None:
            from dataclasses import replace

            context = replace(
                context,
                locked=node.locked,
                outside_date=context.outside_date
                or not self.panel.feature_valid(node.id),
            )
        return context

    def refresh(self, *_args: object) -> None:
        """Update both visible affordances after snapshot or capability changes."""
        if not isValid(self.panel) or not isValid(self.view):
            return
        context = self.context()
        if context is None and self.target and not self.refreshing_scene:
            self.revision += 1
            self.target = None
        reason = "Select one feature" if self.ambiguous else "Select a map feature"
        if self.awaiting_scene:
            reason = "Loading map features"
        self.panel.btn_feature_actions.setEnabled(context is not None)
        self.panel.btn_feature_actions.setToolTip(
            reason if context is None else "Actions for the selected feature"
        )
        node = self.panel.feature_node(self.target.object_id) if self.target else None
        self.panel.feature_selection_label.setText(node.name if node else reason)
        self.panel.feature_selection_label.setToolTip(node.name if node else reason)
        self.selection_updated()

    def scene_ready(self, map_id: str) -> None:
        """Finish a snapshot rebuild without treating restoration as user input."""
        if map_id == self.get_map_id():
            self.refreshing_scene = False
            self.awaiting_scene = False
            self.refresh()

    def bind_model(self, model: "MapLayerModel") -> None:
        """Rebind capability refresh to the current layer model."""
        if self._model is not None:
            for signal in (
                self._model.layer_tree_changed,
                self._model.temporal_state_changed,
            ):
                signal.disconnect(self.refresh)
        self._model = model
        model.layer_tree_changed.connect(self.refresh)
        model.temporal_state_changed.connect(self.refresh)
        self.refresh()

    def reset(self, *, wait_for_scene: bool = False) -> None:
        """Invalidate all captured actions on accepted map replacement."""
        self.ambiguous = False
        self.awaiting_scene = wait_for_scene
        self.select(None, "canvas")

    def capture_guard(self, object_id: str, action_id: str) -> Callable[[], bool]:
        """Capture target and date, rechecking capabilities after modal/deferred UI."""
        target = self.target
        playhead = self.view._playhead_time

        def valid() -> bool:
            if not isValid(self.view) or not isValid(self.panel):
                return False
            if (
                target is None
                or target != self.target
                or target.object_id != object_id
                or target.map_id != self.get_map_id()
                or playhead != self.view._playhead_time
            ):
                return False
            context = self.context(target)
            return context is not None and any(
                action.action_id == action_id and action.enabled
                for action in feature_actions(context)
            )

        return valid

    def populate(self, menu: QMenu) -> None:
        """Capture the selection when a visible menu opens."""
        context, target = self.context(), self.target
        if context is None or target is None:
            menu.clear()
            return
        guards = {
            action.action_id: self.capture_guard(target.object_id, action.action_id)
            for action in feature_actions(context)
        }
        populate_feature_menu(
            menu,
            feature_actions(context),
            lambda key: self.activate(target, key, guards[key]),
        )

    def activate(
        self, target: FeatureTarget, action_id: str, guard: Callable[[], bool]
    ) -> None:
        """Dispatch existing intents only after validating the captured target."""
        if not guard():
            return

        def execute() -> None:
            if not guard():
                return
            self._execute(target.object_id, action_id, guard)

        if action_id in {"copy", "layers"}:
            execute()
        else:
            self.transition("use another feature action", execute)

    def _execute(
        self, object_id: str, action_id: str, guard: Callable[[], bool]
    ) -> None:
        routes: dict[str, Callable[[], None]] = {
            "unlock": lambda: self.view.unlock_feature(object_id),
            "lock": lambda: self.view.set_feature_locked(object_id, True),
            "validity": lambda: self.panel.edit_temporal_validity(object_id),
            "jump": lambda: self.panel.jump_to_valid_time(object_id),
            "layers": lambda: self.panel.select_node(object_id),
        }
        if action_id in routes:
            routes[action_id]()
            return
        item = self.view.find_item_by_id(object_id)
        if isinstance(item, (MarkerItem, PathItem, RegionItem)):
            self.view._interaction.execute_feature_action(
                action_id,
                item,
                lambda: guard() and self.view.find_item_by_id(object_id) is item,
            )

    def show_layers_menu(self) -> None:
        """Open the visible Layers entry point at its labeled control."""
        menu = QMenu(self.panel)
        self.populate(menu)
        menu.exec(
            self.panel.btn_feature_actions.mapToGlobal(
                self.panel.btn_feature_actions.rect().bottomLeft()
            )
        )

    def show_layers_context_menu(self, node_id: str, menu: QMenu) -> None:
        """Reuse descriptors for the feature portion of a Layers context menu."""
        self.layers_selected(node_id)
        self.populate(menu)

    def show_canvas_menu(self, item: FeatureItem, global_pos: QPoint) -> None:
        """Treat right-click as an explicit target, including locked features."""
        self.ambiguous = False
        self.select(item.marker_id, "canvas")
        menu = QMenu(self.view)
        self.populate(menu)
        menu.exec(global_pos)

    def mirror_canvas_selection(self, object_id: str) -> None:
        """Mirror a Layers highlight without changing explicit selection source."""
        self.synchronizing = True
        try:
            item = self.view.find_item_by_id(object_id)
            self.view.graphics_scene.clearSelection()
            if (
                isinstance(item, (MarkerItem, PathItem, RegionItem))
                and not item.is_locked
            ):
                item.setSelected(True)
        finally:
            self.synchronizing = False
        self.refresh()
