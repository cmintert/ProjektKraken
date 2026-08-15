"""Dialog for configuring real-world map scale."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.gui.utils.style_helper import StyleHelper

_METERS_PER_KILOMETER = 1000.0


class MapScaleDialog(QDialog):
    """Configure the shared distance calibration for a map."""

    calibrate_requested = Signal()

    def __init__(
        self,
        current_width: float,
        parent: QWidget | None = None,
        map_name: str = "Map",
    ) -> None:
        """Initialize a scale dialog with the map's current width."""
        super().__init__(parent)
        self._active_unit = (
            "km" if current_width >= _METERS_PER_KILOMETER else "m"
        )
        self._updating = False
        self.setWindowTitle(f"Map Scale — {map_name}")
        self.setModal(True)
        self.setMinimumWidth(390)
        self.setStyleSheet(StyleHelper.get_dialog_base_style())

        layout = QVBoxLayout(self)
        instruction = QLabel(
            "Set the map's real-world width to enable distance measurements "
            "and metric marker sizes."
        )
        instruction.setWordWrap(True)
        layout.addWidget(instruction)

        input_row = QHBoxLayout()
        input_row.addWidget(QLabel("Total width:"))
        self.width_input = QDoubleSpinBox()
        self.width_input.setRange(0.0, 1_000_000_000.0)
        self.width_input.setDecimals(2)
        self.width_input.setSpecialValueText("Not calibrated")
        self.width_input.setStyleSheet(StyleHelper.get_spinbox_style())
        self.unit_selector = QComboBox()
        self.unit_selector.addItems(["m", "km"])
        self.unit_selector.setStyleSheet(StyleHelper.get_input_field_style())
        if self._active_unit == "km":
            self.width_input.setValue(current_width / _METERS_PER_KILOMETER)
        else:
            self.width_input.setValue(max(0.0, current_width))
        self.unit_selector.setCurrentText(self._active_unit)
        self.unit_selector.currentTextChanged.connect(self._change_unit)
        input_row.addWidget(self.width_input, 1)
        input_row.addWidget(self.unit_selector)
        layout.addLayout(input_row)

        calibrate = QPushButton("Calibrate from Measurement...")
        calibrate.setToolTip(
            "Measure a known distance on the map to calculate its total width."
        )
        calibrate.setStyleSheet(StyleHelper.get_primary_button_style())
        calibrate.clicked.connect(self._request_calibration)
        layout.addWidget(calibrate)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _change_unit(self, unit: str) -> None:
        """Convert the display without changing the physical map width."""
        if self._updating or unit == self._active_unit:
            return
        value = self.width_input.value()
        value = value / 1000.0 if unit == "km" else value * 1000.0
        self._active_unit = unit
        self._updating = True
        self.width_input.setValue(value)
        self._updating = False

    def _request_calibration(self) -> None:
        self.reject()
        self.calibrate_requested.emit()

    def get_width(self) -> float:
        """Return the configured total map width in metres."""
        value = self.width_input.value()
        if self.unit_selector.currentText() == "km":
            return value * _METERS_PER_KILOMETER
        return value
