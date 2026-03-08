"""Raster Query Dialog.

Provides a dialog for building cross-layer spatial queries.
Users define up to three conditions, each referencing a raster layer,
a comparison operator, and a value (or range).  Running the query
produces a list of conditions suitable for
:func:`src.gui.widgets.map.map_data_buffer.compute_spatial_query`.
"""

import logging
from typing import Any, Dict, List, Optional

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.gui.utils.style_helper import StyleHelper

logger = logging.getLogger(__name__)

_MAX_CONDITIONS = 3

_OPS: List[tuple[str, str]] = [
    ("eq", "= equals"),
    ("neq", "≠ not equals"),
    ("gt", "> greater than"),
    ("lt", "< less than"),
    ("gte", "≥ greater or equal"),
    ("lte", "≤ less or equal"),
    ("between", "↔ between"),
]


class _ConditionRow(QWidget):
    """A single condition row in the query builder.

    Args:
        layers: Layer metadata list ``[{"node_id": str, "name": str}]``.
        parent: Parent widget.
    """

    def __init__(
        self,
        layers: List[Dict[str, Any]],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._layers = layers

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._layer_combo = QComboBox()
        for layer in layers:
            self._layer_combo.addItem(layer["name"], layer["node_id"])
        layout.addWidget(self._layer_combo, 2)

        self._op_combo = QComboBox()
        for op_key, op_label in _OPS:
            self._op_combo.addItem(op_label, op_key)
        self._op_combo.currentIndexChanged.connect(self._on_op_changed)
        layout.addWidget(self._op_combo, 2)

        self._value_spin = QSpinBox()
        self._value_spin.setRange(0, 65535)
        self._value_spin.setValue(0)
        layout.addWidget(self._value_spin)

        self._dash_label = QLabel("–")
        self._dash_label.setVisible(False)
        layout.addWidget(self._dash_label)

        self._max_spin = QSpinBox()
        self._max_spin.setRange(0, 65535)
        self._max_spin.setValue(65535)
        self._max_spin.setVisible(False)
        layout.addWidget(self._max_spin)

    def _on_op_changed(self, index: int) -> None:
        op = self._op_combo.itemData(index)
        is_between = op == "between"
        self._dash_label.setVisible(is_between)
        self._max_spin.setVisible(is_between)

    def to_condition(self) -> Dict[str, Any]:
        """Build the condition dict for this row.

        Returns:
            Condition dict with ``"node_id"``, ``"op"``, and either
            ``"value"`` (scalar ops) or ``"min"`` / ``"max"`` (between).
        """
        op = self._op_combo.currentData()
        node_id: str = self._layer_combo.currentData() or ""
        if op == "between":
            return {
                "node_id": node_id,
                "op": "between",
                "min": self._value_spin.value(),
                "max": self._max_spin.value(),
            }
        return {
            "node_id": node_id,
            "op": op,
            "value": self._value_spin.value(),
        }


class RasterQueryDialog(QDialog):
    """Dialog for building cross-layer spatial queries.

    Each condition specifies a layer, an operator, and a value.  All
    conditions are AND-ed together.

    Args:
        layers: List of ``{"node_id": str, "name": str, "mode": str}``
            dicts representing available raster layers.
        parent: Parent widget.
    """

    def __init__(
        self,
        layers: List[Dict[str, Any]],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Cross-Layer Spatial Query")
        self.setMinimumWidth(520)
        self._layers = layers
        self._condition_rows: List[_ConditionRow] = []
        self.setStyleSheet(StyleHelper.get_dialog_base_style())
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        help_label = QLabel("Show pixels matching <b>ALL</b> of these conditions:")
        help_label.setWordWrap(True)
        layout.addWidget(help_label)

        # Container for condition rows
        self._rows_widget = QWidget()
        self._rows_layout = QVBoxLayout(self._rows_widget)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(4)
        layout.addWidget(self._rows_widget)

        if self._layers:
            self._add_condition_row()

        # Add / remove row controls
        add_remove_row = QHBoxLayout()
        btn_add = QPushButton("+ Add condition")
        btn_add.clicked.connect(self._on_add_row)
        add_remove_row.addWidget(btn_add)
        self._btn_remove = QPushButton("− Remove last")
        self._btn_remove.clicked.connect(self._on_remove_row)
        add_remove_row.addWidget(self._btn_remove)
        add_remove_row.addStretch()
        layout.addLayout(add_remove_row)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.button(QDialogButtonBox.StandardButton.Ok).setText("Run Query")
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

        self._update_remove_btn()

    def _add_condition_row(self) -> None:
        if len(self._condition_rows) >= _MAX_CONDITIONS:
            return
        row = _ConditionRow(layers=self._layers, parent=self._rows_widget)
        self._condition_rows.append(row)
        self._rows_layout.addWidget(row)
        self._update_remove_btn()

    def _on_add_row(self) -> None:
        self._add_condition_row()

    def _on_remove_row(self) -> None:
        if not self._condition_rows:
            return
        row = self._condition_rows.pop()
        self._rows_layout.removeWidget(row)
        row.deleteLater()
        self._update_remove_btn()

    def _update_remove_btn(self) -> None:
        if hasattr(self, "_btn_remove"):
            self._btn_remove.setEnabled(len(self._condition_rows) > 0)

    # ------------------------------------------------------------------
    # Results
    # ------------------------------------------------------------------

    @property
    def conditions(self) -> List[Dict[str, Any]]:
        """Built condition list (node_id-keyed, ready for MapHandler).

        Returns:
            List of condition dicts, each with ``"node_id"``, ``"op"``,
            and either ``"value"`` or ``"min"``/``"max"``.
        """
        return [row.to_condition() for row in self._condition_rows]
