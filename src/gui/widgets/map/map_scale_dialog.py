"""Dialog for configuring map scale settings."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.gui.utils.style_helper import StyleHelper


class MapScaleDialog(QDialog):
    """Dialog to set the map's real-world width, with a calibration option."""

    calibrate_requested = Signal()

    def __init__(
        self, current_width: float, parent: QWidget = None, map_name: str = "Map"
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Map Scale Base - {map_name}")
        self.setModal(True)
        self.setMinimumWidth(400)
        self.setStyleSheet(StyleHelper.get_dialog_base_style())

        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # Instructions
        instruction = QLabel(
            "Enter the total real-world width of this map image in meters."
        )
        instruction.setWordWrap(True)
        layout.addWidget(instruction)

        # Input Row
        input_layout = QHBoxLayout()

        self.width_input = QDoubleSpinBox()
        self.width_input.setRange(0.1, 1_000_000_000.0)  # Free range: 10cm to 1M km
        self.width_input.setDecimals(1)
        self.width_input.setSingleStep(1.0)  # 1m step
        self.width_input.setSuffix(" m")
        self.width_input.setValue(current_width)
        self.width_input.setStyleSheet(StyleHelper.get_spinbox_style())

        input_layout.addWidget(QLabel("Total Width:"))
        input_layout.addWidget(self.width_input, 1)  # Stretch input
        layout.addLayout(input_layout)

        # Calibration Section
        calib_layout = QVBoxLayout()
        calib_layout.setSpacing(4)

        self.btn_calibrate = QPushButton("Calibrate from Measurement...")
        self.btn_calibrate.setToolTip(
            "Measure a known distance on the map to automatically calculate total width."
        )
        self.btn_calibrate.setStyleSheet(StyleHelper.get_primary_button_style())
        self.btn_calibrate.clicked.connect(self._on_calibrate)

        calib_hint = QLabel(
            "Use this if you know the distance between two specific points."
        )
        calib_hint.setStyleSheet(StyleHelper.get_preview_label_style())

        calib_layout.addWidget(self.btn_calibrate)
        calib_layout.addWidget(calib_hint)
        layout.addLayout(calib_layout)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        # Cancel button uses default style (neutral)

        self.btn_ok = QPushButton("Apply")
        self.btn_ok.setDefault(True)
        self.btn_ok.setStyleSheet(StyleHelper.get_primary_button_style())
        self.btn_ok.clicked.connect(self.accept)

        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_ok)
        layout.addLayout(btn_layout)

    def _on_calibrate(self) -> None:
        """Handle calibrate button click."""
        self.calibrate_requested.emit()
        self.reject()  # Close dialog to let user interact with map

    def get_width(self) -> float:
        """Returns the configured width in meters."""
        return self.width_input.value()
