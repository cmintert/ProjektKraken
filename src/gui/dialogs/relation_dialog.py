"""
Relation Edit Dialog Module.

Provides a consolidated dialog for adding or editing relations,
featuring autocompletion for target entities/events.
"""

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QCompleter,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
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
        suggestion_items: list[tuple[str, str, str]] = None,  # (id, name, type)
    ) -> None:
        """
        Initializes the dialog.

        Args:
            parent: Parent widget.
            target_id: Initial target ID (for editing).
            rel_type: Initial relation type.
            is_bidirectional: Initial bidirectional state.
            suggestion_items: List of (id, name, type) for autocompletion.
        """
        super().__init__(parent)
        self.setWindowTitle("Edit Relation")
        self.setMinimumWidth(400)

        self.layout = QVBoxLayout(self)

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

        # 3. Bidirectional (Only relevant for new relations usually, but fine to expose)
        self.bi_check = QCheckBox("Bidirectional (Create reverse link)")
        self.bi_check.setChecked(is_bidirectional)
        self.form_layout.addRow("", self.bi_check)

        self.layout.addLayout(self.form_layout)

        # Buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout.addWidget(self.button_box)

        # Initial focus
        self.target_edit.setFocus()

    def get_data(self) -> tuple[str, str, bool]:
        """
        Returns the dialog data.

        Returns:
            tuple: (target_id, rel_type, is_bidirectional)
        """
        text = self.target_edit.text().strip()

        # Resolve name to ID if possible, else use text as ID
        # (This handles manual ID entry or cross-project links)
        target_id = self._name_to_id.get(text, text)

        rel_type = self.type_edit.currentText().strip()
        is_bidirectional = self.bi_check.isChecked()

        return target_id, rel_type, is_bidirectional
