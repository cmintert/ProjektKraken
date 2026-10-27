"""Focused editor for map-layer temporal validity."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.core.calendar import CalendarConverter
from src.core.map import MapLayerNode
from src.core.map_constants import MAP_LAYER_TYPE_GROUP
from src.core.temporal_context import TemporalResolutionContext
from src.core.temporal_editing import edit_error, supported_boundary, updated_spec
from src.core.temporal_expression import TemporalExpression
from src.core.temporal_window import (
    TemporalWindow,
    intersect_window_status,
    resolve_temporal_window,
)
from src.gui.dialogs.help_aware_dialog import HelpAwareDialog
from src.gui.utils.help_context import declare_inspection
from src.gui.utils.style_helper import StyleHelper
from src.gui.widgets.compact_date_widget import CompactDateWidget
from src.gui.widgets.event_anchor_controls import EventAnchorControls
from src.gui.widgets.responsive_dialog_buttons import (
    ResponsiveDialogButtonBox as QDialogButtonBox,
)
from src.gui.widgets.standard_buttons import StandardButton as QPushButton
from src.gui.widgets.wrapping_combo_box import WrappingComboBox as ScrollSafeComboBox


class TemporalValidityDialog(HelpAwareDialog):
    """Edit only the optional existence window for one vector layer."""

    def __init__(
        self,
        node: MapLayerNode,
        parent: Optional[QWidget] = None,
        *,
        calendar_converter: Optional[CalendarConverter] = None,
        playhead_time: float = 0.0,
        temporal_context: TemporalResolutionContext | None = None,
        ancestor_windows: tuple[tuple[str, dict[str, Any]], ...] = (),
    ) -> None:
        """Initialize temporal-validity controls for a layer."""
        super().__init__(parent)
        self._node = deepcopy(node)
        self._calendar_converter = calendar_converter
        self._playhead_time = float(playhead_time)
        self._context = temporal_context or TemporalResolutionContext.build(
            [], calendar_converter
        )
        self._calendar_converter = calendar_converter or self._context.converter()
        self._anchors = self._context.anchors()
        self._ancestor_windows = deepcopy(ancestor_windows)
        self._event_controls: dict[str, EventAnchorControls] = {}
        self._dirty_sides: set[str] = set()
        self.setModal(False)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setWindowTitle(f"Temporal Validity — {node.name}")
        self.setMinimumWidth(420)
        self.setStyleSheet(StyleHelper.get_dialog_base_style())

        outer = QVBoxLayout(self)
        scroll = declare_inspection(
            QScrollArea(self),
            "map-visibility-scroll|map.visibility|help-inspect-map-visibility-scroll",
        )
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            StyleHelper.get_scroll_area_style() + StyleHelper.get_scrollbar_style()
        )
        body = QWidget(self)
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)
        layout = QVBoxLayout(body)
        subject = "Visible" if node.layer_type == MAP_LAYER_TYPE_GROUP else "Exists"
        intro = QLabel(
            f"Set when {node.name} is part of the map. Choose a date or an event "
            "to follow, leave a side unbounded, or record its date as unknown."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self._boundary_modes: dict[str, QComboBox] = {}
        self._start_enabled, self._start, start_row = self._optional_date(
            f"{subject} from", node.start_date, "start"
        )
        self._end_enabled, self._end, end_row = self._optional_date(
            f"{subject} until", node.end_date, "end"
        )
        for side, editor in (("start", self._start), ("end", self._end)):
            boundary = node.attributes.get("temporal", {}).get(side, {})
            if (
                "exact" in boundary
                and self._boundary_modes[side].currentData() != "preserved"
            ):
                editor.set_value(float(boundary["exact"]))
                editor.setProperty("exact_lore_value", float(boundary["exact"]))
                (
                    self._start_enabled if side == "start" else self._end_enabled
                ).setChecked(True)
            if (
                "expression" in boundary
                and self._boundary_modes[side].currentData() != "preserved"
            ):
                editor.set_expression(
                    TemporalExpression.from_dict(boundary["expression"])
                )
                editor.setProperty("exact_lore_value", None)
                (
                    self._start_enabled if side == "start" else self._end_enabled
                ).setChecked(True)
        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        form.addRow(f"{subject} from", start_row)
        form.addRow(f"{subject} until", end_row)
        layout.addLayout(form)

        self._temporal_summary = QLabel()
        self._temporal_summary.setWordWrap(True)
        layout.addWidget(self._temporal_summary)
        self._temporal_error = QLabel()
        self._temporal_error.setWordWrap(True)
        self._temporal_error.setStyleSheet(StyleHelper.get_error_label_style())
        self._temporal_error.setVisible(False)
        layout.addWidget(self._temporal_error)

        self._buttons = declare_inspection(
            QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok
                | QDialogButtonBox.StandardButton.Cancel
            ),
            "src-gui-dialogs-temporal-validity-dialog-temporalvaliditydialog-init-self-buttons|map.visibility|help-inspect-src-gui-dialogs-temporal-validity-dialog-temporalvaliditydialog-init-self-buttons",
        )
        self._buttons.accepted.connect(self._accept_if_valid)
        self._buttons.rejected.connect(self.reject)
        outer.addWidget(self._buttons)
        screen = self.screen()
        if screen is not None:
            self.setMaximumHeight(int(screen.availableGeometry().height() * 0.9))

        for signal in (
            self._start_enabled.toggled,
            self._end_enabled.toggled,
            self._start.value_changed,
            self._end.value_changed,
        ):
            signal.connect(self._update_temporal_feedback)
        for mode in self._boundary_modes.values():
            mode.currentIndexChanged.connect(self._update_temporal_feedback)
        self._update_temporal_feedback()
        for side, mode in self._boundary_modes.items():
            mode.currentIndexChanged.connect(lambda _index, s=side: self._mark_side(s))
        for side, editor in (("start", self._start), ("end", self._end)):
            editor.value_changed.connect(lambda _value, s=side: self._mark_side(s))

    def _optional_date(
        self, label: str, value: Optional[float], side: str
    ) -> tuple[QCheckBox, CompactDateWidget, QWidget]:
        enabled = declare_inspection(
            QCheckBox(label, self),
            "src-gui-dialogs-temporal-validity-dialog-temporalvaliditydialog-optional-date-enabled|map.visibility|help-inspect-src-gui-dialogs-temporal-validity-dialog-temporalvaliditydialog-optional-date-enabled",
        )
        enabled.hide()
        enabled.setChecked(value is not None)
        editor = CompactDateWidget(self, text_first=True)
        if self._calendar_converter is not None:
            editor.set_calendar_converter(self._calendar_converter)
        editor.set_value(float(value if value is not None else self._playhead_time))
        editor.setProperty(
            "exact_lore_value",
            float(value) if value is not None else self._playhead_time,
        )
        editor.value_changed.connect(
            lambda _value: editor.setProperty("exact_lore_value", None)
        )
        editor.setEnabled(value is not None)
        enabled.toggled.connect(editor.setEnabled)
        row = QWidget(self)
        row_layout = QVBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        mode = declare_inspection(
            ScrollSafeComboBox(row),
            "src-gui-dialogs-temporal-validity-dialog-temporalvaliditydialog-optional-date-mode|map.visibility|help-inspect-src-gui-dialogs-temporal-validity-dialog-temporalvaliditydialog-optional-date-mode",
        )
        for caption, kind in (
            ("Unbounded", "open"),
            ("Date not known", "unknown"),
            ("Manual date", "manual"),
        ):
            mode.addItem(caption, kind)
        mode.setAccessibleName(label)
        self._boundary_modes[side] = mode
        boundary = self._node.attributes.get("temporal", {}).get(side, {})
        unsupported = not supported_boundary(boundary) or self._node.attributes.get(
            "temporal", {}
        ).get("schema", 1) not in {1, 2}
        if unsupported:
            boundary = {}
        if unsupported:
            mode.addItem("Unsupported date (preserved)", "preserved")
        selected = boundary.get("anchor", {}).get("anchor_id")
        for event in self._context.events():
            mode.addItem(f"Event: {event.name}", f"event:{event.id}")
        if selected and mode.findData(selected) < 0:
            mode.addItem("Referenced event (unavailable)", selected)
        controls = EventAnchorControls(boundary.get("anchor"), row)
        controls.use_map_help()
        controls.set_context(self._context)
        self._event_controls[side] = controls
        controls.changed.connect(lambda s=side: self._dirty_sides.add(s))
        controls.changed.connect(lambda: self._update_temporal_feedback())
        row_layout.addWidget(mode)
        row_layout.addWidget(editor)
        row_layout.addWidget(controls)

        def select_mode() -> None:
            manual = mode.currentData() == "manual"
            enabled.blockSignals(True)
            enabled.setChecked(manual)
            enabled.blockSignals(False)
            editor.setEnabled(manual)
            editor.setVisible(manual)
            is_event = str(mode.currentData()).startswith("event:")
            controls.setVisible(is_event)
            if is_event:
                controls.set_anchor_id(str(mode.currentData()))

        mode.currentIndexChanged.connect(select_mode)
        enabled.toggled.connect(
            lambda checked: mode.setCurrentIndex(2 if checked else 0)
        )
        initial = (
            "preserved"
            if unsupported
            else selected
            or (
                "manual"
                if value is not None or "expression" in boundary or "exact" in boundary
                else boundary.get("status", "open")
            )
        )
        mode.setCurrentIndex(max(0, mode.findData(initial)))
        select_mode()
        controls.dirty = False
        use_playhead = declare_inspection(
            QPushButton("Use Playhead", row),
            "src-gui-dialogs-temporal-validity-dialog-temporalvaliditydialog-optional-date-use-playhead|map.visibility|help-inspect-src-gui-dialogs-temporal-validity-dialog-temporalvaliditydialog-optional-date-use-playhead",
        )
        use_playhead.clicked.connect(lambda: self._copy_playhead(enabled, editor))
        row_layout.addWidget(use_playhead)
        return enabled, editor, row

    def _mark_side(self, side: str) -> None:
        """Track explicit local edits before recomputing draft feedback."""
        self._dirty_sides.add(side)
        self._update_temporal_feedback()

    def _copy_playhead(self, enabled: QCheckBox, editor: CompactDateWidget) -> None:
        """Enable an endpoint and copy the exact active playhead value."""
        enabled.setChecked(True)
        editor.set_value(self._playhead_time)
        editor.setProperty("exact_lore_value", self._playhead_time)
        self._update_temporal_feedback()

    def set_playhead_time(self, playhead_time: float) -> None:
        """Update the value copied by subsequent Use Playhead actions."""
        self._playhead_time = float(playhead_time)
        self._update_temporal_feedback()

    def set_ancestor_windows(
        self, windows: tuple[tuple[str, dict[str, Any]], ...]
    ) -> None:
        """Refresh inherited limits without replacing the feature's own draft."""
        self._ancestor_windows = deepcopy(windows)
        self._update_temporal_feedback()

    def set_temporal_context(self, context: TemporalResolutionContext) -> None:
        """Refresh event names and previews while retaining the active draft."""
        self._context = context
        self._anchors = context.anchors()
        self._calendar_converter = context.converter()
        for editor in (self._start, self._end):
            editor.set_calendar_converter(self._calendar_converter)
        for side, controls in self._event_controls.items():
            mode = self._boundary_modes[side]
            previous = mode.currentData()
            mode.blockSignals(True)
            for index in range(mode.count() - 1, 2, -1):
                mode.removeItem(index)
            for event in context.events():
                mode.addItem(f"Event: {event.name}", f"event:{event.id}")
            if str(previous).startswith("event:") and mode.findData(previous) < 0:
                mode.addItem("Referenced event (unavailable)", previous)
            elif previous == "preserved" and mode.findData(previous) < 0:
                mode.addItem("Unsupported date (preserved)", previous)
            mode.setCurrentIndex(max(0, mode.findData(previous)))
            mode.blockSignals(False)
            controls.set_context(context)
        self._update_temporal_feedback()

    def _temporal_values(self) -> tuple[Optional[float], Optional[float]]:
        start = (
            self._date_value(self._start) if self._start_enabled.isChecked() else None
        )
        end = self._date_value(self._end) if self._end_enabled.isChecked() else None
        return start, end

    @staticmethod
    def _date_value(editor: CompactDateWidget) -> float | None:
        """Preserve an exact loaded or playhead value until the user edits it."""
        exact = editor.property("exact_lore_value")
        if exact is not None:
            return float(exact)
        try:
            return editor.get_value()
        except ValueError:
            return None  # Keep an unresolved expression in semantic metadata.

    def _format_date(self, value: Optional[float]) -> str:
        if value is None:
            return "unbounded"
        if self._calendar_converter is not None:
            return str(self._calendar_converter.format_date(value))
        return f"{value:g}"

    def _valid_window(self) -> bool:
        """Reject impossible edits while preserving unresolved authored intent."""
        return edit_error(self._resolved_window()) is None

    def _resolved_window(self) -> TemporalWindow:
        """Use one domain adapter for numeric and semantic draft boundaries."""
        properties = self.properties()
        return resolve_temporal_window(
            {
                **properties,
                "valid_from": properties["start_date"],
                "valid_to": properties["end_date"],
            },
            converter=self._calendar_converter,
            anchors=self._anchors,
        )

    def _boundary_text(self, editor: CompactDateWidget, value: Optional[float]) -> str:
        expression = editor.get_expression()
        return (
            expression.display_text(self._calendar_converter)
            if expression and value is not None
            else self._format_date(value)
        )

    def _update_temporal_feedback(self, *_args: object) -> None:
        """Refresh the half-open summary and strict-range validation."""
        start, end = self._temporal_values()
        window = self._resolved_window()
        invalid = edit_error(window) is not None
        self._temporal_error.setVisible(invalid)
        self._temporal_error.setText(edit_error(window) or "")
        ok_button = self._buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok_button is not None:
            ok_button.setEnabled(not invalid)
        subject = (
            "Visible" if self._node.layer_type == MAP_LAYER_TYPE_GROUP else "Exists"
        )
        if any(
            mode.currentData() == "unknown" for mode in self._boundary_modes.values()
        ):
            summary = f"{subject} during an unresolved interval; a boundary date is not known."
        elif start is None and end is None:
            summary = f"{subject} at every lore date."
        elif start is None:
            summary = f"{subject} until {self._boundary_text(self._end, end)}."
        elif end is None:
            summary = (
                f"{subject} from {self._boundary_text(self._start, start)} onward."
            )
        else:
            summary = (
                f"{subject} from {self._boundary_text(self._start, start)} until "
                f"{self._boundary_text(self._end, end)}. At the end date it is no longer "
                "part of the map state."
            )
        self._temporal_summary.setText(summary)
        self._update_reference_feedback(window)

    def _update_reference_feedback(self, window: TemporalWindow) -> None:
        """Render authored provenance and the joint inherited presence status."""
        if any(
            str(mode.currentData()).startswith("event:")
            for mode in self._boundary_modes.values()
        ):
            labels = [
                b.error or b.label or "Date unknown"
                for b in (window.start_bounds, window.end_bounds)
                if b
            ]
            self._temporal_summary.setText("; ".join(labels))
        if window.error:
            self._temporal_summary.setText(
                f"Dates unresolved: {window.error} Saved references are retained."
            )
            original = self._node.attributes.get("temporal", {})
            if original.get("schema", 1) not in {1, 2}:
                self._temporal_summary.setText(
                    self._temporal_summary.text()
                    + " Choose both boundary modes explicitly to replace this timing format."
                )
        if self._ancestor_windows:
            inherited = [
                resolve_temporal_window(
                    attrs, converter=self._calendar_converter, anchors=self._anchors
                )
                for _name, attrs in self._ancestor_windows
            ]
            state = intersect_window_status(
                [window, *inherited], self._playhead_time, self._context.constraints()
            )
            caption = {
                "definite": "present",
                "possible": "may be present",
                "inactive": "not present",
                "indeterminate": "presence unresolved",
            }[state.value]
            groups = ", ".join(name for name, _attrs in self._ancestor_windows)
            self._temporal_summary.setText(
                self._temporal_summary.text()
                + f" With group dates ({groups}): {caption} at the viewed date."
            )

    def _accept_if_valid(self) -> None:
        """Accept only when the half-open validity range is non-empty."""
        if not self._start.commit_draft() or not self._end.commit_draft():
            return
        start, end = self._temporal_values()
        if not self._valid_window():
            self._update_temporal_feedback()
            return
        self.accept()

    def properties(self) -> dict[str, Any]:
        """Return only the temporal values changed by this focused editor."""
        start, end = self._temporal_values()
        result: dict[str, Any] = {"start_date": start, "end_date": end}
        original = self._node.attributes.get("temporal")
        if (
            original
            and original.get("schema", 1) not in {1, 2}
            and len(self._dirty_sides) == len(self._boundary_modes)
        ):
            original = {}
        if original is not None and not self._dirty_sides:
            return {
                "start_date": self._node.start_date,
                "end_date": self._node.end_date,
                "temporal": deepcopy(original),
            }
        if (
            self._start.get_expression()
            or self._end.get_expression()
            or "temporal" in self._node.attributes
            or any(
                str(mode.currentData()).startswith("event:")
                for mode in self._boundary_modes.values()
            )
            or any(
                mode.currentData() == "unknown"
                for mode in self._boundary_modes.values()
            )
        ):
            temporal: dict[str, Any] = {"schema": 1, "behavior": "stateful"}
            for side, editor, value in (
                ("start", self._start, start),
                ("end", self._end, end),
            ):
                expression = editor.get_expression()
                temporal[side] = (
                    {"status": "unknown"}
                    if self._boundary_modes[side].currentData() == "unknown"
                    else {"expression": expression.to_dict()}
                    if expression
                    and self._boundary_modes[side].currentData() == "manual"
                    else {"status": "open"}
                    if value is None
                    else {"exact": value}
                )
            result["temporal"] = temporal
            for side, controls in self._event_controls.items():
                if str(self._boundary_modes[side].currentData()).startswith("event:"):
                    temporal[side] = {"anchor": controls.anchor()}
                elif original and side not in self._dirty_sides:
                    temporal[side] = deepcopy(original.get(side, temporal[side]))
            result["temporal"] = updated_spec(original or {}, temporal)
        return result
