"""Normalized polygon geometry and the adapter for polygon overlays."""

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, TypedDict

if TYPE_CHECKING:
    from shapely.geometry import Polygon
    from shapely.geometry.base import BaseGeometry

Point = tuple[float, float]
Ring = list[dict[str, float]]
MIN_REGION_AREA = 1e-12
MIN_REGION_VERTICES = 3


class RegionPayload(TypedDict):
    """Stored region with at least one interior ring."""

    outer: Ring
    holes: list[Ring]


Geometry = Ring | RegionPayload


def geometry_rings(geometry: Geometry) -> tuple[Ring, ...]:
    """Return the outer ring followed by holes, or the points of an open path."""
    if isinstance(geometry, list):
        return (geometry,)
    return (geometry["outer"], *geometry["holes"])


def copy_geometry(geometry: Geometry) -> Geometry:
    """Decode independently owned coordinate lists from a snapshot."""
    outer, *holes = geometry_rings(geometry)
    result = [dict(point) for point in outer]
    if not holes:
        return result
    return {
        "outer": result,
        "holes": [[dict(point) for point in ring] for ring in holes],
    }


def ring_points(ring: Ring) -> tuple[Point, ...]:
    """Convert serialized coordinates to numeric pairs."""
    return tuple((float(point["x"]), float(point["y"])) for point in ring)


def signed_area(points: tuple[Point, ...]) -> float:
    """Return signed area, using a local origin to retain small features."""
    if not points:
        return 0.0
    ox, oy = points[0]
    return (
        math.fsum(
            (x1 - ox) * (y2 - oy) - (x2 - ox) * (y1 - oy)
            for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1])
        )
        / 2
    )


@dataclass(frozen=True)
class RegionPolygon:
    """One connected filled polygon with independent interior exclusions."""

    outer: tuple[Point, ...]
    holes: tuple[tuple[Point, ...], ...] = ()

    @classmethod
    def from_geometry(cls, geometry: Geometry) -> "RegionPolygon":
        """Read either historical coordinate lists or an explicit polygon."""
        outer, *holes = map(ring_points, geometry_rings(geometry))
        return cls(_unclosed(outer), tuple(map(_unclosed, holes)))

    def to_geometry(self) -> Geometry:
        """Encode with implicit closure and preserve the old hole-free format."""

        def encode(ring: tuple[Point, ...]) -> Ring:
            return [{"x": x, "y": y} for x, y in ring]

        outer = encode(self.outer)
        if not self.holes:
            return outer
        return {"outer": outer, "holes": [encode(ring) for ring in self.holes]}

    @property
    def area(self) -> float:
        """Return filled area in normalized coordinates."""
        return abs(signed_area(self.outer)) - sum(
            abs(signed_area(ring)) for ring in self.holes
        )

    def perimeter(self, width: float, height: float) -> float:
        """Measure the outside border and all hole rims."""
        return math.fsum(
            math.hypot((x2 - x1) * width, (y2 - y1) * height)
            for ring in (self.outer, *self.holes)
            for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1])
        )

    def validated(self) -> "Polygon":
        """Construct a GEOS polygon or raise a creator-facing validation error."""
        from shapely import is_valid_reason
        from shapely.geometry import Polygon

        for ring in (self.outer, *self.holes):
            _validate_ring(ring)
        shape = Polygon(self.outer, self.holes)
        if not shape.is_valid:
            raise ValueError(f"The outline is invalid ({is_valid_reason(shape)}).")
        rings = (shape.exterior, *shape.interiors)
        if any(
            first.intersects(second)
            for i, first in enumerate(rings)
            for second in rings[i + 1 :]
        ):
            raise ValueError("Hole rims must not touch each other or the outer border.")
        if self.area <= MIN_REGION_AREA:
            raise ValueError("The region has too little filled area to save.")
        return shape


def _unclosed(points: tuple[Point, ...]) -> tuple[Point, ...]:
    if len(points) > 1 and points[-1] == points[0]:
        return points[:-1]
    return points


def _validate_ring(ring: tuple[Point, ...]) -> None:
    if len(set(ring)) < MIN_REGION_VERTICES or len(set(ring)) != len(ring):
        raise ValueError("Each ring needs at least three distinct vertices.")
    if any(not (0 <= x <= 1 and 0 <= y <= 1) for x, y in ring):
        raise ValueError("Geometry coordinates must be finite and between 0 and 1.")


def feature_anchor(geometry: Geometry) -> Point:
    """Keep the vertex mean unless a holed region needs an interior anchor."""
    outer = geometry_rings(geometry)[0]
    if not outer:
        raise ValueError("Geometry cannot be empty.")
    mean = (
        sum(float(point["x"]) for point in outer) / len(outer),
        sum(float(point["y"]) for point in outer) / len(outer),
    )
    if isinstance(geometry, list) or not geometry["holes"]:
        return mean
    from shapely.geometry import Point as GeosPoint

    shape = RegionPolygon.from_geometry(geometry).validated()
    if shape.contains(GeosPoint(*mean)):
        return mean
    point = shape.representative_point()
    return (float(point.x), float(point.y))


@dataclass(frozen=True)
class CutResult:
    """All surviving polygon parts and a reason when the draft cannot use them."""

    polygons: tuple[RegionPolygon, ...]
    status: Literal["ready", "unchanged", "empty", "split", "invalid"]
    explanation: str = ""


def cut_region(target: RegionPolygon, cutter: RegionPolygon) -> CutResult:
    """Subtract the cutter's filled area without changing either operand."""
    from shapely.errors import GEOSException
    from shapely.geometry import GeometryCollection, MultiPolygon, Polygon

    try:
        original = target.validated()
        result = original.difference(cutter.validated())
        if result.equals(original):
            return CutResult((target,), "unchanged", "No area removed.")
        if result.is_empty:
            return CutResult((), "empty", "The cut removes the entire region.")
        parts: tuple[BaseGeometry, ...]
        if isinstance(result, Polygon):
            parts = (result,)
        elif isinstance(result, (MultiPolygon, GeometryCollection)):
            parts = tuple(result.geoms)
        else:
            parts = ()
        polygons = tuple(
            RegionPolygon(
                _unclosed(tuple((x, y) for x, y in part.exterior.coords)),
                tuple(
                    _unclosed(tuple((x, y) for x, y in ring.coords))
                    for ring in part.interiors
                ),
            )
            for part in parts
            if isinstance(part, Polygon)
        )
        if not polygons:
            return CutResult((), "empty", "The cut removes the entire region.")
        if len(polygons) > 1:
            return CutResult(
                polygons, "split", "The cut splits the region into pieces."
            )
        try:
            polygons[0].validated()
        except ValueError as exc:
            return CutResult(polygons, "invalid", str(exc))
        return CutResult(polygons, "ready")
    except (ValueError, GEOSException) as exc:
        return CutResult((), "invalid", str(exc))
