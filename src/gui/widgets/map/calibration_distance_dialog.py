"""Dialog for entering calibration distance."""

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from src.gui.utils.help_context import declare_inspection
from src.gui.utils.style_helper import StyleHelper
from src.gui.widgets.numeric_inputs import ScrollSafeDoubleSpinBox
from src.gui.widgets.standard_buttons import StandardButton as QPushButton


class CalibrationDistanceDialog(QDialog):
    """Dialog to enter real-world distance for a measured segment."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the calibration distance dialog.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle("Calibration Measurement")
        self.setModal(True)
        self.setMinimumWidth(300)
        self.setStyleSheet(StyleHelper.get_dialog_base_style())

        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # Instructions
        instruction = QLabel("Enter the real-world distance for the measured segment.")
        instruction.setWordWrap(True)
        layout.addWidget(instruction)

        # Input Row
        input_layout = QHBoxLayout()

        self.dist_input = declare_inspection(
            ScrollSafeDoubleSpinBox(),
            "src-gui-widgets-map-calibration-distance-dialog-calibrationdistancedialog-init-self-dist-input|map.calibration|help-inspect-src-gui-widgets-map-calibration-distance-dialog-calibrationdistancedialog-init-self-dist-input",
        )
        self.dist_input.setRange(0.1, 1_000_000_000.0)  # Free range
        self.dist_input.setDecimals(1)
        self.dist_input.setSingleStep(1.0)
        self.dist_input.setValue(100.0)  # Default
        self.dist_input.setStyleSheet(StyleHelper.get_spinbox_style())

        self.unit_selector = declare_inspection(
            QComboBox(),
            "src-gui-widgets-map-calibration-distance-dialog-calibrationdistancedialog-init-self-unit-selector|map.calibration|help-inspect-src-gui-widgets-map-calibration-distance-dialog-calibrationdistancedialog-init-self-unit-selector",
        )
        self.unit_selector.addItems(["m", "km"])
        self.unit_selector.setStyleSheet(StyleHelper.get_input_field_style())

        input_layout.addWidget(QLabel("Distance:"))
        input_layout.addWidget(self.dist_input, 1)
        input_layout.addWidget(self.unit_selector)
        layout.addLayout(input_layout)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_cancel = declare_inspection(
            QPushButton("Cancel"),
            "src-gui-widgets-map-calibration-distance-dialog-calibrationdistancedialog-init-self-btn-cancel|map.calibration|help-inspect-src-gui-widgets-map-calibration-distance-dialog-calibrationdistancedialog-init-self-btn-cancel",
        )
        self.btn_cancel.clicked.connect(self.reject)

        self.btn_ok = declare_inspection(
            QPushButton("Apply"),
            "src-gui-widgets-map-calibration-distance-dialog-calibrationdistancedialog-init-self-btn-ok|map.calibration|help-inspect-src-gui-widgets-map-calibration-distance-dialog-calibrationdistancedialog-init-self-btn-ok",
        )
        self.btn_ok.setDefault(True)
        self.btn_ok.setStyleSheet(StyleHelper.get_primary_button_style())
        self.btn_ok.clicked.connect(self.accept)

        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_ok)
        layout.addLayout(btn_layout)

    def get_distance_meters(self) -> float:
        """Returns the entered distance in meters."""
        val = self.dist_input.value()
        if self.unit_selector.currentText() == "km":
            return val * 1000.0
        return val
