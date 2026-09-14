"""CSV column-mapping presentation with a visible input sample."""

from typing import Any

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPlainTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.transfer import LORE_KINDS
from src.gui.utils.style_helper import StyleHelper


class TransferCsvDialog(QDialog):
    """Collect mapping choices without reading files or interpreting records."""

    def __init__(
        self,
        path: str,
        headers: list[str],
        rows: list[dict[str, str]],
        fields: dict[str, list[str]],
        parent: QWidget,
    ) -> None:
        """Present supplied headers and examples for column mapping."""
        super().__init__(parent)
        self.setWindowTitle("Map CSV columns")
        self.resize(720, 560)
        self.headers = headers
        self.fields = fields
        self.setStyleSheet(StyleHelper.get_dialog_base_style())
        layout = QVBoxLayout(self)
        label = QLabel(
            path + "\nChoose the record kind and map each column. "
            "Unmapped columns are ignored."
        )
        label.setWordWrap(True)
        layout.addWidget(label)
        self.kind = QComboBox()
        self.kind.addItems(list(LORE_KINDS))
        if "source_id" in headers:
            self.kind.setCurrentText("relations")
        elif "lore_date" in headers:
            self.kind.setCurrentText("events")
        layout.addWidget(self.kind)
        self.table = QTableWidget(len(headers), 2)
        self.table.setHorizontalHeaderLabels(["Input column", "Import field"])
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)
        sample = QPlainTextEdit()
        sample.setStyleSheet(StyleHelper.get_input_field_style())
        sample.setReadOnly(True)
        sample.setPlainText("\n".join(str(row) for row in rows[:3]))
        sample.setMaximumHeight(110)
        layout.addWidget(sample)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.kind.currentTextChanged.connect(self._populate)
        self._populate()

    def _populate(self) -> None:
        for index, header in enumerate(self.headers):
            self.table.setItem(index, 0, QTableWidgetItem(header))
            choices = QComboBox()
            choices.addItem("Ignore this column", "")
            for field in self.fields[self.kind.currentText()]:
                choices.addItem(field, field)
            match = choices.findData(header.lower().strip())
            choices.setCurrentIndex(max(match, 0))
            self.table.setCellWidget(index, 1, choices)

    def options(self) -> dict[str, Any]:
        """Return the selected table kind and source-to-target mapping."""
        mapping = {}
        for index, header in enumerate(self.headers):
            widget = self.table.cellWidget(index, 1)
            if isinstance(widget, QComboBox):
                mapping[header] = widget.currentData()
        return {"kind": self.kind.currentText(), "mapping": mapping}
