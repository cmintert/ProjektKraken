"""
Attribute Editor Widget Module.

Provides a table-based interface for editing key-value attribute pairs
with support for different data types.
"""

from typing import Any, Dict, Optional, Union

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.gui.widgets.standard_buttons import StandardButton


class AttributeEditorWidget(QWidget):
    """
    A widget for editing a dictionary of attributes (Key-Value pairs).
    Supports String, Number (Float/Int), and Boolean types.
    """

    attributes_changed = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Initializes the AttributeEditorWidget.

        Args:
            parent (QWidget, optional): The parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        from src.gui.utils.style_helper import StyleHelper

        StyleHelper.apply_compact_spacing(self.layout)

        # Toolbar
        self.toolbar_layout = QHBoxLayout()
        self.btn_add = StandardButton("Add Attribute")
        self.btn_add.clicked.connect(self._on_add)
        self.btn_remove = StandardButton("Remove")
        self.btn_remove.setStyleSheet(StyleHelper.get_destructive_button_style())
        self.btn_remove.clicked.connect(self._on_remove)

        self.toolbar_layout.addWidget(self.btn_add)
        self.toolbar_layout.addWidget(self.btn_remove)
        self.toolbar_layout.addStretch()
        self.layout.addLayout(self.toolbar_layout)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Key", "Value", "Type"])
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.itemChanged.connect(self._on_item_changed)

        self.layout.addWidget(self.table)

        self._block_signals = False

    def load_attributes(self, attributes: Dict[str, Any]) -> None:
        """Populates the table with the given attributes dictionary."""
        self._block_signals = True
        self.table.setRowCount(0)

        for key, value in attributes.items():
            self._add_row(key, value)

        self._block_signals = False

    def get_attributes(self) -> Dict[str, Any]:
        """Returns a dictionary representing the current table state."""
        attrs = {}
        for row in range(self.table.rowCount()):
            key_item = self.table.item(row, 0)
            val_item = self.table.item(row, 1)
            type_widget = self.table.cellWidget(row, 2)

            if not key_item or not val_item or not type_widget:
                continue

            key = key_item.text().strip()
            if not key:
                continue

            raw_val = val_item.text()
            val_type = type_widget.currentText()

            parsed_val = self._parse_value(raw_val, val_type)
            attrs[key] = parsed_val

        return attrs

    def _add_row(self, key: str = "", value: Optional[Any] = None) -> None:
        """
        Adds a new row to the attribute table.

        Args:
            key (str, optional): The attribute key. Defaults to "".
            value (Any, optional): The attribute value. Defaults to None.
        """
        row = self.table.rowCount()
        self.table.insertRow(row)

        # Determine strict type
        val_type = "String"
        if isinstance(value, bool):
            val_type = "Boolean"
            str_val = str(value)  # "True"/"False"
        elif isinstance(value, (int, float)):
            val_type = "Number"
            str_val = str(value)
        else:
            str_val = str(value) if value is not None else ""

        # Key
        self.table.setItem(row, 0, QTableWidgetItem(key))

        # Value
        self.table.setItem(row, 1, QTableWidgetItem(str_val))

        # Type ComboBox
        combo = QComboBox()
        combo.addItems(["String", "Number", "Boolean"])
        combo.setCurrentText(val_type)
        combo.currentTextChanged.connect(lambda: self._on_type_changed(row))
        self.table.setCellWidget(row, 2, combo)

    def _on_add(self) -> None:
        """
        Handles adding a new attribute.

        Prompts for the attribute key and adds a new row.
        """
        key, ok = QInputDialog.getText(self, "New Attribute", "Attribute Key:")
        if ok and key:
            # Check for duplicates?
            existing_keys = self.get_attributes().keys()
            if key in existing_keys:
                QMessageBox.warning(self, "Duplicate", f"Key '{key}' already exists.")
                return

            self._block_signals = True
            self._add_row(key, "")
            self._block_signals = False
            self.attributes_changed.emit()

    def _on_remove(self) -> None:
        """
        Handles removing the selected attribute.
        """
        current_row = self.table.currentRow()
        if current_row >= 0:
            self.table.removeRow(current_row)
            self.attributes_changed.emit()

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        """
        Handles table item changes.

        Args:
            item (QTableWidgetItem): The changed item.
        """
        if not self._block_signals:
            self.attributes_changed.emit()

    def _on_type_changed(self, row: int) -> None:
        """
        Handles attribute type changes.

        Args:
            row (int): The row number of the changed type.
        """
        if not self._block_signals:
            self.attributes_changed.emit()

    def _parse_value(self, raw_val: str, val_type: str) -> Union[str, int, float, bool]:
        """
        Parses a raw string value to the specified type.

        Args:
            raw_val (str): The raw value as a string.
            val_type (str): The target type ("String", "Number", or "Boolean").

        Returns:
            Any: The parsed value in the appropriate type.
        """
        if val_type == "Number":
            try:
                if "." in raw_val:
                    return float(raw_val)
                return int(raw_val)
            except ValueError:
                return 0  # Fallback
        elif val_type == "Boolean":
            return raw_val.lower() in ("true", "1", "yes", "on")
        return raw_val
