"""Attribute Delegate Module.

Provides type-aware editing widgets for the attribute editor table.
"""

import logging
from typing import Any, Optional, cast

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QWidget,
)

logger = logging.getLogger(__name__)


class AttributeDelegate(QStyledItemDelegate):
    """A delegate for rendering and editing attribute values based on their type.

    Provides native widgets for different data types:
    - Boolean: Checkbox
    - Number: SpinBox
    - String: Line edit (default)
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the attribute delegate.

        Args:
            parent: Parent widget.
        """
        super().__init__(parent)
        self._attribute_widget: Any = None

    def set_attribute_widget(self, widget: QWidget) -> None:
        """Set reference to the AttributeEditorWidget for accessing type info.

        Args:
            widget: The AttributeEditorWidget instance.
        """
        self._attribute_widget = widget

    def createEditor(
        self,
        parent: QWidget,
        option: QStyleOptionViewItem,
        index: Any,
    ) -> QWidget:
        """Create the appropriate editor widget based on attribute type.

        Args:
            parent: Parent widget for the editor.
            option: Style options.
            index: Model index being edited.

        Returns:
            Editor widget or None to use default.
        """
        # Only customize column 1 (Value column)
        if index.column() != 1:
            return super().createEditor(parent, option, index)

        if not self._attribute_widget:
            return super().createEditor(parent, option, index)

        # Get the type from column 2 (Type column)
        table = self._attribute_widget.table
        row = index.row()
        type_widget = table.cellWidget(row, 2)

        if not type_widget:
            return super().createEditor(parent, option, index)

        value_type = type_widget.currentText()

        # Create appropriate editor based on type
        if value_type == "Boolean":
            # Use checkbox for boolean values
            checkbox = QCheckBox(parent)
            return checkbox

        elif value_type == "Number":
            # Use double spinbox for numbers
            spinbox = QDoubleSpinBox(parent)
            spinbox.setRange(-999999999.0, 999999999.0)
            spinbox.setDecimals(6)
            return spinbox

        # Default to line edit for strings
        return super().createEditor(parent, option, index)

    def setEditorData(self, editor: QWidget, index: Any) -> None:
        """Set the editor's initial value from the model.

        Args:
            editor: The editor widget.
            index: Model index.
        """
        value = index.model().data(index, Qt.ItemDataRole.EditRole)

        if isinstance(editor, QCheckBox):
            # Parse boolean value
            is_checked = str(value).lower() in {"true", "1", "yes", "on"}
            editor.setChecked(is_checked)

        elif isinstance(editor, QDoubleSpinBox):
            # Parse numeric value
            try:
                numeric_value = float(value) if value else 0.0
                editor.setValue(numeric_value)
            except (ValueError, TypeError):
                editor.setValue(0.0)

        else:
            # Default string handling
            super().setEditorData(editor, index)

    def setModelData(
        self,
        editor: QWidget,
        model: Any,
        index: Any,
    ) -> None:
        """Update the model with the editor's value.

        Args:
            editor: The editor widget.
            model: The data model.
            index: Model index.
        """
        if isinstance(editor, QCheckBox):
            # Store boolean as string
            value = "True" if editor.isChecked() else "False"
            model.setData(index, value, Qt.ItemDataRole.EditRole)

        elif isinstance(editor, QDoubleSpinBox):
            # Store number as string
            value = str(editor.value())
            model.setData(index, value, Qt.ItemDataRole.EditRole)

        else:
            # Default string handling
            super().setModelData(editor, model, index)

    def updateEditorGeometry(
        self,
        editor: QWidget,
        option: QStyleOptionViewItem,
        index: Any,
    ) -> None:
        """Update the editor widget's geometry.

        Args:
            editor: The editor widget.
            option: Style options.
            index: Model index.
        """
        editor.setGeometry(cast(Any, option).rect)
