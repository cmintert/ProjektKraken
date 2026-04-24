"""RED tests for M4: analyse_image() service function.

These tests define the expected interface and behaviour of
``src.services.raster_image_analysis.analyse_image``.  They fail before the
implementation exists.
"""


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


# ---------------------------------------------------------------------------
# value_metadata field
# ---------------------------------------------------------------------------


def test_analyse_image_populates_value_metadata_for_geotiff(tmp_path):
    """analyse_image exposes inferred value range via .value_metadata."""
    from PIL import TiffImagePlugin

    from src.services.raster_image_analysis import analyse_image

    arr = np.full((8, 8), 2.0, dtype=np.float32)
    path = str(tmp_path / "dem.tif")
    extra = TiffImagePlugin.ImageFileDirectory_v2()
    extra[42112] = (
        '<GDALMetadata>'
        '<Item name="STATISTICS_MINIMUM">-4000</Item>'
        '<Item name="STATISTICS_MAXIMUM">8000</Item>'
        '<Item name="UNITTYPE">metre</Item>'
        '</GDALMetadata>'
    )
    PilImage.fromarray(arr, mode="F").save(path, tiffinfo=extra)

    result = analyse_image(path)
    assert result.value_metadata is not None
    assert result.value_metadata.min == pytest.approx(-4000.0)
    assert result.value_metadata.max == pytest.approx(8000.0)
    assert result.value_metadata.unit == "metre"


def test_analyse_image_value_metadata_none_for_plain_png(tmp_path):
    """Plain PNGs yield value_metadata=None."""
    from src.services.raster_image_analysis import analyse_image

    result = analyse_image(_grey_png(tmp_path))
    assert result.value_metadata is None


def test_analyse_image_value_metadata_falls_back_for_float_tiff(tmp_path):
    """Float TIFF without metadata tags falls back to pixel range."""
    from src.services.raster_image_analysis import analyse_image

    result = analyse_image(_float_tiff(tmp_path))
    assert result.value_metadata is not None
    assert result.value_metadata.source == "float_pixel_range"
