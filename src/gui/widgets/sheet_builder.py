"""Sheet Builder Widget Module.

Provides a visual "Stat Block" builder for entity/event attributes. The sheet
presents attributes as draggable key-value boxes arranged in a flex-row grid,
and supports serialization of the spatial layout to a 2D list for persistence.
"""

import logging
from typing import Any, Dict, List, Optional, Union

from PySide6.QtCore import QMimeData, QPoint, Qt, Signal
from src.core.theme_manager import ThemeManager
from PySide6.QtGui import (
    QDrag,
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
    QMouseEvent,
)
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QRubberBand,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)

# Internal MIME type for drag-and-drop within the sheet builder
_SHEET_DRAG_MIME = "application/x-kraken-sheet-key"


class AttributePairWidget(QFrame):
    """A single key-value attribute box for the Sheet Builder.

    Displays a bold key label on top and an editable value line-edit below,
    with an optional type toggle (String / Number / Boolean).

    Signals:
        value_changed: Emitted when the value or type is modified.
        drag_started: Emitted with the attribute key when the user initiates a drag.
    """

    value_changed = Signal()
    drag_started = Signal(str)

    def __init__(
        self,
        key: str,
        value: str = "",
        value_type: str = "String",
        parent: Optional[QWidget] = None,
    ) -> None:
        """Initialize the AttributePairWidget.

        Args:
            key: The attribute key displayed as a bold label.
            value: The initial string value.
            value_type: One of "String", "Number", "Boolean".
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self._key = key
        self._drag_start_pos: Optional[QPoint] = None

        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setObjectName("AttributePairWidget")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(2)

        # Bold key label
        self.key_label = QLabel(f"<b>{key}</b>")
        self.key_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.key_label)

        # Value line-edit
        self.value_edit = QLineEdit(value)
        self.value_edit.setPlaceholderText("Value…")
        self.value_edit.textChanged.connect(self._on_value_changed)
        layout.addWidget(self.value_edit)

        # Type toggle (compact combo)
        self.type_combo = QComboBox()
        self.type_combo.addItems(["String", "Number", "Boolean"])
        self.type_combo.setCurrentText(value_type)
        self.type_combo.currentTextChanged.connect(self._on_value_changed)
        self.type_combo.setMaximumWidth(90)
        layout.addWidget(self.type_combo)

        # Apply initial theme and connect to changes
        self._apply_theme()
        ThemeManager().theme_changed.connect(self._apply_theme)

    def _apply_theme(self) -> None:
        """Apply current theme colors to the widget."""
        theme = ThemeManager().get_theme()
        surface_alt = theme.get("surface_alt", "#2A2A2A")
        border = theme.get("border", "#333333")
        text = theme.get("text", "#E0E0E0")

        self.setStyleSheet(
            f"""
            AttributePairWidget {{
                background-color: {surface_alt};
                border: 1px solid {border};
                border-radius: 4px;
            }}
            QLabel {{
                color: {text};
            }}
            QLineEdit, QComboBox {{
                background-color: transparent;
                border: 1px solid {border};
                border-radius: 2px;
                color: {text};
                padding: 2px;
            }}
            QLineEdit:focus, QComboBox:focus {{
                border: 1px solid {theme.get('primary', '#5C82FF')};
            }}
            QComboBox::drop-down {{
                border: none;
            }}
            QComboBox::down-arrow {{
                image: none;
            }}
        """
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def key(self) -> str:
        """Return the attribute key."""
        return self._key

    def get_value(self) -> str:
        """Return the raw string value."""
        return self.value_edit.text()

    def set_value(self, value: str) -> None:
        """Set the value without emitting value_changed."""
        self.value_edit.blockSignals(True)
        self.value_edit.setText(value)
        self.value_edit.blockSignals(False)

    def get_type(self) -> str:
        """Return the selected type string."""
        return self.type_combo.currentText()

    def set_type(self, value_type: str) -> None:
        """Set the type combo without emitting value_changed."""
        self.type_combo.blockSignals(True)
        self.type_combo.setCurrentText(value_type)
        self.type_combo.blockSignals(False)

    def get_parsed_value(self) -> Union[str, int, float, bool]:
        """Return the value parsed according to the selected type."""
        raw = self.value_edit.text()
        vtype = self.type_combo.currentText()
        if vtype == "Number":
            try:
                return float(raw) if "." in raw else int(raw)
            except ValueError:
                return 0
        if vtype == "Boolean":
            return raw.lower() in {"true", "1", "yes", "on"}
        return raw

    # ------------------------------------------------------------------
    # Drag support
    # ------------------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Record the drag start position on left-click."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Initiate a drag if the mouse moves far enough from the press point."""
        if (
            self._drag_start_pos is not None
            and (event.pos() - self._drag_start_pos).manhattanLength() > 10
        ):
            drag = QDrag(self)
            mime = QMimeData()
            mime.setData(_SHEET_DRAG_MIME, self._key.encode("utf-8"))
            drag.setMimeData(mime)
            self.drag_started.emit(self._key)
            drag.exec(Qt.DropAction.MoveAction)
            self._drag_start_pos = None
        super().mouseMoveEvent(event)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _on_value_changed(self) -> None:
        """Emit value_changed signal."""
        self.value_changed.emit()


class SheetBuilderWidget(QWidget):
    """Visual grid builder for entity/event "stat blocks".

    Arranges ``AttributePairWidget`` instances in a flex-row grid
    (QVBoxLayout of QHBoxLayout rows). The layout is serialised as a 2D
    list of key strings and stored in the ``_sheet_layout`` metadata field.

    Signals:
        attributes_changed: Emitted when any attribute value or the layout
            structure changes.
    """

    attributes_changed = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the SheetBuilderWidget.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self.setAcceptDrops(True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        # Scroll area
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(self._scroll)

        # Inner container
        self._container = QWidget()
        self._grid_layout = QVBoxLayout(self._container)
        self._grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._grid_layout.setSpacing(4)
        self._grid_layout.setContentsMargins(4, 4, 4, 4)
        self._scroll.setWidget(self._container)

        # Pair widget lookup: key -> AttributePairWidget
        self._pairs: Dict[str, AttributePairWidget] = {}

        # Rubber-band for drag feedback
        self._rubber_band: Optional[QRubberBand] = None

        # Block signals flag
        self._block_signals = False

        # Apply initial theme and connect to changes
        self._apply_theme()
        ThemeManager().theme_changed.connect(self._apply_theme)

    def _apply_theme(self) -> None:
        """Apply current theme colors to the widget."""
        theme = ThemeManager().get_theme()
        surface = theme.get("surface", "#1A1A1A")

        # Style the scroll area and container to match the app's surface
        self._scroll.setStyleSheet(
            f"QScrollArea {{ background-color: {surface}; border: none; }}"
        )
        self._container.setStyleSheet(f"QWidget {{ background-color: {surface}; }}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_attributes(
        self,
        attributes: Dict[str, Any],
        layout: Optional[List[List[str]]] = None,
    ) -> None:
        """Populate the sheet from an attributes dict and optional layout.

        Args:
            attributes: Key-value attribute pairs (user-visible, no ``_`` prefix).
            layout: Optional 2D list of key strings describing the row arrangement.
                If ``None``, each attribute gets its own row.
        """
        self._block_signals = True
        self._clear()

        if layout is not None:
            # Build rows according to layout, skipping keys not in attributes
            placed_keys: set[str] = set()
            for row_keys in layout:
                valid_keys = [k for k in row_keys if k in attributes]
                if valid_keys:
                    self._add_row([(k, attributes[k]) for k in valid_keys])
                    placed_keys.update(valid_keys)

            # Append any remaining attributes not referenced by the layout
            for key, value in attributes.items():
                if key not in placed_keys:
                    self._add_row([(key, value)])
        else:
            # No layout – one attribute per row
            for key, value in attributes.items():
                self._add_row([(key, value)])

        self._block_signals = False

    def get_attributes(self) -> Dict[str, Any]:
        """Return the current attribute values as a dict.

        Returns:
            Dict mapping attribute keys to their parsed values.
        """
        return {key: pair.get_parsed_value() for key, pair in self._pairs.items()}

    def get_layout(self) -> List[List[str]]:
        """Serialize the current row arrangement as a 2D list of key strings.

        Returns:
            List of rows, where each row is a list of attribute key strings.
        """
        rows: List[List[str]] = []
        for row_idx in range(self._grid_layout.count()):
            row_layout = self._grid_layout.itemAt(row_idx)
            if row_layout is None or row_layout.layout() is None:
                continue
            hlayout = row_layout.layout()
            keys: List[str] = []
            for col_idx in range(hlayout.count()):
                item = hlayout.itemAt(col_idx)
                if item is None or item.widget() is None:
                    continue
                widget = item.widget()
                if isinstance(widget, AttributePairWidget):
                    keys.append(widget.key)
            if keys:
                rows.append(keys)
        return rows

    def add_attribute(self, key: str, value: Any = "") -> None:
        """Create a new attribute with Universal String default and add it as a new row.

        Args:
            key: The attribute key.
            value: Initial value (defaults to empty string).
        """
        if key in self._pairs:
            return
        self._add_row([(key, value)])
        if not self._block_signals:
            self.attributes_changed.emit()

    def update_attribute_value(self, key: str, value: Any) -> None:
        """Update the value of an existing attribute in the sheet.

        Args:
            key (str): The attribute key to update.
            value (Any): The new value.
        """
        if key in self._pairs:
            self._block_signals = True
            try:
                pair = self._pairs[key]
                str_val = str(value) if value is not None else ""
                pair.set_value(str_val)
            finally:
                self._block_signals = False

    def remove_attribute(self, key: str) -> None:
        """Remove an attribute from the sheet.

        Args:
            key: The attribute key to remove.
        """
        pair = self._pairs.pop(key, None)
        if pair is None:
            return
        # Find the row layout containing this pair and remove it
        for row_idx in range(self._grid_layout.count()):
            row_item = self._grid_layout.itemAt(row_idx)
            if row_item is None or row_item.layout() is None:
                continue
            hlayout = row_item.layout()
            for col_idx in range(hlayout.count()):
                item = hlayout.itemAt(col_idx)
                if item is not None and item.widget() is pair:
                    hlayout.removeWidget(pair)
                    pair.setParent(None)
                    pair.deleteLater()
                    # If the row is now empty, remove it
                    if hlayout.count() == 0:
                        self._grid_layout.removeItem(row_item)
                    if not self._block_signals:
                        self.attributes_changed.emit()
                    return

    # ------------------------------------------------------------------
    # Drag-and-drop (Phase 3: Snap Engine)
    # ------------------------------------------------------------------

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """Accept drags carrying the sheet MIME type."""
        if event.mimeData().hasFormat(_SHEET_DRAG_MIME):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        """Show rubber-band feedback during drag."""
        if not event.mimeData().hasFormat(_SHEET_DRAG_MIME):
            event.ignore()
            return

        event.acceptProposedAction()
        drop_row, insert_col = self._calc_drop_position(event.position().toPoint())

        # Show rubber-band feedback
        if self._rubber_band is None:
            self._rubber_band = QRubberBand(
                QRubberBand.Shape.Rectangle, self._container
            )

        if drop_row < self._grid_layout.count():
            row_item = self._grid_layout.itemAt(drop_row)
            if row_item and row_item.layout():
                geom = row_item.layout().geometry()
                self._rubber_band.setGeometry(geom)
                self._rubber_band.show()
                return

        # Indicate new row at the bottom
        y = self._container.height() - 4
        self._rubber_band.setGeometry(4, y, self._container.width() - 8, 4)
        self._rubber_band.show()

    def dragLeaveEvent(self, event: Any) -> None:
        """Hide rubber-band when drag leaves the widget."""
        if self._rubber_band is not None:
            self._rubber_band.hide()

    def dropEvent(self, event: QDropEvent) -> None:
        """Handle attribute pill drop – move the attribute into the target row."""
        if self._rubber_band is not None:
            self._rubber_band.hide()

        mime = event.mimeData()
        if not mime.hasFormat(_SHEET_DRAG_MIME):
            event.ignore()
            return

        key = bytes(mime.data(_SHEET_DRAG_MIME)).decode("utf-8")
        pair = self._pairs.get(key)
        if pair is None:
            event.ignore()
            return

        # Remove from current row
        self._detach_pair(pair)

        # Calculate target position
        drop_row, insert_col = self._calc_drop_position(event.position().toPoint())

        if drop_row < self._grid_layout.count():
            # Insert into existing row
            row_item = self._grid_layout.itemAt(drop_row)
            if row_item and row_item.layout():
                hlayout = row_item.layout()
                idx = min(insert_col, hlayout.count())
                hlayout.insertWidget(idx, pair)
            else:
                self._append_new_row(pair)
        else:
            # Append new row
            self._append_new_row(pair)

        event.acceptProposedAction()
        if not self._block_signals:
            self.attributes_changed.emit()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _clear(self) -> None:
        """Remove all rows and pair widgets."""
        for pair in list(self._pairs.values()):
            pair.setParent(None)
            pair.deleteLater()
        self._pairs.clear()

        while self._grid_layout.count():
            item = self._grid_layout.takeAt(0)
            if item.layout():
                while item.layout().count():
                    child = item.layout().takeAt(0)
                    if child.widget():
                        child.widget().setParent(None)

    def _add_row(self, pairs: List[tuple]) -> None:
        """Add a new horizontal row of AttributePairWidgets.

        Args:
            pairs: List of (key, value) tuples for each widget in the row.
        """
        hlayout = QHBoxLayout()
        hlayout.setSpacing(4)
        hlayout.setContentsMargins(0, 0, 0, 0)

        for key, value in pairs:
            vtype = "String"
            if isinstance(value, bool):
                vtype = "Boolean"
                str_val = str(value)
            elif isinstance(value, (int, float)):
                vtype = "Number"
                str_val = str(value)
            else:
                str_val = str(value) if value is not None else ""

            pair = AttributePairWidget(key, str_val, vtype)
            pair.value_changed.connect(self._on_pair_changed)
            hlayout.addWidget(pair)
            self._pairs[key] = pair

        self._grid_layout.addLayout(hlayout)

    def _append_new_row(self, pair: AttributePairWidget) -> None:
        """Append a pair as the sole widget in a new row at the bottom."""
        hlayout = QHBoxLayout()
        hlayout.setSpacing(4)
        hlayout.setContentsMargins(0, 0, 0, 0)
        hlayout.addWidget(pair)
        self._grid_layout.addLayout(hlayout)

    def _detach_pair(self, pair: AttributePairWidget) -> None:
        """Remove pair from its current row layout, cleaning up empty rows."""
        for row_idx in range(self._grid_layout.count()):
            row_item = self._grid_layout.itemAt(row_idx)
            if row_item is None or row_item.layout() is None:
                continue
            hlayout = row_item.layout()
            for col_idx in range(hlayout.count()):
                item = hlayout.itemAt(col_idx)
                if item is not None and item.widget() is pair:
                    hlayout.removeWidget(pair)
                    if hlayout.count() == 0:
                        self._grid_layout.removeItem(row_item)
                    return

    def _calc_drop_position(self, pos: QPoint) -> tuple:
        """Determine the target row index and column index for a drop.

        Args:
            pos: Position in container coordinates.

        Returns:
            Tuple of (row_index, col_index).
        """
        container_pos = self._container.mapFrom(self, pos)
        target_row = self._grid_layout.count()  # default: new row at end
        target_col = 0

        for row_idx in range(self._grid_layout.count()):
            row_item = self._grid_layout.itemAt(row_idx)
            if row_item is None or row_item.layout() is None:
                continue
            geom = row_item.layout().geometry()
            if geom.contains(container_pos):
                target_row = row_idx
                # Determine column insertion point
                hlayout = row_item.layout()
                for col_idx in range(hlayout.count()):
                    widget_item = hlayout.itemAt(col_idx)
                    if widget_item and widget_item.widget():
                        w_geom = widget_item.widget().geometry()
                        if container_pos.x() < w_geom.center().x():
                            target_col = col_idx
                            return target_row, target_col
                target_col = hlayout.count()
                break

        return target_row, target_col

    def _on_pair_changed(self) -> None:
        """Forward pair value changes as attributes_changed."""
        if not self._block_signals:
            self.attributes_changed.emit()
