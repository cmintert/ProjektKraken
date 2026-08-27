"""Attribute Editor Widget Module.

Provides a table-based interface for editing key-value attribute pairs with support for
different data types.
"""

from typing import Any, Dict, List, Optional

from PySide6.QtCore import Signal, Slot
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

from src.gui.widgets.standard_buttons import DestructiveButton, StandardButton


class AttributeEditorWidget(QWidget):
    """A widget for editing a dictionary of attributes (Key-Value pairs).

    Supports String, Number (Float/Int), Boolean, and optional null values.
    """

    attributes_changed = Signal()

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        allow_null: bool = False,
    ) -> None:
        """Initializes the AttributeEditorWidget.

        Args:
            parent (QWidget, optional): The parent widget. Defaults to None.
            allow_null: Whether the type selector permits an explicit null value.

        """
        super().__init__(parent)
        self._allow_null = allow_null
        main_layout = QVBoxLayout(self)
        from src.gui.utils.style_helper import StyleHelper

        StyleHelper.apply_compact_spacing(main_layout)

        # Toolbar
        self.toolbar_layout = QHBoxLayout()
        self.btn_add = StandardButton("Add Attribute")
        self.btn_add.clicked.connect(self._on_add)
        self.btn_remove = DestructiveButton("Remove")
        self.btn_remove.clicked.connect(self._on_remove)
        self.btn_remove.setEnabled(False)

        self.toolbar_layout.addWidget(self.btn_add)
        self.toolbar_layout.addWidget(self.btn_remove)
        self.toolbar_layout.addStretch()
        main_layout.addLayout(self.toolbar_layout)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Name", "Value", "Type"])
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.table.itemChanged.connect(self._on_item_changed)
        self.table.itemSelectionChanged.connect(self._update_button_states)

        # Set up custom delegate for type-aware editing
        from src.gui.delegates.attribute_delegate import AttributeDelegate

        self._delegate = AttributeDelegate(self.table)
        self._delegate.set_attribute_widget(self)
        self.table.setItemDelegateForColumn(1, self._delegate)  # Apply to Value column

        main_layout.addWidget(self.table)

        self._block_signals = False
        self._hidden_attributes: Dict[str, Any] = {}

    def load_attributes(
        self,
        attributes: Dict[str, Any],
        *,
        show_hidden: bool = False,
    ) -> None:
        """Populate the table, hiding underscore-prefixed keys by default.

        Hidden values remain preserved by :meth:`get_attributes` even though
        their rows are not displayed.
        """
        self._block_signals = True
        self.table.setRowCount(0)
        self._hidden_attributes = (
            {}
            if show_hidden
            else {
                key: value
                for key, value in attributes.items()
                if key.startswith("_")
            }
        )
        display_attributes = (
            attributes
            if show_hidden
            else {
                key: value
                for key, value in attributes.items()
                if not key.startswith("_")
            }
        )

        for key, value in display_attributes.items():
            self._add_row(key, value)

        self._block_signals = False

    def get_attributes(self) -> Dict[str, Any]:
        """Returns a dictionary representing the current table state."""
        attrs = dict(self._hidden_attributes)
        for row in range(self.table.rowCount()):
            key_item = self.table.item(row, 0)
            val_item = self.table.item(row, 1)
            type_widget = self.table.cellWidget(row, 2)

            if (
                not key_item
                or not val_item
                or not isinstance(type_widget, QComboBox)
            ):
                continue

            key = key_item.text().strip()
            if not key:
                continue

            raw_val = val_item.text()
            val_type = type_widget.currentText()

            parsed_val = self._parse_value(raw_val, val_type)
            attrs[key] = parsed_val

        return attrs

    def update_attribute_value(self, key: str, value: Any) -> None:
        """Updates the value of an existing attribute in the table without breaking focus.

        Args:
            key (str): The attribute key.
            value (Any): The new value.
        """
        self._block_signals = True
        try:
            for row in range(self.table.rowCount()):
                key_item = self.table.item(row, 0)
                if key_item and key_item.text().strip() == key:
                    val_item = self.table.item(row, 1)
                    if val_item:
                        str_val = str(value) if value is not None else ""
                        val_item.setText(str_val)
                    break
        finally:
            self._block_signals = False

    def _add_row(self, key: str = "", value: Optional[Any] = None) -> None:
        """Adds a new row to the attribute table.

        Args:
            key (str, optional): The attribute key. Defaults to "".
            value (Any, optional): The attribute value. Defaults to None.

        """
        row = self.table.rowCount()
        self.table.insertRow(row)

        # Determine strict type
        val_type = "String"
        if value is None and self._allow_null:
            val_type = "Null"
            str_val = ""
        elif isinstance(value, bool):
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
        if self._allow_null:
            combo.addItem("Null")
        combo.setCurrentText(val_type)
        combo.currentTextChanged.connect(lambda: self._on_type_changed(row))
        self.table.setCellWidget(row, 2, combo)

    def update_suggestions(self, keys: List[str]) -> None:
        """Updates the attribute key suggestions.

        Args:
            keys: List of existing attribute keys.

        """
        self._suggestion_keys = keys

    @Slot()
    def _on_add(self) -> None:
        """Handles adding a new attribute.

        Prompts for the attribute key and adds a new row.
        """
        suggestions = getattr(self, "_suggestion_keys", [])
        key, ok = QInputDialog.getItem(
            self, "New Attribute", "Attribute Name:", suggestions, 0, True
        )
        if ok and key:
            key = key.strip()
            # Check for duplicates
            existing_keys = self.get_attributes().keys()
            if key in existing_keys:
                QMessageBox.warning(
                    self,
                    "Duplicate Attribute",
                    f"The attribute name '{key}' already exists.\n\n"
                    "Each attribute must have a unique name.\n\n"
                    "To fix:\n"
                    "1. Choose a different name\n"
                    "2. Or modify the existing attribute with this name\n"
                    "3. Consider using a naming pattern like 'name_2', 'name_v2'",
                )
                return

            self._block_signals = True
            self._add_row(key, "")
            self._block_signals = False
            self.attributes_changed.emit()

    @Slot()
    def _on_remove(self) -> None:
        """Handles removing the selected attribute."""
        current_row = self.table.currentRow()
        if current_row >= 0:
            self.table.removeRow(current_row)
            self.attributes_changed.emit()

    def _update_button_states(self) -> None:
        """Updates enabled state for Remove button based on selection."""
        has_selection = self.table.currentRow() >= 0
        self.btn_remove.setEnabled(has_selection)

    @Slot(QTableWidgetItem)
    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        """Handles table item changes.

        Args:
            item (QTableWidgetItem): The changed item.

        """
        if not self._block_signals:
            self.attributes_changed.emit()

    @Slot(int)
    def _on_type_changed(self, row: int) -> None:
        """Handles attribute type changes.

        Args:
            row (int): The row number of the changed type.

        """
        if not self._block_signals:
            self.attributes_changed.emit()

    def _parse_value(self, raw_val: str, val_type: str) -> Any:
        """Parses a raw string value to the specified type.

        Args:
            raw_val (str): The raw value as a string.
            val_type: The selected value type.

        Returns:
            Any: The parsed value in the appropriate type.

        """
        if val_type == "Null" and self._allow_null:
            return None

        if val_type == "Number":
            try:
                if "." in raw_val:
                    return float(raw_val)
                return int(raw_val)
            except ValueError:
                return 0  # Fallback

        if val_type == "Boolean":
            return raw_val.lower() in {"true", "1", "yes", "on"}

        return raw_val
