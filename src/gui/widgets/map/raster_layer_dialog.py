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
    QFrame,
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
            "<b>Discrete</b>: Each pixel value maps to a named class (e.g. biome, terrain type).\n"
            "Use for categorical data — colours, labels, and linked world items per value.\n\n"
            "<b>Continuous</b>: Pixel values form a smooth scalar gradient (e.g. elevation, temperature).\n"
            "Use for quantitative data — rendered with a start-to-end colour ramp.\n\n"
            "⚠ Mode cannot be changed after the layer is created."
        )
        form.addRow("Mode:", self._mode_combo)

        # Dynamic mode hint — updates when the user changes mode
        self._mode_hint = QLabel()
        self._mode_hint.setWordWrap(True)
        self._mode_hint.setStyleSheet(StyleHelper.get_preview_label_style())
        form.addRow("", self._mode_hint)
        self._mode_combo.currentTextChanged.connect(self._on_mode_changed)
        self._on_mode_changed(self._mode_combo.currentText())

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

        # Separator line
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep)

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
    # Private helpers
    # ------------------------------------------------------------------

    def _on_mode_changed(self, mode: str) -> None:
        """Update the hint label when the mode selection changes.

        Args:
            mode: The newly selected mode string.
        """
        if mode == "discrete":
            self._mode_hint.setText(
                "Categories (biomes, terrain types, land use…). "
                "Paint with integer values; each value can have a label and a linked world item."
            )
        else:
            self._mode_hint.setText(
                "Scalar gradient (elevation, temperature, rainfall…). "
                "Rendered as a smooth colour ramp from start to end colour."
            )

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
