"""Explicit production Help composition, separate from window infrastructure."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QWidget

from src.app.coordinators.help_coordinator import HelpCoordinator
from src.app.help_control_bindings import HelpControlBindings
from src.gui.utils.help_context import HelpContextRegistry
from src.services.help_bundle_service import HelpBundleService


class HelpSurfaceBindings(QObject):
    """Register dynamically created dialogs and semantic composite controls."""

    DIALOG_TOPICS = {
        "GoToDateDialog": "timeline.viewing",
        "RelationEditDialog": "relations.create",
        "TemporalValidityDialog": "map.visibility",
        "TemporalEvidenceDialog": "date.evidence",
        "EventChronologyDialog": "event.chronology",
        "KeyboardShortcutsDialog": "manual.shortcuts",
        "FeatureGeometryStatesDialog": "map.historical-geometry",
    }

    def __init__(self, coordinator: HelpCoordinator) -> None:
        """Retain the feature coordinator, never an application facade."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.inspection = HelpControlBindings(coordinator.registry)

    def bind(self, widget: QWidget) -> None:
        """Associate known production types with reviewed topic meanings."""
        registry = self.coordinator.registry
        self.inspection.bind(widget)
        name = type(widget).__name__
        topic = self.DIALOG_TOPICS.get(name)
        if topic:
            registry.register_dialog(widget, topic)
        if name == "CompactDateWidget":
            registry.register_control(widget, "date.precision")
        if name == "RelationAuthoring":
            registry.register_control(widget, "relations.create")
        if name == "RelationForm":
            for attribute, meaning in (
                ("temporal_group", "relations.timing"),
                ("temporal_behavior", "relations.timing"),
                ("logic_group", "relations.timing"),
                ("type_edit", "relations.create"),
                ("bi_check", "relations.create"),
            ):
                control = getattr(widget, attribute, None)
                if isinstance(control, QWidget):
                    registry.register_control(control, meaning)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Register completed widgets before first focus or Help invocation."""
        if (
            event.type() == QEvent.Type.Show
            and isinstance(watched, QWidget)
            and self.coordinator.belongs(watched)
        ):
            self.bind(watched)
        return False


def compose_help(owner: QWidget, surfaces: Any) -> HelpCoordinator:
    """Adapt existing window composition into narrow feature dependencies."""
    from PySide6.QtWidgets import QApplication

    registry = HelpContextRegistry()
    coordinator = HelpCoordinator(owner, registry, HelpBundleService())
    for attribute, topic in (
        ("list_widget", "authoring.create"),
        ("event_editor", "authoring.details"),
        ("entity_editor", "entity.historical-editing"),
        ("timeline", "timeline.viewing"),
        ("map_widget", "map.features"),
        ("longform_editor", "longform.recovery"),
    ):
        panel = getattr(surfaces, attribute, None)
        if isinstance(panel, QWidget):
            registry.register_panel(panel, topic)
    for editor in (surfaces.event_editor, surfaces.entity_editor):
        registry.register_control(editor.desc_edit, "writing.edit", editor)
        registry.register_control(
            editor.desc_edit.link_toolbar, "writing.links", editor
        )
        registry.register_control(
            editor._presentation.focus_button, "writing.focus", editor
        )
    map_widget = surfaces.map_widget
    registry.register_panel(map_widget.layer_panel, "map.features")
    geometry = surfaces.app_coordinator.feature_geometry
    trajectory = surfaces.app_coordinator.trajectory_edit

    def map_operation() -> str | None:
        if geometry.is_active:
            return "map.historical-geometry"
        if trajectory.is_active:
            return "map.trajectories"
        return None

    registry.register_operation(map_widget, map_operation)
    registry.register_operation(map_widget.layer_panel, map_operation)
    bindings = HelpSurfaceBindings(coordinator)
    for widget in owner.findChildren(QWidget):
        bindings.bind(widget)
    app = QApplication.instance()
    if isinstance(app, QApplication):
        app.installEventFilter(bindings)
        coordinator.stopped.connect(lambda: app.removeEventFilter(bindings))
    return coordinator
