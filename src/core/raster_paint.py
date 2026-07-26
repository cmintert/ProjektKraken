"""Pure, mode-aware raster painting operations.

The functions in this module operate only on NumPy arrays. They deliberately
avoid Qt and filesystem dependencies so GUI tools, commands, and tests share
one set of painting semantics.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal, TypeAlias

import numpy as np

RasterTarget: TypeAlias = int | tuple[int, int, int, int]
GradientKind: TypeAlias = Literal["linear", "radial", "reflected"]
FalloffCurve: TypeAlias = Literal["linear", "cosine", "gaussian"]


class RasterPixelFormat(str, Enum):
    """Storage format for editable raster pixels."""

    VALUE16 = "value16"
    RGBA8 = "rgba8"


class RasterPaintMode(str, Enum):
    """Semantic contract applied while editing a raster."""

    DISCRETE = "discrete"
    CONTINUOUS = "continuous"
    RGBA = "color"


@dataclass(frozen=True)
class BrushSpec:
    """Settings for one brush dab.

    ``hardness`` follows painting-application convention: ``1.0`` is a hard
    edge and ``0.0`` feathers across the complete radius.
    """

    radius_px: int
    hardness: float = 1.0
    opacity: float = 1.0
    curve: FalloffCurve = "cosine"

    def __post_init__(self) -> None:
        if self.radius_px < 1:
            raise ValueError("Brush radius must be positive")
        if not 0.0 <= self.hardness <= 1.0:
            raise ValueError("Brush hardness must be between 0 and 1")
        if not 0.0 <= self.opacity <= 1.0:
            raise ValueError("Brush opacity must be between 0 and 1")


@dataclass(frozen=True)
class FillSpec:
    """Settings for a connected-region fill."""

    tolerance: int = 0

    def __post_init__(self) -> None:
        if self.tolerance < 0:
            raise ValueError("Fill tolerance cannot be negative")


@dataclass(frozen=True)
class GradientSpec:
    """Settings for a two-endpoint gradient."""

    kind: GradientKind
    start: RasterTarget
    end: RasterTarget
    width_px: int = 0

    def __post_init__(self) -> None:
        if self.width_px < 0:
            raise ValueError("Gradient width cannot be negative")


def pixel_format_for_array(array: np.ndarray) -> RasterPixelFormat:
    """Return the supported pixel format for *array*."""
    if array.dtype == np.uint16 and array.ndim == 2:
        return RasterPixelFormat.VALUE16
    if (
        array.dtype == np.uint8
        and array.ndim == 3
        and array.shape[2] == 4
    ):
        return RasterPixelFormat.RGBA8
    raise ValueError(
        f"Unsupported raster array: shape={array.shape}, dtype={array.dtype}"
    )


def brush_bounds(
    shape: tuple[int, ...],
    center_col: float,
    center_row: float,
    radius_px: int,
) -> tuple[int, int, int, int]:
    """Return an inclusive brush rectangle clipped to *shape*."""
    height, width = shape[:2]
    min_col = max(0, int(np.floor(center_col - radius_px)))
    min_row = max(0, int(np.floor(center_row - radius_px)))
    max_col = min(width - 1, int(np.ceil(center_col + radius_px)))
    max_row = min(height - 1, int(np.ceil(center_row + radius_px)))
    return min_col, min_row, max_col, max_row


def _shape_falloff(progress: np.ndarray, curve: FalloffCurve) -> np.ndarray:
    if curve == "cosine":
        return 0.5 - 0.5 * np.cos(np.pi * progress)
    if curve == "gaussian":
        return np.exp(-4.5 * (1.0 - progress) ** 2)
    return progress


def brush_coverage(
    shape: tuple[int, ...],
    center_col: float,
    center_row: float,
    spec: BrushSpec,
) -> tuple[tuple[int, int, int, int], np.ndarray]:
    """Return the clipped brush rectangle and per-pixel coverage."""
    bounds = brush_bounds(shape, center_col, center_row, spec.radius_px)
    min_col, min_row, max_col, max_row = bounds
    yy, xx = np.ogrid[min_row : max_row + 1, min_col : max_col + 1]
    distance = np.sqrt((xx - center_col) ** 2 + (yy - center_row) ** 2)
    inside = distance <= spec.radius_px

    if spec.hardness >= 1.0:
        coverage = inside.astype(np.float32)
    else:
        hard_radius = spec.radius_px * spec.hardness
        feather_width = max(float(spec.radius_px) - hard_radius, 1e-6)
        progress = np.clip(
            (float(spec.radius_px) - distance) / feather_width,
            0.0,
            1.0,
        )
        coverage = _shape_falloff(
            progress.astype(np.float32), spec.curve
        ).astype(np.float32)
        coverage[distance <= hard_radius] = 1.0
        coverage[~inside] = 0.0

    coverage *= spec.opacity
    return bounds, np.clip(coverage, 0.0, 1.0)


def paint_discrete_brush(
    array: np.ndarray,
    center_col: float,
    center_row: float,
    radius_px: int,
    value: int,
) -> tuple[int, int, int, int]:
    """Replace complete categorical pixels inside a hard circular brush."""
    if pixel_format_for_array(array) != RasterPixelFormat.VALUE16:
        raise ValueError("Discrete painting requires a uint16 value raster")
    bounds, coverage = brush_coverage(
        array.shape,
        center_col,
        center_row,
        BrushSpec(radius_px=radius_px),
    )
    min_col, min_row, max_col, max_row = bounds
    region = array[min_row : max_row + 1, min_col : max_col + 1]
    region[coverage > 0.0] = np.uint16(np.clip(value, 0, 65535))
    return bounds


def paint_continuous_brush(
    array: np.ndarray,
    center_col: float,
    center_row: float,
    target: int,
    spec: BrushSpec,
    *,
    baseline: np.ndarray | None = None,
    maximum_coverage: np.ndarray | None = None,
) -> tuple[int, int, int, int]:
    """Blend a value raster toward *target* with idempotent stroke support."""
    if pixel_format_for_array(array) != RasterPixelFormat.VALUE16:
        raise ValueError("Continuous painting requires a uint16 value raster")
    bounds, coverage = brush_coverage(
        array.shape, center_col, center_row, spec
    )
    min_col, min_row, max_col, max_row = bounds
    region = array[min_row : max_row + 1, min_col : max_col + 1]

    if baseline is not None and maximum_coverage is not None:
        if baseline.shape == region.shape and maximum_coverage.shape == region.shape:
            source = baseline
            strength = maximum_coverage
        elif baseline.shape == array.shape and maximum_coverage.shape == array.shape:
            source = baseline[min_row : max_row + 1, min_col : max_col + 1]
            strength = maximum_coverage[
                min_row : max_row + 1, min_col : max_col + 1
            ]
        else:
            raise ValueError("Stroke baseline and coverage must match the raster or dab")
        np.maximum(strength, coverage, out=strength)
        coverage = strength
    else:
        source = region.copy()

    blended = (
        source.astype(np.float32) * (1.0 - coverage)
        + float(np.clip(target, 0, 65535)) * coverage
    )
    region[...] = np.rint(blended).clip(0, 65535).astype(np.uint16)
    return bounds


def _source_over_rgba(
    destination: np.ndarray,
    color: tuple[int, int, int, int],
    coverage: np.ndarray,
) -> np.ndarray:
    """Composite one straight-alpha colour over an RGBA region."""
    dst = destination.astype(np.float32) / 255.0
    src = np.asarray(color, dtype=np.float32).clip(0, 255) / 255.0
    src_alpha = coverage[..., None] * src[3]
    dst_alpha = dst[..., 3:4]
    out_alpha = src_alpha + dst_alpha * (1.0 - src_alpha)
    src_premul = src[:3] * src_alpha
    dst_premul = dst[..., :3] * dst_alpha
    out_premul = src_premul + dst_premul * (1.0 - src_alpha)
    out_rgb = np.divide(
        out_premul,
        out_alpha,
        out=np.zeros_like(out_premul),
        where=out_alpha > 1e-8,
    )
    return np.concatenate((out_rgb, out_alpha), axis=2)


def paint_rgba_brush(
    array: np.ndarray,
    center_col: float,
    center_row: float,
    color: tuple[int, int, int, int],
    spec: BrushSpec,
    *,
    baseline: np.ndarray | None = None,
    maximum_coverage: np.ndarray | None = None,
) -> tuple[int, int, int, int]:
    """Paint a colour using source-over alpha compositing."""
    if pixel_format_for_array(array) != RasterPixelFormat.RGBA8:
        raise ValueError("RGBA painting requires an uint8 RGBA raster")
    bounds, coverage = brush_coverage(
        array.shape, center_col, center_row, spec
    )
    min_col, min_row, max_col, max_row = bounds
    region = array[min_row : max_row + 1, min_col : max_col + 1]

    if baseline is not None and maximum_coverage is not None:
        if (
            baseline.shape == region.shape
            and maximum_coverage.shape == region.shape[:2]
        ):
            source = baseline
            strength = maximum_coverage
        elif (
            baseline.shape == array.shape
            and maximum_coverage.shape == array.shape[:2]
        ):
            source = baseline[min_row : max_row + 1, min_col : max_col + 1]
            strength = maximum_coverage[
                min_row : max_row + 1, min_col : max_col + 1
            ]
        else:
            raise ValueError("Stroke baseline and coverage must match the raster or dab")
        np.maximum(strength, coverage, out=strength)
        coverage = strength
    else:
        source = region.copy()

    composited = _source_over_rgba(source, color, coverage)
    region[...] = np.rint(composited * 255.0).clip(0, 255).astype(np.uint8)
    return bounds


def connected_fill(
    array: np.ndarray,
    start_col: int,
    start_row: int,
    target: RasterTarget,
    spec: FillSpec,
) -> tuple[int, int, int, int] | None:
    """Fill one connected region using mode-appropriate similarity."""
    match = connected_region(array, start_col, start_row, spec)
    if match is None:
        return None
    bounds, mask = match
    pixel_format = pixel_format_for_array(array)
    height, width = array.shape[:2]
    start_col = max(0, min(start_col, width - 1))
    start_row = max(0, min(start_row, height - 1))
    if pixel_format == RasterPixelFormat.VALUE16:
        if isinstance(target, tuple):
            raise ValueError("Value fill target must be an integer")
        target_value = np.uint16(np.clip(int(target), 0, 65535))
        seed = array[start_row, start_col]
        if int(seed) == int(target_value):
            return None
        replacement: RasterTarget = int(target_value)
    else:
        rgba = np.asarray(target, dtype=np.uint8)
        if rgba.shape != (4,):
            raise ValueError("RGBA fill target must contain four channels")
        seed = array[start_row, start_col]
        if np.array_equal(seed, rgba):
            return None
        replacement = tuple(int(channel) for channel in rgba)  # type: ignore[assignment]
    min_col, min_row, max_col, max_row = bounds
    region = array[min_row : max_row + 1, min_col : max_col + 1]
    region[mask] = replacement
    return bounds


def connected_region(
    array: np.ndarray,
    start_col: int,
    start_row: int,
    spec: FillSpec,
) -> tuple[tuple[int, int, int, int], np.ndarray] | None:
    """Return bounds and local mask for one connected similar region."""
    pixel_format = pixel_format_for_array(array)
    height, width = array.shape[:2]
    start_col = max(0, min(start_col, width - 1))
    start_row = max(0, min(start_row, height - 1))
    seed = array[start_row, start_col].copy()

    if pixel_format == RasterPixelFormat.VALUE16:

        def matches(row: int, col: int) -> bool:
            return abs(int(array[row, col]) - int(seed)) <= spec.tolerance

    else:

        def matches(row: int, col: int) -> bool:
            delta = np.abs(
                array[row, col].astype(np.int16) - seed.astype(np.int16)
            )
            return int(delta.max()) <= spec.tolerance

    visited = np.zeros((height, width), dtype=bool)
    matched = np.zeros((height, width), dtype=bool)
    stack = [(start_row, start_col)]
    min_col = max_col = start_col
    min_row = max_row = start_row
    changed = False

    while stack:
        row, col = stack.pop()
        if visited[row, col]:
            continue
        visited[row, col] = True
        if not matches(row, col):
            continue
        matched[row, col] = True
        changed = True
        min_col = min(min_col, col)
        max_col = max(max_col, col)
        min_row = min(min_row, row)
        max_row = max(max_row, row)
        if row > 0:
            stack.append((row - 1, col))
        if row + 1 < height:
            stack.append((row + 1, col))
        if col > 0:
            stack.append((row, col - 1))
        if col + 1 < width:
            stack.append((row, col + 1))

    if not changed:
        return None
    bounds = (min_col, min_row, max_col, max_row)
    return (
        bounds,
        matched[min_row : max_row + 1, min_col : max_col + 1],
    )


def _gradient_factor(
    shape: tuple[int, ...],
    start: tuple[float, float],
    end: tuple[float, float],
    kind: GradientKind,
    width_px: int,
) -> tuple[tuple[int, int, int, int], np.ndarray]:
    height, width = shape[:2]
    sx, sy = start
    ex, ey = end
    yy, xx = np.mgrid[0:height, 0:width]
    dx = ex - sx
    dy = ey - sy
    length_sq = dx * dx + dy * dy
    length = max(float(np.sqrt(length_sq)), 1e-6)

    if kind == "radial":
        factor = np.sqrt((xx - sx) ** 2 + (yy - sy) ** 2) / length
    else:
        projection = (
            ((xx - sx) * dx + (yy - sy) * dy) / max(length_sq, 1e-6)
        )
        factor = np.abs(projection) if kind == "reflected" else projection
    factor = np.clip(factor, 0.0, 1.0).astype(np.float32)

    if width_px > 0 and kind != "radial":
        perpendicular = np.abs((xx - sx) * dy - (yy - sy) * dx) / length
        mask = perpendicular <= width_px
    elif width_px > 0:
        mask = np.sqrt((xx - sx) ** 2 + (yy - sy) ** 2) <= length + width_px
    else:
        mask = np.ones((height, width), dtype=bool)

    rows, cols = np.nonzero(mask)
    if len(rows) == 0:
        return (0, 0, 0, 0), np.zeros((0, 0), dtype=np.float32)
    bounds = (
        int(cols.min()),
        int(rows.min()),
        int(cols.max()),
        int(rows.max()),
    )
    min_col, min_row, max_col, max_row = bounds
    local_factor = factor[min_row : max_row + 1, min_col : max_col + 1]
    local_mask = mask[min_row : max_row + 1, min_col : max_col + 1]
    return bounds, np.where(local_mask, local_factor, np.nan)


def paint_gradient(
    array: np.ndarray,
    start: tuple[float, float],
    end: tuple[float, float],
    spec: GradientSpec,
) -> tuple[int, int, int, int] | None:
    """Paint an explicit two-endpoint continuous or RGBA gradient."""
    pixel_format = pixel_format_for_array(array)
    bounds, factor = _gradient_factor(
        array.shape, start, end, spec.kind, spec.width_px
    )
    if factor.size == 0:
        return None
    min_col, min_row, max_col, max_row = bounds
    mask = ~np.isnan(factor)
    t = np.nan_to_num(factor, nan=0.0)[..., None]
    region = array[min_row : max_row + 1, min_col : max_col + 1]

    if pixel_format == RasterPixelFormat.VALUE16:
        if isinstance(spec.start, tuple) or isinstance(spec.end, tuple):
            raise ValueError("Value gradient endpoints must be integers")
        start_value = float(np.clip(int(spec.start), 0, 65535))
        end_value = float(np.clip(int(spec.end), 0, 65535))
        values = np.rint(
            start_value * (1.0 - t[..., 0]) + end_value * t[..., 0]
        ).astype(np.uint16)
        region[mask] = values[mask]
        return bounds

    start_rgba = np.asarray(spec.start, dtype=np.float32).clip(0, 255) / 255.0
    end_rgba = np.asarray(spec.end, dtype=np.float32).clip(0, 255) / 255.0
    if start_rgba.shape != (4,) or end_rgba.shape != (4,):
        raise ValueError("RGBA gradient endpoints must contain four channels")
    start_premul = np.concatenate(
        (start_rgba[:3] * start_rgba[3], start_rgba[3:])
    )
    end_premul = np.concatenate(
        (end_rgba[:3] * end_rgba[3], end_rgba[3:])
    )
    premul = start_premul * (1.0 - t) + end_premul * t
    alpha = premul[..., 3:4]
    rgb = np.divide(
        premul[..., :3],
        alpha,
        out=np.zeros_like(premul[..., :3]),
        where=alpha > 1e-8,
    )
    rgba = np.concatenate((rgb, alpha), axis=2)
    encoded = np.rint(rgba * 255.0).clip(0, 255).astype(np.uint8)
    region[mask] = encoded[mask]
    return bounds


def sample_pixel(array: np.ndarray, col: int, row: int) -> RasterTarget:
    """Return one clamped value or RGBA pixel."""
    height, width = array.shape[:2]
    col = max(0, min(col, width - 1))
    row = max(0, min(row, height - 1))
    if pixel_format_for_array(array) == RasterPixelFormat.VALUE16:
        return int(array[row, col])
    return tuple(int(channel) for channel in array[row, col])  # type: ignore[return-value]
