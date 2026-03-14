"""RED tests for M4: analyse_image() service function.

These tests define the expected interface and behaviour of
``src.services.raster_image_analysis.analyse_image``.  They fail before the
implementation exists.
"""

import io
import struct

import numpy as np
import pytest

from PIL import Image as PilImage


# ---------------------------------------------------------------------------
# Helpers to build synthetic image files in-memory
# ---------------------------------------------------------------------------


def _grey_png(tmp_path, width: int = 16, height: int = 16) -> str:
    """Create a small greyscale PNG and return its absolute path."""
    arr = np.zeros((height, width), dtype=np.uint8)
    arr[0, 0] = 128  # a non-trivial pixel
    img = PilImage.fromarray(arr, mode="L")
    path = str(tmp_path / "grey.png")
    img.save(path)
    return path


def _color_png(tmp_path, width: int = 16, height: int = 16) -> str:
    """Create a small color PNG (has distinct R/G/B channels) and return its path."""
    arr = np.zeros((height, width, 3), dtype=np.uint8)
    arr[0, 0] = (255, 0, 0)  # red pixel
    arr[0, 1] = (0, 255, 0)  # green pixel
    img = PilImage.fromarray(arr, mode="RGB")
    path = str(tmp_path / "color.png")
    img.save(path)
    return path


def _float_tiff(tmp_path, width: int = 16, height: int = 16) -> str:
    """Create a small float32 TIFF (elevation-style) and return its path."""
    arr = np.random.rand(height, width).astype(np.float32)
    img = PilImage.fromarray(arr, mode="F")
    path = str(tmp_path / "float.tiff")
    img.save(path)
    return path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_analyse_grey_image_returns_continuous_suggestion(tmp_path):
    """A greyscale PNG should suggest 'continuous' mode."""
    from src.services.raster_image_analysis import analyse_image

    result = analyse_image(_grey_png(tmp_path))
    assert result.is_content_grey is True
    assert result.suggested_mode == "continuous"


def test_analyse_color_image_returns_color_suggestion(tmp_path):
    """A colour PNG should suggest 'color' mode."""
    from src.services.raster_image_analysis import analyse_image

    result = analyse_image(_color_png(tmp_path))
    assert result.is_content_grey is False
    assert result.suggested_mode == "color"


def test_analyse_image_returns_dimensions(tmp_path):
    """analyse_image must return the pixel dimensions of the source image."""
    from src.services.raster_image_analysis import analyse_image

    result = analyse_image(_grey_png(tmp_path, width=32, height=48))
    assert result.width == 32
    assert result.height == 48


def test_analyse_image_thumbnail_is_rgb_uint8_array(tmp_path):
    """Thumbnail array must be an RGB uint8 ndarray of max 128×128."""
    from src.services.raster_image_analysis import analyse_image

    result = analyse_image(_color_png(tmp_path, width=64, height=64))
    arr = result.thumbnail_arr
    assert isinstance(arr, np.ndarray)
    assert arr.dtype == np.uint8
    assert arr.ndim == 3  # (H, W, 3)
    assert arr.shape[2] == 3  # RGB
    assert arr.shape[0] <= 128
    assert arr.shape[1] <= 128


def test_analyse_float_tiff_is_float_and_grey(tmp_path):
    """A float TIFF should have is_float=True and is_content_grey=True."""
    from src.services.raster_image_analysis import analyse_image

    result = analyse_image(_float_tiff(tmp_path))
    assert result.is_float is True
    assert result.is_content_grey is True
    assert result.suggested_mode == "continuous"


def test_analyse_missing_file_raises():
    """analyse_image must raise an exception when the file does not exist."""
    from src.services.raster_image_analysis import analyse_image

    with pytest.raises(Exception):
        analyse_image("/no/such/file.png")


def test_analyse_hint_grey_nonfloat_uses_continuous_text(tmp_path):
    """A plain greyscale image hint must mention 'Continuous'."""
    from src.services.raster_image_analysis import analyse_image

    result = analyse_image(_grey_png(tmp_path))
    assert "continuous" in result.hint.lower()


def test_analyse_hint_color_uses_color_text(tmp_path):
    """A color image hint must mention 'Color' or 'Colour'."""
    from src.services.raster_image_analysis import analyse_image

    result = analyse_image(_color_png(tmp_path))
    assert "color" in result.hint.lower() or "colour" in result.hint.lower()
