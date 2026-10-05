"""Focused editor for map-layer temporal validity."""

from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.core.calendar import CalendarConverter
from src.core.map import MapLayerNode
from src.core.map_constants import MAP_LAYER_TYPE_GROUP
from src.core.temporal_expression import TemporalExpression
from src.core.temporal_window import resolve_temporal_window
from src.gui.utils.style_helper import StyleHelper
from src.gui.widgets.choice_inputs import ScrollSafeComboBox
from src.gui.widgets.compact_date_widget import CompactDateWidget


class TemporalValidityDialog(QDialog):
    """Edit only the optional existence window for one vector layer."""

    def __init__(
        self,
        node: MapLayerNode,
        parent: Optional[QWidget] = None,
        *,
        calendar_converter: Optional[CalendarConverter] = None,
        playhead_time: float = 0.0,
    ) -> None:
        """Initialize temporal-validity controls for a layer."""
        super().__init__(parent)
        self._node = node
        self._calendar_converter = calendar_converter
        self._playhead_time = float(playhead_time)
        self.setModal(False)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setWindowTitle(f"Temporal Validity — {node.name}")
        self.setMinimumWidth(420)
        self.setStyleSheet(StyleHelper.get_dialog_base_style())

        layout = QVBoxLayout(self)
        subject = "Visible" if node.layer_type == MAP_LAYER_TYPE_GROUP else "Exists"
        intro = QLabel(
            f"Set when {node.name} is part of the map. Choose an unbounded side "
            "or explicitly mark a date as not known."
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
            if "expression" in boundary:
                editor.set_expression(
                    TemporalExpression.from_dict(boundary["expression"])
                )
                editor.setProperty("exact_lore_value", None)
                (
                    self._start_enabled if side == "start" else self._end_enabled
                ).setChecked(True)
        form = QFormLayout()
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

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._buttons.accepted.connect(self._accept_if_valid)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)

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

    def _optional_date(
        self, label: str, value: Optional[float], side: str
    ) -> tuple[QCheckBox, CompactDateWidget, QWidget]:
        enabled = QCheckBox(label, self)
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
        mode = ScrollSafeComboBox(row)
        for caption, kind in (
            ("Unbounded", "open"),
            ("Date not known", "unknown"),
            ("Manual date", "manual"),
        ):
            mode.addItem(caption, kind)
        mode.setAccessibleName(label)
        self._boundary_modes[side] = mode
        row_layout.addWidget(mode)
        row_layout.addWidget(editor)

        def select_mode() -> None:
            manual = mode.currentData() == "manual"
            enabled.blockSignals(True)
            enabled.setChecked(manual)
            enabled.blockSignals(False)
            editor.setEnabled(manual)
            editor.setVisible(manual)

        mode.currentIndexChanged.connect(select_mode)
        enabled.toggled.connect(
            lambda checked: mode.setCurrentIndex(2 if checked else 0)
        )
        boundary = self._node.attributes.get("temporal", {}).get(side, {})
        initial = (
            "manual"
            if value is not None or "expression" in boundary
            else boundary.get("status", "open")
        )
        mode.setCurrentIndex(max(0, mode.findData(initial)))
        select_mode()
        use_playhead = QPushButton("Use Playhead", row)
        use_playhead.clicked.connect(lambda: self._copy_playhead(enabled, editor))
        row_layout.addWidget(use_playhead)
        return enabled, editor, row

    def _copy_playhead(self, enabled: QCheckBox, editor: CompactDateWidget) -> None:
        """Enable an endpoint and copy the exact active playhead value."""
        enabled.setChecked(True)
        editor.set_value(self._playhead_time)
        editor.setProperty("exact_lore_value", self._playhead_time)
        self._update_temporal_feedback()

    def set_playhead_time(self, playhead_time: float) -> None:
        """Update the value copied by subsequent Use Playhead actions."""
        self._playhead_time = float(playhead_time)

    def _temporal_values(self) -> tuple[Optional[float], Optional[float]]:
        start = (
            self._date_value(self._start) if self._start_enabled.isChecked() else None
        )
        end = self._date_value(self._end) if self._end_enabled.isChecked() else None
        return start, end

    @staticmethod
    def _date_value(editor: CompactDateWidget) -> float:
        """Preserve an exact loaded or playhead value until the user edits it."""
        exact = editor.property("exact_lore_value")
        return float(exact) if exact is not None else editor.get_value()

    def _format_date(self, value: Optional[float]) -> str:
        if value is None:
            return "unbounded"
        if self._calendar_converter is not None:
            return str(self._calendar_converter.format_date(value))
        return f"{value:g}"

    def _valid_window(self) -> bool:
        properties = self.properties()
        return resolve_temporal_window(
            {
                **properties,
                "valid_from": properties["start_date"],
                "valid_to": properties["end_date"],
            },
            converter=self._calendar_converter,
        ).is_valid

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
        invalid = not self._valid_window()
        self._temporal_error.setVisible(invalid)
        self._temporal_error.setText(
            "The end date must be later than the start date." if invalid else ""
        )
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
        if (
            self._start.get_expression()
            or self._end.get_expression()
            or "temporal" in self._node.attributes
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
                    else {"status": "open"}
                    if value is None
                    else {"expression": expression.to_dict()}
                    if expression
                    else {"exact": value}
                )
            result["temporal"] = temporal
        return result
