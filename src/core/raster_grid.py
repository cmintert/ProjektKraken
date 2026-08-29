"""GUI-independent raster grid encoding and patch helpers."""

from __future__ import annotations

from io import BytesIO

import numpy as np
from PIL import Image as PilImage

_VALUE_GRID_DIMENSIONS = 2
_RGBA_GRID_DIMENSIONS = 3
_RGBA_CHANNEL_COUNT = 4


def encode_value_png(array: np.ndarray) -> bytes:
    """Encode a two-dimensional uint16 value grid as PNG."""
    values = np.asarray(array, dtype=np.uint16)
    if values.ndim != _VALUE_GRID_DIMENSIONS:
        raise ValueError("Value raster must be a two-dimensional grid")
    output = BytesIO()
    PilImage.fromarray(values).save(output, format="PNG")
    return output.getvalue()


def encode_rgba_png(array: np.ndarray) -> bytes:
    """Encode an RGBA visual grid as PNG."""
    rgba = np.asarray(array, dtype=np.uint8)
    if rgba.ndim != _RGBA_GRID_DIMENSIONS or rgba.shape[2] != _RGBA_CHANNEL_COUNT:
        raise ValueError("Visual raster must be an RGBA grid")
    output = BytesIO()
    PilImage.fromarray(rgba, mode="RGBA").save(output, format="PNG")
    return output.getvalue()


def load_value_grid(path: str) -> np.ndarray:
    """Load a value raster into an independent uint16 array."""
    with PilImage.open(path) as image:
        values = np.array(image, dtype=np.uint16)
    if values.ndim != _VALUE_GRID_DIMENSIONS:
        raise ValueError("Value raster must be a two-dimensional grid")
    return values


def load_rgba_grid(path: str) -> np.ndarray:
    """Load an image into an independent straight-alpha RGBA array."""
    with PilImage.open(path) as image:
        rgba = np.array(image.convert("RGBA"), dtype=np.uint8)
    return rgba


def apply_value_patch(
    array: np.ndarray,
    region: tuple[int, int, int, int],
    raw: bytes,
) -> np.ndarray:
    """Return a copy with one inclusive uint16 rectangle replaced."""
    min_col, min_row, max_col, max_row = region
    width = max_col - min_col + 1
    height = max_row - min_row + 1
    patch = np.frombuffer(raw, dtype=np.uint16).reshape((height, width))
    result = np.asarray(array, dtype=np.uint16).copy()
    result[min_row : max_row + 1, min_col : max_col + 1] = patch
    return result


def apply_rgba_patch(
    array: np.ndarray,
    region: tuple[int, int, int, int],
    raw: bytes,
) -> np.ndarray:
    """Return a copy with one inclusive RGBA rectangle replaced."""
    min_col, min_row, max_col, max_row = region
    width = max_col - min_col + 1
    height = max_row - min_row + 1
    patch = np.frombuffer(raw, dtype=np.uint8).reshape((height, width, 4))
    result = np.asarray(array, dtype=np.uint8).copy()
    result[min_row : max_row + 1, min_col : max_col + 1] = patch
    return result
