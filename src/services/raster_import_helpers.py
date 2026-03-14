"""Pure helper functions for raster layer image import (M5).

All functions operate on Pillow Images and numpy arrays.  No Qt, no DB, no
side effects — fully unit-testable without a running application.
"""

import numpy as np
from PIL import Image as PilImage

__all__ = [
    "detect_greyscale",
    "normalize_to_uint16",
    "quantize_discrete_rgb",
    "choose_resample",
]

# Max channel difference (inclusive) that still counts as greyscale.
_GREY_THRESHOLD = 2


def detect_greyscale(img: PilImage.Image) -> bool:
    """Return True if *img* contains only greyscale content.

    Handles both natively greyscale modes (L, LA, I, F, I;16) and RGB/RGBA
    images where R ≈ G ≈ B (common output from GIS and rendering tools).

    Args:
        img: The source PIL image in any mode.

    Returns:
        bool: True when the image is effectively greyscale.
    """
    if img.mode in ("L", "LA", "I", "I;16", "F"):
        return True
    if img.mode in ("RGB", "RGBA"):
        rgb = np.array(img.convert("RGB"))
        diff_rg = int(np.max(np.abs(rgb[:, :, 0].astype(np.int32) - rgb[:, :, 1].astype(np.int32))))
        diff_rb = int(np.max(np.abs(rgb[:, :, 0].astype(np.int32) - rgb[:, :, 2].astype(np.int32))))
        return diff_rg <= _GREY_THRESHOLD and diff_rb <= _GREY_THRESHOLD
    return False


def normalize_to_uint16(img: PilImage.Image) -> np.ndarray:
    """Convert a greyscale PIL image to a normalised uint16 numpy array.

    The full data range of the source image is linearly mapped to [0, 65535].
    A constant image normalises to all zeros (no division by zero).

    Supported source modes: F (float), I (int32), L (uint8), and any other
    mode which is first converted to L.

    Args:
        img: A greyscale PIL image.

    Returns:
        np.ndarray: Shape (H, W), dtype uint16.
    """
    mode = img.mode
    if mode == "F":
        arr = np.array(img, dtype=np.float32)
    elif mode == "I":
        arr = np.array(img, dtype=np.float32)
    elif mode == "L":
        arr = np.array(img, dtype=np.float32)
    else:
        arr = np.array(img.convert("L"), dtype=np.float32)

    arr_min = float(arr.min())
    arr_max = float(arr.max())
    if arr_max > arr_min:
        result = ((arr - arr_min) / (arr_max - arr_min) * 65535).astype(np.uint16)
    else:
        result = np.zeros(arr.shape, dtype=np.uint16)
    return result


def quantize_discrete_rgb(
    img: PilImage.Image,
) -> tuple[np.ndarray, list[dict]]:
    """Build a uint16 index image and palette from an RGB source.

    When unique colours ≤ 256 the exact palette is preserved.
    When unique colours > 256 the image is quantized to 256 colours via PIL.

    Args:
        img: An RGB or RGBA Pillow image.

    Returns:
        tuple:
            - np.ndarray: Shape (H, W), dtype uint16 — pixel→palette index.
            - list[dict]: Palette entries, each with keys ``value``,
              ``color`` (``#RRGGBB``), and ``label``.
    """
    rgb = img.convert("RGB")
    pixels = np.array(rgb).reshape(-1, 3)
    unique_colours = np.unique(pixels, axis=0)

    palette_entries: list[dict] = []

    if len(unique_colours) <= 256:
        colour_to_val = {tuple(c): i + 1 for i, c in enumerate(unique_colours)}
        arr16 = np.array(
            [colour_to_val[tuple(p)] for p in pixels], dtype=np.uint16
        ).reshape(rgb.height, rgb.width)
        for i, c in enumerate(unique_colours):
            r, g, b = int(c[0]), int(c[1]), int(c[2])
            palette_entries.append(
                {"value": i + 1, "color": f"#{r:02X}{g:02X}{b:02X}", "label": f"Color {i + 1}"}
            )
    else:
        quantized = rgb.quantize(colors=256)
        palette_data = quantized.getpalette() or []
        arr8 = np.array(quantized, dtype=np.uint8)
        arr16 = arr8.astype(np.uint16)
        for val in np.unique(arr8):
            idx = int(val)
            r = palette_data[idx * 3] if len(palette_data) > idx * 3 else 128
            g = palette_data[idx * 3 + 1] if len(palette_data) > idx * 3 + 1 else 128
            b = palette_data[idx * 3 + 2] if len(palette_data) > idx * 3 + 2 else 128
            palette_entries.append(
                {"value": idx, "color": f"#{r:02X}{g:02X}{b:02X}", "label": f"Color {idx + 1}"}
            )

    return arr16, palette_entries


def choose_resample(mode: str, is_greyscale: bool) -> PilImage.Resampling:
    """Return the resampling filter appropriate for image mode and content.

    Discrete colour maps use NEAREST to preserve sharp class boundaries.
    Continuous or greyscale data uses LANCZOS for gradient smoothness.

    Args:
        mode: Raster layer mode — ``"discrete"``, ``"continuous"``, or
            ``"color"``.
        is_greyscale: Whether the source image is effectively greyscale.

    Returns:
        PilImage.Resampling: The resampling filter to pass to
        ``img.resize()``.
    """
    if mode == "discrete" and not is_greyscale:
        return PilImage.Resampling.NEAREST
    return PilImage.Resampling.LANCZOS
