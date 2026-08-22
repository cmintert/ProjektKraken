"""Pure geometry primitives for deterministic map-context reasoning.

Coordinates are normalized map coordinates.  Callers provide scale factors so
distance calculations respect the map image's aspect ratio or real dimensions.
The module intentionally has no Qt, repository, or presentation dependencies.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal, Sequence

Point = tuple[float, float]
GeometryKind = Literal["point", "path", "region"]
RelationKind = Literal[
    "separate", "touches", "crosses", "inside", "contains", "overlaps"
]
_DEGENERATE_SEGMENT_LENGTH_SQUARED = 1e-24
_MIN_DISTINCT_PATH_POINTS = 2
_MIN_REGION_AREA = 1e-12


@dataclass(frozen=True)
class SpatialGeometry:
    """A validated point, open path, or closed region."""

    kind: GeometryKind
    points: tuple[Point, ...]

    @classmethod
    def from_feature(
        cls,
        feature_type: str,
        x: float,
        y: float,
        geometry: Sequence[dict[str, float]] | None,
    ) -> SpatialGeometry | None:
        """Convert stored feature data, rejecting malformed extended geometry."""
        if feature_type == "point":
            point = _finite_point((x, y))
            return (
                cls("point", (point,))
                if point is not None and _in_normalized_bounds(point)
                else None
            )
        if feature_type not in {"path", "region"} or geometry is None:
            return None
        minimum = 2 if feature_type == "path" else 3
        if len(geometry) < minimum:
            return None
        points: list[Point] = []
        for raw in geometry:
            try:
                point = _finite_point((float(raw["x"]), float(raw["y"])))
            except (KeyError, TypeError, ValueError):
                return None
            if point is None:
                return None
            if not _in_normalized_bounds(point):
                return None
            points.append(point)
        if (
            feature_type == "path"
            and len(set(points)) < _MIN_DISTINCT_PATH_POINTS
        ):
            return None
        if feature_type == "region" and abs(_signed_area(points)) <= _MIN_REGION_AREA:
            return None
        return cls(feature_type, tuple(points))  # type: ignore[arg-type]


@dataclass(frozen=True)
class GeometryMetric:
    """Axis scales and contact tolerance in the resulting distance units."""

    x_scale: float = 1.0
    y_scale: float = 1.0
    tolerance: float = 1e-9


@dataclass(frozen=True)
class GeometryRelation:
    """Directed topological and distance relation from source to target."""

    kind: RelationKind
    distance: float
    source_point: Point
    target_point: Point


def relate_geometries(
    source: SpatialGeometry,
    target: SpatialGeometry,
    metric: GeometryMetric = GeometryMetric(),
) -> GeometryRelation:
    """Return the directed relation between two validated geometries."""
    scaled_source = _scale_geometry(source, metric)
    scaled_target = _scale_geometry(target, metric)
    kind, source_point, target_point = _classify(
        scaled_source, scaled_target, metric.tolerance
    )
    distance = _distance(source_point, target_point)
    return GeometryRelation(
        kind=kind,
        distance=distance,
        source_point=_unscale_point(source_point, metric),
        target_point=_unscale_point(target_point, metric),
    )


def _classify(
    source: SpatialGeometry, target: SpatialGeometry, tolerance: float
) -> tuple[RelationKind, Point, Point]:
    if source.kind == "point":
        return _classify_point(source.points[0], target, tolerance)
    if target.kind == "point":
        inverse_kind, target_point, source_point = _classify_point(
            target.points[0], source, tolerance
        )
        return _inverse_kind(inverse_kind), source_point, target_point
    if source.kind == "path" and target.kind == "path":
        return _classify_path_path(source, target, tolerance)
    if source.kind == "path" and target.kind == "region":
        return _classify_path_region(source, target, tolerance)
    if source.kind == "region" and target.kind == "path":
        inverse_kind, target_point, source_point = _classify_path_region(
            target, source, tolerance
        )
        return _inverse_kind(inverse_kind), source_point, target_point
    return _classify_region_region(source, target, tolerance)


def _classify_point(
    point: Point, target: SpatialGeometry, tolerance: float
) -> tuple[RelationKind, Point, Point]:
    if target.kind == "point":
        distance = _distance(point, target.points[0])
        kind: RelationKind = "overlaps" if distance <= tolerance else "separate"
        return kind, point, target.points[0]
    closest, distance = _closest_point_on_segments(point, _segments(target))
    if target.kind == "path":
        kind = "touches" if distance <= tolerance else "separate"
        return kind, point, closest
    location = _point_in_polygon(point, target.points, tolerance)
    if location == "boundary":
        return "touches", point, closest
    if location == "inside":
        return "inside", point, point
    return "separate", point, closest


def _classify_path_path(
    source: SpatialGeometry, target: SpatialGeometry, tolerance: float
) -> tuple[RelationKind, Point, Point]:
    intersections = _segment_intersections(
        _segments(source), _segments(target), tolerance
    )
    if intersections:
        point, proper, overlap = intersections[0]
        if any(item[2] for item in intersections):
            return "overlaps", point, point
        if any(item[1] for item in intersections):
            return "crosses", point, point
        return "touches", point, point
    source_point, target_point = _closest_between_segments(
        _segments(source), _segments(target)
    )
    if _distance(source_point, target_point) <= tolerance:
        return "touches", source_point, target_point
    return "separate", source_point, target_point


def _classify_path_region(
    path: SpatialGeometry, region: SpatialGeometry, tolerance: float
) -> tuple[RelationKind, Point, Point]:
    locations = [
        _point_in_polygon(point, region.points, tolerance) for point in path.points
    ]
    intersections = _segment_intersections(
        _segments(path), _segments(region), tolerance
    )
    if any(location == "inside" for location in locations) and any(
        location == "outside" for location in locations
    ):
        point = intersections[0][0] if intersections else path.points[0]
        return "crosses", point, point
    if all(location != "outside" for location in locations) and any(
        location == "inside" for location in locations
    ) and not any(item[1] for item in intersections):
        point = path.points[0]
        return "inside", point, point
    if intersections:
        point = intersections[0][0]
        if any(item[1] for item in intersections):
            return "crosses", point, point
        if any(item[2] for item in intersections):
            return "overlaps", point, point
        return "touches", point, point
    path_point, region_point = _closest_between_segments(
        _segments(path), _segments(region)
    )
    if _distance(path_point, region_point) <= tolerance:
        return "touches", path_point, region_point
    return "separate", path_point, region_point


def _classify_region_region(
    source: SpatialGeometry, target: SpatialGeometry, tolerance: float
) -> tuple[RelationKind, Point, Point]:
    intersections = _segment_intersections(
        _segments(source), _segments(target), tolerance
    )
    source_locations = [
        _point_in_polygon(point, target.points, tolerance) for point in source.points
    ]
    target_locations = [
        _point_in_polygon(point, source.points, tolerance) for point in target.points
    ]
    if all(location != "outside" for location in source_locations) and any(
        location == "inside" for location in source_locations
    ):
        point = source.points[0]
        return "inside", point, point
    if all(location != "outside" for location in target_locations) and any(
        location == "inside" for location in target_locations
    ):
        point = target.points[0]
        return "contains", point, point
    if any(location == "inside" for location in source_locations + target_locations):
        point = intersections[0][0] if intersections else source.points[0]
        return "overlaps", point, point
    if intersections:
        point = intersections[0][0]
        if any(item[1] for item in intersections) or _same_polygon(
            source.points, target.points, tolerance
        ):
            return "overlaps", point, point
        return "touches", point, point
    source_point, target_point = _closest_between_segments(
        _segments(source), _segments(target)
    )
    if _distance(source_point, target_point) <= tolerance:
        return "touches", source_point, target_point
    return "separate", source_point, target_point


def _segments(geometry: SpatialGeometry) -> tuple[tuple[Point, Point], ...]:
    points = geometry.points
    pairs = [(points[index], points[index + 1]) for index in range(len(points) - 1)]
    if geometry.kind == "region":
        pairs.append((points[-1], points[0]))
    return tuple(pairs)


def _closest_point_on_segments(
    point: Point, segments: Sequence[tuple[Point, Point]]
) -> tuple[Point, float]:
    best_point = segments[0][0]
    best_distance = math.inf
    for start, end in segments:
        candidate = _closest_point_on_segment(point, start, end)
        distance = _distance(point, candidate)
        if distance < best_distance:
            best_point = candidate
            best_distance = distance
    return best_point, best_distance


def _closest_between_segments(
    source: Sequence[tuple[Point, Point]], target: Sequence[tuple[Point, Point]]
) -> tuple[Point, Point]:
    best_source = source[0][0]
    best_target = target[0][0]
    best_distance = math.inf
    for source_start, source_end in source:
        for target_start, target_end in target:
            candidates = (
                (
                    source_start,
                    _closest_point_on_segment(source_start, target_start, target_end),
                ),
                (
                    source_end,
                    _closest_point_on_segment(source_end, target_start, target_end),
                ),
                (
                    _closest_point_on_segment(target_start, source_start, source_end),
                    target_start,
                ),
                (
                    _closest_point_on_segment(target_end, source_start, source_end),
                    target_end,
                ),
            )
            for source_point, target_point in candidates:
                distance = _distance(source_point, target_point)
                if distance < best_distance:
                    best_source = source_point
                    best_target = target_point
                    best_distance = distance
    return best_source, best_target


def _segment_intersections(
    source: Sequence[tuple[Point, Point]],
    target: Sequence[tuple[Point, Point]],
    tolerance: float,
) -> list[tuple[Point, bool, bool]]:
    results: list[tuple[Point, bool, bool]] = []
    for source_segment in source:
        for target_segment in target:
            intersection = _segment_intersection(
                source_segment[0], source_segment[1], target_segment[0], target_segment[1], tolerance
            )
            if intersection is not None:
                results.append(intersection)
    return results


def _segment_intersection(
    a: Point, b: Point, c: Point, d: Point, tolerance: float
) -> tuple[Point, bool, bool] | None:
    ab = (b[0] - a[0], b[1] - a[1])
    cd = (d[0] - c[0], d[1] - c[1])
    ab_length = math.hypot(*ab)
    cd_length = math.hypot(*cd)
    area_tolerance = tolerance * max(ab_length, cd_length, 1e-12)
    denominator = _cross(ab, cd)
    ac = (c[0] - a[0], c[1] - a[1])
    if abs(denominator) <= area_tolerance:
        if abs(_cross(ac, ab)) > tolerance * max(ab_length, 1e-12):
            return None
        axis = 0 if max(abs(ab[0]), abs(cd[0])) >= max(abs(ab[1]), abs(cd[1])) else 1
        overlap_start = max(min(a[axis], b[axis]), min(c[axis], d[axis]))
        overlap_end = min(max(a[axis], b[axis]), max(c[axis], d[axis]))
        if overlap_end < overlap_start - tolerance:
            return None
        if overlap_end >= overlap_start:
            point = _point_at_axis(a, b, axis, overlap_start)
            return point, False, overlap_end - overlap_start > tolerance
        closest = min(
            ((first, second) for first in (a, b) for second in (c, d)),
            key=lambda pair: _distance(pair[0], pair[1]),
        )
        midpoint = (
            (closest[0][0] + closest[1][0]) / 2.0,
            (closest[0][1] + closest[1][1]) / 2.0,
        )
        return midpoint, False, False
    t = _cross(ac, cd) / denominator
    u = _cross(ac, ab) / denominator
    t_tolerance = tolerance / max(ab_length, 1e-12)
    u_tolerance = tolerance / max(cd_length, 1e-12)
    if (
        -t_tolerance <= t <= 1.0 + t_tolerance
        and -u_tolerance <= u <= 1.0 + u_tolerance
    ):
        point = (a[0] + t * ab[0], a[1] + t * ab[1])
        proper = (
            t_tolerance < t < 1.0 - t_tolerance
            and u_tolerance < u < 1.0 - u_tolerance
        )
        return point, proper, False
    return None


def _point_in_polygon(
    point: Point, polygon: Sequence[Point], tolerance: float
) -> Literal["inside", "boundary", "outside"]:
    for start, end in _segments(SpatialGeometry("region", tuple(polygon))):
        if _point_on_segment(point, start, end, tolerance):
            return "boundary"
    inside = False
    x, y = point
    previous = polygon[-1]
    for current in polygon:
        if (current[1] > y) != (previous[1] > y):
            crossing_x = (
                (previous[0] - current[0])
                * (y - current[1])
                / (previous[1] - current[1])
                + current[0]
            )
            if x < crossing_x:
                inside = not inside
        previous = current
    return "inside" if inside else "outside"


def _point_on_segment(point: Point, start: Point, end: Point, tolerance: float) -> bool:
    return _distance(point, _closest_point_on_segment(point, start, end)) <= tolerance


def _closest_point_on_segment(point: Point, start: Point, end: Point) -> Point:
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length_squared = dx * dx + dy * dy
    if length_squared <= _DEGENERATE_SEGMENT_LENGTH_SQUARED:
        return start
    fraction = (
        (point[0] - start[0]) * dx + (point[1] - start[1]) * dy
    ) / length_squared
    fraction = max(0.0, min(1.0, fraction))
    return (start[0] + fraction * dx, start[1] + fraction * dy)


def _scale_geometry(
    geometry: SpatialGeometry, metric: GeometryMetric
) -> SpatialGeometry:
    return SpatialGeometry(
        geometry.kind,
        tuple(
            (point[0] * metric.x_scale, point[1] * metric.y_scale)
            for point in geometry.points
        ),
    )


def _unscale_point(point: Point, metric: GeometryMetric) -> Point:
    return (point[0] / metric.x_scale, point[1] / metric.y_scale)


def _inverse_kind(kind: RelationKind) -> RelationKind:
    if kind == "inside":
        return "contains"
    if kind == "contains":
        return "inside"
    return kind


def _same_polygon(
    source: Sequence[Point], target: Sequence[Point], tolerance: float
) -> bool:
    if len(source) != len(target):
        return False
    return all(
        any(_distance(source_point, target_point) <= tolerance for target_point in target)
        for source_point in source
    )


def _point_at_axis(start: Point, end: Point, axis: int, value: float) -> Point:
    span = end[axis] - start[axis]
    if abs(span) <= _DEGENERATE_SEGMENT_LENGTH_SQUARED:
        return start
    fraction = (value - start[axis]) / span
    return (
        start[0] + fraction * (end[0] - start[0]),
        start[1] + fraction * (end[1] - start[1]),
    )


def _finite_point(point: Point) -> Point | None:
    if math.isfinite(point[0]) and math.isfinite(point[1]):
        return point
    return None


def _in_normalized_bounds(point: Point) -> bool:
    return 0.0 <= point[0] <= 1.0 and 0.0 <= point[1] <= 1.0


def _signed_area(points: Sequence[Point]) -> float:
    return sum(
        points[index][0] * points[(index + 1) % len(points)][1]
        - points[(index + 1) % len(points)][0] * points[index][1]
        for index in range(len(points))
    ) / 2.0


def _distance(first: Point, second: Point) -> float:
    return math.hypot(second[0] - first[0], second[1] - first[1])


def _cross(first: Point, second: Point) -> float:
    return first[0] * second[1] - first[1] * second[0]
