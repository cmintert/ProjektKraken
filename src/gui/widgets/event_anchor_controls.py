"""Shared event-endpoint and offset controls; domain logic stays in core."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.core.temporal_boundary_resolver import BoundaryResolver
from src.core.temporal_context import TemporalResolutionContext
from src.gui.utils.help_context import declare_inspection
from src.gui.widgets.editor_presentation import DisclosureButton
from src.gui.widgets.event_offset_input import EventOffsetInput
from src.gui.widgets.wrapping_combo_box import WrappingComboBox


class EventAnchorControls(QWidget):
    """Render one reference and emit draft changes without persistence."""

    changed = Signal()

    def __init__(
        self,
        anchor: dict[str, Any] | None = None,
        parent: QWidget | None = None,
        *,
        calculated_only: bool = False,
    ) -> None:
        """Initialize common advanced choices without changing loaded metadata."""
        super().__init__(parent)
        self._original = deepcopy(anchor or {})
        self._context = TemporalResolutionContext()
        self._anchor_id = str(self._original.get("anchor_id", ""))
        self.dirty = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.summary = QLabel(self)
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.disclosure = declare_inspection(
            DisclosureButton("Endpoint and offset…"),
            "src-gui-widgets-relation-form-relationform-group-boundaries-disclosure|relations.timing|help-inspect-src-gui-widgets-relation-form-relationform-group-boundaries-disclosure",
        )
        layout.addWidget(self.disclosure)
        advanced = QWidget(self)
        form = QFormLayout(advanced)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        self.endpoint = declare_inspection(
            WrappingComboBox(self),
            "event-anchor-endpoint|relations.timing|help-inspect-event-anchor-endpoint",
        )
        self.endpoint.addItem(
            "Start" if calculated_only else "Occurrence / start", "start"
        )
        self.endpoint.addItem("End" if calculated_only else "Authored end", "end")
        self.relative = declare_inspection(
            WrappingComboBox(self),
            "src-gui-widgets-relation-form-relationform-setup-boundary-choices-relative|relations.timing|help-inspect-src-gui-widgets-relation-form-relationform-setup-boundary-choices-relative",
        )
        for caption, value in (
            ("At event endpoint", "at"),
            ("Date before endpoint", "before"),
            ("Date after endpoint", "after"),
        ):
            if not calculated_only or value == "at":
                self.relative.addItem(caption, value)
        self.offset = declare_inspection(
            EventOffsetInput(self),
            "src-gui-widgets-relation-form-relationform-setup-boundary-choices-offset|relations.timing|help-inspect-src-gui-widgets-relation-form-relationform-setup-boundary-choices-offset",
        )
        self.offset.setRange(-1e12, 1e12)
        self.offset.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.unit = declare_inspection(
            WrappingComboBox(self),
            "event-anchor-unit|relations.timing|help-inspect-event-anchor-unit",
        )
        for caption, value in (
            ("Days" if calculated_only else "Lore days", "days"),
            ("Calendar months", "months"),
            ("Calendar years", "years"),
        ):
            self.unit.addItem(caption, value)
        offset = self._original.get("offset") or {
            "unit": "days",
            "value": self._original.get("offset_days", 0),
        }
        for control, selected in (
            (self.endpoint, self._original.get("endpoint", "start")),
            (self.relative, self._original.get("relation", "at")),
            (self.unit, offset.get("unit", "days")),
        ):
            index = control.findData(selected)
            if index < 0:
                control.addItem(f"Unsupported ({selected}) — preserved", selected)
                index = control.count() - 1
            control.setCurrentIndex(index)
        self.offset.setValue(float(offset.get("value", 0)))
        for caption, field_control in (
            ("Event endpoint", self.endpoint),
            ("Boundary date", self.relative),
            ("Signed offset", self.offset),
            ("Offset unit", self.unit),
        ):
            field_control.setAccessibleName(caption)
            if field_control is not self.relative or not calculated_only:
                form.addRow(caption, field_control)
            else:
                field_control.hide()
        hint = QLabel("Before/after records an unknown date.")
        hint.setWordWrap(True)
        hint.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        if not calculated_only:
            form.addRow(hint)
        else:
            hint.hide()
        layout.addWidget(advanced)
        self.disclosure.toggled.connect(advanced.setVisible)
        expanded = bool(
            self._original.get("endpoint") == "end"
            or self._original.get("relation", "at") != "at"
            or offset.get("value", 0)
        )
        self.disclosure.setChecked(expanded)
        advanced.setVisible(expanded)
        for control in (self.endpoint, self.relative, self.unit):
            control.currentIndexChanged.connect(self._edited)
        self.offset.valueChanged.connect(self._edited)
        self._feedback()

    def set_context(self, context: TemporalResolutionContext) -> None:
        """Refresh names and precision without emitting an authoring change."""
        self._context = context
        self._feedback()

    def use_map_help(self) -> None:
        """Give shared controls map-specific inspection destinations at composition."""
        declare_inspection(
            self.disclosure,
            "map-anchor-options|map.visibility|help-inspect-map-anchor-options",
        )
        declare_inspection(
            self.endpoint,
            "map-anchor-endpoint|map.visibility|help-inspect-map-anchor-endpoint",
        )
        declare_inspection(
            self.relative,
            "map-anchor-relative|map.visibility|help-inspect-map-anchor-relative",
        )
        declare_inspection(
            self.offset,
            "map-anchor-offset|map.visibility|help-inspect-map-anchor-offset",
        )
        declare_inspection(
            self.unit, "map-anchor-unit|map.visibility|help-inspect-map-anchor-unit"
        )

    def set_anchor_id(self, anchor_id: str) -> None:
        """Select a stable UUID supplied by the owning boundary picker."""
        if anchor_id != self._anchor_id:
            self._anchor_id = anchor_id
            self._edited()

    def use_event_help(self) -> None:
        """Explain calculated Event endpoints without implying before/after dates."""
        declare_inspection(
            self.disclosure,
            "event-follow-options|event.timing|help-inspect-event-follow-options",
        )
        declare_inspection(
            self.endpoint,
            "event-follow-endpoint|event.timing|help-inspect-event-follow-endpoint",
        )
        declare_inspection(
            self.offset,
            "event-follow-offset|event.timing|help-inspect-event-follow-offset",
        )
        declare_inspection(
            self.unit, "event-follow-unit|event.timing|help-inspect-event-follow-unit"
        )

    def anchor(self) -> dict[str, Any]:
        """Preserve the complete reference until an explicit edit occurs."""
        if not self.dirty and self._original:
            return deepcopy(self._original)
        result = deepcopy(self._original)
        result.pop("offset_days", None)
        unit = self.unit.currentData()
        offset = {"unit": unit, "value": self.offset.value()}
        converter = self._context.converter()
        if unit != "days" and converter:
            offset["calendar_id"] = converter._config.id
        result.update(
            anchor_id=self._anchor_id,
            endpoint=self.endpoint.currentData(),
            relation=self.relative.currentData(),
            semantics="strict_v2",
            offset=offset,
        )
        return result

    def _edited(self, *_args: object) -> None:
        self.dirty = True
        self._feedback()
        self.changed.emit()

    def _feedback(self) -> None:
        resolver = BoundaryResolver(
            None, {}, None, self._context.converter(), self._context.anchors()
        )
        try:
            result = resolver.anchor(self.anchor())
            text = result.error or result.label or "Date unknown"
            if (
                not result.error
                and result.hard_start is not None
                and result.hard_end is not None
            ):
                converter = self._context.converter()
                first = (
                    converter.format_date(result.hard_start)
                    if converter
                    else f"{result.hard_start:g} days"
                )
                last = (
                    converter.format_date(result.hard_end)
                    if converter
                    else f"{result.hard_end:g} days"
                )
                date = (
                    first
                    if result.hard_start == result.hard_end
                    else f"{first} to {last} (possible dates)"
                )
                text = f"{text} · {date}"
        except (ValueError, TypeError, KeyError) as exc:
            text = str(exc)
        self.summary.setText(f"Follows event changes. {text}")
