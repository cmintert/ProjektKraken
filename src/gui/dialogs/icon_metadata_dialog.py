"""Edit custom icon metadata with an anchor preview."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPen, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from src.core.marker_icon import MarkerIconDefinition
from src.core.theme_manager import ThemeManager
from src.gui.utils.style_helper import StyleHelper


class IconAnchorPreview(QWidget):
    """Draw artwork and its normalized map attachment point."""

    def __init__(self, path: str, parent: QWidget) -> None:
        """Load preview artwork on the GUI thread."""
        super().__init__(parent)
        self._pixmap = QPixmap(path)
        self.anchor_x = 0.5
        self.anchor_y = 0.5
        self.setMinimumSize(200, 160)

    def paintEvent(self, event: QPaintEvent) -> None:
        """Render aspect-preserved artwork and a theme-colored anchor cross."""
        painter = QPainter(self)
        theme = ThemeManager().get_theme()
        painter.fillRect(self.rect(), QColor(theme["surface"]))
        size = self._pixmap.size().scaled(
            self.size() - QSize(24, 24),
            Qt.AspectRatioMode.KeepAspectRatio,
        )
        rect = QRectF(
            (self.width() - size.width()) / 2,
            (self.height() - size.height()) / 2,
            size.width(),
            size.height(),
        )
        painter.drawPixmap(rect, self._pixmap, QRectF(self._pixmap.rect()))
        x = rect.left() + rect.width() * self.anchor_x
        y = rect.top() + rect.height() * self.anchor_y
        painter.setPen(QPen(QColor(theme["primary"]), 2))
        painter.drawLine(int(x - 8), int(y), int(x + 8), int(y))
        painter.drawLine(int(x), int(y - 8), int(x), int(y + 8))


class IconMetadataDialog(QDialog):
    """Collect creator-editable metadata without modifying the library."""

    def __init__(
        self, definition: MarkerIconDefinition, path: str, parent: QWidget | None = None
    ) -> None:
        """Initialize controls from an immutable definition."""
        super().__init__(parent)
        self.setWindowTitle("Edit Project Icon")
        self.setMinimumWidth(380)
        self.setStyleSheet(StyleHelper.get_dialog_base_style())
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name_edit = QLineEdit(definition.name)
        self.category_edit = QLineEdit(definition.category or "")
        self.diameter = QDoubleSpinBox()
        self.diameter.setDecimals(3)
        self.diameter.setRange(0.001, 1_000_000)
        self.diameter.setSuffix(" px")
        self.diameter.setValue(definition.default_native_diameter_px)
        self.anchor_x = QDoubleSpinBox()
        self.anchor_y = QDoubleSpinBox()
        for control, value in (
            (self.anchor_x, definition.anchor.x),
            (self.anchor_y, definition.anchor.y),
        ):
            control.setRange(0, 1)
            control.setDecimals(3)
            control.setSingleStep(0.05)
            control.setValue(value)
        form.addRow("Name", self.name_edit)
        form.addRow("Category", self.category_edit)
        form.addRow("Native diameter", self.diameter)
        form.addRow("Anchor X (left → right)", self.anchor_x)
        form.addRow("Anchor Y (top → bottom)", self.anchor_y)
        layout.addLayout(form)
        self.preview = IconAnchorPreview(path, self)
        self.anchor_x.valueChanged.connect(self._update_preview)
        self.anchor_y.valueChanged.connect(self._update_preview)
        self._update_preview()
        layout.addWidget(self.preview)
        note = QLabel(
            "Existing markers that follow icon defaults update too. "
            "Individual size and anchor overrides are preserved."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        save = buttons.button(QDialogButtonBox.StandardButton.Save)
        self.name_edit.textChanged.connect(
            lambda text: save.setEnabled(bool(text.strip()))
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _update_preview(self) -> None:
        self.preview.anchor_x = self.anchor_x.value()
        self.preview.anchor_y = self.anchor_y.value()
        self.preview.update()

    def changes(self) -> dict[str, Any]:
        """Return a serializable edit intent for command validation."""
        return {
            "name": self.name_edit.text().strip(),
            "category": self.category_edit.text().strip(),
            "default_native_diameter_px": self.diameter.value(),
            "anchor": {"x": self.anchor_x.value(), "y": self.anchor_y.value()},
        }
