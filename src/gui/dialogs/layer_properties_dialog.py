"""Contextual editor for persisted map-layer properties."""

from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.core.map import MapLayerNode
from src.core.map_constants import MAP_LAYER_TYPE_GROUP
from src.gui.utils.style_helper import StyleHelper


class LayerPropertiesDialog(QDialog):
    """Edit common and advanced properties without mutating the layer model."""

    def __init__(
        self,
        node: MapLayerNode,
        parent: Optional[QWidget] = None,
    ) -> None:
        """Initialize the layer-properties editor."""
        super().__init__(parent)
        self._node = node
        self.setModal(False)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setWindowTitle("Layer Properties")
        self.setMinimumWidth(420)
        self.setStyleSheet(StyleHelper.get_dialog_base_style())

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self._name = QLineEdit(node.name)
        self._visible = QCheckBox()
        self._visible.setChecked(node.visible)
        self._opacity = QDoubleSpinBox()
        self._opacity.setRange(0.0, 1.0)
        self._opacity.setSingleStep(0.05)
        self._opacity.setValue(node.opacity)
        self._notes = QPlainTextEdit(
            str(node.attributes.get("notes", ""))
        )
        self._notes.setMaximumHeight(90)
        form.addRow("Name:", self._name)
        form.addRow("Visible:", self._visible)
        form.addRow("Opacity:", self._opacity)
        form.addRow("Notes:", self._notes)

        self._exclusive = QCheckBox("Only one child visible at a time")
        self._exclusive.setChecked(node.mutually_exclusive)
        self._exclusive.setVisible(node.layer_type == MAP_LAYER_TYPE_GROUP)
        form.addRow("Group:", self._exclusive)

        self._min_zoom = QDoubleSpinBox()
        self._min_zoom.setRange(0.01, 100.0)
        self._min_zoom.setDecimals(2)
        self._min_zoom.setValue(max(0.01, float(node.min_zoom or 0.01)))
        self._max_zoom_enabled = QCheckBox("Maximum zoom")
        self._max_zoom = QDoubleSpinBox()
        self._max_zoom.setRange(0.01, 100.0)
        self._max_zoom.setDecimals(2)
        finite_max = node.max_zoom != float("inf")
        self._max_zoom_enabled.setChecked(finite_max)
        self._max_zoom.setEnabled(finite_max)
        self._max_zoom.setValue(
            float(node.max_zoom) if finite_max else 100.0
        )
        self._max_zoom_enabled.toggled.connect(self._max_zoom.setEnabled)
        form.addRow("Minimum zoom ratio:", self._min_zoom)
        form.addRow(self._max_zoom_enabled, self._max_zoom)
        layout.addLayout(form)

        hint = QLabel(
            "Zoom ratios are relative to Fit to Map; 1.0 is the fitted view."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        self._buttons = buttons
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def properties(self) -> dict[str, Any]:
        """Return validated values for ``UpdateLayerPropertiesCommand``."""
        return {
            "name": self._name.text().strip(),
            "visible": self._visible.isChecked(),
            "opacity": self._opacity.value(),
            "notes": self._notes.toPlainText(),
            "mutually_exclusive": self._exclusive.isChecked(),
            "min_zoom": self._min_zoom.value(),
            "max_zoom": (
                self._max_zoom.value()
                if self._max_zoom_enabled.isChecked()
                else float("inf")
            ),
            "zoom_basis": "fit_ratio",
        }
