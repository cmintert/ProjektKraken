"""Cached map-to-map affine resolution over validated, detached hierarchies."""

import math
from typing import Any

from src.core.map import Map
from src.core.map_hierarchy import MapHierarchy
from src.services.map_nesting_service import validate_registration_payload


def _registration_geometry(
    registration: dict[str, Any],
) -> tuple[float, float, float, float, float]:
    center = registration["master_center_norm"]
    return (
        float(center["x"]),
        float(center["y"]),
        float(registration["scale_norm"]),
        float(registration["aspect_ratio"]),
        float(registration.get("rotation_deg", 0.0)) % 360,
    )


def _relative_affine(
    source: list[dict[str, Any]], target: list[dict[str, Any]]
) -> tuple[float, ...]:
    """Compose around image centers so linear terms never depend on translations."""
    forward = [_registration_geometry(record) for record in source]
    inverse = [_registration_geometry(record) for record in target]
    # The same outer transform cancels even when its scale is below one ULP.
    while forward and inverse and forward[-1] == inverse[-1]:
        forward.pop()
        inverse.pop()

    origin, x_axis, y_axis = (0.0, 0.0), (1.0, 0.0), (0.0, 1.0)
    for cx, cy, scale, aspect, rotation in forward:
        angle = math.radians(rotation)
        cos, sin = math.cos(angle), math.sin(angle)

        def into_parent(vector: tuple[float, float]) -> tuple[float, float]:
            x, y = vector[0] * scale, vector[1] * (scale / aspect)
            return cos * x - sin * y, sin * x + cos * y

        ox, oy = into_parent(origin)
        origin = ox + (cx - 0.5), oy + (cy - 0.5)
        x_axis, y_axis = into_parent(x_axis), into_parent(y_axis)

    for cx, cy, scale, aspect, rotation in reversed(inverse):
        angle = math.radians(rotation)
        cos, sin = math.cos(angle), math.sin(angle)

        def into_detail(vector: tuple[float, float]) -> tuple[float, float]:
            x, y = vector
            return (cos * x + sin * y) / scale, (-sin * x + cos * y) / (scale / aspect)

        origin = into_detail((origin[0] - (cx - 0.5), origin[1] - (cy - 0.5)))
        x_axis, y_axis = into_detail(x_axis), into_detail(y_axis)

    a, d = x_axis
    b, e = y_axis
    return a, b, d, e, origin[0] + 0.5 - (a + b) / 2, origin[1] + 0.5 - (d + e) / 2


class MapCoordinates:
    """Resolve connected maps without imposing the saved-format shear restriction."""

    def __init__(self, maps: list[Map]) -> None:
        """Index snapshots once; cache validated chains and affine pairs."""
        self.hierarchy = MapHierarchy(maps)
        self.maps = {m.id: m for m in maps}
        self._chains: dict[str, tuple[str, list[dict[str, Any]]]] = {}
        self._pairs: dict[tuple[str, str], tuple[float, ...]] = {}
        self._roots: dict[str, str] = {}

    def root(self, map_id: str) -> str:
        """Identify connectivity before validating geographically unrelated data."""
        if map_id not in self._roots:
            ancestors = self.hierarchy.ancestors(map_id)
            self._roots[map_id] = ancestors[-1].id if ancestors else map_id
        return self._roots[map_id]

    def chain(self, map_id: str) -> tuple[str, list[dict[str, Any]]]:
        """Return the root and validated child-to-parent registrations in order."""
        if map_id not in self._chains:
            path = [self.maps[map_id], *self.hierarchy.ancestors(map_id)]
            registrations = []
            for record in path[:-1]:
                registration = (record.attributes or {}).get("registration")
                if not isinstance(registration, dict):
                    raise ValueError(f"Map {record.name} has no saved alignment.")
                validate_registration_payload(registration)
                registrations.append(registration)
            self._chains[map_id] = path[-1].id, registrations
        return self._chains[map_id]

    def affine(self, source: str, target: str) -> tuple[float, ...]:
        """Return Shapely-order coefficients (a, b, d, e, xoff, yoff)."""
        key = source, target
        if key not in self._pairs:
            root, source_chain = self.chain(source)
            target_root, target_chain = self.chain(target)
            if root != target_root:
                raise ValueError("Maps have no shared registered root.")

            try:
                transform = _relative_affine(source_chain, target_chain)
            except (ZeroDivisionError, OverflowError) as exc:
                raise ValueError(
                    "Saved alignment cannot be resolved reliably."
                ) from exc
            a, b, d, e, _, _ = transform
            determinant = a * e - b * d
            if (
                not all(map(math.isfinite, (*transform, determinant)))
                or determinant <= 0
            ):
                raise ValueError("Saved alignment cannot be resolved reliably.")
            self._pairs[key] = transform
        return self._pairs[key]

    def point(
        self, source: str, target: str, x: float, y: float
    ) -> tuple[float, float]:
        """Transform a normalized point; containment belongs to the display policy."""
        a, b, d, e, tx, ty = self.affine(source, target)
        return a * x + b * y + tx, d * x + e * y + ty
