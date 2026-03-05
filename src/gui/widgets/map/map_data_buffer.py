"""Map Data Buffer — 16-bit raster data layer.

Wraps a ``numpy.ndarray`` (dtype ``uint16``) for in-memory raster
editing.  Provides normalised-coordinate access, brush painting,
palette-based colorisation, and 16-bit PNG persistence via Pillow.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
from PySide6.QtGui import QImage

logger = logging.getLogger(__name__)


@dataclass
class ColorEntry:
    """A single value → colour mapping for discrete palettes.

    Attributes:
        value: The 16-bit raster value.
        color: Hex colour string, e.g. ``"#88C070"``.

    """

    value: int
    color: str

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to JSON-friendly dict."""
        return {"value": self.value, "color": self.color}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ColorEntry":
        """Deserialise from dict."""
        return cls(value=int(data["value"]), color=str(data["color"]))


@dataclass
class ColorMap:
    """Colour look-up table for raster visualisation.

    Supports two modes:

    * **palette** — explicit value→colour list (discrete layers).
    * **gradient** — two-colour linear ramp across the full 0–65535 range.

    Attributes:
        type: ``"palette"`` or ``"gradient"``.
        entries: Colour entries (used when *type* is ``"palette"``).
        gradient_start: Hex colour for value 0 (gradient mode).
        gradient_end: Hex colour for value 65535 (gradient mode).

    """

    type: str = "palette"
    entries: List[ColorEntry] = field(default_factory=list)
    gradient_start: str = "#000000"
    gradient_end: str = "#FFFFFF"

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to JSON-friendly dict."""
        d: Dict[str, Any] = {"type": self.type}
        if self.type == "palette":
            d["entries"] = [e.to_dict() for e in self.entries]
        else:
            d["gradient_start"] = self.gradient_start
            d["gradient_end"] = self.gradient_end
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ColorMap":
        """Deserialise from dict."""
        ctype = data.get("type", "palette")
        entries = [ColorEntry.from_dict(e) for e in data.get("entries", [])]
        return cls(
            type=ctype,
            entries=entries,
            gradient_start=data.get("gradient_start", "#000000"),
            gradient_end=data.get("gradient_end", "#FFFFFF"),
        )


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
        self._width = width
        self._height = height
        self._default_value = default_value
        self._data: np.ndarray = np.full(
            (height, width), default_value, dtype=np.uint16
        )

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
        col = int(round(x_norm * (self._width - 1)))
        row = int(round(y_norm * (self._height - 1)))
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

    def paint_brush(
        self,
        center_x: float,
        center_y: float,
        radius_px: int,
        value: int,
        falloff: float = 0.0,
    ) -> Tuple[int, int, int, int]:
        """Paint a circular brush stroke onto the buffer.

        Args:
            center_x: Normalised X centre [0, 1].
            center_y: Normalised Y centre [0, 1].
            radius_px: Brush radius in **buffer pixels**.
            value: Value to paint.
            falloff: 0.0 = hard brush (no falloff), 1.0 = full linear falloff.

        Returns:
            Dirty region as ``(min_col, min_row, max_col, max_row)``.

        """
        cx, cy = self._norm_to_pixel(center_x, center_y)
        r = max(1, radius_px)

        min_col = max(0, cx - r)
        max_col = min(self._width - 1, cx + r)
        min_row = max(0, cy - r)
        max_row = min(self._height - 1, cy + r)

        # Build pixel coordinate grids for the affected region
        rows = np.arange(min_row, max_row + 1)
        cols = np.arange(min_col, max_col + 1)
        cc, rr = np.meshgrid(cols, rows)

        dist = np.sqrt((cc - cx) ** 2 + (rr - cy) ** 2).astype(np.float32)
        mask = dist <= r

        if falloff > 0.0:
            # Linear falloff: full value at centre, 0 at radius edge
            strength = np.clip(1.0 - (dist / r) * falloff, 0.0, 1.0)
            blended = (
                self._data[min_row : max_row + 1, min_col : max_col + 1].astype(
                    np.float32
                )
                * (1.0 - strength * mask)
                + value * strength * mask
            )
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

    def colorize(self, color_map: ColorMap) -> QImage:
        """Produce an RGBA ``QImage`` from the buffer using a colour map.

        Args:
            color_map: The colour mapping to apply.

        Returns:
            QImage in ARGB32 format, same dimensions as buffer.

        """
        rgba = np.zeros((self._height, self._width, 4), dtype=np.uint8)

        if color_map.type == "palette":
            for entry in color_map.entries:
                r, g, b, a = _hex_to_rgba(entry.color)
                mask = self._data == entry.value
                rgba[mask] = [r, g, b, a]
        else:
            # Gradient mode: linear interpolation across 0–65535
            sr, sg, sb, sa = _hex_to_rgba(color_map.gradient_start)
            er, eg, eb, ea = _hex_to_rgba(color_map.gradient_end)
            t = self._data.astype(np.float32) / 65535.0
            rgba[:, :, 0] = (sr + (er - sr) * t).astype(np.uint8)
            rgba[:, :, 1] = (sg + (eg - sg) * t).astype(np.uint8)
            rgba[:, :, 2] = (sb + (eb - sb) * t).astype(np.uint8)
            rgba[:, :, 3] = (sa + (ea - sa) * t).astype(np.uint8)

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
        """Save the buffer as a 16-bit grayscale PNG.

        Args:
            path: File system path for the output PNG.

        """
        from PIL import Image

        img = Image.fromarray(self._data)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        img.save(path)
        logger.info("Saved raster buffer %dx%d → %s", self._width, self._height, path)

    @classmethod
    def from_file(cls, path: str) -> "MapDataBuffer":
        """Load a 16-bit PNG into a new buffer.

        Args:
            path: Path to a 16-bit grayscale PNG.

        Returns:
            MapDataBuffer populated with the file's pixel data.

        Raises:
            FileNotFoundError: If *path* does not exist.
            ValueError: If the image cannot be read as 16-bit.

        """
        from PIL import Image

        if not Path(path).exists():
            raise FileNotFoundError(f"Raster file not found: {path}")

        img = Image.open(path)
        arr = np.array(img, dtype=np.uint16)
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

        region = self._data[min_row : max_row + 1, min_col : max_col + 1]
        rh, rw = region.shape
        rgba = np.zeros((rh, rw, 4), dtype=np.uint8)

        if color_map.type == "palette":
            for entry in color_map.entries:
                r, g, b, a = _hex_to_rgba(entry.color)
                mask = region == entry.value
                rgba[mask] = [r, g, b, a]
        else:
            sr, sg, sb, sa = _hex_to_rgba(color_map.gradient_start)
            er, eg, eb, ea = _hex_to_rgba(color_map.gradient_end)
            t = region.astype(np.float32) / 65535.0
            rgba[:, :, 0] = (sr + (er - sr) * t).astype(np.uint8)
            rgba[:, :, 1] = (sg + (eg - sg) * t).astype(np.uint8)
            rgba[:, :, 2] = (sb + (eb - sb) * t).astype(np.uint8)
            rgba[:, :, 3] = (sa + (ea - sa) * t).astype(np.uint8)

        image = QImage(
            rgba.data, rw, rh, rw * 4, QImage.Format.Format_RGBA8888
        )
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

        if target == fill_val:
            return (col, row, col, row)

        min_c, max_c = col, col
        min_r, max_r = row, row

        visited = np.zeros((self._height, self._width), dtype=np.bool_)
        queue: list[Tuple[int, int]] = [(col, row)]
        visited[row, col] = True

        while queue:
            c, r = queue.pop()
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

        return (min_c, min_r, max_c, max_r)

    # ------------------------------------------------------------------
    # Gradient paint
    # ------------------------------------------------------------------

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

        vals = (value_start + (value_end - value_start) * t).astype(np.uint16)
        region = self._data[min_row : max_row + 1, min_col : max_col + 1]
        self._data[min_row : max_row + 1, min_col : max_col + 1] = np.where(
            mask, vals, region
        )

        return (min_col, min_row, max_col, max_row)
