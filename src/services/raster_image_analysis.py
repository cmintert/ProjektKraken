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
from collections import Counter
from dataclasses import dataclass
from typing import Any, Optional

import numpy as np

from src.core.raster_mapping import lookup_label_for_value

logger = logging.getLogger(__name__)

_FLOAT_TAG_BYTE_COUNT = 4
_GREYSCALE_CHANNEL_TOLERANCE = 2
_MAX_PATH_CLASSES = 5
_MAX_REGION_CLASSES = 3
_MIN_PATH_POINTS = 2
_MIN_REGION_POINTS = 3

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
    if (
        isinstance(tag_data, (bytes, bytearray))
        and len(tag_data) >= _FLOAT_TAG_BYTE_COUNT
    ):
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


def _sample_pixel_value(file_path: str, norm_x: float, norm_y: float) -> Optional[int]:
    """Return the integer pixel value at a normalised position, or ``None``.

    Strict bounds check — coordinates outside ``[0, 1]`` return ``None``.
    Only discrete single-channel PIL modes are supported.
    """
    if not (0.0 <= norm_x <= 1.0 and 0.0 <= norm_y <= 1.0):
        return None

    from PIL import Image as PilImage

    try:
        with PilImage.open(file_path) as im:
            if im.mode not in ("L", "I", "I;16"):
                return None
            width, height = im.size
            if width <= 0 or height <= 0:
                return None
            raw = im.getpixel(
                (int(norm_x * (width - 1)), int(norm_y * (height - 1)))
            )
    except (OSError, ValueError):
        return None

    if isinstance(raw, (tuple, list)):
        if not raw:
            return None
        raw = raw[0]
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def sample_raster_semantic(
    file_path: str,
    norm_x: float,
    norm_y: float,
    value_entity_map: dict,
) -> Optional[str]:
    """Sample one pixel of a discrete raster and resolve it to a VEM label.

    Used by the spatial-context builder to answer "what class does the raster
    layer assign to this entity's position?" — e.g. ``"Temperate Forest"``.

    Bounds handling is **strict**: normalised coordinates outside ``[0, 1]``
    return ``None`` rather than clamping to the edge pixel. This avoids the
    ``MapDataBuffer.get_value_at`` failure mode where out-of-coverage points
    silently report the edge pixel's class (commonly "No data" or whatever
    fill value sits at the image border).

    Supported PIL modes: ``"L"``, ``"I"``, ``"I;16"`` (discrete single-channel
    rasters). Color or float-continuous rasters have no categorical mapping
    and return ``None``.

    Args:
        file_path: Absolute path to the raster PNG/TIFF file.
        norm_x: Normalised horizontal position in ``[0, 1]``.
        norm_y: Normalised vertical position in ``[0, 1]``.
        value_entity_map: Canonical VEM dict with ``"mode"`` and ``"mappings"``
            keys, as produced by ``raster_mapping.normalize_value_entity_map``.

    Returns:
        The matching mapping's ``"label"`` field, or ``None`` if the pixel
        cannot be sampled, falls outside bounds, the raster mode is not
        discrete, or no mapping entry covers the sampled value.
    """
    if not isinstance(value_entity_map, dict):
        return None
    if not value_entity_map.get("mappings"):
        return None

    value = _sample_pixel_value(file_path, norm_x, norm_y)
    if value is None:
        return None

    return lookup_label_for_value({"value_entity_map": value_entity_map}, value)


def sample_raster_path_semantics(
    file_path: str,
    points: tuple[tuple[float, float], ...],
    value_entity_map: dict,
) -> Optional[str]:
    """Return bounded semantic transitions along an open normalized path."""
    if len(points) < _MIN_PATH_POINTS or not _valid_vem(value_entity_map):
        return None
    opened = _open_discrete_raster(file_path)
    if opened is None:
        return None
    image, width, height = opened
    try:
        if any(not _in_normalized_bounds(point) for point in points):
            return None
        pixels: list[tuple[int, int]] = []
        for start, end in zip(points, points[1:]):
            start_pixel = _normalized_pixel(start, width, height)
            end_pixel = _normalized_pixel(end, width, height)
            segment = _supercover_line(start_pixel, end_pixel)
            if pixels and segment and pixels[-1] == segment[0]:
                segment = segment[1:]
            pixels.extend(segment)
        labels = [
            _label_for_pixel(image, pixel, value_entity_map) for pixel in pixels
        ]
    finally:
        image.close()
    transitions = _smooth_transitions(labels)
    if not transitions:
        return None
    rendered = transitions[:_MAX_PATH_CLASSES]
    if len(transitions) > _MAX_PATH_CLASSES:
        rendered.append("…")
    return " → ".join(rendered)


def sample_raster_region_semantics(
    file_path: str,
    points: tuple[tuple[float, float], ...],
    value_entity_map: dict,
) -> Optional[str]:
    """Return leading semantic classes by covered raster-cell area."""
    if len(points) < _MIN_REGION_POINTS or not _valid_vem(value_entity_map):
        return None
    opened = _open_discrete_raster(file_path)
    if opened is None:
        return None
    image, width, height = opened
    try:
        if any(not _in_normalized_bounds(point) for point in points):
            return None
        from PIL import Image as PilImage
        from PIL import ImageDraw

        mask = PilImage.new("1", (width, height), 0)
        polygon = [_normalized_pixel(point, width, height) for point in points]
        ImageDraw.Draw(mask).polygon(polygon, fill=1)
        image_values = np.asarray(image)
        mask_values = np.asarray(mask, dtype=bool)
        covered = image_values[mask_values]
        if covered.size == 0:
            return None
        raw_counts = Counter(int(value) for value in covered.tolist())
        label_counts: Counter[str] = Counter()
        for value, count in raw_counts.items():
            label = lookup_label_for_value(
                {"value_entity_map": value_entity_map}, value
            )
            if label:
                label_counts[label] += count
    finally:
        image.close()
    total = sum(label_counts.values())
    if total == 0:
        return None
    leading = sorted(label_counts.items(), key=lambda item: (-item[1], item[0]))[
        :_MAX_REGION_CLASSES
    ]
    return ", ".join(
        f"{label} {round(count * 100 / total)}%" for label, count in leading
    )


def _open_discrete_raster(file_path: str) -> tuple[Any, int, int] | None:
    from PIL import Image as PilImage

    try:
        image = PilImage.open(file_path)
        if image.mode not in ("L", "I", "I;16"):
            image.close()
            return None
        width, height = image.size
        if width <= 0 or height <= 0:
            image.close()
            return None
        return image, width, height
    except (OSError, ValueError):
        return None


def _valid_vem(value_entity_map: dict) -> bool:
    return isinstance(value_entity_map, dict) and bool(
        value_entity_map.get("mappings")
    )


def _in_normalized_bounds(point: tuple[float, float]) -> bool:
    return 0.0 <= point[0] <= 1.0 and 0.0 <= point[1] <= 1.0


def _normalized_pixel(
    point: tuple[float, float], width: int, height: int
) -> tuple[int, int]:
    return (
        int(point[0] * (width - 1)),
        int(point[1] * (height - 1)),
    )


def _label_for_pixel(
    image: Any, pixel: tuple[int, int], value_entity_map: dict
) -> str | None:
    raw = image.getpixel(pixel)
    if isinstance(raw, (tuple, list)):
        raw = raw[0] if raw else None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return lookup_label_for_value({"value_entity_map": value_entity_map}, value)


def _supercover_line(
    start: tuple[int, int], end: tuple[int, int]
) -> list[tuple[int, int]]:
    """Return every raster cell crossed by a line between pixel centres."""
    x, y = start
    end_x, end_y = end
    dx = end_x - x
    dy = end_y - y
    x_step = 1 if dx >= 0 else -1
    y_step = 1 if dy >= 0 else -1
    nx = abs(dx)
    ny = abs(dy)
    cells = [(x, y)]
    ix = 0
    iy = 0
    while ix < nx or iy < ny:
        decision = (1 + 2 * ix) * ny - (1 + 2 * iy) * nx
        if decision == 0:
            x += x_step
            y += y_step
            ix += 1
            iy += 1
        elif decision < 0:
            x += x_step
            ix += 1
        else:
            y += y_step
            iy += 1
        cells.append((x, y))
    return cells


def _smooth_transitions(labels: list[str | None]) -> list[str]:
    runs: list[tuple[str | None, int]] = []
    for label in labels:
        if runs and runs[-1][0] == label:
            previous, count = runs[-1]
            runs[-1] = (previous, count + 1)
        else:
            runs.append((label, 1))
    for index in range(1, len(runs) - 1):
        label, count = runs[index]
        if count == 1 and runs[index - 1][0] == runs[index + 1][0]:
            runs[index] = (runs[index - 1][0], count)
    transitions: list[str] = []
    for label, _count in runs:
        if label is not None and (not transitions or transitions[-1] != label):
            transitions.append(label)
    return transitions


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
        working: Any = im

        # I;16 is PIL's raw 16-bit representation — unusable for copy/thumbnail.
        # Promote to I (32-bit int, still greyscale) to preserve values.
        if mode == "I;16":
            working = im.convert("I")
            mode = working.mode
        # Palette modes carry no scalar data — convert to colour.
        elif mode in ("P", "PA"):
            working = im.convert("RGBA" if mode == "PA" else "RGB")
            mode = working.mode
            mode_converted = True
        # Any other exotic mode: fall back to RGB but flag the conversion.
        elif mode not in ("L", "LA", "I", "F", "RGB", "RGBA"):
            working = im.convert("RGB")
            mode = working.mode
            mode_converted = True

        # ------------------------------------------------------------------ #
        # Greyscale detection
        # ------------------------------------------------------------------ #
        _native_grey = mode in ("L", "LA", "I", "I;16", "F")
        _is_float = mode == "F"
        _is_content_grey = _native_grey

        if not _native_grey and mode in ("RGB", "RGBA"):
            arr = np.array(working.convert("RGB"))
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
            _is_content_grey = (
                _drg <= _GREYSCALE_CHANNEL_TOLERANCE
                and _drb <= _GREYSCALE_CHANNEL_TOLERANCE
            )

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
        thumb = working.copy()
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
def gradient_from_rgb_image(image: Any, stop_count: int = 12) -> dict[str, Any]:
    """Extract a deterministic luminance-ordered gradient from an RGB image."""
    rgb = np.asarray(image.convert("RGB"), dtype=np.uint8).reshape(-1, 3)
    if rgb.size == 0:
        raise ValueError("Cannot extract a palette from an empty image")
    luminance = (
        0.2126 * rgb[:, 0] + 0.7152 * rgb[:, 1] + 0.0722 * rgb[:, 2]
    )
    order = np.argsort(luminance, kind="stable")
    sorted_rgb = rgb[order]
    if np.all(sorted_rgb == sorted_rgb[0]):
        color = "#{:02X}{:02X}{:02X}FF".format(*sorted_rgb[0])
        stops = [
            {"position": 0.0, "color": color},
            {"position": 1.0, "color": color},
        ]
    else:
        count = max(2, min(int(stop_count), len(sorted_rgb)))
        indices = np.linspace(0, len(sorted_rgb) - 1, count).round().astype(int)
        stops = [
            {
                "position": index / (count - 1),
                "color": "#{:02X}{:02X}{:02X}FF".format(*sorted_rgb[pixel]),
            }
            for index, pixel in enumerate(indices)
        ]
    return {
        "type": "gradient",
        "gradient_stops": stops,
        "stretch_min": 0,
        "stretch_max": 65535,
    }
