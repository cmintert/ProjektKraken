"""Shared lightweight name and type capture for entity creation."""

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from src.gui.widgets.choice_inputs import ScrollSafeComboBox


class EntityCreationDialog(QDialog):
    """Require an authored type unless capture explicitly supplies a default."""

    DEFAULT_TYPES = ("Character", "Location", "Faction", "Item", "Concept")

    def __init__(
        self,
        parent: QWidget | None = None,
        entity_types: list[str] | None = None,
        *,
        initial_type: str | None = None,
    ) -> None:
        """Show common and world-specific types, allowing custom classification."""
        super().__init__(parent)
        self.setWindowTitle("New Entity")
        self.setModal(True)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name_edit = QLineEdit(self)
        self.name_edit.setObjectName("entityNameEdit")
        self.type_combo = ScrollSafeComboBox(self)
        self.type_combo.setObjectName("entityTypeCombo")
        self.type_combo.setEditable(True)
        types = list(self.DEFAULT_TYPES)
        types.extend(
            sorted(
                {value.strip() for value in entity_types or [] if value.strip()}
                - set(types),
                key=str.casefold,
            )
        )
        self.type_combo.addItems(types)
        self.type_combo.setCurrentIndex(-1)
        type_edit = self.type_combo.lineEdit()
        assert type_edit is not None
        type_edit.setPlaceholderText("Choose or enter a type")
        if initial_type is not None:
            self.type_combo.setCurrentText(initial_type)
        form.addRow("&Name:", self.name_edit)
        form.addRow("&Type:", self.type_combo)
        layout.addLayout(form)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        create_button = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        assert create_button is not None
        create_button.setText("Create")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.name_edit.textChanged.connect(self._update_accept_enabled)
        self.type_combo.currentTextChanged.connect(self._update_accept_enabled)
        self._update_accept_enabled()
        self.name_edit.setFocus()

    def _update_accept_enabled(self) -> None:
        button = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        assert button is not None
        button.setEnabled(bool(self.name() and self.entity_type()))

    def accept(self) -> None:
        """Prevent Enter or programmatic acceptance of an incomplete request."""
        if self.name() and self.entity_type():
            super().accept()

    def name(self) -> str:
        """Return the trimmed entity name."""
        return self.name_edit.text().strip()

    def entity_type(self) -> str:
        """Return the explicitly chosen or entered type."""
        return self.type_combo.currentText().strip()
