"""Focused editor for map-layer temporal validity."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.core.calendar import CalendarConverter
from src.core.map import MapLayerNode
from src.core.map_constants import MAP_LAYER_TYPE_GROUP
from src.gui.utils.style_helper import StyleHelper
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
            f"Set when {node.name} is part of the map. Leave either boundary "
            "disabled to keep that side unbounded."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self._start_enabled, self._start, start_row = self._optional_date(
            f"{subject} from", node.start_date
        )
        self._end_enabled, self._end, end_row = self._optional_date(
            f"{subject} until", node.end_date
        )
        form = QFormLayout()
        form.addRow(self._start_enabled, start_row)
        form.addRow(self._end_enabled, end_row)
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
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
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
        self._update_temporal_feedback()

    def _optional_date(
        self, label: str, value: Optional[float]
    ) -> tuple[QCheckBox, CompactDateWidget, QWidget]:
        enabled = QCheckBox(label)
        enabled.setChecked(value is not None)
        editor = CompactDateWidget(self)
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
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(editor, 1)
        use_playhead = QPushButton("Use Playhead", row)
        use_playhead.clicked.connect(lambda: self._copy_playhead(enabled, editor))
        row_layout.addWidget(use_playhead)
        return enabled, editor, row

    def _copy_playhead(
        self, enabled: QCheckBox, editor: CompactDateWidget
    ) -> None:
        """Enable an endpoint and copy the exact active playhead value."""
        enabled.setChecked(True)
        editor.set_value(self._playhead_time)
        editor.setProperty("exact_lore_value", self._playhead_time)
        self._update_temporal_feedback()

    def set_playhead_time(self, playhead_time: float) -> None:
        """Update the value copied by subsequent Use Playhead actions."""
        self._playhead_time = float(playhead_time)

    def _temporal_values(self) -> tuple[Optional[float], Optional[float]]:
        start = self._date_value(self._start) if self._start_enabled.isChecked() else None
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

    def _update_temporal_feedback(self, *_args: object) -> None:
        """Refresh the half-open summary and strict-range validation."""
        start, end = self._temporal_values()
        invalid = start is not None and end is not None and end <= start
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
        if start is None and end is None:
            summary = f"{subject} at every lore date."
        elif start is None:
            summary = f"{subject} until {self._format_date(end)}."
        elif end is None:
            summary = f"{subject} from {self._format_date(start)} onward."
        else:
            summary = (
                f"{subject} from {self._format_date(start)} until "
                f"{self._format_date(end)}. At the end date it is no longer "
                "part of the map state."
            )
        self._temporal_summary.setText(summary)

    def _accept_if_valid(self) -> None:
        """Accept only when the half-open validity range is non-empty."""
        start, end = self._temporal_values()
        if start is not None and end is not None and end <= start:
            self._update_temporal_feedback()
            return
        self.accept()

    def properties(self) -> dict[str, Optional[float]]:
        """Return only the temporal values changed by this focused editor."""
        start, end = self._temporal_values()
        return {"start_date": start, "end_date": end}
