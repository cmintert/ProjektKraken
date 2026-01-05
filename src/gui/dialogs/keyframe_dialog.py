"""
Dialog for editing keyframe properties.
"""

from typing import Optional, Tuple

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)


class KeyframeDialog(QDialog):
    """
    Dialog to edit keyframe time and position.
    """

    def __init__(
        self,
        t: float,
        x: float,
        y: float,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit Keyframe")
        self.resize(300, 200)

        self._t = t
        self._x = x
        self._y = y

        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)

        form_layout = QFormLayout()

        # Time
        self.spin_t = QDoubleSpinBox()
        self.spin_t.setRange(0, 999999)
        self.spin_t.setDecimals(2)
        self.spin_t.setValue(self._t)
        self.spin_t.setSuffix(" s")
        form_layout.addRow("Time:", self.spin_t)

        # X
        self.spin_x = QDoubleSpinBox()
        self.spin_x.setRange(0, 1)
        self.spin_x.setDecimals(3)
        self.spin_x.setSingleStep(0.01)
        self.spin_x.setValue(self._x)
        form_layout.addRow("X (0-1):", self.spin_x)

        # Y
        self.spin_y = QDoubleSpinBox()
        self.spin_y.setRange(0, 1)
        self.spin_y.setDecimals(3)
        self.spin_y.setSingleStep(0.01)
        self.spin_y.setValue(self._y)
        form_layout.addRow("Y (0-1):", self.spin_y)

        # Info Note
        if self._t == 0:
            lbl_note = QLabel(
                "Note: Start keyframe (t=0) usually defines initial position."
            )
            lbl_note.setWordWrap(True)
            lbl_note.setStyleSheet("color: gray; font-size: 10pt;")
            layout.addWidget(lbl_note)

        layout.addLayout(form_layout)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_values(self) -> Tuple[float, float, float]:
        """Returns (t, x, y)."""
        return (self.spin_t.value(), self.spin_x.value(), self.spin_y.value())
