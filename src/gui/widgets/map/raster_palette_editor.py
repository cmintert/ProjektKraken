"""Raster Palette Editor Dialog.

Provides a themed dialog for editing a raster layer's colour map
(LUT / palette) and value→item semantic mappings (raster attribute table).

Supports discrete palettes (value → colour + linked item) and continuous
gradients (start/end colour).

Overlap validation is enforced on accept for discrete mode: entries must
be mutually exclusive (no two entries may share the same value).
"""

import logging
import uuid
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QLinearGradient, QPainter
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from src.gui.utils.style_helper import StyleHelper
from src.gui.widgets.map.map_data_buffer import ColorEntry, ColorMap
from src.gui.widgets.map.raster_mapping import (
    normalize_value_entity_map,
    validate_no_overlaps,
)

logger = logging.getLogger(__name__)

_ITEM_TYPES = ["None", "Entity", "Event"]

_COL_VALUE = 0
_COL_COLOR = 1
_COL_LABEL = 2
_COL_ENTITY_ID = 3
_COL_TYPE = 4
_COL_DELETE = 5

_MAPPING_ID_ROLE = Qt.ItemDataRole.UserRole


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
    """Dialog for editing a raster layer's colour map and value→item mappings.

    Each discrete entry represents one class in the raster attribute table
    (RAT): a cell value, a display colour, a human-readable label, and an
    optional link to a world item (entity or event).

    Overlap validation is enforced on accept — entries must be mutually
    exclusive (no two entries may share the same value).

    Args:
        color_map: Current :class:`ColorMap` to edit.
        mode: ``"discrete"`` or ``"continuous"``.
        value_entity_map: Existing canonical VEM dict for this layer.
            Used to pre-populate label, entity ID, and item type columns.
        parent: Parent widget.
    """

    def __init__(
        self,
        color_map: ColorMap,
        mode: str = "discrete",
        value_entity_map: Optional[Dict[str, Any]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit Palette")
        self.setMinimumWidth(640)
        self._mode = mode
        self._color_map = color_map
        self._vem = normalize_value_entity_map(value_entity_map or {})
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

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _build_discrete_ui(self, layout: QVBoxLayout) -> None:
        layout.addWidget(QLabel("Value → Colour → Linked Item entries:"))

        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels(
            ["Value", "Colour", "Label", "Item ID", "Type", ""]
        )
        header = self._table.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(
                _COL_VALUE, QHeaderView.ResizeMode.ResizeToContents
            )
            header.setSectionResizeMode(_COL_COLOR, QHeaderView.ResizeMode.Fixed)
            header.setSectionResizeMode(_COL_LABEL, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(_COL_ENTITY_ID, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(
                _COL_TYPE, QHeaderView.ResizeMode.ResizeToContents
            )
            header.setSectionResizeMode(_COL_DELETE, QHeaderView.ResizeMode.Fixed)
            header.resizeSection(_COL_COLOR, 40)
            header.resizeSection(_COL_DELETE, 36)
        layout.addWidget(self._table)

        self._populate_discrete_rows()

        btn_add = QPushButton("+ Add Entry")
        btn_add.clicked.connect(lambda: self._add_entry_row(0, "#808080"))
        layout.addWidget(btn_add)

    def _populate_discrete_rows(self) -> None:
        """Merge ColorMap entries and VEM entries, populating the table."""
        vem_by_value: Dict[int, Dict[str, Any]] = {}
        for m in self._vem.get("mappings", []):
            v = m.get("value")
            if v is not None:
                vem_by_value[int(v)] = m

        seen_values: set = set()
        if self._color_map.type == "palette":
            for entry in self._color_map.entries:
                vem_entry = vem_by_value.get(entry.value, {})
                self._add_entry_row(
                    value=entry.value,
                    color=entry.color,
                    label=vem_entry.get("label", ""),
                    entity_id=vem_entry.get("entity_id") or entry.entity_id or "",
                    item_type=vem_entry.get("item_type") or "",
                    mapping_id=vem_entry.get("id") or str(uuid.uuid4()),
                )
                seen_values.add(entry.value)

        # Add VEM-only entries (no matching colour entry)
        for m in self._vem.get("mappings", []):
            v = m.get("value")
            if v is None or int(v) in seen_values:
                continue
            self._add_entry_row(
                value=int(v),
                color="#808080",
                label=m.get("label", ""),
                entity_id=m.get("entity_id") or "",
                item_type=m.get("item_type") or "",
                mapping_id=m.get("id") or str(uuid.uuid4()),
            )

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

        self._gradient_preview = _GradientPreview(
            start_color=self._color_map.gradient_start or "#000000",
            end_color=self._color_map.gradient_end or "#FFFFFF",
        )
        layout.addWidget(self._gradient_preview)

    def _refresh_gradient_preview(self, *_args: object) -> None:
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
        self,
        value: int = 0,
        color: str = "#808080",
        label: str = "",
        entity_id: str = "",
        item_type: str = "",
        mapping_id: Optional[str] = None,
    ) -> None:
        if not mapping_id:
            mapping_id = str(uuid.uuid4())
        row = self._table.rowCount()
        self._table.insertRow(row)

        # Col 0: value spinner; stable mapping_id stored as a property
        spin = QSpinBox()
        spin.setRange(0, 65535)
        spin.setValue(value)
        spin.setProperty("mapping_id", mapping_id)
        self._table.setCellWidget(row, _COL_VALUE, spin)

        # Col 1: colour picker
        btn = _ColorButton(color)
        self._table.setCellWidget(row, _COL_COLOR, btn)

        # Col 2: human-readable label
        label_edit = QLineEdit(label)
        label_edit.setPlaceholderText("Class label…")
        self._table.setCellWidget(row, _COL_LABEL, label_edit)

        # Col 3: entity / event UUID
        entity_edit = QLineEdit(entity_id)
        entity_edit.setPlaceholderText("Item UUID…")
        self._table.setCellWidget(row, _COL_ENTITY_ID, entity_edit)

        # Col 4: item type combo
        type_combo = QComboBox()
        type_combo.addItems(_ITEM_TYPES)
        itype = item_type.lower() if item_type else ""
        if itype == "entity":
            type_combo.setCurrentText("Entity")
        elif itype == "event":
            type_combo.setCurrentText("Event")
        else:
            type_combo.setCurrentText("None")
        self._table.setCellWidget(row, _COL_TYPE, type_combo)

        # Col 5: delete button
        remove_btn = QPushButton("✕")
        remove_btn.setFixedWidth(36)
        remove_btn.clicked.connect(lambda: self._remove_row_for(remove_btn))
        self._table.setCellWidget(row, _COL_DELETE, remove_btn)

    def _remove_row_for(self, btn: QPushButton) -> None:
        for r in range(self._table.rowCount()):
            if self._table.cellWidget(r, _COL_DELETE) is btn:
                self._table.removeRow(r)
                return

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def accept(self) -> None:
        """Validate overlap-free entries before closing the dialog."""
        if self._mode == "discrete":
            errors = validate_no_overlaps(self.result_value_entity_map())
            if errors:
                QMessageBox.warning(
                    self,
                    "Overlapping Entries",
                    "Fix the following conflicts before saving:\n\n"
                    + "\n".join(f"• {e}" for e in errors),
                )
                return
        super().accept()

    # ------------------------------------------------------------------
    # Results
    # ------------------------------------------------------------------

    def result_color_map(self) -> ColorMap:
        """Build a :class:`ColorMap` from the current dialog state.

        Returns:
            New ColorMap reflecting the user's edits.
        """
        if self._mode == "discrete":
            entries: List[ColorEntry] = []
            for r in range(self._table.rowCount()):
                spin = self._table.cellWidget(r, _COL_VALUE)
                btn = self._table.cellWidget(r, _COL_COLOR)
                entity_edit = self._table.cellWidget(r, _COL_ENTITY_ID)
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

    def result_value_entity_map(self) -> Dict[str, Any]:
        """Build a canonical ``value_entity_map`` dict from the current state.

        Returns:
            Canonical VEM dict ready for :class:`SetRasterMappingCommand`.
            For continuous/gradient mode, returns an empty canonical VEM.
        """
        if self._mode != "discrete":
            return normalize_value_entity_map({})

        mappings: List[Dict[str, Any]] = []
        for r in range(self._table.rowCount()):
            spin = self._table.cellWidget(r, _COL_VALUE)
            label_edit = self._table.cellWidget(r, _COL_LABEL)
            entity_edit = self._table.cellWidget(r, _COL_ENTITY_ID)
            type_combo = self._table.cellWidget(r, _COL_TYPE)
            if not isinstance(spin, QSpinBox):
                continue

            mapping_id = spin.property("mapping_id") or str(uuid.uuid4())
            label = (
                label_edit.text().strip() if isinstance(label_edit, QLineEdit) else ""
            )
            eid = (
                entity_edit.text().strip() if isinstance(entity_edit, QLineEdit) else ""
            )
            itype_str = (
                type_combo.currentText()
                if isinstance(type_combo, QComboBox)
                else "None"
            )
            item_type: Optional[str] = (
                None if itype_str == "None" else itype_str.lower()
            )

            entry: Dict[str, Any] = {
                "id": mapping_id,
                "value": spin.value(),
                "label": label,
            }
            if eid:
                entry["entity_id"] = eid
            if item_type:
                entry["item_type"] = item_type
            mappings.append(entry)

        return {"mode": self._vem.get("mode", "exact"), "mappings": mappings}
