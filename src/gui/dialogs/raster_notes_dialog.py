"""Raster Layer Notes Dialog.

A simple text-editor dialog for attaching free-form notes to a raster layer.
Notes are persisted via :class:`~src.commands.raster_commands.SetRasterNotesCommand`.
"""

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTextEdit,
    QVBoxLayout,
)


class RasterNotesDialog(QDialog):
    """Dialog for editing raster layer notes.

    Args:
        layer_name: Human-readable name of the raster layer (shown in title).
        current_notes: Existing notes text to pre-populate the editor.
        parent: Optional parent widget.
    """

    def __init__(
        self,
        layer_name: str,
        current_notes: str = "",
        parent: Optional[object] = None,
    ) -> None:
        """Initialize the raster notes editor."""
        super().__init__(parent)  # type: ignore[arg-type]
        self.setWindowTitle(f"Notes — {layer_name}")
        self.setMinimumSize(400, 300)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Layer notes:"))

        self._text_edit = QTextEdit()
        self._text_edit.setPlainText(current_notes)
        self._text_edit.setPlaceholderText("Add notes about this raster layer…")
        layout.addWidget(self._text_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_notes(self) -> str:
        """Return the edited notes text (stripped of leading/trailing whitespace).

        Returns:
            The current text content of the editor.
        """
        return self._text_edit.toPlainText().strip()
