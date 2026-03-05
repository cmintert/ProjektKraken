"""Unit tests for MapDataBuffer — 16-bit raster data operations.

Tests cover:
- Buffer creation and default values
- Normalised coordinate read/write
- Brush painting
- Save/load round-trip (16-bit PNG)
- Colorisation to QImage
- Bucket fill
- Region snapshot and restore
"""

import os
import tempfile

import pytest
from PySide6.QtGui import QImage

from src.gui.widgets.map.map_data_buffer import (
    ColorEntry,
    ColorMap,
    MapDataBuffer,
    _hex_to_rgba,
)

# ------------------------------------------------------------------
# Construction & default values
# ------------------------------------------------------------------


class TestBufferCreation:
    """Tests for buffer construction."""

    def test_default_value_readback(self) -> None:
        """A freshly created buffer should read back the default value."""
        buf = MapDataBuffer(64, 64, default_value=42)
        assert buf.get_value_at(0.5, 0.5) == 42

    def test_dimensions(self) -> None:
        """Width and height are stored correctly."""
        buf = MapDataBuffer(128, 64)
        assert buf.width == 128
        assert buf.height == 64

    def test_zero_default(self) -> None:
        """Default value of 0 fills the entire buffer."""
        buf = MapDataBuffer(32, 32)
        assert buf.get_value_at(0.0, 0.0) == 0
        assert buf.get_value_at(1.0, 1.0) == 0

    def test_invalid_dimensions_raise(self) -> None:
        """Zero or negative dimensions should raise ValueError."""
        with pytest.raises(ValueError):
            MapDataBuffer(0, 10)
        with pytest.raises(ValueError):
            MapDataBuffer(10, -1)


# ------------------------------------------------------------------
# Point access
# ------------------------------------------------------------------


class TestPointAccess:
    """Tests for get/set at normalised coordinates."""

    def test_set_get_roundtrip(self) -> None:
        """Setting a value and reading it back should match."""
        buf = MapDataBuffer(100, 100)
        buf.set_value_at(0.5, 0.5, 1234)
        assert buf.get_value_at(0.5, 0.5) == 1234

    def test_corners(self) -> None:
        """Writing to all four corners should be independent."""
        buf = MapDataBuffer(64, 64)
        buf.set_value_at(0.0, 0.0, 1)
        buf.set_value_at(1.0, 0.0, 2)
        buf.set_value_at(0.0, 1.0, 3)
        buf.set_value_at(1.0, 1.0, 4)
        assert buf.get_value_at(0.0, 0.0) == 1
        assert buf.get_value_at(1.0, 0.0) == 2
        assert buf.get_value_at(0.0, 1.0) == 3
        assert buf.get_value_at(1.0, 1.0) == 4

    def test_clamping(self) -> None:
        """Values outside 0–65535 should be clamped."""
        buf = MapDataBuffer(16, 16)
        buf.set_value_at(0.5, 0.5, 70000)
        assert buf.get_value_at(0.5, 0.5) == 65535
        buf.set_value_at(0.5, 0.5, -5)
        assert buf.get_value_at(0.5, 0.5) == 0

    def test_out_of_bounds_coords_clamped(self) -> None:
        """Coordinates outside [0,1] should be clamped to edges."""
        buf = MapDataBuffer(16, 16, default_value=99)
        buf.set_value_at(-0.5, -0.5, 10)
        assert buf.get_value_at(0.0, 0.0) == 10
        buf.set_value_at(1.5, 1.5, 20)
        assert buf.get_value_at(1.0, 1.0) == 20


# ------------------------------------------------------------------
# Brush painting
# ------------------------------------------------------------------


class TestBrushPaint:
    """Tests for paint_brush."""

    def test_brush_paints_center(self) -> None:
        """A brush at (0.5, 0.5) should paint the centre pixel."""
        buf = MapDataBuffer(64, 64)
        buf.paint_brush(0.5, 0.5, radius_px=3, value=100)
        assert buf.get_value_at(0.5, 0.5) == 100

    def test_brush_returns_dirty_region(self) -> None:
        """paint_brush should return a valid (non-empty) dirty region."""
        buf = MapDataBuffer(64, 64)
        dirty = buf.paint_brush(0.5, 0.5, radius_px=5, value=200)
        min_col, min_row, max_col, max_row = dirty
        assert min_col <= max_col
        assert min_row <= max_row

    def test_brush_does_not_affect_distant_pixels(self) -> None:
        """Pixels far from the brush centre should remain unchanged."""
        buf = MapDataBuffer(256, 256, default_value=0)
        buf.paint_brush(0.1, 0.1, radius_px=3, value=500)
        # Far corner should still be 0
        assert buf.get_value_at(0.9, 0.9) == 0

    def test_brush_with_falloff(self) -> None:
        """Falloff > 0 should produce a gradient from centre to edge."""
        buf = MapDataBuffer(128, 128)
        buf.paint_brush(0.5, 0.5, radius_px=20, value=10000, falloff=1.0)
        centre_val = buf.get_value_at(0.5, 0.5)
        edge_val = buf.get_value_at(0.5, 0.35)  # Near the edge of brush
        assert centre_val >= edge_val


# ------------------------------------------------------------------
# Save / load round-trip
# ------------------------------------------------------------------


class TestSaveLoad:
    """Tests for 16-bit PNG persistence."""

    def test_save_load_roundtrip(self) -> None:
        """Saving and loading should produce identical buffer contents."""
        buf = MapDataBuffer(32, 32, default_value=12345)
        buf.set_value_at(0.25, 0.75, 60000)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test_raster.png")
            buf.save(path)

            loaded = MapDataBuffer.from_file(path)
            assert loaded.width == 32
            assert loaded.height == 32
            assert loaded.get_value_at(0.5, 0.5) == 12345
            assert loaded.get_value_at(0.25, 0.75) == 60000

    def test_load_nonexistent_raises(self) -> None:
        """Loading a file that doesn't exist should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            MapDataBuffer.from_file("/nonexistent/path/raster.png")

    def test_save_creates_parent_dirs(self) -> None:
        """save() should create parent directories if needed."""
        buf = MapDataBuffer(8, 8)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "subdir", "nested", "raster.png")
            buf.save(path)
            assert os.path.exists(path)


# ------------------------------------------------------------------
# Colorisation
# ------------------------------------------------------------------


class TestColorize:
    """Tests for colorize → QImage."""

    def test_colorize_palette_returns_correct_size(self) -> None:
        """Output QImage should match buffer dimensions."""
        buf = MapDataBuffer(64, 48)
        cm = ColorMap(
            type="palette",
            entries=[ColorEntry(value=0, color="#FF0000")],
        )
        img = buf.colorize(cm)
        assert isinstance(img, QImage)
        assert img.width() == 64
        assert img.height() == 48

    def test_colorize_gradient_returns_correct_size(self) -> None:
        """Gradient colour map should also produce correctly sized QImage."""
        buf = MapDataBuffer(32, 32)
        cm = ColorMap(
            type="gradient",
            gradient_start="#000000",
            gradient_end="#FFFFFF",
        )
        img = buf.colorize(cm)
        assert img.width() == 32
        assert img.height() == 32

    def test_colorize_palette_colours_pixels(self) -> None:
        """Pixels with a matching palette entry should be coloured."""
        buf = MapDataBuffer(4, 4, default_value=1)
        cm = ColorMap(
            type="palette",
            entries=[ColorEntry(value=1, color="#00FF00")],
        )
        img = buf.colorize(cm)
        # Check centre pixel — should have green channel
        pixel = img.pixelColor(2, 2)
        assert pixel.green() == 255

    def test_colorize_unmapped_values_transparent(self) -> None:
        """Pixels with no palette entry should be transparent (alpha=0)."""
        buf = MapDataBuffer(4, 4, default_value=99)
        cm = ColorMap(
            type="palette",
            entries=[ColorEntry(value=1, color="#FF0000")],
        )
        img = buf.colorize(cm)
        pixel = img.pixelColor(2, 2)
        assert pixel.alpha() == 0


# ------------------------------------------------------------------
# Bucket fill
# ------------------------------------------------------------------


class TestBucketFill:
    """Tests for bucket_fill."""

    def test_bucket_fill_all_pixels(self) -> None:
        """After bucket_fill, every pixel should have the new value."""
        buf = MapDataBuffer(16, 16, default_value=0)
        buf.bucket_fill(500)
        assert buf.get_value_at(0.0, 0.0) == 500
        assert buf.get_value_at(0.5, 0.5) == 500
        assert buf.get_value_at(1.0, 1.0) == 500


# ------------------------------------------------------------------
# Region snapshot / restore
# ------------------------------------------------------------------


class TestRegionSnapshot:
    """Tests for get_region / set_region."""

    def test_region_roundtrip(self) -> None:
        """Snapshot and restore should preserve data."""
        buf = MapDataBuffer(32, 32, default_value=0)
        buf.set_value_at(0.0, 0.0, 111)
        snapshot = buf.get_region(0, 0, 5, 5)
        buf.bucket_fill(999)
        buf.set_region(0, 0, snapshot)
        assert buf.get_value_at(0.0, 0.0) == 111


# ------------------------------------------------------------------
# Colour helpers
# ------------------------------------------------------------------


class TestColorHelpers:
    """Tests for hex→RGBA conversion."""

    def test_hex_to_rgba_6(self) -> None:
        """6-character hex should parse to RGB + default alpha."""
        assert _hex_to_rgba("#FF8000") == (255, 128, 0, 255)

    def test_hex_to_rgba_8(self) -> None:
        """8-character hex should parse to RGBA."""
        assert _hex_to_rgba("#FF800080") == (255, 128, 0, 128)


# ------------------------------------------------------------------
# ColorMap serialisation
# ------------------------------------------------------------------


class TestColorMapSerialization:
    """Tests for ColorMap to_dict/from_dict."""

    def test_palette_roundtrip(self) -> None:
        """Palette colour map should serialise and deserialise."""
        cm = ColorMap(
            type="palette",
            entries=[ColorEntry(value=1, color="#AABBCC")],
        )
        d = cm.to_dict()
        cm2 = ColorMap.from_dict(d)
        assert cm2.type == "palette"
        assert len(cm2.entries) == 1
        assert cm2.entries[0].value == 1
        assert cm2.entries[0].color == "#AABBCC"

    def test_gradient_roundtrip(self) -> None:
        """Gradient colour map should serialise and deserialise."""
        cm = ColorMap(
            type="gradient",
            gradient_start="#000000",
            gradient_end="#FFFFFF",
        )
        d = cm.to_dict()
        cm2 = ColorMap.from_dict(d)
        assert cm2.type == "gradient"
        assert cm2.gradient_start == "#000000"
        assert cm2.gradient_end == "#FFFFFF"
