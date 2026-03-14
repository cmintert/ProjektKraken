"""Raster image analysis helpers.

Provides :func:`analyse_image`, a pure (Qt-free) function that opens an image
file with Pillow, detects its content type, builds a thumbnail array, and
returns a structured :class:`ImageAnalysisResult`.

The function is intended to be called during file selection in the import
dialog (``raster_layer_dialog._on_browse_clicked``) so that the heavy PIL work
can be kept out of the GUI layer and fully unit-tested without Qt.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)

# Maximum thumbnail dimension (pixels)
_THUMB_MAX = 128


@dataclass(frozen=True)
class ImageAnalysisResult:
    """Structured result returned by :func:`analyse_image`.

    Attributes:
        width: Source image width in pixels.
        height: Source image height in pixels.
        pil_mode: Original PIL image mode string (e.g. ``"L"``, ``"RGB"``).
        is_content_grey: True when all channels carry the same intensity
            (native greyscale modes *or* RGB files where R==G==B within a
            2-count tolerance).
        is_float: True when the source mode is ``"F"`` (32-bit float TIFF).
        suggested_mode: ``"continuous"`` for greyscale/float images,
            ``"color"`` otherwise.
        hint: A short human-readable detection summary for display in the UI.
        thumbnail_arr: A uint8 ndarray of shape ``(H, W, 3)`` suitable for
            direct use with :class:`PySide6.QtGui.QImage` Format_RGB888.
            Dimensions are at most ``128 × 128``.
    """

    width: int
    height: int
    pil_mode: str
    is_content_grey: bool
    is_float: bool
    suggested_mode: str
    hint: str
    thumbnail_arr: np.ndarray


def analyse_image(path: str) -> ImageAnalysisResult:
    """Open *path* with Pillow and return image analysis metadata.

    The function is intentionally Qt-free so that it can be tested without a
    running QApplication.

    Args:
        path: Absolute or relative filesystem path to the image file.

    Returns:
        An :class:`ImageAnalysisResult` dataclass with all analysis fields
        populated.

    Raises:
        FileNotFoundError: If *path* does not point to an existing file.
        OSError: If Pillow cannot open the file (unsupported format, corrupt
            data, etc.).
    """
    from PIL import Image as PilImage  # lazy import — PIL not always present

    with PilImage.open(path) as im:
        width, height = im.size
        mode = im.mode

        # ------------------------------------------------------------------ #
        # Greyscale detection
        # ------------------------------------------------------------------ #
        _native_grey = mode in ("L", "LA", "I", "I;16", "F")
        _is_float = mode == "F"
        _is_content_grey = _native_grey

        if not _native_grey and mode in ("RGB", "RGBA"):
            arr = np.array(im.convert("RGB"))
            _drg = int(
                np.max(
                    np.abs(
                        arr[:, :, 0].astype(np.int32) - arr[:, :, 1].astype(np.int32)
                    )
                )
            )
            _drb = int(
                np.max(
                    np.abs(
                        arr[:, :, 0].astype(np.int32) - arr[:, :, 2].astype(np.int32)
                    )
                )
            )
            _is_content_grey = _drg <= 2 and _drb <= 2

        # ------------------------------------------------------------------ #
        # Mode suggestion and hint text
        # ------------------------------------------------------------------ #
        suggested_mode = "continuous" if _is_content_grey else "color"

        if _is_float:
            hint = (
                "Greyscale float (elevation/GIS) — Continuous recommended; "
                "values will be normalised to 0–65535"
            )
        elif _is_content_grey:
            hint = "Greyscale — Continuous recommended"
        else:
            hint = "Colour — Color recommended (RGB preserved as-is)"

        # ------------------------------------------------------------------ #
        # Thumbnail (convert to RGB for safe QImage display across all modes)
        # ------------------------------------------------------------------ #
        thumb = im.copy()
        thumb.thumbnail((_THUMB_MAX, _THUMB_MAX), PilImage.Resampling.LANCZOS)
        thumb_rgb = thumb.convert("RGB")
        thumbnail_arr = np.array(thumb_rgb, dtype=np.uint8)

    return ImageAnalysisResult(
        width=width,
        height=height,
        pil_mode=mode,
        is_content_grey=_is_content_grey,
        is_float=_is_float,
        suggested_mode=suggested_mode,
        hint=hint,
        thumbnail_arr=thumbnail_arr,
    )
