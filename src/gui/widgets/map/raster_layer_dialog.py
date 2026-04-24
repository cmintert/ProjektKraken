"""Raster Layer Creation Dialog.

Provides a themed dialog for creating new raster (heatmap) layers.
The user chooses a name, mode (discrete / continuous), resolution
preset, and default fill value.
"""

import logging
import os
from typing import Any, Dict, Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtGui import QDoubleValidator, QImage, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.gui.utils.style_helper import StyleHelper
from src.services.raster_image_analysis import ImageAnalysisResult, analyse_image

logger = logging.getLogger(__name__)

def _parse_float_or_none(text: str) -> Optional[float]:
    """Return a float parsed from *text*, or ``None`` for blank / invalid."""
    text = text.strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


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

        # Value range (continuous mode only)
        self._build_value_range_group(layout)
        self._update_value_range_visibility(self._mode_combo.currentText())

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
        """Open a file dialog, analyse the chosen image, and populate fields."""
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
        self._apply_imported_file(path)

    def _apply_imported_file(self, path: str) -> None:
        """Analyse *path* and populate preview / inferred fields.

        Separated from :meth:`_on_browse_clicked` so tests can drive the
        inference flow without opening a native file dialog.
        """
        try:
            result: ImageAnalysisResult = analyse_image(path)
        except Exception as exc:
            logger.warning("RasterLayerDialog: cannot open %r: %s", path, exc)
            return

        w, h = result.width, result.height

        # Auto-select mode
        idx = self._mode_combo.findText(result.suggested_mode)
        if idx >= 0:
            self._mode_combo.setCurrentIndex(idx)

        # Detection hint label
        self._detect_hint_label.setText(result.hint)
        self._detect_hint_label.setVisible(True)

        # Thumbnail preview
        arr = result.thumbnail_arr
        th, tw = arr.shape[:2]
        qimg = QImage(arr.data, tw, th, tw * 3, QImage.Format.Format_RGB888)
        self._preview_label.setPixmap(QPixmap.fromImage(qimg.copy()))
        self._preview_label.setVisible(True)

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

        # Pre-fill real-world value range from inferred metadata
        self._apply_value_metadata(result.value_metadata)

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
        # Clear inferred value-range fields
        self._display_min_edit.clear()
        self._display_max_edit.clear()
        self._display_unit_edit.clear()
        self._value_range_hint.setVisible(False)

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
        self._update_value_range_visibility(mode)

    # ------------------------------------------------------------------
    # Value-range section (continuous mode only)
    # ------------------------------------------------------------------

    def _build_value_range_group(self, layout: QVBoxLayout) -> None:
        """Create the collapsible value-range group and append it to *layout*.

        Populates ``self._value_range_group`` and its child edits so that
        :meth:`_apply_value_metadata` and :meth:`result_data` can reference
        them.
        """
        self._value_range_group = QGroupBox("Value Range (optional)")
        self._value_range_group.setToolTip(
            "Map raw pixel values (0–65535) to real-world units such as "
            "elevation in metres or temperature in °C. Used by the legend and "
            "probe popup."
        )
        group_layout = QVBoxLayout(self._value_range_group)
        group_layout.setContentsMargins(8, 8, 8, 8)
        group_layout.setSpacing(4)

        # Hint: shown after a successful inference pre-fill
        self._value_range_hint = QLabel("")
        self._value_range_hint.setWordWrap(True)
        self._value_range_hint.setStyleSheet(StyleHelper.get_preview_label_style())
        self._value_range_hint.setVisible(False)
        group_layout.addWidget(self._value_range_hint)

        row = QHBoxLayout()
        row.setSpacing(6)
        row.addWidget(QLabel("Min:"))
        self._display_min_edit = QLineEdit()
        self._display_min_edit.setFixedWidth(80)
        self._display_min_edit.setPlaceholderText("e.g. -4000")
        self._display_min_edit.setValidator(QDoubleValidator())
        row.addWidget(self._display_min_edit)
        row.addWidget(QLabel("Max:"))
        self._display_max_edit = QLineEdit()
        self._display_max_edit.setFixedWidth(80)
        self._display_max_edit.setPlaceholderText("e.g. 8000")
        self._display_max_edit.setValidator(QDoubleValidator())
        row.addWidget(self._display_max_edit)
        row.addWidget(QLabel("Unit:"))
        self._display_unit_edit = QLineEdit()
        self._display_unit_edit.setFixedWidth(60)
        self._display_unit_edit.setPlaceholderText("e.g. m")
        row.addWidget(self._display_unit_edit)
        row.addStretch()
        group_layout.addLayout(row)

        layout.addWidget(self._value_range_group)

    def _update_value_range_visibility(self, mode: str) -> None:
        """Show the value-range group only in continuous mode."""
        if hasattr(self, "_value_range_group"):
            self._value_range_group.setVisible(mode == "continuous")

    def _apply_value_metadata(self, meta: Any) -> None:
        """Populate value-range fields from an inferred ValueMetadata.

        Args:
            meta: A :class:`ValueMetadata` instance or ``None``.
        """
        if meta is None:
            self._value_range_hint.setVisible(False)
            return
        # Only pre-fill when user hasn't typed anything yet
        if not self._display_min_edit.text():
            self._display_min_edit.setText(str(float(meta.min)))
        if not self._display_max_edit.text():
            self._display_max_edit.setText(str(float(meta.max)))
        if not self._display_unit_edit.text() and meta.unit:
            self._display_unit_edit.setText(meta.unit)

        source_text = {
            "gdal_metadata": "GDAL statistics",
            "tiff_sample_tags": "TIFF sample tags",
            "float_pixel_range": "float pixel range",
        }.get(meta.source, meta.source)
        self._value_range_hint.setText(
            f"📊 Inferred from {source_text} — edit to override."
        )
        self._value_range_hint.setVisible(True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def result_data(self) -> Dict[str, Any]:
        """Return the user's choices as a dict.

        Keys: ``name``, ``mode``, ``width``, ``height``, ``default_value``,
        ``import_path``, plus optional real-world value-range keys
        (``display_min``, ``display_max``, ``unit``) populated only in
        *continuous* mode.  When *import_path* is non-empty the width/height
        come from the detected image dimensions.

        """
        if self._import_path:
            w, h = self._import_width, self._import_height
        else:
            idx = self._res_combo.currentIndex()
            _label, w, h = _RESOLUTION_PRESETS[idx]

        mode = self._mode_combo.currentText()
        display_min: Optional[float] = None
        display_max: Optional[float] = None
        unit = ""
        if mode == "continuous":
            display_min = _parse_float_or_none(self._display_min_edit.text())
            display_max = _parse_float_or_none(self._display_max_edit.text())
            unit = self._display_unit_edit.text().strip()

        return {
            "name": self._name_edit.text().strip() or "Raster Layer",
            "mode": mode,
            "width": w,
            "height": h,
            "default_value": self._default_spin.value(),
            "import_path": self._import_path,
            "display_min": display_min,
            "display_max": display_max,
            "unit": unit,
        }
