"""Source claims and chronology editing from serializable event snapshots."""

from copy import deepcopy
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.date_parser import DateParser
from src.core.temporal_authoring import author_temporal_evidence
from src.core.temporal_expression import TemporalExpression
from src.gui.utils.style_helper import StyleHelper


class TemporalEvidenceDialog(QDialog):
    """Edit claims and ordering without reading or writing a database."""

    def __init__(
        self,
        event_id: str,
        metadata: dict[str, Any],
        parser: DateParser,
        events: list[tuple[str, str, str]],
        parent: QWidget | None = None,
    ) -> None:
        """Build source and order controls from a detached metadata snapshot."""
        super().__init__(parent)
        self.setWindowTitle("Date sources and chronology")
        self.setMinimumWidth(650)
        self.setStyleSheet(StyleHelper.get_dialog_base_style())
        self._event_id, self._metadata, self._parser = (
            event_id,
            deepcopy(metadata),
            parser,
        )
        self._events = [
            (identity, name)
            for identity, name, kind in events
            if kind.casefold() == "event"
        ]
        self.result_metadata = deepcopy(metadata)
        layout = QVBoxLayout(self)
        intro = QLabel(
            "Keep conflicting source dates as separate claims. Choosing a preferred claim changes the event date; it does not merge the claims into a range."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self.claims = QTableWidget(0, 2)
        self.claims.setHorizontalHeaderLabels(
            ["Source / citation", "Source date expression"]
        )
        self.claims.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.claims.setStyleSheet(StyleHelper.get_table_widget_style())
        layout.addWidget(self.claims)
        self.preferred = QComboBox()
        self.preferred.addItem("Keep the current event date", -1)
        for index, claim in enumerate(metadata.get("claims", [])):
            self._add_claim(
                str(claim.get("source", "")),
                TemporalExpression.from_dict(claim["expression"]).display_text(
                    parser.converter
                ),
            )
            item = self.claims.item(index, 0)
            assert item is not None
            item.setData(Qt.ItemDataRole.UserRole, claim.get("id"))
            if claim.get("id") == metadata.get("preferred_claim_id"):
                self.preferred.setCurrentIndex(index + 1)
        add = QPushButton("Add source claim")
        add.clicked.connect(lambda: self._add_claim())
        layout.addWidget(add)
        remove = QPushButton("Remove selected source claim")
        remove.clicked.connect(self._remove_claim)
        layout.addWidget(remove)
        layout.addWidget(QLabel("Preferred assertion"))
        layout.addWidget(self.preferred)
        layout.addWidget(QLabel("Known ordering relative to this event"))
        self.orders = QTableWidget(0, 4)
        self.orders.setHorizontalHeaderLabels(
            ["Event", "Order", "Other event", "Min. gap (days)"]
        )
        self.orders.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.orders.verticalHeader().hide()
        self.orders.setStyleSheet(StyleHelper.get_table_widget_style())
        layout.addWidget(self.orders)
        for constraint in metadata.get("constraints", []):
            self._add_order(constraint)
        buttons = QHBoxLayout()
        add_order = QPushButton("Add ordering")
        add_order.clicked.connect(lambda: self._add_order())
        remove_order = QPushButton("Remove selected ordering")
        remove_order.clicked.connect(
            lambda: self.orders.removeRow(self.orders.currentRow())
        )
        buttons.addWidget(add_order)
        buttons.addWidget(remove_order)
        layout.addLayout(buttons)
        self.error = QLabel()
        self.error.setWordWrap(True)
        self.error.setStyleSheet(StyleHelper.get_error_label_style())
        layout.addWidget(self.error)
        actions = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        actions.accepted.connect(self._accept_valid)
        actions.rejected.connect(self.reject)
        layout.addWidget(actions)

    def _add_claim(self, source: str = "", date: str = "") -> None:
        row = self.claims.rowCount()
        self.claims.insertRow(row)
        self.claims.setItem(row, 0, QTableWidgetItem(source))
        self.claims.setItem(row, 1, QTableWidgetItem(date))
        self.preferred.addItem(f"Source claim {row + 1}", row)

    def _add_order(self, data: dict[str, Any] | None = None) -> None:
        data = data or {}
        row = self.orders.rowCount()
        self.orders.insertRow(row)
        relation = QComboBox()
        for label, value in (
            ("Before", "before"),
            ("After", "after"),
            ("Same transition", "same_as"),
        ):
            relation.addItem(label, value)
        relation.setCurrentIndex(
            max(0, relation.findData(data.get("relation", "before")))
        )
        target = QComboBox()
        for identity, name in self._events:
            target.addItem(name, f"event:{identity}")
        selected = data.get("anchor_b")
        if selected and target.findData(selected) < 0:
            target.addItem(f"Unavailable event ({selected})", selected)
        if selected:
            target.setCurrentIndex(target.findData(selected))
        offset = QDoubleSpinBox()
        offset.setRange(0, 1e12)
        offset.setDecimals(6)
        offset.setValue(float(data.get("min_offset_days", 0)))
        subject = QComboBox()
        subject.addItem("This event", f"event:{self._event_id}")
        for identity, name in self._events:
            if identity != self._event_id:
                subject.addItem(name, f"event:{identity}")
        anchor_a = data.get("anchor_a", f"event:{self._event_id}")
        if subject.findData(anchor_a) < 0:
            subject.addItem(f"Unavailable event ({anchor_a})", anchor_a)
        subject.setCurrentIndex(subject.findData(anchor_a))
        for column, widget in enumerate((subject, relation, target, offset)):
            self.orders.setCellWidget(row, column, widget)
        for combo in (subject, target):
            combo.setToolTip(combo.currentText())
            combo.currentTextChanged.connect(combo.setToolTip)
        offset.setEnabled(relation.currentData() != "same_as")
        relation.currentIndexChanged.connect(
            lambda: offset.setEnabled(relation.currentData() != "same_as")
        )

    def _remove_claim(self) -> None:
        row = self.claims.currentRow()
        if row < 0:
            return
        selected = int(self.preferred.currentData())
        self.claims.removeRow(row)
        self.preferred.clear()
        self.preferred.addItem("Keep the current event date", -1)
        for index in range(self.claims.rowCount()):
            self.preferred.addItem(f"Source claim {index + 1}", index)
        if selected != row and selected >= 0:
            self.preferred.setCurrentIndex(selected + 1 - int(selected > row))

    def _accept_valid(self) -> None:
        try:
            claims = []
            claim_ids = []
            for row in range(self.claims.rowCount()):
                source, date = self.claims.item(row, 0), self.claims.item(row, 1)
                if source is None or date is None:
                    raise ValueError("Each claim needs a source and a date.")
                claims.append((source.text(), date.text()))
                claim_ids.append(source.data(Qt.ItemDataRole.UserRole))
            constraints = []
            for row in range(self.orders.rowCount()):
                subject = self.orders.cellWidget(row, 0)
                relation = self.orders.cellWidget(row, 1)
                target = self.orders.cellWidget(row, 2)
                offset = self.orders.cellWidget(row, 3)
                assert isinstance(subject, QComboBox)
                assert isinstance(relation, QComboBox) and isinstance(target, QComboBox)
                assert isinstance(offset, QDoubleSpinBox)
                if not target.currentData():
                    raise ValueError("Choose another event for the ordering.")
                constraints.append(
                    {
                        "anchor_a": subject.currentData(),
                        "relation": relation.currentData(),
                        "anchor_b": target.currentData(),
                        "min_offset_days": offset.value() if offset.isEnabled() else 0,
                    }
                )
            self.result_metadata = author_temporal_evidence(
                self._metadata,
                self._parser,
                claims,
                int(self.preferred.currentData()),
                constraints,
                claim_ids,
            )
        except (ValueError, TypeError, KeyError) as exc:
            self.error.setText(str(exc))
            return
        self.accept()
