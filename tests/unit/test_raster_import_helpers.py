"""Tests for the raster_import_helpers pure-function module (M5).

All functions operate on PIL Images and/or numpy arrays; no Qt required.
"""
import numpy as np
import pytest
from PIL import Image as PilImage

from src.services.raster_import_helpers import (
    choose_resample,
    detect_greyscale,
    normalize_to_uint16,
    quantize_discrete_rgb,
)


# ---------------------------------------------------------------------------
# detect_greyscale
# ---------------------------------------------------------------------------

def test_detect_greyscale_native_l_mode():
    """L-mode image is always greyscale."""
    img = PilImage.new("L", (4, 4), 128)
    assert detect_greyscale(img) is True


def test_detect_greyscale_native_f_mode():
    """F-mode (float) image is treated as greyscale."""
    img = PilImage.new("F", (4, 4), 0.5)
    assert detect_greyscale(img) is True


def test_detect_greyscale_true_for_grey_rgb():
    """RGB image where R==G==B is detected as greyscale."""
    arr = np.full((8, 8, 3), 100, dtype=np.uint8)
    img = PilImage.fromarray(arr, mode="RGB")
    assert detect_greyscale(img) is True


def test_detect_greyscale_threshold_tolerance():
    """Channels differing by ≤2 still count as greyscale."""
    arr = np.full((4, 4, 3), 100, dtype=np.uint8)
    arr[:, :, 1] = 102  # diff = 2 exactly => still grey
    arr[:, :, 2] = 99   # diff = 1
    img = PilImage.fromarray(arr, mode="RGB")
    assert detect_greyscale(img) is True


def test_detect_greyscale_false_for_color():
    """Colorful RGB image is detected as NOT greyscale."""
    arr = np.zeros((8, 8, 3), dtype=np.uint8)
    arr[:, :, 0] = 255  # pure red
    img = PilImage.fromarray(arr, mode="RGB")
    assert detect_greyscale(img) is False


# ---------------------------------------------------------------------------
# normalize_to_uint16
# ---------------------------------------------------------------------------

def test_normalize_to_uint16_float_full_range():
    """Float32 array [0.0, 1.0] normalises to uint16 [0, 65535]."""
    arr = np.array([[0.0, 0.5], [0.75, 1.0]], dtype=np.float32)
    img = PilImage.fromarray(arr, mode="F")
    result = normalize_to_uint16(img)
    assert result.dtype == np.uint16
    assert int(result.min()) == 0
    assert int(result.max()) == 65535


def test_normalize_to_uint16_float_constant_is_zeros():
    """Constant float array normalises to all-zero (range = 0)."""
    arr = np.full((4, 4), 42.0, dtype=np.float32)
    img = PilImage.fromarray(arr, mode="F")
    result = normalize_to_uint16(img)
    assert result.dtype == np.uint16
    assert int(result.max()) == 0


def test_normalize_to_uint16_l_mode():
    """8-bit greyscale [0, 255] normalises to full uint16 range."""
    arr = np.array([[0, 128, 255]], dtype=np.uint8)
    arr = np.tile(arr, (4, 1))
    img = PilImage.fromarray(arr, mode="L")
    result = normalize_to_uint16(img)
    assert result.dtype == np.uint16
    assert int(result.min()) == 0
    assert int(result.max()) == 65535


def test_normalize_to_uint16_i_mode():
    """I-mode (int32) image normalises to uint16."""
    arr = np.array([[0, 1000, 65535]], dtype=np.int32)
    arr = np.tile(arr, (4, 1))
    img = PilImage.fromarray(arr, mode="I")
    result = normalize_to_uint16(img)
    assert result.dtype == np.uint16
    assert int(result.min()) == 0
    assert int(result.max()) == 65535


# ---------------------------------------------------------------------------
# quantize_discrete_rgb
# ---------------------------------------------------------------------------

def _build_rgb_image(n_colors: int) -> PilImage.Image:
    """Build an RGB image with exactly *n_colors* distinct solid blocks."""
    size = max(n_colors, 4)
    arr = np.zeros((size, size, 3), dtype=np.uint8)
    for i in range(n_colors):
        # Each row gets a unique colour
        r = (i * 73) % 256
        g = (i * 131) % 256
        b = (i * 197) % 256
        row = i % size
        arr[row, :, :] = [r, g, b]
    return PilImage.fromarray(arr, mode="RGB")


def test_quantize_discrete_rgb_small_palette():
    """≤256 unique colors → uint16 index array + matching palette entries."""
    n = 10
    img = _build_rgb_image(n)
    arr16, palette = quantize_discrete_rgb(img)
    assert arr16.dtype == np.uint16
    assert len(palette) == n
    assert all("value" in e and "color" in e for e in palette)


def test_quantize_discrete_rgb_too_many_colors():
    """300 unique colors → quantized to ≤256, palette_entries length ≤ 256."""
    img = _build_rgb_image(300)
    arr16, palette = quantize_discrete_rgb(img)
    assert arr16.dtype == np.uint16
    assert len(palette) <= 256


def test_quantize_discrete_rgb_single_color():
    """Single-color image → palette with 1 entry."""
    arr = np.full((4, 4, 3), 200, dtype=np.uint8)
    img = PilImage.fromarray(arr, mode="RGB")
    arr16, palette = quantize_discrete_rgb(img)
    assert len(palette) == 1


# ---------------------------------------------------------------------------
# choose_resample
# ---------------------------------------------------------------------------

def test_choose_resample_discrete_color():
    """Discrete non-greyscale mode → NEAREST (sharp class boundaries)."""
    result = choose_resample(mode="discrete", is_greyscale=False)
    assert result == PilImage.Resampling.NEAREST


def test_choose_resample_discrete_greyscale():
    """Discrete greyscale mode → LANCZOS (greyscale has gradients)."""
    result = choose_resample(mode="discrete", is_greyscale=True)
    assert result == PilImage.Resampling.LANCZOS


def test_choose_resample_continuous():
    """Continuous mode → LANCZOS regardless of greyscale."""
    assert choose_resample(mode="continuous", is_greyscale=False) == PilImage.Resampling.LANCZOS
    assert choose_resample(mode="continuous", is_greyscale=True) == PilImage.Resampling.LANCZOS
