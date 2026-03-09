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

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QColor, QDoubleValidator, QLinearGradient, QPainter
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QCompleter,
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
from src.gui.widgets.map.map_data_buffer import (
    ColorEntry,
    ColorMap,
    format_display_value,
)
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


_AUTO_COLORS = [
    "#e41a1c",
    "#377eb8",
    "#4daf4a",
    "#984ea3",
    "#ff7f00",
    "#a65628",
    "#f781bf",
    "#999999",
    "#66c2a5",
    "#fc8d62",
    "#8da0cb",
    "#e78ac3",
]


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
        buffer_min: Minimum non-zero data value in the buffer (continuous only).
        buffer_max: Maximum data value in the buffer (continuous only).
        entities: List of entity objects with ``.id`` and ``.name`` attributes.
            Used to populate the entity name completer in discrete mode.
        events: List of event objects with ``.id`` and ``.name`` attributes.
            Used to populate the event name completer in discrete mode.
        parent: Parent widget.
    """

    def __init__(
        self,
        color_map: ColorMap,
        mode: str = "discrete",
        value_entity_map: Optional[Dict[str, Any]] = None,
        buffer_min: Optional[float] = None,
        buffer_max: Optional[float] = None,
        entities: Optional[List[Any]] = None,
        events: Optional[List[Any]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        mode_label = "Discrete" if mode == "discrete" else "Continuous"
        self.setWindowTitle(f"Edit Palette — {mode_label} Mode")
        self.setMinimumWidth(680)
        self._mode = mode
        self._color_map = color_map
        self._vem = normalize_value_entity_map(value_entity_map or {})
        self._buffer_min = buffer_min
        self._buffer_max = buffer_max
        self.setStyleSheet(StyleHelper.get_dialog_base_style())

        # Build name↔ID lookup tables from the provided entity/event lists.
        self._name_to_id: Dict[str, str] = {}
        self._id_to_name: Dict[str, str] = {}
        self._entity_id_set: set = set()
        self._event_id_set: set = set()
        for obj in entities or []:
            name = getattr(obj, "name", None) or ""
            oid = getattr(obj, "id", None) or ""
            if name and oid:
                self._name_to_id[name] = oid
                self._id_to_name[oid] = name
                self._entity_id_set.add(oid)
        for obj in events or []:
            name = getattr(obj, "name", None) or ""
            oid = getattr(obj, "id", None) or ""
            if name and oid:
                self._name_to_id[name] = oid
                self._id_to_name[oid] = name
                self._event_id_set.add(oid)
        self._all_item_names: List[str] = sorted(self._name_to_id.keys(), key=str.lower)

        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Mode info banner
        if self._mode == "discrete":
            banner_text = (
                "📊  <b>Discrete mode</b> — each pixel value maps to a named class. "
                "Assign colours, labels, and optionally link each value to a world item."
            )
        else:
            banner_text = (
                "📈  <b>Continuous mode</b> — pixel values form a smooth scalar gradient. "
                "Choose start and end colours for the colour ramp."
            )
        banner = QLabel(banner_text)
        banner.setTextFormat(Qt.TextFormat.RichText)
        banner.setWordWrap(True)
        banner.setStyleSheet(StyleHelper.get_preview_label_style())
        layout.addWidget(banner)

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

        # Auto-color toolbar
        auto_row = QHBoxLayout()
        auto_row.setSpacing(4)
        btn_auto_color = QPushButton("🎨 Auto-color")
        btn_auto_color.setToolTip(
            "Assign a qualitative colour palette to each row in sequence"
        )
        btn_auto_color.clicked.connect(self._on_auto_color)
        auto_row.addWidget(btn_auto_color)

        btn_export = QPushButton("⬆ Export…")
        btn_export.setToolTip("Export palette to JSON")
        btn_export.clicked.connect(self._on_export_palette)
        auto_row.addWidget(btn_export)

        btn_import = QPushButton("⬇ Import…")
        btn_import.setToolTip("Import palette from JSON")
        btn_import.clicked.connect(self._on_import_palette)
        auto_row.addWidget(btn_import)

        auto_row.addStretch()
        layout.addLayout(auto_row)

        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels(
            ["Value", "Colour", "Label", "Linked Item", "Type", ""]
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

        # Data range info + stretch controls
        if self._buffer_min is not None and self._buffer_max is not None:
            data_range_label = QLabel(
                f"Data range: {self._buffer_min:.0f} – {self._buffer_max:.0f}"
            )
            data_range_label.setStyleSheet(StyleHelper.get_preview_label_style())
            layout.addWidget(data_range_label)

        stretch_row = QHBoxLayout()
        stretch_row.setSpacing(4)
        stretch_row.addWidget(QLabel("Stretch range:"))
        self._stretch_min_spin = QSpinBox()
        self._stretch_min_spin.setRange(0, 65535)
        self._stretch_min_spin.setValue(
            self._color_map.stretch_min
            if self._color_map.stretch_min is not None
            else 0
        )
        self._stretch_min_spin.setToolTip("Minimum value mapped to the start colour")
        stretch_row.addWidget(self._stretch_min_spin)
        stretch_row.addWidget(QLabel("–"))
        self._stretch_max_spin = QSpinBox()
        self._stretch_max_spin.setRange(0, 65535)
        self._stretch_max_spin.setValue(
            self._color_map.stretch_max
            if self._color_map.stretch_max is not None
            else 65535
        )
        self._stretch_max_spin.setToolTip("Maximum value mapped to the end colour")
        stretch_row.addWidget(self._stretch_max_spin)

        btn_auto_stretch = QPushButton("Auto-stretch")
        btn_auto_stretch.setToolTip("Set stretch range from actual data range")
        btn_auto_stretch.clicked.connect(self._on_auto_stretch)
        stretch_row.addWidget(btn_auto_stretch)

        btn_reset_stretch = QPushButton("Reset")
        btn_reset_stretch.setToolTip("Reset stretch to full 0–65535 range")
        btn_reset_stretch.clicked.connect(self._on_reset_stretch)
        stretch_row.addWidget(btn_reset_stretch)

        stretch_row.addStretch()
        layout.addLayout(stretch_row)

        # --- Value Range Mapping (optional) -----------------------------------
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: rgba(255,255,255,30);")
        layout.addWidget(sep)

        mapping_hdr = QHBoxLayout()
        self._display_mapping_enabled = QCheckBox("Map raw values to real-world units")
        self._display_mapping_enabled.setToolTip(
            "Display values in the legend and probe popup using a real-world scale "
            "(e.g. 0–65535 → -10–40 °C)"
        )
        mapping_hdr.addWidget(self._display_mapping_enabled)
        mapping_hdr.addStretch()
        layout.addLayout(mapping_hdr)

        # Min / max / unit row
        range_row = QHBoxLayout()
        range_row.setSpacing(6)
        range_row.addWidget(QLabel("Display min:"))
        self._display_min_edit = QLineEdit()
        self._display_min_edit.setFixedWidth(80)
        self._display_min_edit.setPlaceholderText("e.g. -10.0")
        self._display_min_edit.setValidator(QDoubleValidator())
        range_row.addWidget(self._display_min_edit)
        range_row.addWidget(QLabel("max:"))
        self._display_max_edit = QLineEdit()
        self._display_max_edit.setFixedWidth(80)
        self._display_max_edit.setPlaceholderText("e.g. 40.0")
        self._display_max_edit.setValidator(QDoubleValidator())
        range_row.addWidget(self._display_max_edit)
        range_row.addWidget(QLabel("Unit:"))
        self._display_unit_edit = QLineEdit()
        self._display_unit_edit.setFixedWidth(60)
        self._display_unit_edit.setPlaceholderText("e.g. °C")
        range_row.addWidget(self._display_unit_edit)
        range_row.addStretch()
        layout.addLayout(range_row)

        # Format / scale row
        fmt_row = QHBoxLayout()
        fmt_row.setSpacing(6)
        fmt_row.addWidget(QLabel("Format:"))
        self._display_format_edit = QLineEdit("{:.2f}")
        self._display_format_edit.setFixedWidth(80)
        self._display_format_edit.setToolTip(
            "Python format string applied to each display value, e.g. {:.1f} or {:.0f}"
        )
        fmt_row.addWidget(self._display_format_edit)
        fmt_row.addWidget(QLabel("Scale:"))
        self._display_scale_combo = QComboBox()
        self._display_scale_combo.addItems(["Linear", "Log"])
        fmt_row.addWidget(self._display_scale_combo)
        fmt_row.addStretch()
        layout.addLayout(fmt_row)

        # Live preview
        self._display_preview_label = QLabel("")
        self._display_preview_label.setStyleSheet(StyleHelper.get_preview_label_style())
        layout.addWidget(self._display_preview_label)

        # Wire signals for live preview and enable/disable
        self._display_mapping_enabled.toggled.connect(self._on_display_mapping_toggled)
        for widget in (
            self._display_min_edit,
            self._display_max_edit,
            self._display_unit_edit,
            self._display_format_edit,
        ):
            widget.textChanged.connect(self._update_display_preview)
        self._display_scale_combo.currentTextChanged.connect(
            self._update_display_preview
        )
        self._stretch_min_spin.valueChanged.connect(self._update_display_preview)
        self._stretch_max_spin.valueChanged.connect(self._update_display_preview)

        # Initialise from existing color_map
        has_mapping = self._color_map.display_min is not None
        if has_mapping:
            self._display_min_edit.setText(str(self._color_map.display_min))
            self._display_max_edit.setText(str(self._color_map.display_max))
            self._display_unit_edit.setText(self._color_map.unit or "")
            self._display_format_edit.setText(self._color_map.format_str or "{:.2f}")
            scale_text = (
                "Log" if self._color_map.scale == "log" else "Linear"
            )
            self._display_scale_combo.setCurrentText(scale_text)
        self._display_mapping_enabled.setChecked(has_mapping)
        self._on_display_mapping_toggled(has_mapping)
        self._update_display_preview()

        # --- Linked Entity / Event -------------------------------------------
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("color: rgba(255,255,255,30);")
        layout.addWidget(sep2)

        link_lbl = QLabel("Linked Entity / Event (optional):")
        link_lbl.setStyleSheet(StyleHelper.get_preview_label_style())
        layout.addWidget(link_lbl)

        link_row = QHBoxLayout()
        link_row.setSpacing(6)
        self._linked_type_combo = QComboBox()
        self._linked_type_combo.addItems(["None", "Entity", "Event"])
        self._linked_type_combo.setFixedWidth(80)
        link_row.addWidget(self._linked_type_combo)
        self._linked_name_edit = QLineEdit()
        self._linked_name_edit.setPlaceholderText("Start typing a name…")
        self._linked_name_edit.setToolTip(
            "Link this colour map to a world entity or event by name"
        )
        link_row.addWidget(self._linked_name_edit, 1)
        layout.addLayout(link_row)

        # Completer for the name field
        comp = QCompleter(self._all_item_names, self._linked_name_edit)
        comp.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        comp.setFilterMode(Qt.MatchFlag.MatchContains)
        self._linked_name_edit.setCompleter(comp)
        comp.activated.connect(self._on_linked_entity_activated)
        self._linked_name_edit.editingFinished.connect(
            self._on_linked_entity_editing_finished
        )

        # Pre-populate from existing color_map
        if self._color_map.linked_entity_id:
            lid = self._color_map.linked_entity_id
            name = self._id_to_name.get(lid, "")
            if name:
                self._linked_name_edit.setText(name)
            self._linked_name_edit.setProperty("linked_id", lid)
            ltype = self._color_map.linked_entity_type or ""
            if ltype == "entity":
                self._linked_type_combo.setCurrentText("Entity")
            elif ltype == "event":
                self._linked_type_combo.setCurrentText("Event")

    def _refresh_gradient_preview(self, *_args: object) -> None:
        if (
            hasattr(self, "_gradient_preview")
            and hasattr(self, "_start_btn")
            and hasattr(self, "_end_btn")
        ):
            self._gradient_preview.set_colors(
                self._start_btn.color_hex, self._end_btn.color_hex
            )

    def _on_auto_stretch(self) -> None:
        """Set stretch spinboxes to the actual buffer data range."""
        lo = int(self._buffer_min) if self._buffer_min is not None else 0
        hi = int(self._buffer_max) if self._buffer_max is not None else 65535
        self._stretch_min_spin.setValue(lo)
        self._stretch_max_spin.setValue(hi)

    def _on_reset_stretch(self) -> None:
        """Reset stretch spinboxes to the full 0–65535 range."""
        self._stretch_min_spin.setValue(0)
        self._stretch_max_spin.setValue(65535)

    def _on_display_mapping_toggled(self, enabled: bool) -> None:
        """Enable or disable the value-range mapping controls.

        Args:
            enabled: ``True`` when the mapping checkbox is checked.
        """
        for widget in (
            self._display_min_edit,
            self._display_max_edit,
            self._display_unit_edit,
            self._display_format_edit,
            self._display_scale_combo,
        ):
            widget.setEnabled(enabled)
        self._update_display_preview()

    def _update_display_preview(self, *_args: object) -> None:
        """Refresh the live preview label for the value-range mapping."""
        if not hasattr(self, "_display_preview_label"):
            return
        if not self._display_mapping_enabled.isChecked():
            self._display_preview_label.setText("")
            return
        try:
            d_min = float(self._display_min_edit.text())
            d_max = float(self._display_max_edit.text())
        except ValueError:
            self._display_preview_label.setText("Enter valid min and max values")
            return
        unit = self._display_unit_edit.text().strip()
        fmt = self._display_format_edit.text().strip() or "{:.2f}"
        scale = (
            "log"
            if self._display_scale_combo.currentText() == "Log"
            else "linear"
        )
        s_min = self._stretch_min_spin.value()
        s_max = self._stretch_max_spin.value()
        sample_raw = (s_min + s_max) // 2
        temp_cmap = ColorMap(
            type="gradient",
            display_min=d_min,
            display_max=d_max,
            unit=unit,
            format_str=fmt,
            scale=scale,
            stretch_min=s_min,
            stretch_max=s_max,
        )
        try:
            sample_display = format_display_value(temp_cmap, sample_raw)
            lo_display = format_display_value(temp_cmap, s_min)
            hi_display = format_display_value(temp_cmap, s_max)
            self._display_preview_label.setText(
                f"Raw {s_min} → {lo_display}   ·   "
                f"Raw {sample_raw} → {sample_display}   ·   "
                f"Raw {s_max} → {hi_display}"
            )
        except Exception:
            self._display_preview_label.setText("(preview error)")

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

        # Col 4: item type combo (built before col 3 so completer can reference it)
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

        # Col 3: linked entity/event — shows human name, stores UUID as a property.
        # If the ID is known in our lookup table, show the name; otherwise show the
        # raw ID (backward-compat when no entity/event list was provided).
        display_name = self._id_to_name.get(entity_id, entity_id)
        entity_name_edit = QLineEdit(display_name)
        entity_name_edit.setPlaceholderText("Link to entity or event…")
        entity_name_edit.setProperty("linked_id", entity_id)
        if self._all_item_names:
            comp = QCompleter(self._all_item_names, entity_name_edit)
            comp.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            comp.setFilterMode(Qt.MatchFlag.MatchContains)
            entity_name_edit.setCompleter(comp)
            comp.activated.connect(
                lambda name, _e=entity_name_edit, _c=type_combo: self._on_entity_activated(
                    name, _e, _c
                )
            )
        entity_name_edit.editingFinished.connect(
            lambda _e=entity_name_edit, _c=type_combo: self._on_entity_editing_finished(
                _e, _c
            )
        )
        self._table.setCellWidget(row, _COL_ENTITY_ID, entity_name_edit)

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

    def _on_entity_activated(
        self, name: str, edit: QLineEdit, combo: QComboBox
    ) -> None:
        """Called when the user selects a name from the entity/event completer.

        Stores the resolved UUID in the ``linked_id`` property and auto-sets
        the type combo to ``"Entity"`` or ``"Event"``.

        Args:
            name: Display name chosen by the user.
            edit: The entity name QLineEdit for the affected row.
            combo: The type QComboBox for the affected row.
        """
        eid = self._name_to_id.get(name, "")
        edit.setProperty("linked_id", eid)
        if eid in self._entity_id_set:
            combo.setCurrentText("Entity")
        elif eid in self._event_id_set:
            combo.setCurrentText("Event")

    def _on_entity_editing_finished(
        self, edit: QLineEdit, combo: QComboBox
    ) -> None:
        """Called when the entity name field loses focus.

        Resolves the typed name to an ID; clears the link if the text does
        not match any known entity or event.

        Args:
            edit: The entity name QLineEdit for the affected row.
            combo: The type QComboBox for the affected row.
        """
        text = edit.text().strip()
        if not text:
            edit.setProperty("linked_id", "")
            combo.setCurrentText("None")
            return
        eid = self._name_to_id.get(text, "")
        edit.setProperty("linked_id", eid)
        if eid:
            if eid in self._entity_id_set:
                combo.setCurrentText("Entity")
            elif eid in self._event_id_set:
                combo.setCurrentText("Event")

    @Slot(str)
    def _on_linked_entity_activated(self, name: str) -> None:
        """Store UUID when a name is chosen from the continuous-mode link completer.

        Args:
            name: The entity/event name selected from the completer.
        """
        eid = self._name_to_id.get(name, "")
        self._linked_name_edit.setProperty("linked_id", eid)
        if eid and hasattr(self, "_linked_type_combo"):
            if eid in self._entity_id_set:
                self._linked_type_combo.setCurrentText("Entity")
            elif eid in self._event_id_set:
                self._linked_type_combo.setCurrentText("Event")

    @Slot()
    def _on_linked_entity_editing_finished(self) -> None:
        """Resolve or clear the linked entity when the continuous-mode name field loses focus."""
        if not hasattr(self, "_linked_name_edit"):
            return
        text = self._linked_name_edit.text().strip()
        if not text:
            self._linked_name_edit.setProperty("linked_id", "")
            if hasattr(self, "_linked_type_combo"):
                self._linked_type_combo.setCurrentText("None")
            return
        # Keep existing UUID if it still matches the typed name
        current_lid = (self._linked_name_edit.property("linked_id") or "").strip()
        if current_lid:
            expected = self._id_to_name.get(current_lid, "")
            if expected.lower() == text.lower():
                return
        # Try to resolve by name (case-insensitive fallback)
        eid = self._name_to_id.get(text, "")
        if not eid:
            lower_map = {k.lower(): v for k, v in self._name_to_id.items()}
            eid = lower_map.get(text.lower(), "")
        self._linked_name_edit.setProperty("linked_id", eid)

    def _on_auto_color(self) -> None:
        """Assign auto-colors from _AUTO_COLORS to each table row in sequence."""
        for row in range(self._table.rowCount()):
            btn = self._table.cellWidget(row, _COL_COLOR)
            if isinstance(btn, _ColorButton):
                btn.color_hex = _AUTO_COLORS[row % len(_AUTO_COLORS)]

    def _on_export_palette(self) -> None:
        """Export the current discrete palette entries to a JSON file."""
        import json

        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getSaveFileName(
            self, "Export Palette", "palette.json", "JSON Files (*.json)"
        )
        if not path:
            return

        entries: List[Dict[str, Any]] = []
        for r in range(self._table.rowCount()):
            spin = self._table.cellWidget(r, _COL_VALUE)
            btn = self._table.cellWidget(r, _COL_COLOR)
            label_edit = self._table.cellWidget(r, _COL_LABEL)
            entity_edit = self._table.cellWidget(r, _COL_ENTITY_ID)
            type_combo = self._table.cellWidget(r, _COL_TYPE)
            if not isinstance(spin, QSpinBox) or not isinstance(btn, _ColorButton):
                continue
            entry: Dict[str, Any] = {
                "value": spin.value(),
                "color": btn.color_hex,
                "label": label_edit.text().strip()
                if isinstance(label_edit, QLineEdit)
                else "",
            }
            eid = ""
            if isinstance(entity_edit, QLineEdit):
                eid = (entity_edit.property("linked_id") or "").strip()
                if not eid:
                    raw = entity_edit.text().strip()
                    if raw and " " not in raw and len(raw) == 36:
                        eid = raw
            if eid:
                entry["entity_id"] = eid
                # Include the resolved name for human readability
                resolved_name = self._id_to_name.get(eid)
                if resolved_name:
                    entry["entity_name"] = resolved_name
            itype = (
                type_combo.currentText()
                if isinstance(type_combo, QComboBox)
                else "None"
            )
            if itype != "None":
                entry["item_type"] = itype.lower()
            entries.append(entry)

        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(entries, f, indent=2)
        except OSError as exc:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(self, "Export Failed", str(exc))

    def _on_import_palette(self) -> None:
        """Import palette entries from a JSON file, replacing current entries."""
        import json

        from PySide6.QtWidgets import QFileDialog, QMessageBox

        path, _ = QFileDialog.getOpenFileName(
            self, "Import Palette", "", "JSON Files (*.json)"
        )
        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            QMessageBox.warning(self, "Import Failed", str(exc))
            return

        if not isinstance(data, list):
            QMessageBox.warning(
                self,
                "Import Failed",
                "Expected a JSON array of palette entries.",
            )
            return

        self._table.setRowCount(0)
        for entry in data:
            if not isinstance(entry, dict):
                continue
            self._add_entry_row(
                value=int(entry.get("value", 0)),
                color=str(entry.get("color", "#808080")),
                label=str(entry.get("label", "")),
                entity_id=str(entry.get("entity_id", "")),
                item_type=str(entry.get("item_type", "")),
            )

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
                    if isinstance(entity_edit, QLineEdit):
                        eid = (entity_edit.property("linked_id") or "").strip() or None
                    entries.append(
                        ColorEntry(
                            value=spin.value(), color=btn.color_hex, entity_id=eid
                        )
                    )
            return ColorMap(type="palette", entries=entries)
        else:
            stretch_min: Optional[int] = None
            stretch_max: Optional[int] = None
            if hasattr(self, "_stretch_min_spin") and hasattr(
                self, "_stretch_max_spin"
            ):
                stretch_min = self._stretch_min_spin.value()
                stretch_max = self._stretch_max_spin.value()
            # Collect display mapping if enabled
            display_min: Optional[float] = None
            display_max: Optional[float] = None
            unit = ""
            format_str = "{:.2f}"
            scale = "linear"
            if (
                hasattr(self, "_display_mapping_enabled")
                and self._display_mapping_enabled.isChecked()
            ):
                try:
                    display_min = float(self._display_min_edit.text())
                    display_max = float(self._display_max_edit.text())
                    unit = self._display_unit_edit.text().strip()
                    format_str = self._display_format_edit.text().strip() or "{:.2f}"
                    scale = (
                        "log"
                        if self._display_scale_combo.currentText() == "Log"
                        else "linear"
                    )
                except ValueError:
                    pass
            # Collect linked entity/event for this continuous color map
            linked_entity_id: Optional[str] = None
            linked_entity_type = ""
            if hasattr(self, "_linked_name_edit"):
                linked_entity_id = (
                    self._linked_name_edit.property("linked_id") or ""
                ).strip() or None
                if linked_entity_id and hasattr(self, "_linked_type_combo"):
                    ltype_text = self._linked_type_combo.currentText()
                    if ltype_text == "Entity":
                        linked_entity_type = "entity"
                    elif ltype_text == "Event":
                        linked_entity_type = "event"
            return ColorMap(
                type="gradient",
                gradient_start=self._start_btn.color_hex,
                gradient_end=self._end_btn.color_hex,
                stretch_min=stretch_min,
                stretch_max=stretch_max,
                display_min=display_min,
                display_max=display_max,
                unit=unit,
                format_str=format_str,
                scale=scale,
                linked_entity_id=linked_entity_id,
                linked_entity_type=linked_entity_type,
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
            eid = ""
            if isinstance(entity_edit, QLineEdit):
                eid = (entity_edit.property("linked_id") or "").strip()
                if not eid:
                    # Fallback: if no linked_id stored but text looks like a UUID
                    # (backward-compat for rows added without a completer available)
                    raw = entity_edit.text().strip()
                    if raw and " " not in raw and len(raw) == 36:
                        eid = raw
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
