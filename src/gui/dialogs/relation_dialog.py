"""
Relation Edit Dialog Module.

Provides a consolidated dialog for adding or editing relations,
featuring autocompletion for target entities/events.
"""

from typing import Any, Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QCompleter,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLineEdit,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class RelationEditDialog(QDialog):
    """
    A dialog for adding or editing a relationship.
    Supports autocompletion for the target field.
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        target_id: str = "",
        rel_type: str = "involved",
        is_bidirectional: bool = False,
        attributes: Dict[str, Any] = None,
        suggestion_items: list[tuple[str, str, str]] = None,  # (id, name, type)
    ) -> None:
        """
        Initializes the dialog.

        Args:
            parent: Parent widget.
            target_id: Initial target ID (for editing).
            rel_type: Initial relation type.
            is_bidirectional: Initial bidirectional state.
            attributes: Initial relation attributes.
            suggestion_items: List of (id, name, type) for autocompletion.
        """
        super().__init__(parent)
        self.setWindowTitle("Edit Relation")
        self.setMinimumWidth(400)

        self.attributes = attributes or {}

        main_layout = QVBoxLayout(self)

        # Form
        self.form_layout = QFormLayout()

        # 1. Target Input with Autocomplete
        self.target_edit = QLineEdit()
        self.target_edit.setPlaceholderText("Search for entity or event...")

        # Setup Completer
        self._name_to_id = {}
        self._id_to_name = {}

        display_names = []
        if suggestion_items:
            for item_id, name, item_type in suggestion_items:
                self._name_to_id[name] = item_id
                self._id_to_name[item_id] = name
                display_names.append(name)

            # Sort names for better UX
            display_names.sort(key=str.lower)

        completer = QCompleter(display_names, self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        self.target_edit.setCompleter(completer)

        # Pre-fill if editing
        if target_id:
            # Try to resolve ID to name for display, otherwise fallback to ID
            initial_text = self._id_to_name.get(target_id, target_id)
            self.target_edit.setText(initial_text)

        self.form_layout.addRow("Target:", self.target_edit)

        # 2. Relation Type
        self.type_edit = QComboBox()
        self.type_edit.addItems(
            ["caused", "involved", "located_at", "parent_of", "member_of", "owns"]
        )
        self.type_edit.setEditable(True)
        self.type_edit.setCurrentText(rel_type)
        self.form_layout.addRow("Type:", self.type_edit)

        # 3. Attributes Section
        self.attributes_group = QGroupBox("Attributes (Optional)")
        # Checkboxes removed per user request - always enabled, implicit save

        attr_layout = QFormLayout()

        # Weight
        self.weight_spin = QDoubleSpinBox()
        self.weight_spin.setRange(0.0, 10.0)
        self.weight_spin.setSingleStep(0.1)
        self.weight_spin.setValue(self.attributes.get("weight", 1.0))
        attr_layout.addRow("Weight:", self.weight_spin)

        # Confidence
        self.confidence_spin = QDoubleSpinBox()
        self.confidence_spin.setRange(0.0, 1.0)
        self.confidence_spin.setSingleStep(0.1)
        self.confidence_spin.setValue(self.attributes.get("confidence", 1.0))
        attr_layout.addRow("Confidence:", self.confidence_spin)

        # Source removed per user request

        # Notes
        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("Additional context...")
        self.notes_edit.setMaximumHeight(60)
        self.notes_edit.setPlainText(str(self.attributes.get("notes", "")))
        attr_layout.addRow("Notes:", self.notes_edit)

        self.attributes_group.setLayout(attr_layout)
        self.form_layout.addRow(self.attributes_group)

        # 4. Custom Attributes
        self.custom_attrs_group = QGroupBox("Custom Attributes")
        # Checkboxes removed per user request

        # Check if there are any non-standard attributes to load
        standard_keys = {"weight", "confidence", "notes"}
        custom_attrs = {
            k: v for k, v in self.attributes.items() if k not in standard_keys
        }

        custom_layout = QVBoxLayout()
        from src.gui.widgets.attribute_editor import AttributeEditorWidget

        self.custom_attr_editor = AttributeEditorWidget()
        self.custom_attr_editor.load_attributes(custom_attrs)
        custom_layout.addWidget(self.custom_attr_editor)
        self.custom_attrs_group.setLayout(custom_layout)

        self.form_layout.addRow(self.custom_attrs_group)

        # 5. Bidirectional
        self.bi_check = QCheckBox("Bidirectional (Create reverse link)")
        self.bi_check.setChecked(is_bidirectional)
        self.form_layout.addRow("", self.bi_check)

        main_layout.addLayout(self.form_layout)

        # Buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

        # Initial focus
        self.target_edit.setFocus()

    def _get_attributes(self) -> Dict[str, Any]:
        """Collects attributes from UI fields."""
        attrs = {}

        # Standard Attributes
        # Only include non-default values to keep data clean
        weight = self.weight_spin.value()
        if weight != 1.0:
            attrs["weight"] = weight

        confidence = self.confidence_spin.value()
        if confidence != 1.0:
            attrs["confidence"] = confidence

        # Source removed

        notes = self.notes_edit.toPlainText().strip()
        if notes:
            attrs["notes"] = notes

        # Custom Attributes
        custom = self.custom_attr_editor.get_attributes()
        # Prevent overwriting standard keys via custom editor
        # (Source is no longer standard)
        standard_keys = {"weight", "confidence", "notes"}
        for k, v in custom.items():
            if k not in standard_keys:
                attrs[k] = v

        return attrs

    def get_data(self) -> tuple[str, str, bool, Dict[str, Any]]:
        """
        Returns the dialog data.

        Returns:
            tuple: (target_id, rel_type, is_bidirectional, attributes)
        """
        text = self.target_edit.text().strip()

        # Resolve name to ID if possible, else use text as ID
        # (This handles manual ID entry or cross-project links)
        target_id = self._name_to_id.get(text, text)

        rel_type = self.type_edit.currentText().strip()
        is_bidirectional = self.bi_check.isChecked()
        attributes = self._get_attributes()

        return target_id, rel_type, is_bidirectional, attributes
