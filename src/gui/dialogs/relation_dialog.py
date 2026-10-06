"""Expert dialog shell for the shared relation authoring form."""

from typing import Any

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtWidgets import (
    QMessageBox as QMessageBox,
)

from src.gui.utils.style_helper import StyleHelper
from src.gui.widgets.relation_form import RelationForm


class RelationEditDialog(QDialog):
    """Keep the full relation editor available with shared lossless fields."""

    def __init__(self, parent: QWidget | None = None, **kwargs: Any) -> None:
        """Create the reusable form and a fixed approval footer."""
        super().__init__(parent)
        self.setWindowTitle("Edit Relation")
        self.setMinimumWidth(400)
        self.setStyleSheet(StyleHelper.get_dialog_base_style())
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            self.setMaximumHeight(
                max(400, int(screen.availableGeometry().height() * 0.85))
            )
        layout = QVBoxLayout(self)
        self.form = RelationForm(self, **kwargs)
        layout.addWidget(self.form, 1)
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)
        self.form.target_edit.setFocus()

    def __getattr__(self, name: str) -> Any:
        """Retain the existing dialog field API during the form extraction."""
        form = self.__dict__.get("form")
        if form is not None:
            return getattr(form, name)
        raise AttributeError(name)

    def accept(self) -> None:
        """Commit only after validating the shared form."""
        if self.form.validate():
            super().accept()
