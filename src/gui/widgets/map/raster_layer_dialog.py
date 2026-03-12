"""Raster Layer Creation Dialog.

Provides a themed dialog for creating new raster (heatmap) layers.
The user chooses a name, mode (discrete / continuous), resolution
preset, and default fill value.
"""

import logging
import os
from typing import Any, Dict, Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
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
        self.setMinimumWidth(380)

        self._map_aspect = map_aspect
        self._import_path: str = ""
        self._import_width: int = 0
        self._import_height: int = 0

        layout = QVBoxLayout(self)
        form = QFormLayout()

        # Name
        self._name_edit = QLineEdit()
        self._name_edit.setText("Raster Layer")
        self._name_edit.setPlaceholderText("Layer name")
        form.addRow("Name:", self._name_edit)

        # Mode
        self._mode_combo = QComboBox()
        self._mode_combo.addItems(["discrete", "continuous", "color"])
        self._mode_combo.setToolTip(
            "<b>Discrete</b>: Each pixel value maps to a named class (e.g. biome, terrain type).\n"
            "Use for categorical data — colours, labels, and linked world items per value.\n\n"
            "<b>Continuous</b>: Pixel values form a smooth scalar gradient (e.g. elevation, temperature).\n"
            "Use for quantitative data — rendered with a start-to-end colour ramp.\n\n"
            "<b>Color</b>: Displays an imported RGB image with its original colours.\n"
            "Use for pre-coloured overlays such as illustrated terrain or satellite imagery.\n"
            "Painting and value mapping are not supported in this mode.\n\n"
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

        # Import from file section
        import_form = QFormLayout()

        browse_row = QHBoxLayout()
        self._browse_btn = QPushButton("Browse…")
        self._browse_btn.setToolTip("Import an existing image as the raster layer data")
        self._browse_btn.clicked.connect(self._on_browse_clicked)
        browse_row.addWidget(self._browse_btn)
        self._clear_btn = QPushButton("✕")
        self._clear_btn.setFixedSize(24, 24)
        self._clear_btn.setToolTip("Clear selected file")
        self._clear_btn.clicked.connect(self._on_clear_import)
        self._clear_btn.setVisible(False)
        browse_row.addWidget(self._clear_btn)
        browse_row.addStretch()
        import_form.addRow("Import image:", browse_row)

        self._import_file_label = QLabel("No file selected")
        import_form.addRow("", self._import_file_label)

        self._import_dims_label = QLabel("")
        self._import_dims_label.setVisible(False)
        import_form.addRow("Detected size:", self._import_dims_label)

        self._aspect_warn_label = QLabel("⚠ Aspect ratio mismatch — image will be stretched")
        self._aspect_warn_label.setWordWrap(True)
        self._aspect_warn_label.setStyleSheet(StyleHelper.get_preview_label_style())
        self._aspect_warn_label.setVisible(False)
        import_form.addRow("", self._aspect_warn_label)
        # JPEG/lossy format warning
        self._lossy_warn_label = QLabel(
            "\u26a0 JPEG is lossy \u2014 compression artefacts will reduce precision"
        )
        self._lossy_warn_label.setWordWrap(True)
        self._lossy_warn_label.setStyleSheet(StyleHelper.get_preview_label_style())
        self._lossy_warn_label.setVisible(False)
        import_form.addRow("", self._lossy_warn_label)

        # Auto-detected content type hint
        self._detect_hint_label = QLabel("")
        self._detect_hint_label.setWordWrap(True)
        self._detect_hint_label.setVisible(False)
        import_form.addRow("Detected:", self._detect_hint_label)

        # Thumbnail preview
        self._preview_label = QLabel()
        self._preview_label.setFixedSize(128, 128)
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setStyleSheet(
            "border: 1px solid gray; background-color: #222222;"
        )
        self._preview_label.setVisible(False)
        import_form.addRow("Preview:", self._preview_label)
        layout.addLayout(import_form)

        # Info label
        info = QLabel(
            "Raster layers are stored as PNG files alongside your project "
            "(16-bit greyscale for discrete/continuous; 8-bit RGBA for color)."
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

    def _on_browse_clicked(self) -> None:
        """Open a file dialog and populate the import fields."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Image as Raster Layer",
            "",
            "Supported images (*.png *.tif *.tiff *.jpg *.jpeg)"
            ";;PNG — lossless (*.png)"
            ";;TIFF — lossless / float (*.tif *.tiff)"
            ";;JPEG — lossy (*.jpg *.jpeg)",
        )
        if not path:
            return

        import numpy as _np

        try:
            from PIL import Image as PilImage

            with PilImage.open(path) as im:
                w, h = im.size
                mode = im.mode

                # Detect greyscale content (also covers RGB files where R==G==B)
                _is_native_grey = mode in ("L", "LA", "I", "I;16", "F")
                _is_float = mode == "F"
                _is_content_grey = _is_native_grey
                if not _is_native_grey and mode in ("RGB", "RGBA"):
                    _arr = _np.array(im.convert("RGB"))
                    _drg = int(_np.max(_np.abs(
                        _arr[:, :, 0].astype(_np.int32) - _arr[:, :, 1].astype(_np.int32)
                    )))
                    _drb = int(_np.max(_np.abs(
                        _arr[:, :, 0].astype(_np.int32) - _arr[:, :, 2].astype(_np.int32)
                    )))
                    _is_content_grey = _drg <= 2 and _drb <= 2

                # Auto-select mode
                if _is_content_grey:
                    suggested_mode = "continuous"
                else:
                    suggested_mode = "color"
                idx = self._mode_combo.findText(suggested_mode)
                if idx >= 0:
                    self._mode_combo.setCurrentIndex(idx)

                # Detection hint label
                if _is_float:
                    hint = (
                        "Greyscale float (elevation/GIS) — Continuous recommended; "
                        "values will be normalised to 0–65535"
                    )
                elif _is_content_grey:
                    hint = "Greyscale — Continuous recommended"
                else:
                    hint = "Colour — Color recommended (RGB preserved as-is)"
                self._detect_hint_label.setText(hint)
                self._detect_hint_label.setVisible(True)

                # Thumbnail (convert to RGB for safe display across all modes)
                thumb = im.copy()
                thumb.thumbnail((128, 128), PilImage.Resampling.LANCZOS)
                thumb_rgb = thumb.convert("RGB")
                thumb_arr = _np.array(thumb_rgb, dtype=_np.uint8)
                th, tw = thumb_arr.shape[:2]
                qimg = QImage(
                    thumb_arr.data, tw, th, tw * 3, QImage.Format.Format_RGB888
                )
                self._preview_label.setPixmap(QPixmap.fromImage(qimg.copy()))
                self._preview_label.setVisible(True)

        except Exception as exc:
            logger.warning("RasterLayerDialog: cannot open %r: %s", path, exc)
            return

        # Show warning for lossy formats
        self._lossy_warn_label.setVisible(path.lower().endswith((".jpg", ".jpeg")))

        self._import_path = path
        self._import_width = w
        self._import_height = h
        self._import_file_label.setText(os.path.basename(path))
        self._import_dims_label.setText(f"{w} × {h}")
        self._import_dims_label.setVisible(True)
        self._clear_btn.setVisible(True)
        if h > 0 and self._map_aspect > 0:
            mismatch = abs(w / h - self._map_aspect) / self._map_aspect > 0.05
            self._aspect_warn_label.setVisible(mismatch)
        self._res_combo.setEnabled(False)
        self._default_spin.setEnabled(False)

    def _on_clear_import(self) -> None:
        """Clear the selected import file and re-enable resolution controls."""
        self._import_path = ""
        self._import_width = 0
        self._import_height = 0
        self._import_file_label.setText("No file selected")
        self._import_dims_label.setVisible(False)
        self._aspect_warn_label.setVisible(False)
        self._lossy_warn_label.setVisible(False)
        self._detect_hint_label.setVisible(False)
        self._preview_label.setVisible(False)
        self._clear_btn.setVisible(False)
        self._res_combo.setEnabled(True)
        self._default_spin.setEnabled(self._mode_combo.currentText() != "color")

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
        elif mode == "continuous":
            self._mode_hint.setText(
                "Scalar gradient (elevation, temperature, rainfall…). "
                "Rendered as a smooth colour ramp from start to end colour."
            )
        else:  # color
            self._mode_hint.setText(
                "RGB image overlay — original colours are preserved as-is. "
                "No painting or value mapping. Ideal for illustrated maps or satellite imagery."
            )
        # Default value only makes sense for discrete/continuous
        if hasattr(self, "_default_spin"):
            self._default_spin.setEnabled(mode != "color")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def result_data(self) -> Dict[str, Any]:
        """Return the user's choices as a dict.

        Keys: ``name``, ``mode``, ``width``, ``height``, ``default_value``,
        ``import_path``.  When *import_path* is non-empty the width/height
        come from the detected image dimensions.

        """
        if self._import_path:
            w, h = self._import_width, self._import_height
        else:
            idx = self._res_combo.currentIndex()
            _label, w, h = _RESOLUTION_PRESETS[idx]
        return {
            "name": self._name_edit.text().strip() or "Raster Layer",
            "mode": self._mode_combo.currentText(),
            "width": w,
            "height": h,
            "default_value": self._default_spin.value(),
            "import_path": self._import_path,
        }
