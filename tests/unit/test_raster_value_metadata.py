"""Tests for raster value-range metadata inference.

Covers :func:`src.services.raster_image_analysis.extract_value_metadata`,
which reads real-world value ranges (min/max/unit) from image metadata.

Inference sources, tried in order:

1. TIFF tag ``42112`` (``GDAL_METADATA``) — XML ``<Item name="STATISTICS_MINIMUM">``
2. TIFF tags ``340``/``341`` (``SMinSampleValue``/``SMaxSampleValue``)
3. Float TIFFs (``mode == "F"``) — computed from pixel min/max
4. Otherwise → ``None``
"""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image as PilImage
from PIL import TiffImagePlugin


def _write_float_tiff(
    path: str,
    data: np.ndarray,
    gdal_metadata_xml: str | None = None,
    smin: float | None = None,
    smax: float | None = None,
) -> None:
    """Write a float32 TIFF with optional GDAL_METADATA / SMin/SMax tags."""
    img = PilImage.fromarray(data.astype(np.float32), mode="F")
    extra = TiffImagePlugin.ImageFileDirectory_v2()
    if gdal_metadata_xml is not None:
        extra[42112] = gdal_metadata_xml
    if smin is not None:
        extra[340] = float(smin)
    if smax is not None:
        extra[341] = float(smax)
    img.save(path, tiffinfo=extra)


def _write_grey_png(path: str, width: int = 8, height: int = 8) -> None:
    """Write a trivial greyscale PNG (no metadata)."""
    arr = np.full((height, width), 100, dtype=np.uint8)
    PilImage.fromarray(arr, mode="L").save(path)


# ---------------------------------------------------------------------------
# Source 1: GDAL_METADATA XML
# ---------------------------------------------------------------------------


def test_extract_from_gdal_metadata_minmax(tmp_path):
    """GDAL_METADATA XML with STATISTICS_MINIMUM/MAXIMUM must be parsed."""
    from src.services.raster_image_analysis import extract_value_metadata

    xml = (
        '<GDALMetadata>'
        '<Item name="STATISTICS_MINIMUM">-4000</Item>'
        '<Item name="STATISTICS_MAXIMUM">8000</Item>'
        '</GDALMetadata>'
    )
    path = str(tmp_path / "dem.tif")
    _write_float_tiff(path, np.zeros((4, 4), dtype=np.float32), gdal_metadata_xml=xml)

    meta = extract_value_metadata(path)
    assert meta is not None
    assert meta.min == pytest.approx(-4000.0)
    assert meta.max == pytest.approx(8000.0)
    assert meta.source == "gdal_metadata"


def test_extract_unit_from_gdal_metadata(tmp_path):
    """UNITTYPE in GDAL_METADATA should populate the unit field."""
    from src.services.raster_image_analysis import extract_value_metadata

    xml = (
        '<GDALMetadata>'
        '<Item name="STATISTICS_MINIMUM">0</Item>'
        '<Item name="STATISTICS_MAXIMUM">100</Item>'
        '<Item name="UNITTYPE">metre</Item>'
        '</GDALMetadata>'
    )
    path = str(tmp_path / "unit.tif")
    _write_float_tiff(path, np.zeros((4, 4), dtype=np.float32), gdal_metadata_xml=xml)

    meta = extract_value_metadata(path)
    assert meta is not None
    assert meta.unit == "metre"


def test_extract_handles_corrupt_gdal_metadata(tmp_path):
    """A corrupt GDAL_METADATA tag must fall back (not raise)."""
    from src.services.raster_image_analysis import extract_value_metadata

    path = str(tmp_path / "corrupt.tif")
    _write_float_tiff(
        path,
        np.full((4, 4), 2.5, dtype=np.float32),
        gdal_metadata_xml="<<< not valid xml >>>",
    )

    # Corrupt XML → falls through to float-pixel-range source
    meta = extract_value_metadata(path)
    assert meta is not None
    assert meta.source == "float_pixel_range"


# ---------------------------------------------------------------------------
# Source 2: SMinSampleValue / SMaxSampleValue TIFF tags
# ---------------------------------------------------------------------------


def test_extract_from_tiff_sample_tags(tmp_path):
    """SMin/SMaxSampleValue tags are read when GDAL_METADATA is absent."""
    from src.services.raster_image_analysis import extract_value_metadata

    path = str(tmp_path / "smin.tif")
    _write_float_tiff(
        path,
        np.full((4, 4), 2.5, dtype=np.float32),
        smin=0.5,
        smax=42.7,
    )

    meta = extract_value_metadata(path)
    assert meta is not None
    assert meta.min == pytest.approx(0.5, rel=1e-3)
    assert meta.max == pytest.approx(42.7, rel=1e-3)
    assert meta.source == "tiff_sample_tags"


# ---------------------------------------------------------------------------
# Source 3: Float pixel range
# ---------------------------------------------------------------------------


def test_extract_from_float_pixels(tmp_path):
    """Float TIFFs without metadata yield pixel min/max."""
    from src.services.raster_image_analysis import extract_value_metadata

    data = np.array([[-1.2, 0.0], [1.5, 3.8]], dtype=np.float32)
    path = str(tmp_path / "pixels.tif")
    _write_float_tiff(path, data)

    meta = extract_value_metadata(path)
    assert meta is not None
    assert meta.min == pytest.approx(-1.2, rel=1e-3)
    assert meta.max == pytest.approx(3.8, rel=1e-3)
    assert meta.source == "float_pixel_range"


def test_extract_skips_nan_inf_in_float_pixels(tmp_path):
    """NaN/Inf pixels must not leak into min/max."""
    from src.services.raster_image_analysis import extract_value_metadata

    data = np.array(
        [[np.nan, 0.0], [1.5, np.inf]],
        dtype=np.float32,
    )
    path = str(tmp_path / "nan.tif")
    _write_float_tiff(path, data)

    meta = extract_value_metadata(path)
    assert meta is not None
    assert np.isfinite(meta.min)
    assert np.isfinite(meta.max)
    assert meta.min == pytest.approx(0.0, rel=1e-3)
    assert meta.max == pytest.approx(1.5, rel=1e-3)


# ---------------------------------------------------------------------------
# No-metadata case
# ---------------------------------------------------------------------------


def test_extract_returns_none_for_plain_png(tmp_path):
    """Plain greyscale PNG has no real-world metadata."""
    from src.services.raster_image_analysis import extract_value_metadata

    path = str(tmp_path / "plain.png")
    _write_grey_png(path)

    assert extract_value_metadata(path) is None


def test_extract_returns_none_for_missing_file(tmp_path):
    """Missing files return None (the caller may still analyse other fields)."""
    from src.services.raster_image_analysis import extract_value_metadata

    assert extract_value_metadata(str(tmp_path / "nope.tif")) is None


# ---------------------------------------------------------------------------
# Priority / precedence
# ---------------------------------------------------------------------------


def test_gdal_metadata_takes_precedence_over_sample_tags(tmp_path):
    """When both GDAL_METADATA and SMin/SMax are present, GDAL wins."""
    from src.services.raster_image_analysis import extract_value_metadata

    xml = (
        '<GDALMetadata>'
        '<Item name="STATISTICS_MINIMUM">-100</Item>'
        '<Item name="STATISTICS_MAXIMUM">200</Item>'
        '</GDALMetadata>'
    )
    path = str(tmp_path / "both.tif")
    _write_float_tiff(
        path,
        np.zeros((4, 4), dtype=np.float32),
        gdal_metadata_xml=xml,
        smin=0.0,
        smax=1.0,
    )

    meta = extract_value_metadata(path)
    assert meta is not None
    assert meta.source == "gdal_metadata"
    assert meta.min == pytest.approx(-100.0)
    assert meta.max == pytest.approx(200.0)


def test_sample_tags_take_precedence_over_pixel_range(tmp_path):
    """SMin/SMax should beat pure pixel-range fallback."""
    from src.services.raster_image_analysis import extract_value_metadata

    # Pixel range is 0..1 but sample tags claim 10..20
    path = str(tmp_path / "precedence.tif")
    _write_float_tiff(
        path,
        np.linspace(0, 1, 16, dtype=np.float32).reshape(4, 4),
        smin=10.0,
        smax=20.0,
    )

    meta = extract_value_metadata(path)
    assert meta is not None
    assert meta.source == "tiff_sample_tags"
    assert meta.min == pytest.approx(10.0, rel=1e-3)
    assert meta.max == pytest.approx(20.0, rel=1e-3)
