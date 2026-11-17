"""Unclipped ambiguity decisions and topology-preserving display-only geometry."""

from bisect import bisect_right
from collections import defaultdict
from typing import TYPE_CHECKING, Any

from shapely.affinity import affine_transform
from shapely.errors import GEOSException
from shapely.geometry import LineString, Point, Polygon, box
from shapely.geometry.base import BaseGeometry

from src.core.feature_geometry_state import resolve_feature_geometry
from src.core.marker import Marker
from src.core.projected_geometry import ProjectedGeometry
from src.core.region_geometry import RegionPolygon
from src.core.spatial_geometry import SpatialGeometry

if TYPE_CHECKING:
    from src.services.map_projection import MapProjector

_AGREEMENT_TOLERANCE = 1e-8
_PIXEL_TOLERANCE = 0.5


def components(shape: BaseGeometry, kind: type) -> list[Any]:
    """Recursively retain every polygon or line, excluding empty/tangent parts."""
    if shape.is_empty:
        return []
    if isinstance(shape, kind):
        return [shape]
    return [
        part
        for child in getattr(shape, "geoms", [])
        for part in components(child, kind)
    ]


def source_shape(
    projector: "MapProjector", marker: Marker, date: float
) -> tuple[BaseGeometry, str | None, float | None]:
    """Resolve canonical dated geometry, caching topology by immutable state ID."""
    if marker.is_point:
        return Point(*projector.position(marker, date)), None, None
    states = sorted(
        projector.snapshot.states.get(marker.id, []), key=lambda s: s.effective_date
    )
    index = bisect_right([s.effective_date for s in states], date) - 1
    state = states[index] if index >= 0 else None
    key = marker.id, state.id if state else None
    if key not in projector.shapes:
        resolved = resolve_feature_geometry(marker, states, date)
        geometry = SpatialGeometry.from_feature(
            marker.feature_type, resolved.anchor_x, resolved.anchor_y, resolved.geometry
        )
        if geometry is None:
            raise ValueError("Invalid source geometry")
        shape = (
            RegionPolygon.from_geometry(resolved.geometry).validated()
            if marker.is_region
            else LineString(geometry.points)
        )
        if not shape.is_valid:
            raise ValueError("Invalid source topology")
        projector.shapes[key] = shape
    return (
        projector.shapes[key],
        state.id if state else None,
        state.effective_date if state else None,
    )


def metadata(
    projector: "MapProjector", marker: Marker, opacity: float
) -> dict[str, Any]:
    """Preserve source/object identity and supporting provenance in every frame."""
    key = marker.object_type, marker.object_id
    return {
        "source_id": marker.id,
        "source_map": marker.map_id,
        "source_name": projector.coordinates.maps[marker.map_id].name,
        "object_id": marker.object_id,
        "object_type": marker.object_type,
        "feature_type": marker.feature_type,
        "label": projector.snapshot.labels.get(key, marker.label or marker.object_id),
        "opacity": opacity,
    }


def display_geometry(
    shape: BaseGeometry,
    data: dict[str, Any],
    target: str,
    pixel_size: tuple[float, float] | None,
) -> dict[str, Any] | None:
    """Clip/simplify a copy, retaining holes and disconnected surviving pieces."""
    clipped = shape.intersection(box(0, 0, 1, 1))
    kind = Polygon if data["feature_type"] == "region" else LineString
    parts = components(clipped, kind)
    if not parts:
        return None
    if pixel_size and min(pixel_size) > 0:
        tolerance = _PIXEL_TOLERANCE / max(pixel_size)
        simplified = clipped.simplify(tolerance, preserve_topology=True)
        new_parts = components(simplified, kind)
        old_holes = sum(len(p.interiors) for p in parts) if kind is Polygon else 0
        new_holes = sum(len(p.interiors) for p in new_parts) if kind is Polygon else 0
        if (
            simplified.is_valid
            and len(new_parts) == len(parts)
            and old_holes == new_holes
        ):
            parts = new_parts
    polygons = (
        tuple(
            RegionPolygon(
                tuple(p.exterior.coords)[:-1],
                tuple(tuple(ring.coords)[:-1] for ring in p.interiors),
            )
            for p in parts
        )
        if kind is Polygon
        else ()
    )
    lines = tuple(tuple(p.coords) for p in parts) if kind is LineString else ()
    model = ProjectedGeometry(
        data["source_id"],
        data["source_map"],
        target,
        data["feature_type"],
        polygons,
        lines,
        data["state_id"],
        data["effective_date"],
    )
    return {**data, **model.to_dict()}


def projection_frame(
    projector: "MapProjector",
    target: str,
    date: float,
    *,
    zoom: float,
    include_detail: bool,
    fit_ratio: float | None,
    pixel_size: tuple[float, float] | None,
) -> dict[str, Any]:
    """Resolve all authored representations before clipping or simplifying any."""
    local = {
        (m.object_type, m.object_id)
        for m in projector.snapshot.markers
        if m.map_id == target
    }
    root = projector.coordinates.chain(target)[0]
    candidates: dict[tuple[str, str], list[tuple[dict[str, Any], BaseGeometry]]] = (
        defaultdict(list)
    )
    issues: list[str] = []
    blocked: set[tuple[str, str]] = set()
    for marker in projector.snapshot.markers:
        key = marker.object_type, marker.object_id
        if (
            marker.map_id == target
            or key in local
            or marker.feature_type not in {"point", "path", "region"}
        ):
            continue
        try:
            if projector.coordinates.root(marker.map_id) != root:
                continue
            eligible, opacity = projector.eligible(
                marker, target, date, zoom, include_detail, fit_ratio
            )
            if not eligible:
                continue
            source, state_id, effective_date = source_shape(projector, marker, date)
            shape = affine_transform(
                source, projector.coordinates.affine(marker.map_id, target)
            )
            if not shape.is_valid or shape.is_empty:
                raise ValueError("Invalid projected geometry")
            data = {
                **metadata(projector, marker, opacity),
                "state_id": state_id,
                "effective_date": effective_date,
            }
            candidates[key].append((data, shape))
        except (ValueError, KeyError, TypeError, OverflowError, GEOSException) as exc:
            issues.append(f"{marker.label or marker.object_id}: {exc}")
            blocked.add(key)
    return choose_displays(candidates, blocked, issues, target, pixel_size)


def choose_displays(
    candidates: dict[tuple[str, str], list[tuple[dict[str, Any], BaseGeometry]]],
    blocked: set[tuple[str, str]],
    issues: list[str],
    target: str,
    pixel_size: tuple[float, float] | None,
) -> dict[str, Any]:
    """Choose agreeing full representations and emit every target-display part."""
    points, geometries = [], []
    for key, alternatives in sorted(candidates.items()):
        if key in blocked:
            continue
        alternatives.sort(key=lambda p: (p[0]["source_map"], p[0]["source_id"]))
        data, shape = alternatives[0]
        if any(
            other.geom_type != shape.geom_type
            or not (
                shape.equals(other)
                or shape.equals_exact(other, _AGREEMENT_TOLERANCE, normalize=True)
            )
            for _, other in alternatives[1:]
        ):
            issues.append(
                f"{data['label']}: conflicting placements on "
                + ", ".join(p[0]["source_name"] for p in alternatives)
            )
            continue
        data = {**data, "sources": [p[0]["source_id"] for p in alternatives]}
        if isinstance(shape, Point):
            if box(0, 0, 1, 1).covers(shape):
                points.append({**data, "x": shape.x, "y": shape.y})
        else:
            try:
                display = display_geometry(shape, data, target, pixel_size)
            except (ValueError, GEOSException) as exc:
                issues.append(f"{data['label']}: display geometry unavailable: {exc}")
                continue
            if display:
                geometries.append(display)
    return {"points": points, "geometries": geometries, "issues": issues}
