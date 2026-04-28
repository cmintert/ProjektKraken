"""Dialog for importing JSON content pasted by the user."""

from typing import Any, Optional

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
)

from src.gui.utils.style_helper import StyleHelper


class PasteJsonImportDialog(QDialog):
    """Collects raw JSON text for import."""

    def __init__(self, parent: Optional[Any] = None) -> None:
        """Initialize the dialog.

        Args:
            parent: Optional parent widget.

        """
        super().__init__(parent)
        self.setWindowTitle("Import Pasted JSON")
        self.resize(860, 580)

        self._init_ui()

    def _init_ui(self) -> None:
        """Build the dialog UI."""
        layout = QVBoxLayout(self)

        header = QLabel("Paste JSON to import entities, events, and relations.")
        layout.addWidget(header)

        helper = QLabel(
            "Supported keys: entities, events, relations, tags, and _tags."
        )
        layout.addWidget(helper)

        self.json_edit = QPlainTextEdit(self)
        self.json_edit.setStyleSheet(StyleHelper.get_input_field_style())
        self.json_edit.setPlaceholderText(
            "{\n"
            "  \"entities\": [\n"
            "    {\n"
            "      \"name\": \"Example Entity\",\n"
            "      \"type\": \"character\",\n"
            "      \"tags\": [\"hero\", \"party\"]\n"
            "    }\n"
            "  ],\n"
            "  \"events\": []\n"
            "}"
        )
        layout.addWidget(self.json_edit)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Import")
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        self.json_edit.textChanged.connect(self._update_import_enabled)
        self.setStyleSheet(StyleHelper.get_dialog_base_style())

    def _update_import_enabled(self) -> None:
        """Enable import only when the text box has content."""
        has_text = bool(self.json_edit.toPlainText().strip())
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(has_text)

    def get_json_text(self) -> str:
        """Return the raw text currently entered by the user."""
        return self.json_edit.toPlainText()
