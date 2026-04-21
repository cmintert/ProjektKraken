"""Map Data Buffer — 16-bit raster data layer.

Wraps a ``numpy.ndarray`` (dtype ``uint16``) for in-memory raster
editing.  Provides normalised-coordinate access, brush painting,
palette-based colorisation, and 16-bit PNG persistence via Pillow.
"""

import logging
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PySide6.QtGui import QImage

from src.gui.widgets.map.raster_mapping import normalize_value_entity_map

logger = logging.getLogger(__name__)


@dataclass
class ClassStat:
    """Statistics for a single discrete class in a raster buffer.

    Attributes:
        value: The 16-bit raster value for this class.
        label: Human-readable label.
        pixel_count: Number of pixels with this value.
        percentage: Fraction of total pixels (0–100).
    """

    value: int
    label: str
    pixel_count: int
    percentage: float


@dataclass
class CoverageStats:
    """Aggregated coverage statistics for a raster buffer.

    Attributes:
        mode: ``"discrete"`` or ``"continuous"``.
        total_pixels: Total pixel count (width × height).
        classes: Per-class stats list (discrete mode only).
        histogram_counts: 32-bucket histogram counts (continuous mode).
        histogram_edges: 33 bucket edges (continuous mode).
        min_val: Minimum non-zero value (continuous mode).
        max_val: Maximum non-zero value (continuous mode).
        mean_val: Mean of non-zero values (continuous mode).
        median_val: Median of non-zero values (continuous mode).
    """

    mode: str
    total_pixels: int
    classes: List[ClassStat] = field(default_factory=list)
    histogram_counts: Optional[List[int]] = None
    histogram_edges: Optional[List[float]] = None
    min_val: Optional[float] = None
    max_val: Optional[float] = None
    mean_val: Optional[float] = None
    median_val: Optional[float] = None


@dataclass
class ColorEntry:
    """A single value → colour mapping for discrete palettes.

    Attributes:
        value: The 16-bit raster value.
        color: Hex colour string, e.g. ``"#88C070"``.
        entity_id: Optional entity UUID linked to this palette entry.

    """

    value: int
    color: str
    entity_id: Optional[str] = None
    label: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to JSON-friendly dict."""
        d: Dict[str, Any] = {"value": self.value, "color": self.color}
        if self.entity_id is not None:
            d["entity_id"] = self.entity_id
        if self.label is not None:
            d["label"] = self.label
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ColorEntry":
        """Deserialise from dict."""
        return cls(
            value=int(data["value"]),
            color=str(data["color"]),
            entity_id=data.get("entity_id"),
            label=data.get("label"),
        )


@dataclass
class GradientStop:
    """A single position→colour stop for multi-stop gradient colour maps.

    Attributes:
        position: Normalised position in [0.0, 1.0] along the gradient.
        color: Hex colour string, e.g. ``"#88C070"`` or ``"#88C07080"`` (with alpha).

    """

    position: float
    color: str

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to JSON-friendly dict."""
        return {"position": self.position, "color": self.color}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "GradientStop":
        """Deserialise from dict."""
        return cls(position=float(d["position"]), color=str(d["color"]))


@dataclass
class ColorMap:
    """Colour look-up table for raster visualisation.

    Supports two modes:

    * **palette** — explicit value→colour list (discrete layers).
    * **gradient** — multi-stop colour ramp across the full 0–65535 range.

    Attributes:
        type: ``"palette"`` or ``"gradient"``.
        entries: Colour entries (used when *type* is ``"palette"``).
        gradient_stops: Ordered list of colour stops (gradient mode).
            Must contain at least two stops with positions 0.0 and 1.0.
        stretch_min: Raw value mapped to position 0.0 (gradient mode).
        stretch_max: Raw value mapped to position 1.0 (gradient mode).
        display_min: Real-world value corresponding to *stretch_min*
            (e.g. ``-10.0`` for −10 °C).  ``None`` means no display mapping.
        display_max: Real-world value corresponding to *stretch_max*.
        unit: Unit label appended to formatted values (e.g. ``"°C"``).
        format_str: Python format string for display values (e.g. ``"{:.1f}"``).
        scale: Interpolation scale — ``"linear"`` or ``"log"``.
        linked_entity_id: UUID of a world entity/event that this colour map
            represents (gradient mode).  ``None`` means not linked.
        linked_entity_type: ``"entity"``, ``"event"``, or ``""`` when not set.

    """

    type: str = "palette"
    entries: List[ColorEntry] = field(default_factory=list)
    gradient_stops: List[GradientStop] = field(default_factory=list)
    stretch_min: Optional[int] = None
    stretch_max: Optional[int] = None
    display_min: Optional[float] = None
    display_max: Optional[float] = None
    unit: str = ""
    format_str: str = "{:.2f}"
    scale: str = "linear"
    linked_entity_id: Optional[str] = None
    linked_entity_type: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to JSON-friendly dict."""
        d: Dict[str, Any] = {"type": self.type}
        if self.type == "palette":
            d["entries"] = [e.to_dict() for e in self.entries]
        else:
            d["gradient_stops"] = [s.to_dict() for s in self.gradient_stops]
        if self.stretch_min is not None:
            d["stretch_min"] = self.stretch_min
        if self.stretch_max is not None:
            d["stretch_max"] = self.stretch_max
        if self.display_min is not None:
            d["display_min"] = self.display_min
        if self.display_max is not None:
            d["display_max"] = self.display_max
        if self.unit:
            d["unit"] = self.unit
        if self.format_str and self.format_str != "{:.2f}":
            d["format_str"] = self.format_str
        if self.scale and self.scale != "linear":
            d["scale"] = self.scale
        if self.linked_entity_id:
            d["linked_entity_id"] = self.linked_entity_id
        if self.linked_entity_type:
            d["linked_entity_type"] = self.linked_entity_type
        return d

    @classmethod
    def from_rgb_image(
        cls,
        img: Any,
        n_stops: int = 8,
        max_iter: int = 20,
    ) -> "ColorMap":
        """Build a gradient ColorMap that reconstructs an RGB image's colours.

        Pixels are clustered in weighted (luminance, R, G, B) space using
        k-means so that perceptually distinct hues each get their own
        gradient stop.  Stops are ordered by perceived luminance so the
        resulting gradient maps the greyscale buffer back to the original
        colours with high fidelity.

        Args:
            img: PIL ``Image`` (any mode) **or** a numpy array (H×W×3/4).
            n_stops: Number of gradient stops (≥ 2, default 8).
            max_iter: Maximum k-means iterations (default 20).

        Returns:
            ``ColorMap`` of type ``"gradient"`` with *n_stops* stops spanning
            0.0 → 1.0 and ``stretch_min=0, stretch_max=65535``.

        Raises:
            ValueError: If *n_stops* < 2.
        """
        from PIL import Image as _PILImage

        if n_stops < 2:
            raise ValueError("n_stops must be >= 2")

        # --- Normalise input to (H, W, 3) uint8 array -------------------
        if isinstance(img, _PILImage.Image):
            rgb_arr = np.array(img.convert("RGB"), dtype=np.uint8)
        else:
            rgb_arr = np.asarray(img, dtype=np.uint8)
            if rgb_arr.ndim == 2:
                rgb_arr = np.stack([rgb_arr] * 3, axis=-1)
            elif rgb_arr.shape[2] == 4:
                rgb_arr = rgb_arr[:, :, :3]

        flat = rgb_arr.reshape(-1, 3).astype(np.float32)  # (N, 3)

        # Perceived luminance (Rec. 709)
        lum = 0.2126 * flat[:, 0] + 0.7152 * flat[:, 1] + 0.0722 * flat[:, 2]

        # Feature vector: (lum_weighted, R, G, B).
        # Luminance is weighted 2× so that brightness has the strongest
        # influence on cluster ordering.
        features = np.column_stack([lum * 2.0, flat])  # (N, 4)

        # --- Simple k-means (no scipy dependency) -----------------------
        rng = np.random.RandomState(42)
        n_pixels = features.shape[0]
        k = min(n_stops, n_pixels)

        # Initialise centroids via k-means++ seeding
        indices = np.empty(k, dtype=np.intp)
        indices[0] = rng.randint(n_pixels)
        for ci in range(1, k):
            dists = np.min(
                np.sum((features[indices[:ci], np.newaxis] - features[np.newaxis, :]) ** 2, axis=2),
                axis=0,
            )
            probs = dists / dists.sum()
            indices[ci] = rng.choice(n_pixels, p=probs)
        centroids = features[indices].copy()

        labels = np.zeros(n_pixels, dtype=np.intp)
        for _ in range(max_iter):
            # Assign each pixel to the nearest centroid
            dists = np.sum(
                (features[:, np.newaxis, :] - centroids[np.newaxis, :, :]) ** 2,
                axis=2,
            )
            new_labels = np.argmin(dists, axis=1)
            if np.array_equal(new_labels, labels):
                break
            labels = new_labels
            # Recompute centroids
            for ci in range(k):
                members = features[labels == ci]
                if len(members) > 0:
                    centroids[ci] = members.mean(axis=0)

        # --- Build gradient stops from clusters -------------------------
        cluster_rgb: List[Tuple[int, int, int]] = []
        cluster_lum: List[float] = []
        for ci in range(k):
            members = flat[labels == ci]
            if len(members) == 0:
                continue
            mean_col = members.mean(axis=0)
            r, g, b = (int(max(0, min(255, c))) for c in mean_col)
            cluster_rgb.append((r, g, b))
            cluster_lum.append(
                0.2126 * r + 0.7152 * g + 0.0722 * b,
            )

        # Sort clusters from darkest to lightest
        order = np.argsort(cluster_lum)
        cluster_rgb = [cluster_rgb[i] for i in order]

        n_actual = len(cluster_rgb)
        stops: List["GradientStop"] = []
        for idx, (r, g, b) in enumerate(cluster_rgb):
            # Spread stops evenly across 0→1
            pos = idx / max(n_actual - 1, 1)
            stops.append(GradientStop(position=round(pos, 6), color=f"#{r:02X}{g:02X}{b:02X}FF"))

        # Guarantee endpoints
        stops[0] = GradientStop(position=0.0, color=stops[0].color)
        stops[-1] = GradientStop(position=1.0, color=stops[-1].color)

        return cls(
            type="gradient",
            gradient_stops=stops,
            stretch_min=0,
            stretch_max=65535,
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ColorMap":
        """Deserialise from dict."""
        ctype = data.get("type", "palette")
        entries = [ColorEntry.from_dict(e) for e in data.get("entries", [])]
        # Load gradient stops; fall back from legacy gradient_start/gradient_end if absent
        raw_stops = data.get("gradient_stops")
        if raw_stops is not None:
            gradient_stops = [GradientStop.from_dict(s) for s in raw_stops]
        else:
            gradient_stops = [
                GradientStop(0.0, data.get("gradient_start", "#000000")),
                GradientStop(1.0, data.get("gradient_end", "#FFFFFF")),
            ]
        stretch_min_raw = data.get("stretch_min")
        stretch_max_raw = data.get("stretch_max")
        display_min_raw = data.get("display_min")
        display_max_raw = data.get("display_max")
        return cls(
            type=ctype,
            entries=entries,
            gradient_stops=gradient_stops,
            stretch_min=int(stretch_min_raw) if stretch_min_raw is not None else None,
            stretch_max=int(stretch_max_raw) if stretch_max_raw is not None else None,
            display_min=float(display_min_raw) if display_min_raw is not None else None,
            display_max=float(display_max_raw) if display_max_raw is not None else None,
            unit=str(data.get("unit", "")),
            format_str=str(data.get("format_str", "{:.2f}")),
            scale=str(data.get("scale", "linear")),
            linked_entity_id=data.get("linked_entity_id") or None,
            linked_entity_type=str(data.get("linked_entity_type", "")),
        )


def format_display_value(color_map: "ColorMap", raw_value: int) -> str:
    """Map a raw 16-bit raster value to a human-readable display string.

    Uses the *display_min* / *display_max* fields of *color_map* to linearly
    (or logarithmically) interpolate the raw value into the real-world range,
    then formats it with *format_str* and appends *unit*.

    Falls back to the plain integer string when no display mapping is defined.

    Args:
        color_map: The :class:`ColorMap` carrying display mapping metadata.
        raw_value: 16-bit cell value to format.

    Returns:
        Formatted string such as ``"23.5 °C"`` or just ``"32767"``.
    """
    if color_map.display_min is None or color_map.display_max is None:
        return str(raw_value)

    s_min = color_map.stretch_min if color_map.stretch_min is not None else 0
    s_max = color_map.stretch_max if color_map.stretch_max is not None else 65535

    if s_max == s_min:
        t = 0.0
    else:
        t = max(0.0, min(1.0, (raw_value - s_min) / (s_max - s_min)))

    d_min = color_map.display_min
    d_max = color_map.display_max

    if color_map.scale == "log" and d_min > 0 and d_max > 0:
        import math

        display_val = math.exp(
            math.log(d_min) + t * (math.log(d_max) - math.log(d_min))
        )
    else:
        display_val = d_min + t * (d_max - d_min)

    try:
        formatted = color_map.format_str.format(display_val)
    except (ValueError, KeyError):
        formatted = f"{display_val:.2f}"

    return f"{formatted} {color_map.unit}".rstrip() if color_map.unit else formatted


def _hex_to_rgba(hex_color: str, alpha: int = 255) -> Tuple[int, int, int, int]:
    """Convert a hex colour string to an RGBA tuple.

    Args:
        hex_color: Colour in ``#RRGGBB`` or ``#RRGGBBAA`` format.
        alpha: Default alpha if not specified in hex.

    Returns:
        Tuple of (R, G, B, A) values in 0–255.

    """
    h = hex_color.lstrip("#")
    if len(h) == 8:
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), int(h[6:8], 16))
    if len(h) == 6:
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), alpha)
    return (128, 128, 128, alpha)


class MapDataBuffer:
    """16-bit raster data buffer for heatmap / data overlays.

    The buffer is stored as a 2-D ``numpy.ndarray`` with dtype ``uint16``,
    giving a range of 0–65 535.  Coordinates are **normalised** [0.0, 1.0]
    mapping to the underlying map image extent.

    For *color* mode layers an additional ``_rgba_data`` array of shape
    ``(H, W, 4)`` with dtype ``uint8`` holds the original RGBA pixels.
    When ``_rgba_data`` is present the uint16 ``_data`` array is an unused
    placeholder and :meth:`colorize` with ``color_map.type == "passthrough"``
    returns the RGBA data directly.

    Args:
        width: Buffer width in pixels.
        height: Buffer height in pixels.
        default_value: Initial fill value for all pixels.

    """

    def __init__(
        self,
        width: int,
        height: int,
        default_value: int = 0,
    ) -> None:
        if width <= 0 or height <= 0:
            raise ValueError(f"Invalid buffer dimensions: {width}×{height}")
        if not isinstance(default_value, int) or not (0 <= default_value <= 0xFFFF):
            raise ValueError(
                f"default_value must be an int in 0–65535, got {default_value!r}"
            )
        self._width = width
        self._height = height
        self._default_value = default_value
        self._data: np.ndarray = np.full(
            (height, width), default_value, dtype=np.uint16
        )
        self._rgba_data: Optional[np.ndarray] = None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def width(self) -> int:
        """Buffer width in pixels."""
        return self._width

    @property
    def height(self) -> int:
        """Buffer height in pixels."""
        return self._height

    @property
    def data(self) -> np.ndarray:
        """Raw numpy buffer (read-only access)."""
        return self._data

    @property
    def default_value(self) -> int:
        """The default fill value used at creation."""
        return self._default_value

    # ------------------------------------------------------------------
    # Coordinate helpers
    # ------------------------------------------------------------------

    def _norm_to_pixel(self, x_norm: float, y_norm: float) -> Tuple[int, int]:
        """Convert normalised [0, 1] coordinates to pixel indices.

        Args:
            x_norm: Horizontal position (0 = left, 1 = right).
            y_norm: Vertical position (0 = top, 1 = bottom).

        Returns:
            (col, row) clamped to buffer bounds.

        """
        # Map normalized coordinates [0,1] to pixel indices 0..width-1.
        # Use truncation after scaling by the full width/height so that
        # fractions like c/width map to column c (e.g. 3/4 -> col 3).
        # Clamp to bounds to handle the x_norm==1.0 case.
        try:
            col = int(x_norm * self._width)
        except Exception:
            col = 0
        try:
            row = int(y_norm * self._height)
        except Exception:
            row = 0
        col = max(0, min(col, self._width - 1))
        row = max(0, min(row, self._height - 1))
        return col, row

    # ------------------------------------------------------------------
    # Point access
    # ------------------------------------------------------------------

    def get_value_at(self, x_norm: float, y_norm: float) -> int:
        """Read the raster value at normalised coordinates.

        Args:
            x_norm: Horizontal position [0, 1].
            y_norm: Vertical position [0, 1].

        Returns:
            int: The 16-bit raster value.

        """
        col, row = self._norm_to_pixel(x_norm, y_norm)
        return int(self._data[row, col])

    def set_value_at(self, x_norm: float, y_norm: float, value: int) -> None:
        """Write a raster value at normalised coordinates.

        Args:
            x_norm: Horizontal position [0, 1].
            y_norm: Vertical position [0, 1].
            value: 16-bit value to write (clamped to 0–65535).

        """
        col, row = self._norm_to_pixel(x_norm, y_norm)
        self._data[row, col] = np.uint16(max(0, min(value, 65535)))

    # ------------------------------------------------------------------
    # Brush painting
    # ------------------------------------------------------------------

    @staticmethod
    def _apply_falloff_curve(t: "np.ndarray", curve: str) -> "np.ndarray":
        """Map linear ramp progress *t* through a shaped falloff curve.

        Args:
            t: Progress array in [0, 1] where 0 = outer edge, 1 = core.
            curve: One of ``"linear"``, ``"cosine"``, or ``"gaussian"``.

        Returns:
            Shaped strength array same shape as *t*, values in [0, 1].
        """
        if curve == "cosine":
            # S-shaped ease in/out: smooth transition at both ends
            return 0.5 - 0.5 * np.cos(np.pi * t)
        if curve == "gaussian":
            # Bell curve: tight, bright centre with rapid falloff toward edge
            return np.exp(-4.5 * (1.0 - t) ** 2)
        # Default: linear
        return t

    def paint_brush(
        self,
        center_x: float,
        center_y: float,
        radius_px: int,
        value: int,
        falloff: float = 0.0,
        falloff_curve: str = "cosine",
        stroke_before: "Optional[np.ndarray]" = None,
        stroke_strength_map: "Optional[np.ndarray]" = None,
    ) -> Tuple[int, int, int, int]:
        """Paint a circular brush stroke onto the buffer.

        Feathering model
        ----------------
        - ``falloff = 0.0`` — Hard circle: uniform *value* inside the
          radius, untouched outside.
        - ``falloff = 1.0`` — Full shaped ramp: full *value* at the
          centre, decaying to zero at the outer edge via *falloff_curve*.
        - ``0 < falloff < 1`` — Hard inner core of radius
          ``r * (1 - falloff)`` (full value), then a shaped ramp from
          the core boundary down to zero at the outer radius.

        Idempotent stroke mode
        ----------------------
        When both *stroke_before* and *stroke_strength_map* are supplied the
        method operates in idempotent stroke mode: each dab records the
        *maximum* strength it contributes per pixel, and the final pixel
        colour is always ``before * (1 - max_strength) + value * max_strength``.
        This prevents the feather zone from accumulating toward full opacity
        on slow, overlapping strokes.

        Args:
            center_x: Normalised X centre [0, 1].
            center_y: Normalised Y centre [0, 1].
            radius_px: Brush radius in **buffer pixels**.
            value: Value to paint.
            falloff: 0.0 = hard brush, 1.0 = full ramp.
            falloff_curve: Shape of the feather ramp — ``"linear"``,
                ``"cosine"`` (default), or ``"gaussian"``.
            stroke_before: Full-buffer snapshot at stroke start (uint16).
                Must be supplied together with *stroke_strength_map*.
            stroke_strength_map: Per-pixel maximum-strength accumulator
                (float32, same shape as buffer data).  Updated in-place.

        Returns:
            Dirty region as ``(min_col, min_row, max_col, max_row)``.

        """
        cx, cy = self._norm_to_pixel(center_x, center_y)
        r = max(1, radius_px)

        min_col = max(0, cx - r)
        max_col = min(self._width - 1, cx + r)
        min_row = max(0, cy - r)
        max_row = min(self._height - 1, cy + r)

        logger.debug(
            "paint_brush: center_px=(%d,%d) radius=%d value=%d "
            "falloff=%.2f curve=%s dirty=(%d,%d,%d,%d)",
            cx,
            cy,
            r,
            value,
            falloff,
            falloff_curve,
            min_col,
            min_row,
            max_col,
            max_row,
        )

        # Build pixel coordinate grids for the affected region
        rows = np.arange(min_row, max_row + 1)
        cols = np.arange(min_col, max_col + 1)
        cc, rr = np.meshgrid(cols, rows)

        dist = np.sqrt((cc - cx) ** 2 + (rr - cy) ** 2).astype(np.float32)
        mask = dist <= r

        if falloff > 0.0:
            # Hard-core + shaped-ramp feathering
            core_r = r * (1.0 - falloff)
            ramp_width = r - core_r  # == r * falloff

            # Linear progress through the feather zone: 0 at outer edge, 1 at core
            t_linear = np.clip(
                (r - dist) / max(ramp_width, 1e-6),
                0.0,
                1.0,
            ).astype(np.float32)

            # Apply the chosen curve to the ramp zone only; core stays at 1.0
            strength = np.where(
                dist <= core_r,
                np.float32(1.0),
                self._apply_falloff_curve(t_linear, falloff_curve),
            ).astype(np.float32)

            # Zero out anything outside the circle
            strength = strength * mask

            if stroke_before is not None and stroke_strength_map is not None:
                # --- Idempotent stroke mode ---
                region_before = stroke_before[
                    min_row : max_row + 1, min_col : max_col + 1
                ].astype(np.float32)
                cur_max = stroke_strength_map[min_row : max_row + 1, min_col : max_col + 1]
                new_max = np.maximum(cur_max, strength)
                stroke_strength_map[min_row : max_row + 1, min_col : max_col + 1] = new_max
                blended = region_before * (1.0 - new_max) + value * new_max
                self._data[min_row : max_row + 1, min_col : max_col + 1] = np.clip(
                    blended, 0, 65535
                ).astype(np.uint16)
            else:
                # --- Legacy accumulation mode (backward-compatible) ---
                region = self._data[
                    min_row : max_row + 1, min_col : max_col + 1
                ].astype(np.float32)
                blended = region * (1.0 - strength) + value * strength
                self._data[min_row : max_row + 1, min_col : max_col + 1] = np.clip(
                    blended, 0, 65535
                ).astype(np.uint16)
        else:
            self._data[min_row : max_row + 1, min_col : max_col + 1] = np.where(
                mask,
                np.uint16(max(0, min(value, 65535))),
                self._data[min_row : max_row + 1, min_col : max_col + 1],
            )

        return (min_col, min_row, max_col, max_row)

    # ------------------------------------------------------------------
    # Region snapshot (for undo)
    # ------------------------------------------------------------------

    def get_region(
        self, min_col: int, min_row: int, max_col: int, max_row: int
    ) -> np.ndarray:
        """Return a copy of a rectangular region.

        Args:
            min_col: Left column index.
            min_row: Top row index.
            max_col: Right column index (inclusive).
            max_row: Bottom row index (inclusive).

        Returns:
            numpy array copy of the region.

        """
        return self._data[min_row : max_row + 1, min_col : max_col + 1].copy()

    def set_region(self, min_col: int, min_row: int, region_data: np.ndarray) -> None:
        """Restore a rectangular region from a snapshot.

        Args:
            min_col: Left column index.
            min_row: Top row index.
            region_data: The data to write.

        """
        h, w = region_data.shape
        self._data[min_row : min_row + h, min_col : min_col + w] = region_data

    # ------------------------------------------------------------------
    # Colorisation
    # ------------------------------------------------------------------

    @staticmethod
    def _build_palette_lut(color_map: ColorMap) -> np.ndarray:
        """Build a uint16 → RGBA lookup table from palette entries.

        Returns:
            Array of shape ``(65536, 4)`` with dtype ``uint8``.
            Unmapped values default to ``(0, 0, 0, 0)`` (transparent).
        """
        lut = np.zeros((65536, 4), dtype=np.uint8)
        for entry in color_map.entries:
            r, g, b, a = _hex_to_rgba(entry.color)
            lut[entry.value] = [r, g, b, a]
        return lut

    def colorize(self, color_map: ColorMap) -> QImage:
        """Produce an RGBA ``QImage`` from the buffer using a colour map.

        Args:
            color_map: The colour mapping to apply.

        Returns:
            QImage in ARGB32 format, same dimensions as buffer.

        """
        logger.debug(
            "colorize: buffer=%dx%d color_map_type=%s entries=%d",
            self._width,
            self._height,
            color_map.type,
            len(color_map.entries) if color_map.type == "palette" else 0,
        )
        if color_map.type == "passthrough":
            if self._rgba_data is None:
                logger.warning("colorize: passthrough requested but no RGBA data; returning blank")
                blank = np.zeros((self._height, self._width, 4), dtype=np.uint8)
                image = QImage(
                    blank.data,
                    self._width,
                    self._height,
                    self._width * 4,
                    QImage.Format.Format_RGBA8888,
                )
                return image.copy()
            image = QImage(
                self._rgba_data.data,
                self._width,
                self._height,
                self._width * 4,
                QImage.Format.Format_RGBA8888,
            )
            return image.copy()

        if color_map.type == "palette":
            lut = self._build_palette_lut(color_map)
            rgba = lut[self._data]
        else:
            rgba = np.zeros((self._height, self._width, 4), dtype=np.uint8)
            # Gradient mode: multi-stop interpolation with optional stretch range
            stops = sorted(color_map.gradient_stops, key=lambda s: s.position)
            if len(stops) < 2:
                # Degenerate gradient — return transparent image rather than crashing
                return QImage(
                    self._width, self._height, QImage.Format.Format_RGBA8888
                )
            positions = np.array([s.position for s in stops], dtype=np.float32)
            rgba_stops = np.array(
                [_hex_to_rgba(s.color) for s in stops], dtype=np.float32
            )
            s_min = color_map.stretch_min if color_map.stretch_min is not None else 0
            s_max = (
                color_map.stretch_max if color_map.stretch_max is not None else 65535
            )
            t = np.clip(
                (self._data.astype(np.float32) - s_min) / max(s_max - s_min, 1),
                0.0,
                1.0,
            )
            for ch in range(4):
                rgba[:, :, ch] = np.interp(t, positions, rgba_stops[:, ch]).astype(
                    np.uint8
                )

        # QImage expects ARGB32 (B, G, R, A in memory on little-endian)
        # but Format_RGBA8888 reads R, G, B, A which matches our array
        image = QImage(
            rgba.data,
            self._width,
            self._height,
            self._width * 4,
            QImage.Format.Format_RGBA8888,
        )
        # Must copy — the numpy data would otherwise be garbage-collected
        return image.copy()

    # ------------------------------------------------------------------
    # Persistence (16-bit PNG via Pillow)
    # ------------------------------------------------------------------

    def save(self, path: str) -> None:
        """Save the buffer as a PNG.

        For color mode buffers (``_rgba_data`` is set) the file is written as
        an 8-bit RGBA PNG.  All other buffers are written as 16-bit grayscale.

        Args:
            path: File system path for the output PNG.

        """
        from PIL import Image

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        if self._rgba_data is not None:
            img = Image.fromarray(self._rgba_data, mode="RGBA")
        else:
            img = Image.fromarray(self._data)
        img.save(path)
        logger.info("Saved raster buffer %dx%d → %s", self._width, self._height, path)

    @classmethod
    def from_file(cls, path: str) -> "MapDataBuffer":
        """Load a PNG into a new buffer.

        For 8-bit RGB/RGBA images (color mode layers) the pixel data is stored
        in ``_rgba_data`` and ``colorize`` handles them via the ``"passthrough"``
        ColorMap type.  All other images (grayscale / 16-bit) are loaded as the
        standard uint16 ``_data`` array.

        Args:
            path: Path to a PNG (16-bit grayscale **or** 8-bit RGB/RGBA).

        Returns:
            MapDataBuffer populated with the file's pixel data.

        Raises:
            FileNotFoundError: If *path* does not exist.
            ValueError: If the image cannot be read.

        """
        from PIL import Image

        if not Path(path).exists():
            raise FileNotFoundError(f"Raster file not found: {path}")

        img = Image.open(path)

        # Color mode: 8-bit RGB or RGBA image → store as RGBA uint8
        if img.mode in ("RGB", "RGBA", "P"):
            rgba_img = img.convert("RGBA")
            rgba_arr = np.array(rgba_img, dtype=np.uint8)
            buf = cls(width=rgba_arr.shape[1], height=rgba_arr.shape[0], default_value=0)
            buf._rgba_data = rgba_arr
            return buf

        # Grayscale / 16-bit path (discrete / continuous modes)
        _16BIT_MODES = {"I;16", "I;16B", "I;16L", "I;16N"}
        arr = np.array(img)
        if img.mode not in _16BIT_MODES and arr.dtype != np.uint16:
            raise ValueError(
                f"Expected 16-bit grayscale image, got mode={img.mode!r} "
                f"dtype={arr.dtype}"
            )
        arr = arr.astype(np.uint16)
        if arr.ndim != 2:
            raise ValueError(f"Expected 2-D grayscale image, got shape {arr.shape}")

        buf = cls(width=arr.shape[1], height=arr.shape[0], default_value=0)
        buf._data = arr
        return buf

    # ------------------------------------------------------------------
    # Partial colorisation
    # ------------------------------------------------------------------

    def colorize_region(
        self,
        color_map: ColorMap,
        min_col: int,
        min_row: int,
        max_col: int,
        max_row: int,
    ) -> QImage:
        """Colourize a rectangular sub-region of the buffer.

        Args:
            color_map: Colour mapping to apply.
            min_col: Left column (inclusive).
            min_row: Top row (inclusive).
            max_col: Right column (inclusive).
            max_row: Bottom row (inclusive).

        Returns:
            QImage (RGBA8888) covering the requested region.

        """
        min_col = max(0, min_col)
        min_row = max(0, min_row)
        max_col = min(self._width - 1, max_col)
        max_row = min(self._height - 1, max_row)

        logger.debug(
            "colorize_region: region=(%d,%d,%d,%d) color_map_type=%s",
            min_col,
            min_row,
            max_col,
            max_row,
            color_map.type,
        )

        if color_map.type == "passthrough":
            if self._rgba_data is not None:
                region_rgba = self._rgba_data[
                    min_row : max_row + 1, min_col : max_col + 1
                ].copy()
            else:
                rh = max_row - min_row + 1
                rw = max_col - min_col + 1
                region_rgba = np.zeros((rh, rw, 4), dtype=np.uint8)
            rh, rw = region_rgba.shape[:2]
            image = QImage(region_rgba.data, rw, rh, rw * 4, QImage.Format.Format_RGBA8888)
            return image.copy()

        region = self._data[min_row : max_row + 1, min_col : max_col + 1]
        rh, rw = region.shape

        if color_map.type == "palette":
            lut = self._build_palette_lut(color_map)
            rgba = lut[region]
        else:
            rgba = np.zeros((rh, rw, 4), dtype=np.uint8)
            stops = sorted(color_map.gradient_stops, key=lambda s: s.position)
            positions = np.array([s.position for s in stops], dtype=np.float32)
            rgba_stops = np.array(
                [_hex_to_rgba(s.color) for s in stops], dtype=np.float32
            )
            s_min = color_map.stretch_min if color_map.stretch_min is not None else 0
            s_max = (
                color_map.stretch_max if color_map.stretch_max is not None else 65535
            )
            t = np.clip(
                (region.astype(np.float32) - s_min) / max(s_max - s_min, 1),
                0.0,
                1.0,
            )
            for ch in range(4):
                rgba[:, :, ch] = np.interp(t, positions, rgba_stops[:, ch]).astype(
                    np.uint8
                )

        image = QImage(rgba.data, rw, rh, rw * 4, QImage.Format.Format_RGBA8888)
        return image.copy()

    # ------------------------------------------------------------------
    # Bucket fill
    # ------------------------------------------------------------------

    def bucket_fill(self, value: int) -> None:
        """Fill the entire buffer with a single value.

        Args:
            value: 16-bit value to fill.

        """
        self._data[:] = np.uint16(max(0, min(value, 65535)))

    # ------------------------------------------------------------------
    # Flood fill
    # ------------------------------------------------------------------

    def flood_fill(
        self, x_norm: float, y_norm: float, value: int
    ) -> Tuple[int, int, int, int]:
        """Queue-based flood fill from a seed point.

        Replaces all connected pixels sharing the seed's value with
        *value*.  Uses 4-connectivity (no diagonals).

        Args:
            x_norm: Normalised X of seed [0, 1].
            y_norm: Normalised Y of seed [0, 1].
            value: Replacement value (0–65535).

        Returns:
            Dirty region ``(min_col, min_row, max_col, max_row)``.

        """
        col, row = self._norm_to_pixel(x_norm, y_norm)
        target = int(self._data[row, col])
        fill_val = np.uint16(max(0, min(value, 65535)))

        logger.debug(
            "flood_fill: seed=(%d,%d) target=%d fill_val=%d buffer=%dx%d",
            col,
            row,
            target,
            fill_val,
            self._width,
            self._height,
        )
        if target == fill_val:
            logger.debug("flood_fill: target==fill_val — no-op")
            return (col, row, col, row)

        min_c, max_c = col, col
        min_r, max_r = row, row

        visited = np.zeros((self._height, self._width), dtype=np.bool_)
        queue: deque[Tuple[int, int]] = deque([(col, row)])
        visited[row, col] = True

        while queue:
            c, r = queue.popleft()
            self._data[r, c] = fill_val
            min_c = min(min_c, c)
            max_c = max(max_c, c)
            min_r = min(min_r, r)
            max_r = max(max_r, r)

            for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nc, nr = c + dc, r + dr
                if (
                    0 <= nc < self._width
                    and 0 <= nr < self._height
                    and not visited[nr, nc]
                    and int(self._data[nr, nc]) == target
                ):
                    visited[nr, nc] = True
                    queue.append((nc, nr))

        logger.debug(
            "flood_fill: dirty=(%d,%d,%d,%d) pixels_changed=%d",
            min_c,
            min_r,
            max_c,
            max_r,
            int(np.sum(self._data[min_r : max_r + 1, min_c : max_c + 1] == fill_val)),
        )
        return (min_c, min_r, max_c, max_r)

    def paint_gradient(
        self,
        x0_norm: float,
        y0_norm: float,
        x1_norm: float,
        y1_norm: float,
        value_start: int,
        value_end: int,
        width_px: int = 0,
    ) -> Tuple[int, int, int, int]:
        """Paint a linear gradient between two normalised points.

        Args:
            x0_norm: Start X [0, 1].
            y0_norm: Start Y [0, 1].
            x1_norm: End X [0, 1].
            y1_norm: End Y [0, 1].
            value_start: Value at start point.
            value_end: Value at end point.
            width_px: Perpendicular half-width in pixels.  0 means the
                gradient covers the entire buffer projection (no width
                constraint).

        Returns:
            Dirty region ``(min_col, min_row, max_col, max_row)``.

        """
        c0, r0 = self._norm_to_pixel(x0_norm, y0_norm)
        c1, r1 = self._norm_to_pixel(x1_norm, y1_norm)

        logger.debug(
            "paint_gradient: px0=(%d,%d) px1=(%d,%d) values=%d→%d width_px=%d",
            c0,
            r0,
            c1,
            r1,
            value_start,
            value_end,
            width_px,
        )

        dx = float(c1 - c0)
        dy = float(r1 - r0)
        length = max(1.0, np.sqrt(dx * dx + dy * dy))

        # Determine affected region
        if width_px > 0:
            min_col = max(0, min(c0, c1) - width_px)
            max_col = min(self._width - 1, max(c0, c1) + width_px)
            min_row = max(0, min(r0, r1) - width_px)
            max_row = min(self._height - 1, max(r0, r1) + width_px)
        else:
            min_col, max_col = 0, self._width - 1
            min_row, max_row = 0, self._height - 1

        rows = np.arange(min_row, max_row + 1)
        cols = np.arange(min_col, max_col + 1)
        cc, rr = np.meshgrid(cols, rows)

        # Project onto gradient axis: t ∈ [0, 1]
        t = ((cc - c0) * dx + (rr - r0) * dy) / (length * length)
        t = np.clip(t, 0.0, 1.0)

        # Perpendicular distance
        if width_px > 0:
            perp = np.abs((cc - c0) * (-dy) + (rr - r0) * dx) / length
            mask = perp <= width_px
        else:
            mask = np.ones_like(t, dtype=bool)

        vals = np.clip(
            value_start + (value_end - value_start) * t, 0, 65535
        ).astype(np.uint16)
        region = self._data[min_row : max_row + 1, min_col : max_col + 1]
        self._data[min_row : max_row + 1, min_col : max_col + 1] = np.where(
            mask, vals, region
        )

        logger.debug(
            "paint_gradient: dirty=(%d,%d,%d,%d)",
            min_col,
            min_row,
            max_col,
            max_row,
        )
        return (min_col, min_row, max_col, max_row)

    def paint_radial_gradient(
        self,
        cx_norm: float,
        cy_norm: float,
        radius_norm: float,
        value_center: int,
        value_edge: int,
    ) -> Tuple[int, int, int, int]:
        """Paint a radial gradient from center outward.

        Args:
            cx_norm: Centre X [0, 1].
            cy_norm: Centre Y [0, 1].
            radius_norm: Radius as fraction of min(width, height).
            value_center: Value at the centre.
            value_edge: Value at the edge (and beyond).

        Returns:
            Dirty region ``(min_col, min_row, max_col, max_row)``.
        """
        cx, cy = self._norm_to_pixel(cx_norm, cy_norm)
        radius_px = int(radius_norm * min(self._width, self._height))
        if radius_px < 1:
            radius_px = 1

        min_col = max(0, cx - radius_px)
        max_col = min(self._width - 1, cx + radius_px)
        min_row = max(0, cy - radius_px)
        max_row = min(self._height - 1, cy + radius_px)

        rows = np.arange(min_row, max_row + 1)
        cols = np.arange(min_col, max_col + 1)
        cc, rr = np.meshgrid(cols, rows)

        dist = np.sqrt((cc - cx) ** 2 + (rr - cy) ** 2) / float(radius_px)
        t = np.clip(dist, 0.0, 1.0)

        mask = dist <= 1.0
        vals = np.clip(
            value_center + (value_edge - value_center) * t, 0, 65535
        ).astype(np.uint16)
        region = self._data[min_row : max_row + 1, min_col : max_col + 1]
        self._data[min_row : max_row + 1, min_col : max_col + 1] = np.where(
            mask, vals, region
        )

        logger.debug(
            "paint_radial_gradient: center_px=(%d,%d) radius=%d dirty=(%d,%d,%d,%d)",
            cx,
            cy,
            radius_px,
            min_col,
            min_row,
            max_col,
            max_row,
        )
        return (min_col, min_row, max_col, max_row)

    def paint_reflected_gradient(
        self,
        x0_norm: float,
        y0_norm: float,
        x1_norm: float,
        y1_norm: float,
        value_center: int,
        value_edge: int,
        width_px: int = 0,
    ) -> Tuple[int, int, int, int]:
        """Paint a reflected (symmetric) gradient centred on the drag axis.

        The gradient goes *value_center* at the drag axis and *value_edge*
        at both perpendicular edges.

        Args:
            x0_norm: Start X [0, 1].
            y0_norm: Start Y [0, 1].
            x1_norm: End X [0, 1].
            y1_norm: End Y [0, 1].
            value_center: Value at the gradient axis.
            value_edge: Value at the perpendicular edges.
            width_px: Half-width in pixels (perpendicular).  0 = full buffer.

        Returns:
            Dirty region ``(min_col, min_row, max_col, max_row)``.
        """
        c0, r0 = self._norm_to_pixel(x0_norm, y0_norm)
        c1, r1 = self._norm_to_pixel(x1_norm, y1_norm)

        dx = float(c1 - c0)
        dy = float(r1 - r0)
        length = max(1.0, np.sqrt(dx * dx + dy * dy))
        half_width = length / 2.0 if width_px <= 0 else float(width_px)
        half_width = max(1.0, half_width)

        if width_px > 0:
            min_col = max(0, min(c0, c1) - width_px)
            max_col = min(self._width - 1, max(c0, c1) + width_px)
            min_row = max(0, min(r0, r1) - width_px)
            max_row = min(self._height - 1, max(r0, r1) + width_px)
        else:
            min_col, max_col = 0, self._width - 1
            min_row, max_row = 0, self._height - 1

        rows = np.arange(min_row, max_row + 1)
        cols = np.arange(min_col, max_col + 1)
        cc, rr = np.meshgrid(cols, rows)

        perp = np.abs((cc - c0) * (-dy) + (rr - r0) * dx) / length
        t = np.clip(perp / half_width, 0.0, 1.0)

        if width_px > 0:
            mask: np.ndarray = perp <= half_width
        else:
            mask = np.ones_like(t, dtype=bool)

        vals = np.clip(
            value_center + (value_edge - value_center) * t, 0, 65535
        ).astype(np.uint16)
        region = self._data[min_row : max_row + 1, min_col : max_col + 1]
        self._data[min_row : max_row + 1, min_col : max_col + 1] = np.where(
            mask, vals, region
        )

        logger.debug(
            "paint_reflected_gradient: p0=(%d,%d) p1=(%d,%d) half_w=%.1f "
            "dirty=(%d,%d,%d,%d)",
            c0,
            r0,
            c1,
            r1,
            half_width,
            min_col,
            min_row,
            max_col,
            max_row,
        )
        return (min_col, min_row, max_col, max_row)

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def compute_coverage_stats(
        self,
        color_map: "ColorMap",
        value_entity_map: Optional[Dict[str, Any]] = None,
        name_map: Optional[Dict[str, str]] = None,
    ) -> "CoverageStats":
        """Compute pixel coverage statistics for this raster buffer.

        For discrete (palette) colour maps, returns per-class pixel counts
        and percentages.  For continuous (gradient) colour maps, returns a
        32-bucket histogram and basic descriptive statistics (min, max,
        mean, median) computed over non-zero pixels.

        Args:
            color_map: The colour map that describes this layer's type and
                palette entries.
            value_entity_map: Optional value→entity mapping dict.  Currently
                unused in computation but reserved for future label lookup.
            name_map: Optional cache of resolved entity/event names keyed by ID.

        Returns:
            A :class:`CoverageStats` instance populated with statistics
            appropriate for the colour map type.
        """
        total = self._width * self._height
        flat = self._data.flatten()

        if color_map.type == "palette":
            counts = np.bincount(flat.astype(np.int64), minlength=65536)
            classes: List[ClassStat] = []
            covered_values: set = set()

            for entry in color_map.entries:
                v = entry.value
                covered_values.add(v)
                px = int(counts[v]) if v < len(counts) else 0
                pct = (px / total * 100.0) if total > 0 else 0.0

                # Precedence: Entity/Event Name > VEM Label > Palette Label > UUID > Value Fallback
                # Build VEM label lookup once (value_entity_map may be a dict or None)
                vm = normalize_value_entity_map(value_entity_map or {})
                label_by_value: Dict[int, str] = {}
                for m in vm.get("mappings", []):
                    val = m.get("value")
                    if val is None:
                        continue
                    lbl = m.get("label")
                    if lbl:
                        try:
                            label_by_value[int(val)] = lbl
                        except (ValueError, TypeError):
                            pass

                entity_id = entry.entity_id
                if entity_id and name_map and entity_id in name_map:
                    label = name_map[entity_id]
                elif v in label_by_value:
                    label = label_by_value[v]
                elif entry.label:
                    label = entry.label
                elif entity_id:
                    label = entity_id
                else:
                    label = f"Value {v}"

                classes.append(
                    ClassStat(
                        value=v,
                        label=label,
                        pixel_count=px,
                        percentage=round(pct, 2),
                    )
                )

            # Add "No data" entry for value=0 if it has pixels and isn't covered
            if 0 not in covered_values:
                zero_px = int(counts[0]) if len(counts) > 0 else 0
                if zero_px > 0:
                    pct = zero_px / total * 100.0 if total > 0 else 0.0
                    classes.append(
                        ClassStat(
                            value=0,
                            label="No data",
                            pixel_count=zero_px,
                            percentage=round(pct, 2),
                        )
                    )

            classes.sort(key=lambda s: s.pixel_count, reverse=True)
            return CoverageStats(
                mode="discrete",
                total_pixels=total,
                classes=classes,
            )
        else:
            # Continuous / gradient
            hist_counts, edges = np.histogram(
                flat.astype(np.float64), bins=32, range=(0, 65535)
            )
            non_zero = flat[flat > 0].astype(np.float64)
            if len(non_zero) > 0:
                min_val: Optional[float] = float(non_zero.min())
                max_val: Optional[float] = float(non_zero.max())
                mean_val: Optional[float] = float(non_zero.mean())
                median_val: Optional[float] = float(np.median(non_zero))
            else:
                min_val = max_val = mean_val = median_val = None
            return CoverageStats(
                mode="continuous",
                total_pixels=total,
                histogram_counts=[int(c) for c in hist_counts],
                histogram_edges=[float(e) for e in edges],
                min_val=min_val,
                max_val=max_val,
                mean_val=mean_val,
                median_val=median_val,
            )


# ---------------------------------------------------------------------------
# Module-level spatial query helper (Feature D)
# ---------------------------------------------------------------------------


def compute_spatial_query(
    arrays: List[np.ndarray],
    conditions: List[Dict[str, Any]],
) -> np.ndarray:
    """Compute a boolean mask from multi-layer conditions.

    Args:
        arrays: List of 2-D uint16 arrays (all same shape), indexed by
            condition order.
        conditions: List of dicts, each with:

            - ``"index"`` (int) — which array in *arrays* to use (0-based).
            - ``"op"`` (str) — one of ``"eq"``, ``"neq"``, ``"gt"``,
              ``"lt"``, ``"gte"``, ``"lte"``, ``"between"``.
            - ``"value"`` (int) — threshold (for all ops except ``"between"``).
            - ``"min"`` / ``"max"`` (int) — range bounds for ``"between"``.

    Returns:
        Boolean numpy array of the same shape as the input arrays; ``True``
        means *all* conditions are satisfied for that pixel.

    Raises:
        ValueError: If arrays have different shapes, are not 2-D, or if a
            condition references an invalid index.
    """
    if not arrays:
        raise ValueError("arrays must not be empty")

    ref_shape = arrays[0].shape
    for i, arr in enumerate(arrays):
        if arr.ndim != 2:
            raise ValueError(f"arrays[{i}] is not 2-D (shape={arr.shape})")
        if arr.shape != ref_shape:
            raise ValueError(
                f"Shape mismatch: arrays[0] is {ref_shape} "
                f"but arrays[{i}] is {arr.shape}"
            )

    mask = np.ones(ref_shape, dtype=np.bool_)

    for cond in conditions:
        idx = int(cond["index"])
        if idx < 0 or idx >= len(arrays):
            raise ValueError(
                f"Condition references index {idx} but only {len(arrays)} "
                "arrays provided"
            )
        arr = arrays[idx].astype(np.int32)
        op = str(cond["op"])

        if op == "eq":
            mask &= arr == int(cond["value"])
        elif op == "neq":
            mask &= arr != int(cond["value"])
        elif op == "gt":
            mask &= arr > int(cond["value"])
        elif op == "lt":
            mask &= arr < int(cond["value"])
        elif op == "gte":
            mask &= arr >= int(cond["value"])
        elif op == "lte":
            mask &= arr <= int(cond["value"])
        elif op == "between":
            lo = int(cond["min"])
            hi = int(cond["max"])
            mask &= (arr >= lo) & (arr <= hi)
        else:
            raise ValueError(f"Unknown operator: {op!r}")

    return mask
