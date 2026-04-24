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
import os
import struct
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# Maximum thumbnail dimension (pixels)
_THUMB_MAX = 128

# TIFF tag numbers used for value-range inference
_TAG_GDAL_METADATA = 42112
_TAG_SMIN_SAMPLE = 340
_TAG_SMAX_SAMPLE = 341


@dataclass(frozen=True)
class ValueMetadata:
    """Real-world value range inferred from image metadata.

    Attributes:
        min: Real-world value corresponding to the lowest pixel value.
        max: Real-world value corresponding to the highest pixel value.
        unit: Optional unit label (e.g. ``"metre"``, ``"m"``, ``"°C"``).
        source: Where the metadata came from.  One of:
            ``"gdal_metadata"`` — parsed from GDAL_METADATA TIFF tag XML.
            ``"tiff_sample_tags"`` — SMinSampleValue / SMaxSampleValue tags.
            ``"float_pixel_range"`` — computed from float32 pixel data.
    """

    min: float
    max: float
    unit: str = ""
    source: str = ""


def _parse_gdal_metadata_xml(xml_text: str) -> Optional[ValueMetadata]:
    """Parse a GDAL_METADATA XML blob and extract statistics + unit.

    Args:
        xml_text: The raw XML string from TIFF tag 42112.

    Returns:
        ValueMetadata or None if the XML is malformed or missing both
        STATISTICS_MINIMUM and STATISTICS_MAXIMUM.
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        logger.debug("GDAL_METADATA XML parse failed")
        return None

    items: dict[str, str] = {}
    for item in root.findall(".//Item"):
        name = item.get("name")
        if name and item.text is not None:
            items[name] = item.text.strip()

    smin = items.get("STATISTICS_MINIMUM")
    smax = items.get("STATISTICS_MAXIMUM")
    if smin is None or smax is None:
        return None
    try:
        vmin = float(smin)
        vmax = float(smax)
    except ValueError:
        return None

    unit = items.get("UNITTYPE", "")
    return ValueMetadata(min=vmin, max=vmax, unit=unit, source="gdal_metadata")


def _read_sample_value_tag(
    tag_data: object,
) -> Optional[float]:
    """Decode the SMinSampleValue / SMaxSampleValue tag payload.

    PIL may expose these as a ``bytes`` object (we packed them that way in
    tests) or as a tuple/list of floats depending on the writer.  Handle
    both defensively.
    """
    if tag_data is None:
        return None
    if isinstance(tag_data, (int, float)):
        return float(tag_data)
    if isinstance(tag_data, (tuple, list)) and tag_data:
        try:
            return float(tag_data[0])
        except (TypeError, ValueError):
            return None
    if isinstance(tag_data, (bytes, bytearray)) and len(tag_data) >= 4:
        try:
            return struct.unpack("<f", bytes(tag_data[:4]))[0]
        except struct.error:
            return None
    return None


def _pixel_range_from_float(path: str) -> Optional[ValueMetadata]:
    """Compute finite pixel min/max from a float-mode image file.

    Only applies to PIL-mode ``"F"`` (32-bit float) images, which are
    typical for DEM GeoTIFFs with raw elevation values.  NaN and Inf
    are skipped.
    """
    from PIL import Image as PilImage

    try:
        with PilImage.open(path) as im:
            if im.mode != "F":
                return None
            arr = np.asarray(im, dtype=np.float32)
    except (OSError, ValueError):
        return None

    finite = arr[np.isfinite(arr)]
    if finite.size == 0:
        return None

    return ValueMetadata(
        min=float(finite.min()),
        max=float(finite.max()),
        source="float_pixel_range",
    )


def extract_value_metadata(path: str) -> Optional[ValueMetadata]:
    """Infer the real-world value range for a raster image file.

    Inference sources, tried in order:

    1. ``GDAL_METADATA`` TIFF tag (42112) — XML with
       ``STATISTICS_MINIMUM`` / ``STATISTICS_MAXIMUM`` (and optional
       ``UNITTYPE``).
    2. ``SMinSampleValue`` / ``SMaxSampleValue`` TIFF tags (340/341).
    3. Float TIFFs (PIL mode ``"F"``) — min/max of finite pixel values.

    Args:
        path: Absolute or relative filesystem path to the image file.

    Returns:
        A :class:`ValueMetadata` instance, or ``None`` if no source
        matched or the file cannot be opened.
    """
    if not os.path.isfile(path):
        return None

    from PIL import Image as PilImage

    # --- Sources 1 and 2: TIFF tags ---------------------------------------
    try:
        with PilImage.open(path) as im:
            tags = getattr(im, "tag_v2", None)
            if tags is not None:
                # Source 1: GDAL_METADATA XML
                gdal_raw = tags.get(_TAG_GDAL_METADATA)
                if isinstance(gdal_raw, bytes):
                    try:
                        gdal_raw = gdal_raw.decode("utf-8", errors="replace")
                    except Exception:  # pragma: no cover - defensive
                        gdal_raw = None
                if isinstance(gdal_raw, str) and gdal_raw.strip():
                    parsed = _parse_gdal_metadata_xml(gdal_raw)
                    if parsed is not None:
                        return parsed

                # Source 2: SMin/SMax sample tags
                smin = _read_sample_value_tag(tags.get(_TAG_SMIN_SAMPLE))
                smax = _read_sample_value_tag(tags.get(_TAG_SMAX_SAMPLE))
                if smin is not None and smax is not None:
                    return ValueMetadata(
                        min=smin,
                        max=smax,
                        source="tiff_sample_tags",
                    )
    except (OSError, ValueError):
        return None

    # --- Source 3: float pixel range --------------------------------------
    return _pixel_range_from_float(path)


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
        mode_converted: True if the image was converted from an unsupported
            mode to RGB for analysis.
        value_metadata: Inferred real-world value range (min/max/unit) from
            image metadata, or ``None`` if no source matched.
    """

    width: int
    height: int
    pil_mode: str
    is_content_grey: bool
    is_float: bool
    suggested_mode: str
    hint: str
    thumbnail_arr: np.ndarray
    mode_converted: bool = False
    value_metadata: Optional[ValueMetadata] = None


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
        original_mode = im.mode
        mode = original_mode
        mode_converted = False

        # I;16 is PIL's raw 16-bit representation — unusable for copy/thumbnail.
        # Promote to I (32-bit int, still greyscale) to preserve values.
        if mode == "I;16":
            im = im.convert("I")
            mode = im.mode
        # Palette modes carry no scalar data — convert to colour.
        elif mode in ("P", "PA"):
            im = im.convert("RGBA" if mode == "PA" else "RGB")
            mode = im.mode
            mode_converted = True
        # Any other exotic mode: fall back to RGB but flag the conversion.
        elif mode not in ("L", "LA", "I", "F", "RGB", "RGBA"):
            im = im.convert("RGB")
            mode = im.mode
            mode_converted = True

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

        if mode_converted:
            hint += f" (⚠ Image format '{original_mode}' was converted to RGB for compatibility)"

        # ------------------------------------------------------------------ #
        # Thumbnail (convert to RGB for safe QImage display across all modes)
        # ------------------------------------------------------------------ #
        thumb = im.copy()
        thumb.thumbnail((_THUMB_MAX, _THUMB_MAX), PilImage.Resampling.LANCZOS)
        thumb_rgb = thumb.convert("RGB")
        thumbnail_arr = np.array(thumb_rgb, dtype=np.uint8)

    # Real-world value-range inference (GeoTIFF metadata, float pixel range…)
    try:
        value_metadata = extract_value_metadata(path)
    except Exception:  # pragma: no cover - defensive
        logger.debug("extract_value_metadata raised unexpectedly", exc_info=True)
        value_metadata = None

    return ImageAnalysisResult(
        width=width,
        height=height,
        pil_mode=mode,
        is_content_grey=_is_content_grey,
        is_float=_is_float,
        suggested_mode=suggested_mode,
        hint=hint,
        thumbnail_arr=thumbnail_arr,
        mode_converted=mode_converted,
        value_metadata=value_metadata,
    )
