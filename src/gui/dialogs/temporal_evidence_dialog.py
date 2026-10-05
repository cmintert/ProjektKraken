"""Documentary source-date claims from serializable event snapshots."""

from copy import deepcopy
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
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
from src.gui.widgets.choice_inputs import ScrollSafeComboBox


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
        self.setWindowTitle("Date evidence")
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
            "Record different accounts separately. Choosing one as the event "
            "date keeps the other source dates available for reference."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self.claims = QTableWidget(0, 2)
        self.claims.setHorizontalHeaderLabels(
            ["Source / citation", "Date given by source"]
        )
        self.claims.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.claims.setStyleSheet(StyleHelper.get_table_widget_style())
        layout.addWidget(self.claims)
        self.preferred = ScrollSafeComboBox()
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
        self.claims.itemChanged.connect(self._update_preferred_labels)
        add = QPushButton("Add source date")
        add.clicked.connect(lambda: self._add_claim())
        layout.addWidget(add)
        remove = QPushButton("Remove selected source date")
        remove.clicked.connect(self._remove_claim)
        layout.addWidget(remove)
        layout.addWidget(QLabel("Use this source as the event date"))
        layout.addWidget(self.preferred)
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
        self.preferred.addItem(source or f"Source {row + 1}", row)

    def _update_preferred_labels(self) -> None:
        """Keep source choices readable as citation cells are edited."""
        for row in range(self.claims.rowCount()):
            source = self.claims.item(row, 0)
            self.preferred.setItemText(
                row + 1,
                source.text().strip() if source and source.text().strip()
                else f"Source {row + 1}",
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
            source = self.claims.item(index, 0)
            self.preferred.addItem(
                source.text().strip() if source and source.text().strip()
                else f"Source {index + 1}",
                index,
            )
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
            self.result_metadata = author_temporal_evidence(
                self._metadata,
                self._parser,
                claims,
                int(self.preferred.currentData()),
                deepcopy(self._metadata.get("constraints", [])),
                claim_ids,
            )
        except (ValueError, TypeError, KeyError) as exc:
            self.error.setText(str(exc))
            return
        self.accept()
