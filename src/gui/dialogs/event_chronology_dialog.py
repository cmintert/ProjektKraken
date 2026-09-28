"""Plain-language editor for direct event chronology."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QCompleter,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.core.calendar import CalendarConverter
from src.core.events import Event
from src.core.temporal_constraints import TemporalConstraintKind
from src.core.temporal_expression import expression_from_attributes
from src.core.theme_manager import ThemeManager
from src.gui.utils.style_helper import StyleHelper
from src.services.chronology_service import (
    collect_chronology,
    direct_chronology,
    world_issues,
)


class EventChronologyDialog(QDialog):
    """Edit direct rules without exposing storage direction or source claims."""

    def __init__(
        self,
        event_id: str,
        events: list[Event],
        converter: CalendarConverter | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Build rows from a detached snapshot of the current world."""
        super().__init__(parent)
        self.setWindowTitle("Chronology")
        self.setMinimumWidth(630)
        theme = ThemeManager().get_theme()
        surface = theme["surface"]
        border = theme["border"]
        text_color = theme["text_main"]
        self.setStyleSheet(
            StyleHelper.get_dialog_base_style()
            + f" QLabel {{ color: {text_color}; }}"
            + " QComboBox, QDoubleSpinBox, QComboBox QLineEdit {"
            + f" color: {text_color}; background-color: {surface};"
            + f" border: 1px solid {border}; padding: 3px; }}"
            + f" QComboBox QAbstractItemView {{ color: {text_color};"
            + f" background-color: {surface}; }}"
            + f" QPushButton {{ color: {text_color}; background-color: {surface};"
            + f" border: 1px solid {border}; padding: 5px; }}"
            + " QPushButton:hover { background-color:"
            + f" {theme.get('surface_alt', theme['app_bg'])}; }}"
        )
        self.event_id = event_id
        self.events = {event.id: event for event in events}
        self.converter = converter
        self.operations: list[dict[str, Any]] = []
        self._rows: list[dict[str, Any]] = []
        layout = QVBoxLayout(self)
        current = self.events[event_id]
        heading = QLabel(f"Chronology — {current.name}")
        layout.addWidget(heading)
        layout.addWidget(QLabel(f"Date: {self._date_label(current)}"))
        explanation = QLabel(
            "Record what you know about event order. Dates stay as they are. "
            "For events with a duration, order compares their start points; "
            "the events may still overlap."
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            f"QScrollArea {{ background-color: {theme['app_bg']}; border: none; }}"
        )
        body = QWidget()
        body.setStyleSheet(f"background-color: {theme['app_bg']};")
        self.rows_layout = QVBoxLayout(body)
        self.rows_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(body)
        layout.addWidget(scroll)
        for record, other, relation in direct_chronology(
            event_id, collect_chronology(events)
        ):
            self._add_row(other, relation, record.reference, record.data)
        relevant = [
            issue.message
            for issue in world_issues(events, converter)
            if f"event:{event_id}" in issue.anchor_ids
        ]
        if relevant:
            warning = QLabel(
                "Existing chronology needs review: " + " ".join(dict.fromkeys(relevant))
            )
            warning.setWordWrap(True)
            layout.addWidget(warning)
        add = QPushButton("Add ordering")
        add.clicked.connect(self._add_row)
        layout.addWidget(add)
        self.error = QLabel()
        self.error.setWordWrap(True)
        self.error.setStyleSheet(StyleHelper.get_error_label_style())
        layout.addWidget(self.error)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept_valid)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _add_row(
        self,
        other: str | None = None,
        relation: TemporalConstraintKind = TemporalConstraintKind.BEFORE,
        reference: str | None = None,
        old_data: dict[str, Any] | None = None,
    ) -> None:
        container = QWidget()
        row = QVBoxLayout(container)
        row.setContentsMargins(0, 3, 0, 9)
        primary = QHBoxLayout()
        primary.addWidget(QLabel("This event"))
        order = QComboBox()
        for label, value in (
            ("Before", "before"),
            ("After", "after"),
            ("Same transition as", "same_as"),
        ):
            order.addItem(label, value)
        order.setCurrentIndex(max(0, order.findData(relation.value)))
        order.setToolTip(
            "Same transition treats both events as one chronological point, "
            "not merely overlapping dates."
        )
        primary.addWidget(order)
        target = QComboBox()
        target.setEditable(True)
        target.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        target.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        target.setMinimumWidth(200)
        for event in sorted(
            self.events.values(), key=lambda item: item.name.casefold()
        ):
            if event.id != self.event_id:
                target.addItem(
                    f"{event.name} — {self._date_label(event)}", f"event:{event.id}"
                )
        if other and target.findData(other) < 0:
            target.addItem("⚠ Deleted / unavailable event", other)
        if other:
            target.setCurrentIndex(target.findData(other))
        else:
            target.setCurrentIndex(-1)
            target.setEditText("")
        completer = target.completer()
        if completer is not None:
            completer.setFilterMode(Qt.MatchFlag.MatchContains)
            completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        primary.addWidget(target, 1)
        row.addLayout(primary)
        secondary = QHBoxLayout()
        secondary.addStretch()
        gap = QDoubleSpinBox()
        gap.setRange(0, 1e12)
        gap.setDecimals(6)
        gap.setSuffix(" days")
        gap.setValue(float((old_data or {}).get("min_offset_days", 0)))
        gap.setToolTip("Minimum separation between event starts")
        gap.setVisible(gap.value() > 0)
        more = QPushButton("Gap…")
        more.clicked.connect(lambda: gap.setVisible(not gap.isVisible()))
        secondary.addWidget(more)
        secondary.addWidget(gap)
        remove = QPushButton("Remove")
        secondary.addWidget(remove)
        row.addLayout(secondary)
        self.rows_layout.addWidget(container)
        state = {
            "container": container,
            "remove_button": remove,
            "relation": order,
            "target": target,
            "gap": gap,
            "reference": reference,
            "old_data": deepcopy(old_data),
            "removed": False,
            "original_other": other,
            "original_relation": relation,
        }
        self._rows.append(state)

        def remove_row() -> None:
            state["removed"] = True
            container.hide()

        remove.clicked.connect(remove_row)
        order.currentIndexChanged.connect(
            lambda: gap.setEnabled(order.currentData() != "same_as")
        )
        gap.setEnabled(order.currentData() != "same_as")

    def _date_label(self, event: Event) -> str:
        """Show authored precision or format a legacy lore coordinate."""
        expression = expression_from_attributes(event.attributes)
        if expression is not None:
            return expression.display_text(self.converter)
        if self.converter is not None:
            return self.converter.format_date(event.lore_date)
        return str(event.lore_date)

    def _accept_valid(self) -> None:
        operations = []
        for row in self._rows:
            reference = row["reference"]
            old_data = row["old_data"]
            if row["removed"]:
                if reference:
                    operations.append(
                        {"kind": "delete", "reference": reference, "old_data": old_data}
                    )
                continue
            target = row["target"]
            index = target.currentIndex()
            if index < 0 or target.currentText() != target.itemText(index):
                self.error.setText("Choose an event from the search results.")
                return
            other = target.currentData()
            if not other or other == f"event:{self.event_id}":
                self.error.setText("Choose another event.")
                return
            relation = row["relation"].currentData()
            gap = row["gap"].value() if relation != "same_as" else 0.0
            original_gap = float((old_data or {}).get("min_offset_days", 0))
            if (
                reference
                and other == row["original_other"]
                and relation == row["original_relation"].value
                and gap == original_gap
            ):
                continue
            data = {
                "anchor_a": f"event:{self.event_id}",
                "relation": relation,
                "anchor_b": other,
                "min_offset_days": gap,
            }
            if old_data and old_data.get("id"):
                data["id"] = old_data["id"]
            operation = {"kind": "update" if reference else "create", "data": data}
            if reference:
                operation.update(reference=reference, old_data=old_data)
            operations.append(operation)
        self.operations = operations
        self.accept()
