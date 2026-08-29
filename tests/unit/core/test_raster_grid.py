"""Tests for GUI-independent raster grid encoding."""

import warnings
from io import BytesIO

import numpy as np
from PIL import Image as PilImage

from src.core.raster_grid import encode_value_png


def test_encode_value_png_preserves_uint16_without_pillow_warning() -> None:
    """Pillow infers 16-bit mode without the deprecated mode argument."""
    values = np.array(
        [[0, 1, 255, 256, 32_768, 65_535]],
        dtype=np.uint16,
    )

    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        encoded = encode_value_png(values)

    with PilImage.open(BytesIO(encoded)) as image:
        decoded = np.array(image, dtype=np.uint16)

    np.testing.assert_array_equal(decoded, values)
