"""Explicit finite control-inspection composition for production surfaces."""

from __future__ import annotations

import weakref
from typing import Any

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QFormLayout, QLabel, QListWidget, QTableWidget, QWidget

from src.gui.utils.help_context import ControlHelpRegistration, HelpContextRegistry

CONTROL_TOPICS = {
    "date.qualification": "date.precision",
    "date.month": "date.precision",
    "date.day": "date.precision",
    "date.limits": "date.precision",
    "event.duration": "event.timing",
    "event.keep-span": "event.timing",
    "entity.baseline": "entity.historical-editing",
    "entity.at-time": "entity.historical-editing",
    "entity.source": "entity.value-source",
    "relation.direction": "relations.create",
    "relation.meaning": "relations.timing",
    "relation.start": "relations.timing",
    "relation.end": "relations.timing",
    "relation.shared-event": "relations.timing",
    "geometry.dated": "map.historical-geometry",
    "geometry.base": "map.historical-geometry",
    "map.exists-from": "map.visibility",
    "map.exists-until": "map.visibility",
    "timeline.viewing": "timeline.viewing",
    "timeline.world-time": "timeline.viewing",
}
_SOURCE_COLUMN = 3
_TIME_HIT_TOLERANCE = 4


class HelpControlBindings:
    """Bind semantic attributes rather than guessing from displayed UI wording."""

    def __init__(self, registry: HelpContextRegistry) -> None:
        """Depend only on the GUI-local registry."""
        self.registry = registry

    def control(self, widget: QWidget, meaning: str) -> None:
        """Register equivalent controls and their form labels."""
        self.registry.register_inspection(widget, meaning, CONTROL_TOPICS[meaning])
        parent = widget.parentWidget()
        if parent:
            for layout in parent.findChildren(QFormLayout):
                label = layout.labelForField(widget)
                if isinstance(label, QLabel):
                    self.registry.register_inspection(
                        label, meaning, CONTROL_TOPICS[meaning]
                    )

    def fields(self, widget: QWidget, fields: tuple[tuple[str, str], ...]) -> None:
        """Map named semantic controls, including optional advanced instances."""
        for attribute, meaning in fields:
            control = getattr(widget, attribute, None)
            if isinstance(control, QWidget):
                self.control(control, meaning)

    def bind(self, widget: QWidget) -> None:
        """Dispatch known surfaces to small, feature-specific binding adapters."""
        marker = widget.property("krakenHelpMeaning")
        if isinstance(marker, str) and marker in CONTROL_TOPICS:
            self.control(widget, marker)
        handler = {
            "CompactDateWidget": self.date,
            "TemporalRangeWidget": self.span,
            "RelationForm": self.relation,
            "FeatureGeometryStatesDialog": self.geometry,
            "TemporalValidityDialog": self.visibility,
            "EntityEditorWidget": self.entity,
            "AttributeEditorWidget": self.attribute_source,
            "TimelineView": self.timeline,
            "TimelineTimeStatus": self.timeline_status,
        }.get(type(widget).__name__)
        if handler:
            handler(widget)

    def date(self, widget: QWidget) -> None:
        """Cover precise components and explicit occurrence-limit disclosure."""
        self.fields(
            widget,
            (
                ("qualifier_combo", "date.qualification"),
                ("combo_month", "date.month"),
                ("combo_day", "date.day"),
                ("limits_button", "date.limits"),
            ),
        )
        for label, component in getattr(widget, "_structured_fields", []):
            for attribute, meaning in (
                ("combo_month", "date.month"),
                ("combo_day", "date.day"),
            ):
                if component is getattr(widget, attribute, None):
                    self.control(label, meaning)
        row = getattr(widget, "_qualification_row", None)
        if isinstance(row, QWidget):
            for label in row.findChildren(QLabel):
                self.control(label, "date.qualification")

    def span(self, widget: QWidget) -> None:
        """Keep the two lock choices under one reviewed control meaning."""
        self.fields(
            widget,
            (
                ("duration_widget", "event.duration"),
                ("btn_lock_duration", "event.keep-span"),
                ("btn_lock_end", "event.keep-span"),
            ),
        )

    def relation(self, widget: QWidget) -> None:
        """Register relation semantics independently from date precision."""
        self.fields(
            widget,
            (
                ("bi_check", "relation.direction"),
                ("temporal_behavior", "relation.meaning"),
                ("rb_starts", "relation.shared-event"),
                ("rb_ends", "relation.shared-event"),
                ("rb_at_event", "relation.shared-event"),
            ),
        )
        for side, meaning in (("start", "relation.start"), ("end", "relation.end")):
            for mapping in ("_boundary_choices", "_boundary_offsets"):
                control = getattr(widget, mapping, {}).get(side)
                if isinstance(control, QWidget):
                    self.control(control, meaning)
            relative = getattr(widget, "_anchor_relations", {}).get(side)
            if isinstance(relative, QWidget):
                self.control(relative, "relation.shared-event")

    def visibility(self, widget: QWidget) -> None:
        """Existence boundaries explain presence rather than geometry."""
        self.fields(
            widget,
            (
                ("_start_enabled", "map.exists-from"),
                ("_start", "map.exists-from"),
                ("_end_enabled", "map.exists-until"),
                ("_end", "map.exists-until"),
            ),
        )
        for side, control in getattr(widget, "_boundary_modes", {}).items():
            self.control(
                control, "map.exists-from" if side == "start" else "map.exists-until"
            )

    def entity(self, widget: QWidget) -> None:
        """Register the non-focusable visible description Source label."""
        self.fields(widget, (("description_source_label", "entity.source"),))

    def attribute_source(self, widget: QWidget) -> None:
        """Resolve only the Source column, leaving value edits exempt."""
        table: QTableWidget = getattr(widget, "table")
        reference = weakref.ref(table)

        def region(point: QPoint | None) -> ControlHelpRegistration | None:
            live = reference()
            if live is None:
                return None
            column = (
                live.columnAt(point.x()) if point is not None else live.currentColumn()
            )
            if column == _SOURCE_COLUMN:
                return ControlHelpRegistration("entity.source", "entity.value-source")
            return self.registry.inspection.get(live)

        self.registry.register_inspection_region(table.viewport(), region)
        self.registry.register_inspection_region(table, region)

    def geometry(self, widget: QWidget) -> None:
        """Read item identity under the pointer without selecting that item."""
        listing: QListWidget = getattr(widget, "state_list")
        reference = weakref.ref(listing)

        def region(point: QPoint | None) -> ControlHelpRegistration | None:
            live = reference()
            if live is None:
                return None
            item = live.itemAt(point) if point is not None else live.currentItem()
            if item is None:
                return None
            meaning = (
                "geometry.base"
                if item.data(Qt.ItemDataRole.UserRole) is None
                else "geometry.dated"
            )
            return ControlHelpRegistration(meaning, CONTROL_TOPICS[meaning])

        self.registry.register_inspection_region(listing.viewport(), region)
        self.registry.register_inspection_region(listing, region)

    def timeline_status(self, widget: QWidget) -> None:
        """Expose both time identities through their common canonical explanation."""
        self.fields(widget, (("dates", "timeline.viewing"),))

    def timeline(self, widget: QWidget) -> None:
        """Resolve painted time lines by geometry rather than selection."""
        reference = weakref.ref(widget)

        def region(point: QPoint | None) -> ControlHelpRegistration | None:
            view: Any = reference()
            if view is None:
                return None
            fallback = self.registry.inspection.get(view)
            if point is None:
                return fallback
            for marker, meaning in (
                (view._playhead, "timeline.viewing"),
                (view._current_time_line, "timeline.world-time"),
            ):
                x = view.mapFromScene(marker.x(), 0).x()
                if marker.isVisible() and abs(point.x() - x) <= _TIME_HIT_TOLERANCE:
                    return ControlHelpRegistration(meaning, "timeline.viewing")
            return fallback

        self.registry.register_inspection_region(getattr(widget, "viewport")(), region)
