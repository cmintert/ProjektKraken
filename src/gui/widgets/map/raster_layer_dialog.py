"""Raster Layer Creation Dialog.

Provides a themed dialog for creating new raster (heatmap) layers.
The user chooses a name, mode (discrete / continuous), resolution
preset, and default fill value.
"""

import logging
from typing import Any, Dict, Optional, Tuple

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.gui.utils.style_helper import StyleHelper

logger = logging.getLogger(__name__)

# Pre-defined resolution presets as (width, height) tuples
_RESOLUTION_PRESETS: list[Tuple[str, int, int]] = [
    ("256 × 256  (tiny)", 256, 256),
    ("512 × 512  (small)", 512, 512),
    ("1024 × 512 (medium, 2:1)", 1024, 512),
    ("1024 × 1024 (medium)", 1024, 1024),
    ("2048 × 1024 (large, 2:1)", 2048, 1024),
    ("2048 × 2048 (large)", 2048, 2048),
]


class RasterLayerDialog(QDialog):
    """Dialog for creating a new raster layer.

    After ``exec()`` returns ``Accepted``, call :meth:`result_data`
    to retrieve the user's choices.

    Args:
        parent: Parent widget.
        map_aspect: Aspect ratio (width/height) of the current map image.
            Used to suggest matching resolutions.

    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        map_aspect: float = 1.0,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Raster Layer")
        self.setMinimumWidth(360)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        # Name
        self._name_edit = QLineEdit()
        self._name_edit.setText("Raster Layer")
        self._name_edit.setPlaceholderText("Layer name")
        form.addRow("Name:", self._name_edit)

        # Mode
        self._mode_combo = QComboBox()
        self._mode_combo.addItems(["discrete", "continuous"])
        self._mode_combo.setToolTip(
            "discrete: category / biome map\ncontinuous: height / temperature gradient"
        )
        form.addRow("Mode:", self._mode_combo)

        # Resolution preset
        self._res_combo = QComboBox()
        for label, _w, _h in _RESOLUTION_PRESETS:
            self._res_combo.addItem(label)
        # Default to 1024×1024
        self._res_combo.setCurrentIndex(3)
        form.addRow("Resolution:", self._res_combo)

        # Default value
        self._default_spin = QSpinBox()
        self._default_spin.setRange(0, 65535)
        self._default_spin.setValue(0)
        self._default_spin.setToolTip("Initial value for all pixels (0–65535)")
        form.addRow("Default value:", self._default_spin)

        layout.addLayout(form)

        # Info label
        info = QLabel(
            "Raster layers are stored as 16-bit PNG files alongside your project."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # Apply theme
        self.setStyleSheet(StyleHelper.get_dialog_base_style())

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def result_data(self) -> Dict[str, Any]:
        """Return the user's choices as a dict.

        Keys: ``name``, ``mode``, ``width``, ``height``, ``default_value``.

        """
        idx = self._res_combo.currentIndex()
        _label, w, h = _RESOLUTION_PRESETS[idx]
        return {
            "name": self._name_edit.text().strip() or "Raster Layer",
            "mode": self._mode_combo.currentText(),
            "width": w,
            "height": h,
            "default_value": self._default_spin.value(),
        }
