"""Diagnostic script for raster map import pipeline.

Run from project root:
    python tmp/diag_raster_import.py

Tests PIL round-trip fidelity, mode handling, and the full import logic
extracted from CreateRasterLayerCommand.execute().
"""

import sys
import tempfile
import os
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def sep(title: str) -> None:
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print('─'*60)


def summary(arr: np.ndarray, label: str) -> None:
    print(f"  {label}: shape={arr.shape} dtype={arr.dtype} "
          f"min={arr.min()} max={arr.max()} mean={arr.mean():.1f}")


# ──────────────────────────────────────────────────────────────────────────────
# Part 1 – PIL save/load round-trip for uint16
# ──────────────────────────────────────────────────────────────────────────────
sep("1. PIL uint16 ↔ PNG round-trip")

# Build a known gradient: 0 → 65535
w, h = 64, 64
xs = np.linspace(0, 65535, w, dtype=np.float32)
gradient_u16 = np.tile(xs, (h, 1)).astype(np.uint16)
summary(gradient_u16, "original uint16")

with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
    tmp_path = f.name

# Save via MapDataBuffer.save() strategy
pil_img = Image.fromarray(gradient_u16)
print(f"  fromarray → mode={pil_img.mode!r}")
pil_img.save(tmp_path)
print(f"  Saved to {tmp_path} ({os.path.getsize(tmp_path)} bytes)")

# Reload via MapDataBuffer.from_file() strategy
reloaded = Image.open(tmp_path)
reloaded.load()
print(f"  Reloaded mode={reloaded.mode!r}")
arr_reloaded = np.array(reloaded, dtype=np.uint16)
summary(arr_reloaded, "reloaded uint16")

if np.array_equal(gradient_u16, arr_reloaded):
    print("  ✓ Round-trip PERFECT")
else:
    diff = arr_reloaded.astype(np.int32) - gradient_u16.astype(np.int32)
    print(f"  ✗ Round-trip MISMATCH – diff range: {diff.min()} → {diff.max()}")

os.unlink(tmp_path)

# ──────────────────────────────────────────────────────────────────────────────
# Part 2 – Test every PIL mode that an imported image might arrive in
# ──────────────────────────────────────────────────────────────────────────────
sep("2. Import pipeline – mode handling")

TARGET_W, TARGET_H = 128, 128

def run_import_pipeline(source_img: Image.Image, label: str, mode: str = "continuous") -> None:
    print(f"\n  [{label}]  PIL mode={source_img.mode!r}  size={source_img.size}")

    img = source_img.copy()

    # ── same logic as CreateRasterLayerCommand ──
    if img.mode == "I;16":
        img = img.convert("I")

    _is_grey_mode = img.mode in ("L", "LA", "I", "F")
    if not _is_grey_mode and img.mode in ("RGB", "RGBA"):
        _rgb_arr = np.array(img.convert("RGB"))
        _diff_rg = int(np.max(np.abs(
            _rgb_arr[:, :, 0].astype(np.int32) - _rgb_arr[:, :, 1].astype(np.int32)
        )))
        _diff_rb = int(np.max(np.abs(
            _rgb_arr[:, :, 0].astype(np.int32) - _rgb_arr[:, :, 2].astype(np.int32)
        )))
        _is_grey_mode = _diff_rg <= 2 and _diff_rb <= 2

    _resample = (
        Image.Resampling.NEAREST
        if mode == "discrete" and not _is_grey_mode
        else Image.Resampling.LANCZOS
    )
    img_resized = img.resize((TARGET_W, TARGET_H), _resample)
    is_greyscale = _is_grey_mode or img_resized.mode in ("L", "LA", "I")

    auto_palette_entries: list = []
    arr16: np.ndarray

    if mode == "discrete" and not is_greyscale:
        rgb = img_resized.convert("RGB")
        pixels = np.array(rgb).reshape(-1, 3)
        unique_colours = np.unique(pixels, axis=0)
        if len(unique_colours) <= 256:
            colour_to_val = {tuple(c): i + 1 for i, c in enumerate(unique_colours)}
            arr16 = np.array(
                [colour_to_val[tuple(p)] for p in pixels], dtype=np.uint16
            ).reshape(TARGET_H, TARGET_W)
        else:
            quantized = rgb.quantize(colors=256)
            arr8 = np.array(quantized, dtype=np.uint8)
            arr16 = arr8.astype(np.uint16)
    else:
        if img_resized.mode == "F":
            arr_f = np.array(img_resized, dtype=np.float32)
            arr_min, arr_max = float(arr_f.min()), float(arr_f.max())
            arr16 = (
                ((arr_f - arr_min) / (arr_max - arr_min) * 65535).astype(np.uint16)
                if arr_max > arr_min
                else np.zeros((TARGET_H, TARGET_W), dtype=np.uint16)
            )
        elif img_resized.mode == "I":
            arr16 = np.clip(np.array(img_resized), 0, 65535).astype(np.uint16)
        elif img_resized.mode == "L":
            arr16 = np.array(img_resized, dtype=np.uint16) * 257
        else:
            arr16 = np.array(img_resized.convert("L"), dtype=np.uint16) * 257

    summary(arr16, "arr16")
    if arr16.max() == 0:
        print("  ✗ ALL BLACK – arr16 is entirely zero!")
    elif arr16.max() < 100:
        print("  ✗ NEARLY BLACK – max value only", arr16.max())
    else:
        print("  ✓ Values look reasonable")


# 8-bit L mode (most common terrain PNG)
img_l = Image.fromarray(
    np.tile(np.linspace(0, 255, TARGET_W, dtype=np.uint8), (TARGET_H, 1)),
    mode="L",
)
run_import_pipeline(img_l, "8-bit L (horizontal gradient)")

# 16-bit grayscale via I mode (how Pillow loads 16-bit PNG)
arr_16 = np.tile(np.linspace(0, 65535, TARGET_W, dtype=np.float32).astype(np.int32), (TARGET_H, 1))
img_i = Image.fromarray(arr_16, mode="I")
run_import_pipeline(img_i, "16-bit I mode (simulated 16-bit PNG)")

# Float F mode (GeoTIFF elevation)
arr_f = np.tile(np.linspace(-100.0, 3000.0, TARGET_W, dtype=np.float32), (TARGET_H, 1))
img_f = Image.fromarray(arr_f, mode="F")
run_import_pipeline(img_f, "float F mode (GeoTIFF)")

# RGB image (e.g. a colour biome map)
rgb_arr = np.zeros((TARGET_H, TARGET_W, 3), dtype=np.uint8)
rgb_arr[:, :TARGET_W // 2] = [255, 0, 0]    # red half
rgb_arr[:, TARGET_W // 2:] = [0, 128, 255]  # blue half
img_rgb = Image.fromarray(rgb_arr, mode="RGB")
run_import_pipeline(img_rgb, "RGB colour biome map", mode="discrete")

# RGB-stored grayscale
grey_rgb = np.stack([np.linspace(0, 255, TARGET_W, dtype=np.uint8).reshape(1, -1).repeat(TARGET_H, 0)] * 3, axis=2)
img_grey_rgb = Image.fromarray(grey_rgb.astype(np.uint8), mode="RGB")
run_import_pipeline(img_grey_rgb, "RGB-stored greyscale (R==G==B)")

# ──────────────────────────────────────────────────────────────────────────────
# Part 3 – Simulate opening an actual 16-bit PNG as Pillow would
# ──────────────────────────────────────────────────────────────────────────────
sep("3. 16-bit PNG open → mode check")

# Create a real 16-bit PNG file and open it
arr16_real = np.tile(np.linspace(0, 65535, 128, dtype=np.float32).astype(np.uint16), (64, 1))
with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
    tmp16 = f.name

# Save properly as 16-bit PNG using int32 pathway (known-good)
Image.fromarray(arr16_real.astype(np.int32), mode="I").save(tmp16)
print(f"  Saved {arr16_real.shape} uint16 as int32-I PNG ({os.path.getsize(tmp16)} bytes)")

opened = Image.open(tmp16)
opened.load()
print(f"  Opened: mode={opened.mode!r}")
arr_reopen = np.array(opened, dtype=np.uint16)
summary(arr_reopen, "reopened as uint16")

if np.array_equal(arr16_real, arr_reopen):
    print("  ✓ 16-bit PNG round-trip OK with int32 save")
else:
    diff = arr_reopen.astype(np.int32) - arr16_real.astype(np.int32)
    print(f"  ✗ MISMATCH diff range: {diff.min()} → {diff.max()}")

os.unlink(tmp16)

# ──────────────────────────────────────────────────────────────────────────────
# Part 4 – MapDataBuffer save/reload round-trip
# ──────────────────────────────────────────────────────────────────────────────
sep("4. MapDataBuffer.save() / from_file() round-trip")

import sys
sys.path.insert(0, "src")
# Need PySide6 QApplication for QImage
try:
    from src.gui.widgets.map.map_data_buffer import MapDataBuffer, ColorMap, GradientStop

    known_arr = np.tile(
        np.linspace(0, 65535, 256, dtype=np.float32).astype(np.uint16), (128, 1)
    )

    buf_orig = MapDataBuffer(256, 128, 0)
    buf_orig._data = known_arr.copy()
    summary(buf_orig._data, "original buffer")

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        buf_path = f.name

    buf_orig.save(buf_path)
    print(f"  Saved buffer PNG ({os.path.getsize(buf_path)} bytes)")

    buf_reloaded = MapDataBuffer.from_file(buf_path)
    summary(buf_reloaded._data, "reloaded buffer")

    if np.array_equal(known_arr, buf_reloaded._data):
        print("  ✓ MapDataBuffer round-trip PERFECT")
    else:
        diff = buf_reloaded._data.astype(np.int32) - known_arr.astype(np.int32)
        print(f"  ✗ MISMATCH diff range: {diff.min()} → {diff.max()}")
        unique_diffs = np.unique(diff)
        print(f"  Unique diff values: {unique_diffs[:20]}")

    os.unlink(buf_path)

except ImportError as e:
    print(f"  Skipped (import error): {e}")

print("\n" + "─"*60)
print("  Diagnostic complete")
print("─"*60)
