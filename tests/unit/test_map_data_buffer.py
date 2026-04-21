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
    GradientStop,
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
    """Tests for paint_brush hard-edge behaviour."""

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
        assert buf.get_value_at(0.9, 0.9) == 0

    def test_hard_brush_uniform_inside(self) -> None:
        """falloff=0: every pixel inside the radius gets the full value."""
        buf = MapDataBuffer(256, 256)
        buf.paint_brush(0.5, 0.5, radius_px=30, value=5000, falloff=0.0)
        # Centre
        assert buf.get_value_at(0.5, 0.5) == 5000
        # ~15 px away (inside radius 30)
        assert buf.get_value_at(0.5, 0.5 + 15 / 255) == 5000
        # ~29 px away (still inside)
        assert buf.get_value_at(0.5, 0.5 + 29 / 255) == 5000

    def test_hard_brush_zero_outside(self) -> None:
        """falloff=0: pixels outside the radius are untouched."""
        buf = MapDataBuffer(256, 256, default_value=0)
        buf.paint_brush(0.5, 0.5, radius_px=30, value=5000, falloff=0.0)
        # ~35 px away (outside)
        assert buf.get_value_at(0.5, 0.5 + 35 / 255) == 0


# ------------------------------------------------------------------
# Brush feathering (falloff)
# ------------------------------------------------------------------


class TestBrushFeathering:
    """Tests for brush feathering (falloff) behaviour.

    Feathering model
    ----------------
    - ``falloff = 0.0``: Hard circle — uniform value everywhere inside
      the radius, zero outside.
    - ``falloff = 1.0``: Full linear ramp — full value at the centre,
      linearly decreasing to zero at the outer edge of the radius.
    - ``0 < falloff < 1``: Hard inner core of radius
      ``r * (1 - falloff)`` (full value), then a linear ramp from the
      core boundary down to zero at the outer radius.
    """

    # -- Full falloff (1.0) -----------------------------------------

    def test_full_falloff_center_is_target(self) -> None:
        """falloff=1.0: the centre pixel must be the target value."""
        buf = MapDataBuffer(256, 256)
        buf.paint_brush(0.5, 0.5, radius_px=40, value=10000, falloff=1.0)
        assert buf.get_value_at(0.5, 0.5) == 10000

    def test_full_falloff_half_radius(self) -> None:
        """falloff=1.0: at half the radius, value ≈ 50% of target."""
        buf = MapDataBuffer(256, 256)
        buf.paint_brush(0.5, 0.5, radius_px=40, value=10000, falloff=1.0)
        # 20 px away = half radius → strength ≈ 0.5
        val = buf.get_value_at(0.5, 0.5 + 20 / 255)
        assert 4000 < val < 6000

    def test_full_falloff_near_edge(self) -> None:
        """falloff=1.0: near the radius edge the value is close to 0."""
        buf = MapDataBuffer(256, 256)
        buf.paint_brush(0.5, 0.5, radius_px=40, value=10000, falloff=1.0)
        # 38 px away → strength ≈ 0.05
        val = buf.get_value_at(0.5, 0.5 + 38 / 255)
        assert val < 1500

    def test_full_falloff_outside_is_zero(self) -> None:
        """falloff=1.0: pixels beyond the radius are untouched."""
        buf = MapDataBuffer(256, 256, default_value=0)
        buf.paint_brush(0.5, 0.5, radius_px=40, value=10000, falloff=1.0)
        assert buf.get_value_at(0.5, 0.5 + 45 / 255) == 0

    def test_full_falloff_monotonic_decrease(self) -> None:
        """falloff=1.0: values must decrease monotonically from centre."""
        buf = MapDataBuffer(256, 256)
        buf.paint_brush(0.5, 0.5, radius_px=40, value=10000, falloff=1.0)
        prev = buf.get_value_at(0.5, 0.5)
        for px_away in (5, 10, 15, 20, 25, 30, 35):
            cur = buf.get_value_at(0.5, 0.5 + px_away / 255)
            assert cur <= prev, (
                f"Value at {px_away}px ({cur}) > value at previous ({prev})"
            )
            prev = cur

    # -- Partial falloff (0.5) --------------------------------------

    def test_partial_falloff_core_is_full(self) -> None:
        """falloff=0.5: hard core at r*(1-0.5)=20px has full value."""
        buf = MapDataBuffer(256, 256)
        buf.paint_brush(0.5, 0.5, radius_px=40, value=10000, falloff=0.5)
        # 15 px from centre (inside 20px core) must be full value
        val = buf.get_value_at(0.5, 0.5 + 15 / 255)
        assert val == 10000

    def test_partial_falloff_ramp_zone(self) -> None:
        """falloff=0.5: between core edge and outer edge values ramp."""
        buf = MapDataBuffer(256, 256)
        buf.paint_brush(0.5, 0.5, radius_px=40, value=10000, falloff=0.5)
        # core_r = 20, outer_r = 40, sample at 30px → midpoint of ramp
        val = buf.get_value_at(0.5, 0.5 + 30 / 255)
        assert 3500 < val < 6500

    def test_partial_falloff_outside_is_zero(self) -> None:
        """falloff=0.5: beyond the outer radius, value is zero."""
        buf = MapDataBuffer(256, 256, default_value=0)
        buf.paint_brush(0.5, 0.5, radius_px=40, value=10000, falloff=0.5)
        assert buf.get_value_at(0.5, 0.5 + 45 / 255) == 0

    # -- Small falloff (0.14, user's real setting) ------------------

    def test_small_falloff_core_is_full(self) -> None:
        """falloff=0.14: large hard core, thin soft edge."""
        buf = MapDataBuffer(256, 256)
        # core_r = 40 * (1 - 0.14) = 34.4 px
        buf.paint_brush(0.5, 0.5, radius_px=40, value=10000, falloff=0.14)
        # 30 px (inside core)
        val = buf.get_value_at(0.5, 0.5 + 30 / 255)
        assert val == 10000

    def test_small_falloff_ramp_zone(self) -> None:
        """falloff=0.14: the thin ramp zone produces intermediate vals."""
        buf = MapDataBuffer(256, 256)
        buf.paint_brush(0.5, 0.5, radius_px=40, value=10000, falloff=0.14)
        # core_r ≈ 34.4, outer_r = 40, sample at 37px → in ramp
        val = buf.get_value_at(0.5, 0.5 + 37 / 255)
        # Should be noticeably less than 10000
        assert val < 9000
        assert val > 0

    # -- Painting over existing values ------------------------------

    def test_feathered_blends_with_existing(self) -> None:
        """Feathered brush blends towards target from existing values."""
        buf = MapDataBuffer(256, 256, default_value=5000)
        buf.paint_brush(0.5, 0.5, radius_px=40, value=10000, falloff=1.0)
        # Centre should be fully painted to target
        assert buf.get_value_at(0.5, 0.5) == 10000
        # 20 px away: strength ≈ 0.5 → blended ≈ 5000*(1-0.5)+10000*0.5 = 7500
        mid = buf.get_value_at(0.5, 0.5 + 20 / 255)
        assert 6500 < mid < 8500


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
            gradient_stops=[GradientStop(0.0, "#000000"), GradientStop(1.0, "#FFFFFF")],
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
            gradient_stops=[GradientStop(0.0, "#000000"), GradientStop(1.0, "#FFFFFF")],
        )
        d = cm.to_dict()
        cm2 = ColorMap.from_dict(d)
        assert cm2.type == "gradient"
        assert len(cm2.gradient_stops) == 2
        assert cm2.gradient_stops[0].color == "#000000"
        assert cm2.gradient_stops[1].color == "#FFFFFF"


# ------------------------------------------------------------------
# LUT-based palette colorisation
# ------------------------------------------------------------------


class TestColorizeLUT:
    """Tests for LUT-based palette colorisation.

    These tests ensure the LUT optimisation produces pixel-exact results
    compared to the naive per-entry masking approach, and that edge cases
    (unmapped values, high value indices, sub-region colorisation) are
    handled correctly.
    """

    def test_colorize_palette_pixel_exact_multi_value(self) -> None:
        """Palette with multiple entries produces correct RGBA per pixel."""

        buf = MapDataBuffer(8, 8)
        # Paint distinct values into known pixel positions
        arr = buf._data
        arr[0, 0] = 0
        arr[0, 1] = 1
        arr[1, 0] = 5
        arr[1, 1] = 100
        arr[2, 0] = 65535

        cm = ColorMap(
            type="palette",
            entries=[
                ColorEntry(value=0, color="#FF0000"),      # red
                ColorEntry(value=1, color="#00FF00"),      # green
                ColorEntry(value=5, color="#0000FF"),      # blue
                ColorEntry(value=100, color="#FFFF00"),    # yellow
                ColorEntry(value=65535, color="#FF00FF"),  # magenta
            ],
        )
        img = buf.colorize(cm)

        # Pixel (col, row) — QImage.pixelColor(x, y)
        p00 = img.pixelColor(0, 0)
        assert (p00.red(), p00.green(), p00.blue(), p00.alpha()) == (255, 0, 0, 255)

        p10 = img.pixelColor(1, 0)
        assert (p10.red(), p10.green(), p10.blue(), p10.alpha()) == (0, 255, 0, 255)

        p01 = img.pixelColor(0, 1)
        assert (p01.red(), p01.green(), p01.blue(), p01.alpha()) == (0, 0, 255, 255)

        p11 = img.pixelColor(1, 1)
        assert (p11.red(), p11.green(), p11.blue(), p11.alpha()) == (255, 255, 0, 255)

        p02 = img.pixelColor(0, 2)
        assert (p02.red(), p02.green(), p02.blue(), p02.alpha()) == (255, 0, 255, 255)

    def test_colorize_region_matches_full_colorize(self) -> None:
        """Colorize sub-region must be pixel-exact vs full colorize crop."""

        buf = MapDataBuffer(16, 16)
        # Fill with a pattern of values
        for row in range(16):
            for col in range(16):
                buf._data[row, col] = (row * 16 + col) % 5

        cm = ColorMap(
            type="palette",
            entries=[
                ColorEntry(value=0, color="#FF0000"),
                ColorEntry(value=1, color="#00FF00"),
                ColorEntry(value=2, color="#0000FF"),
                ColorEntry(value=3, color="#FFFF00"),
                ColorEntry(value=4, color="#FF00FF"),
            ],
        )

        # Full colorize then crop
        full_img = buf.colorize(cm)

        # Region colorize (cols 2-6, rows 3-7)
        region_img = buf.colorize_region(cm, 2, 3, 6, 7)

        assert region_img.width() == 5   # 6-2+1
        assert region_img.height() == 5  # 7-3+1

        for ry in range(5):
            for rx in range(5):
                expected = full_img.pixelColor(rx + 2, ry + 3)
                actual = region_img.pixelColor(rx, ry)
                assert (actual.red(), actual.green(), actual.blue(), actual.alpha()) == (
                    expected.red(),
                    expected.green(),
                    expected.blue(),
                    expected.alpha(),
                ), f"Mismatch at region ({rx},{ry}) / full ({rx+2},{ry+3})"

    def test_colorize_palette_unmapped_multi_value_transparent(self) -> None:
        """Values absent from the palette must remain fully transparent."""
        buf = MapDataBuffer(4, 4)
        buf._data[0, 0] = 10   # mapped
        buf._data[0, 1] = 20   # unmapped
        buf._data[1, 0] = 30   # unmapped
        buf._data[1, 1] = 40   # mapped

        cm = ColorMap(
            type="palette",
            entries=[
                ColorEntry(value=10, color="#FF0000"),
                ColorEntry(value=40, color="#00FF00"),
            ],
        )
        img = buf.colorize(cm)

        # Mapped values have full alpha
        assert img.pixelColor(0, 0).alpha() == 255
        assert img.pixelColor(1, 1).alpha() == 255

        # Unmapped values are transparent
        assert img.pixelColor(1, 0).alpha() == 0
        assert img.pixelColor(0, 1).alpha() == 0


# ------------------------------------------------------------------
# Falloff curve shapes
# ------------------------------------------------------------------


class TestFalloffCurves:
    """Tests for cosine and gaussian falloff curve shapes.

    These tests verify that the shaped falloff curves differ from the
    linear baseline in the expected directions, and that boundary
    conditions are preserved for all curves.
    """

    def test_cosine_center_is_full_value(self) -> None:
        """Cosine curve: centre pixel must be the target value."""
        buf = MapDataBuffer(256, 256)
        buf.paint_brush(0.5, 0.5, radius_px=40, value=10000, falloff=1.0, falloff_curve="cosine")
        assert buf.get_value_at(0.5, 0.5) == 10000

    def test_gaussian_center_is_full_value(self) -> None:
        """Gaussian curve: centre pixel must be the target value."""
        buf = MapDataBuffer(256, 256)
        buf.paint_brush(0.5, 0.5, radius_px=40, value=10000, falloff=1.0, falloff_curve="gaussian")
        assert buf.get_value_at(0.5, 0.5) == 10000

    def test_cosine_outside_is_zero(self) -> None:
        """Cosine curve: pixels beyond the radius are untouched."""
        buf = MapDataBuffer(256, 256, default_value=0)
        buf.paint_brush(0.5, 0.5, radius_px=40, value=10000, falloff=1.0, falloff_curve="cosine")
        assert buf.get_value_at(0.5, 0.5 + 45 / 255) == 0

    def test_gaussian_outside_is_zero(self) -> None:
        """Gaussian curve: pixels beyond the radius are untouched."""
        buf = MapDataBuffer(256, 256, default_value=0)
        buf.paint_brush(0.5, 0.5, radius_px=40, value=10000, falloff=1.0, falloff_curve="gaussian")
        assert buf.get_value_at(0.5, 0.5 + 45 / 255) == 0

    def test_cosine_midpoint_near_half(self) -> None:
        """Cosine at t=0.5 of ramp (= half radius with full falloff) ≈ 50 % value.

        For a symmetric cosine S-curve, f(0.5) = 0.5 - 0.5*cos(pi*0.5) = 0.5.
        """
        buf = MapDataBuffer(256, 256)
        buf.paint_brush(0.5, 0.5, radius_px=40, value=10000, falloff=1.0, falloff_curve="cosine")
        # At exactly half the radius, linear progress t ≈ 0.5, cosine f(t) ≈ 0.5
        val = buf.get_value_at(0.5, 0.5 + 20 / 255)
        assert 3500 < val < 6500

    def test_gaussian_tighter_than_linear_near_edge(self) -> None:
        """Gaussian falloff has lower strength near the edge than linear.

        Near the outer edge (small t) the Gaussian bell curve falls faster
        than the linear ramp.
        """
        buf_lin = MapDataBuffer(256, 256)
        buf_lin.paint_brush(0.5, 0.5, radius_px=40, value=10000, falloff=1.0, falloff_curve="linear")

        buf_gauss = MapDataBuffer(256, 256)
        buf_gauss.paint_brush(0.5, 0.5, radius_px=40, value=10000, falloff=1.0, falloff_curve="gaussian")

        # 36 px away from centre in a 40-px brush → in feather zone, near edge
        y_offset = 36 / 255
        linear_val = buf_lin.get_value_at(0.5, 0.5 + y_offset)
        gauss_val = buf_gauss.get_value_at(0.5, 0.5 + y_offset)
        assert gauss_val < linear_val, (
            f"Expected gaussian ({gauss_val}) < linear ({linear_val}) near edge"
        )

    def test_cosine_monotonic_decrease(self) -> None:
        """Cosine falloff values decrease monotonically from centre outward."""
        buf = MapDataBuffer(256, 256)
        buf.paint_brush(0.5, 0.5, radius_px=40, value=10000, falloff=1.0, falloff_curve="cosine")
        prev = buf.get_value_at(0.5, 0.5)
        for px_away in (5, 10, 15, 20, 25, 30, 35):
            cur = buf.get_value_at(0.5, 0.5 + px_away / 255)
            assert cur <= prev, f"Value at {px_away}px ({cur}) > previous ({prev})"
            prev = cur


# ------------------------------------------------------------------
# Idempotent stroke strength map
# ------------------------------------------------------------------


class TestStrokeStrengthMap:
    """Tests for idempotent stroke mode using stroke_before + stroke_strength_map.

    When both are supplied, repeated dabs at the same location must not
    accumulate beyond the first dab's contribution.
    """

    def test_idempotent_single_vs_repeated(self) -> None:
        """Painting 10 dabs at the same position equals one dab in stroke mode."""
        import numpy as np

        buf_single = MapDataBuffer(128, 128)
        buf_single.paint_brush(0.5, 0.5, radius_px=20, value=8000, falloff=0.8, falloff_curve="cosine")

        buf_repeat = MapDataBuffer(128, 128)
        before = buf_repeat.data.copy()
        strength_map = np.zeros(buf_repeat.data.shape, dtype=np.float32)
        for _ in range(10):
            buf_repeat.paint_brush(
                0.5, 0.5,
                radius_px=20, value=8000, falloff=0.8, falloff_curve="cosine",
                stroke_before=before, stroke_strength_map=strength_map,
            )

        # In idempotent mode, 10 overlapping dabs == 1 dab
        assert buf_single.data.tobytes() == buf_repeat.data.tobytes()

    def test_stroke_max_strength_takes_largest_dab(self) -> None:
        """A larger-radius dab over the same region dominates the feather zone."""
        import numpy as np

        buf = MapDataBuffer(128, 128)
        before = buf.data.copy()
        strength_map = np.zeros(buf.data.shape, dtype=np.float32)

        # Small dab — low strength at the feather zone of the large dab
        buf.paint_brush(
            0.5, 0.5, radius_px=5, value=8000, falloff=1.0, falloff_curve="linear",
            stroke_before=before, stroke_strength_map=strength_map,
        )
        # Large dab — higher strength at its own feather zone
        buf.paint_brush(
            0.5, 0.5, radius_px=30, value=8000, falloff=1.0, falloff_curve="linear",
            stroke_before=before, stroke_strength_map=strength_map,
        )

        # Build reference: only large dab
        buf_ref = MapDataBuffer(128, 128)
        buf_ref.paint_brush(0.5, 0.5, radius_px=30, value=8000, falloff=1.0, falloff_curve="linear")

        # Centre should be full value in both
        assert buf.get_value_at(0.5, 0.5) == 8000
        assert buf_ref.get_value_at(0.5, 0.5) == 8000

        # In the feather zone of the large dab (beyond the small dab),
        # the strength_map should match the large dab's contribution.
        # At 20 px from centre (inside large dab, outside small dab),
        # the combined result must equal the large-dab-only result.
        combined = buf.get_value_at(0.5, 0.5 + 20 / 127)
        reference = buf_ref.get_value_at(0.5, 0.5 + 20 / 127)
        assert abs(combined - reference) <= 1, (
            f"combined={combined} should match reference={reference}"
        )

    def test_no_strength_map_behaves_as_accumulation(self) -> None:
        """Without stroke_strength_map, repeated dabs still accumulate (legacy mode)."""
        buf = MapDataBuffer(128, 128)
        # First dab with falloff=1.0 sets feather zone to ~50 % at half radius
        for _ in range(20):
            buf.paint_brush(0.5, 0.5, radius_px=20, value=8000, falloff=1.0, falloff_curve="cosine")
        # After 20 accumulations, feather zone should converge toward full value
        val_at_half_r = buf.get_value_at(0.5, 0.5 + 10 / 127)
        assert val_at_half_r > 7000, (
            f"Legacy accumulation: expected near-full value, got {val_at_half_r}"
        )


# ------------------------------------------------------------------
# Brush kernel LRU cache
# ------------------------------------------------------------------


class TestBrushKernelCache:
    """Tests for the module-level ``_compute_brush_kernel`` LRU cache."""

    def test_kernel_cached_same_object(self) -> None:
        """The same (r, falloff, curve) triple returns the identical array."""
        from src.gui.widgets.map.map_data_buffer import _compute_brush_kernel

        k1 = _compute_brush_kernel(10, 0.5, "cosine")
        k2 = _compute_brush_kernel(10, 0.5, "cosine")
        assert k1 is k2, "Expected lru_cache to return the same array object"

    def test_different_args_different_kernels(self) -> None:
        """Different arguments produce distinct arrays."""
        from src.gui.widgets.map.map_data_buffer import _compute_brush_kernel

        k_soft = _compute_brush_kernel(10, 0.8, "cosine")
        k_hard = _compute_brush_kernel(10, 0.0, "cosine")
        # Hard brush has ones/zeros only; soft brush has gradients

        assert not (k_soft == k_hard).all()

    def test_kernel_shape(self) -> None:
        """Kernel has the expected (2r+1, 2r+1) shape."""
        from src.gui.widgets.map.map_data_buffer import _compute_brush_kernel

        r = 15
        k = _compute_brush_kernel(r, 0.5, "gaussian")
        assert k.shape == (2 * r + 1, 2 * r + 1)

    def test_kernel_centre_is_one(self) -> None:
        """The centre pixel of any kernel with falloff > 0 is always 1.0."""

        from src.gui.widgets.map.map_data_buffer import _compute_brush_kernel

        for curve in ("cosine", "linear", "gaussian"):
            k = _compute_brush_kernel(12, 0.6, curve)
            assert k[12, 12] == pytest.approx(1.0), f"curve={curve} centre should be 1.0"

    def test_hard_kernel_is_binary(self) -> None:
        """falloff=0 kernel contains only 0.0 and 1.0."""
        import numpy as np

        from src.gui.widgets.map.map_data_buffer import _compute_brush_kernel

        k = _compute_brush_kernel(8, 0.0, "cosine")
        unique = set(np.unique(k).tolist())
        assert unique <= {0.0, 1.0}, f"Hard kernel should be binary, got {unique}"


# ------------------------------------------------------------------
# Gradient LUT builder + colorize_region(lut=) fast path
# ------------------------------------------------------------------


class TestGradientLut:
    """Tests for ``_build_gradient_lut`` and the ``lut=`` parameter on
    ``colorize_region``."""

    def _make_gradient_color_map(self) -> ColorMap:
        """Two-stop gradient: black → white over the full 0–65535 range."""
        return ColorMap(
            type="gradient",
            entries=[],
            gradient_stops=[
                GradientStop(position=0.0, color="#000000ff"),
                GradientStop(position=1.0, color="#ffffffff"),
            ],
        )

    def test_gradient_lut_shape(self) -> None:
        """LUT must be (65536, 4) uint8."""
        import numpy as np

        cmap = self._make_gradient_color_map()
        lut = MapDataBuffer._build_gradient_lut(cmap)
        assert lut.shape == (65536, 4)
        assert lut.dtype == np.uint8

    def test_gradient_lut_endpoints(self) -> None:
        """Index 0 → black (0,0,0,255); index 65535 → white (255,255,255,255)."""
        cmap = self._make_gradient_color_map()
        lut = MapDataBuffer._build_gradient_lut(cmap)
        assert list(lut[0]) == [0, 0, 0, 255]
        assert list(lut[65535]) == [255, 255, 255, 255]

    def test_colorize_region_lut_matches_no_lut(self) -> None:
        """``colorize_region(lut=…)`` pixel values match the slow path."""

        buf = MapDataBuffer(64, 64, default_value=0)
        # Paint a gradient of values across the buffer
        for col in range(64):
            buf._data[:, col] = int(col / 63 * 65535)

        cmap = self._make_gradient_color_map()
        lut = MapDataBuffer._build_gradient_lut(cmap)

        img_slow = buf.colorize_region(cmap, 0, 0, 63, 63)
        img_fast = buf.colorize_region(cmap, 0, 0, 63, 63, lut=lut)

        slow_bytes = img_slow.bits().tobytes()
        fast_bytes = img_fast.bits().tobytes()
        assert slow_bytes == fast_bytes, "LUT fast path must match per-pixel interp path"

    def test_palette_lut_passed_to_colorize_region(self) -> None:
        """A pre-built palette LUT produces the same output as the default path."""
        buf = MapDataBuffer(16, 16, default_value=1)
        cmap = ColorMap(
            type="palette",
            entries=[
                ColorEntry(value=0, color="#000000ff", label="bg"),
                ColorEntry(value=1, color="#ff0000ff", label="red"),
            ],
        )
        lut = MapDataBuffer._build_palette_lut(cmap)

        img_default = buf.colorize_region(cmap, 0, 0, 15, 15)
        img_with_lut = buf.colorize_region(cmap, 0, 0, 15, 15, lut=lut)

        assert img_default.bits().tobytes() == img_with_lut.bits().tobytes()

