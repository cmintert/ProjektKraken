"""Raster Palette Editor Dialog.

Provides a themed dialog for editing a raster layer's colour map
(LUT / palette).  Supports discrete palettes (value → colour list)
and continuous gradients (start/end colour).
"""

import logging
from typing import List, Optional

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor, QLinearGradient, QPainter
from PySide6.QtWidgets import (
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from src.gui.utils.style_helper import StyleHelper
from src.gui.widgets.map.map_data_buffer import ColorEntry, ColorMap

logger = logging.getLogger(__name__)


class _ColorButton(QPushButton):
    """Small push-button that displays and lets the user pick a colour."""

    color_changed = Signal(str)

    def __init__(
        self, color_hex: str = "#808080", parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._color = color_hex
        self.setFixedSize(28, 28)
        self._apply_color()
        self.clicked.connect(self._pick)

    @property
    def color_hex(self) -> str:
        return self._color

    @color_hex.setter
    def color_hex(self, value: str) -> None:
        self._color = value
        self._apply_color()

    def _apply_color(self) -> None:
        self.setStyleSheet(
            f"background-color: {self._color}; border: 1px solid #888; border-radius: 3px;"
        )

    def _pick(self) -> None:
        c = QColorDialog.getColor(QColor(self._color), self, "Pick Colour")
        if c.isValid():
            self._color = c.name()
            self._apply_color()
            self.color_changed.emit(self._color)


class _GradientPreview(QFrame):
    """A horizontal strip showing the current gradient from start to end colour."""

    def __init__(
        self,
        start_color: str = "#000000",
        end_color: str = "#FFFFFF",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setFixedHeight(28)
        self.setMinimumWidth(120)
        self._start = start_color
        self._end = end_color
        self.setFrameShape(QFrame.Shape.StyledPanel)

    def set_colors(self, start: str, end: str) -> None:
        """Update the gradient colours and repaint."""
        self._start = start
        self._end = end
        self.update()

    def paintEvent(self, event: object) -> None:  # type: ignore[override]
        painter = QPainter(self)
        grad = QLinearGradient(0, 0, self.width(), 0)
        grad.setColorAt(0.0, QColor(self._start))
        grad.setColorAt(1.0, QColor(self._end))
        painter.fillRect(self.rect(), grad)
        painter.end()


class RasterPaletteEditor(QDialog):
    """Dialog for editing a raster layer's colour map.

    Args:
        color_map: Current :class:`ColorMap` to edit.
        mode: ``"discrete"`` or ``"continuous"``.
        parent: Parent widget.
    """

    def __init__(
        self,
        color_map: ColorMap,
        mode: str = "discrete",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit Palette")
        self.setMinimumWidth(460)
        self._mode = mode
        self._color_map = color_map
        self.setStyleSheet(StyleHelper.get_dialog_base_style())
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        if self._mode == "discrete":
            self._build_discrete_ui(layout)
        else:
            self._build_gradient_ui(layout)

        # Buttons
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _build_discrete_ui(self, layout: QVBoxLayout) -> None:
        layout.addWidget(QLabel("Value → Colour → Entity entries:"))

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["Value", "Colour", "Entity", ""])
        header = self._table.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
            header.resizeSection(1, 40)
            header.resizeSection(3, 36)
        layout.addWidget(self._table)

        # Populate from existing palette
        if self._color_map.type == "palette":
            for entry in self._color_map.entries:
                self._add_entry_row(
                    entry.value, entry.color, entity_id=entry.entity_id or ""
                )

        btn_add = QPushButton("+ Add Entry")
        btn_add.clicked.connect(lambda: self._add_entry_row(0, "#808080"))
        layout.addWidget(btn_add)

    def _build_gradient_ui(self, layout: QVBoxLayout) -> None:
        layout.addWidget(QLabel("Gradient start / end colours:"))

        row = QHBoxLayout()
        row.addWidget(QLabel("Start:"))
        self._start_btn = _ColorButton(self._color_map.gradient_start or "#000000")
        self._start_btn.color_changed.connect(self._refresh_gradient_preview)
        row.addWidget(self._start_btn)
        row.addWidget(QLabel("End:"))
        self._end_btn = _ColorButton(self._color_map.gradient_end or "#FFFFFF")
        self._end_btn.color_changed.connect(self._refresh_gradient_preview)
        row.addWidget(self._end_btn)
        row.addStretch()
        layout.addLayout(row)

        # Gradient preview strip
        self._gradient_preview = _GradientPreview(
            start_color=self._color_map.gradient_start or "#000000",
            end_color=self._color_map.gradient_end or "#FFFFFF",
        )
        layout.addWidget(self._gradient_preview)

    def _refresh_gradient_preview(self, *_args: object) -> None:
        """Update the gradient preview strip from current button colours."""
        if (
            hasattr(self, "_gradient_preview")
            and hasattr(self, "_start_btn")
            and hasattr(self, "_end_btn")
        ):
            self._gradient_preview.set_colors(
                self._start_btn.color_hex, self._end_btn.color_hex
            )

    # ------------------------------------------------------------------
    # Discrete table helpers
    # ------------------------------------------------------------------

    def _add_entry_row(
        self, value: int = 0, color: str = "#808080", entity_id: str = ""
    ) -> None:
        row = self._table.rowCount()
        self._table.insertRow(row)

        spin = QSpinBox()
        spin.setRange(0, 65535)
        spin.setValue(value)
        self._table.setCellWidget(row, 0, spin)

        btn = _ColorButton(color)
        self._table.setCellWidget(row, 1, btn)

        entity_edit = QLineEdit(entity_id)
        entity_edit.setPlaceholderText("entity UUID or name…")
        self._table.setCellWidget(row, 2, entity_edit)

        remove_btn = QPushButton("✕")
        remove_btn.setFixedWidth(36)
        remove_btn.clicked.connect(lambda: self._remove_row_for(remove_btn))
        self._table.setCellWidget(row, 3, remove_btn)

    def _remove_row_for(self, btn: QPushButton) -> None:
        """Remove the table row containing *btn*."""
        for r in range(self._table.rowCount()):
            if self._table.cellWidget(r, 3) is btn:
                self._table.removeRow(r)
                return

    def _remove_row(self, row: int) -> None:
        self._table.removeRow(row)

    # ------------------------------------------------------------------
    # Result
    # ------------------------------------------------------------------

    def result_color_map(self) -> ColorMap:
        """Build a :class:`ColorMap` from the current dialog state.

        Returns:
            New ColorMap reflecting the user's edits.
        """
        if self._mode == "discrete":
            entries: List[ColorEntry] = []
            for r in range(self._table.rowCount()):
                spin = self._table.cellWidget(r, 0)
                btn = self._table.cellWidget(r, 1)
                entity_edit = self._table.cellWidget(r, 2)
                if isinstance(spin, QSpinBox) and isinstance(btn, _ColorButton):
                    eid: Optional[str] = None
                    if (
                        isinstance(entity_edit, QLineEdit)
                        and entity_edit.text().strip()
                    ):
                        eid = entity_edit.text().strip()
                    entries.append(
                        ColorEntry(
                            value=spin.value(), color=btn.color_hex, entity_id=eid
                        )
                    )
            return ColorMap(type="palette", entries=entries)
        else:
            return ColorMap(
                type="gradient",
                gradient_start=self._start_btn.color_hex,
                gradient_end=self._end_btn.color_hex,
            )
