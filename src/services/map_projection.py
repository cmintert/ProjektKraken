"""Read-only shared-point display policy; persisted markers remain authoritative."""

import math
from dataclasses import asdict, dataclass, field
from typing import Any

from src.core.feature_geometry_state import FeatureGeometryState
from src.core.map import Map, MapLayerNode, resolve_layer_temporal_validity
from src.core.marker import Marker
from src.core.temporal_context import TemporalResolutionContext
from src.core.trajectory import Keyframe, SegmentKey, SegmentMode, interpolate_position
from src.services.map_coordinates import MapCoordinates
from src.services.map_geometry_projection import projection_frame


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
    states: dict[str, list[FeatureGeometryState]] = field(default_factory=dict)

    image_sizes: dict[str, tuple[int, int]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Encode detached inputs for the dedicated calculation thread."""
        return {
            "maps": [m.to_dict() for m in self.maps],
            "image_sizes": self.image_sizes,
            "markers": [m.to_dict() for m in self.markers],
            "tracks": {
                key: [
                    {
                        "points": [asdict(p) for p in points],
                        "modes": [[a, b, mode] for (a, b), mode in modes.items()],
                    }
                    for points, modes in tracks
                ]
                for key, tracks in self.tracks.items()
            },
            "context": asdict(self.context),
            "labels": [
                [kind, key, label] for (kind, key), label in self.labels.items()
            ],
            "states": {
                key: [s.to_dict() for s in states]
                for key, states in self.states.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProjectionSnapshot":
        """Reconstruct private models; no GUI/database object crosses threads."""
        return cls(
            maps=[Map.from_dict(m) for m in data["maps"]],
            markers=[Marker.from_dict(m) for m in data["markers"]],
            image_sizes={
                key: (width, height)
                for key, (width, height) in data.get("image_sizes", {}).items()
            },
            tracks={
                key: [
                    (
                        [Keyframe(**p) for p in track["points"]],
                        {(a, b): mode for a, b, mode in track["modes"]},
                    )
                    for track in tracks
                ]
                for key, tracks in data["tracks"].items()
            },
            context=TemporalResolutionContext(**data["context"]),
            labels={(kind, key): label for kind, key, label in data["labels"]},
            states={
                key: [FeatureGeometryState.from_dict(s) for s in states]
                for key, states in data["states"].items()
            },
        )


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
        self.shapes: dict[tuple[str, str | None], Any] = {}

    def pixel_scale(self, source: str, target: str) -> float:
        """Convert area scale from normalized coordinates to image pixels."""
        source_size = self.snapshot.image_sizes.get(source)
        target_size = self.snapshot.image_sizes.get(target)
        if source_size is None or target_size is None:
            return 1.0
        return math.sqrt(math.prod(target_size) / math.prod(source_size))

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
        absolute_zoom = zoom * scale * self.pixel_scale(marker.map_id, target)
        opacity = 1.0
        for node in path[1:]:
            comparison = (
                fit_ratio * scale
                if node.attributes.get("zoom_basis") == "fit_ratio"
                and fit_ratio is not None
                else absolute_zoom
            )
            if not node.visible or not node.min_zoom <= comparison <= node.max_zoom:
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
        pixel_size: tuple[float, float] | None = None,
    ) -> dict[str, Any]:
        """Resolve authoritative representations before display-only clipping."""
        return projection_frame(
            self,
            target,
            date,
            zoom=zoom,
            include_detail=include_detail,
            fit_ratio=fit_ratio,
            pixel_size=pixel_size,
        )
