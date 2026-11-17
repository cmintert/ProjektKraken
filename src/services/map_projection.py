"""Read-only shared-point display policy; persisted markers remain authoritative."""

import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from src.core.map import Map, MapLayerNode, resolve_layer_temporal_validity
from src.core.marker import Marker
from src.core.temporal_context import TemporalResolutionContext
from src.core.trajectory import Keyframe, SegmentKey, SegmentMode, interpolate_position
from src.services.map_coordinates import MapCoordinates


@dataclass
class ProjectionSnapshot:
    """Worker-owned authored inputs; never passed as live objects to the GUI."""

    maps: list[Map]
    markers: list[Marker]
    tracks: dict[str, list[tuple[list[Keyframe], dict[SegmentKey, SegmentMode]]]] = (
        field(default_factory=dict)
    )
    context: TemporalResolutionContext = field(
        default_factory=TemporalResolutionContext
    )
    labels: dict[tuple[str, str], str] = field(default_factory=dict)


def layer_paths(root: MapLayerNode | None) -> dict[str, list[MapLayerNode]]:
    """Index full authored visibility ancestry without a GUI model."""
    result: dict[str, list[MapLayerNode]] = {}
    pending: list[tuple[MapLayerNode, list[MapLayerNode]]] = (
        [(root, [])] if root else []
    )
    while pending:
        node, ancestors = pending.pop()
        path = [*ancestors, node]
        result[node.id] = path
        pending.extend((child, path) for child in node.children)
    return result


class MapProjector:
    """Reuse hierarchy and visibility indexes across playhead-only refreshes."""

    def __init__(self, snapshot: ProjectionSnapshot) -> None:
        """Retain private detached inputs and resolved temporal evidence."""
        self.snapshot = snapshot
        self.coordinates = MapCoordinates(snapshot.maps)
        self.paths = {m.id: layer_paths(m.layers) for m in snapshot.maps}
        self.anchors = snapshot.context.anchors()
        self.constraints = snapshot.context.constraints()
        self.converter = snapshot.context.converter()

    def eligible(
        self,
        marker: Marker,
        target: str,
        date: float,
        zoom: float,
        include_detail: bool,
        fit_ratio: float | None = None,
    ) -> tuple[bool, float]:
        """Honor source visibility/time and conservatively hide zoomed-out detail."""
        a, b, d, e, _, _ = self.coordinates.affine(marker.map_id, target)
        scale = math.sqrt(abs(a * e - b * d))
        if not include_detail and scale < 1 - 1e-9:
            return False, 0
        path = self.paths[marker.map_id].get(marker.id, [])
        opacity = 1.0
        for node in path[1:]:
            comparison = (
                fit_ratio
                if node.attributes.get("zoom_basis") == "fit_ratio"
                and fit_ratio is not None
                else zoom
            )
            if (
                not node.visible
                or not node.min_zoom <= comparison * scale <= node.max_zoom
            ):
                return False, 0
            opacity *= node.opacity
        source = self.coordinates.maps[marker.map_id]
        if (
            source.layers
            and not resolve_layer_temporal_validity(
                source.layers,
                marker.id,
                date,
                self.converter,
                anchors=self.anchors,
                constraints=self.constraints,
            ).valid
        ):
            return False, 0
        return opacity > 0, opacity

    def position(self, marker: Marker, date: float) -> tuple[float, float]:
        """Resolve a unique trajectory before transformation, including step modes."""
        tracks = self.snapshot.tracks.get(marker.id, [])
        if len(tracks) > 1:
            raise ValueError("Multiple authored trajectories")
        if not tracks:
            return marker.x, marker.y
        points, modes = tracks[0]
        return interpolate_position(
            points, date, segment_modes=modes, base_position=(marker.x, marker.y)
        ) or (marker.x, marker.y)

    def frame(
        self,
        target: str,
        date: float,
        *,
        zoom: float = 1,
        include_detail: bool = False,
        fit_ratio: float | None = None,
    ) -> dict[str, Any]:
        """Build a deterministic ephemeral frame, reporting conflicting sources."""
        local = {
            (m.object_type, m.object_id)
            for m in self.snapshot.markers
            if m.map_id == target
        }
        candidates: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        issues: list[str] = []
        blocked: set[tuple[str, str]] = set()
        root = self.coordinates.chain(target)[0]
        for marker in self.snapshot.markers:
            key = marker.object_type, marker.object_id
            if marker.map_id == target or key in local or not marker.is_point:
                continue
            try:
                if self.coordinates.root(marker.map_id) != root:
                    continue
                eligible, opacity = self.eligible(
                    marker, target, date, zoom, include_detail, fit_ratio
                )
                if not eligible:
                    continue
                x, y = self.coordinates.point(
                    marker.map_id, target, *self.position(marker, date)
                )
                if not all(math.isfinite(v) for v in (x, y)):
                    raise ValueError("Nonfinite location")
                # Resolve ambiguity before containment: an outside competing source
                # must not make an inside placement appear uniquely authoritative.
                candidates[key].append(
                    {
                        "source_id": marker.id,
                        "source_map": marker.map_id,
                        "source_name": self.coordinates.maps[marker.map_id].name,
                        "object_id": marker.object_id,
                        "object_type": marker.object_type,
                        "label": self.snapshot.labels.get(
                            key, marker.label or marker.object_id
                        ),
                        "x": x,
                        "y": y,
                        "opacity": opacity,
                    }
                )
            except (ValueError, KeyError, TypeError, OverflowError) as exc:
                issues.append(f"{marker.label or marker.object_id}: {exc}")
                blocked.add(key)
        points = []
        for key, alternatives in sorted(candidates.items()):
            if key in blocked:
                continue
            alternatives.sort(key=lambda p: (p["source_map"], p["source_id"]))
            chosen = alternatives[0]
            if any(
                not math.isclose(p[axis], chosen[axis], abs_tol=1e-8, rel_tol=0)
                for p in alternatives[1:]
                for axis in ("x", "y")
            ):
                issues.append(
                    f"{chosen['label']}: conflicting placements on "
                    + ", ".join(p["source_name"] for p in alternatives)
                )
                continue
            if 0 <= chosen["x"] <= 1 and 0 <= chosen["y"] <= 1:
                points.append(
                    {**chosen, "sources": [p["source_id"] for p in alternatives]}
                )
        return {"points": points, "issues": issues}
