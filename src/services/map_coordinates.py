"""Cached map-to-map affine resolution over validated, detached hierarchies."""

import math
from typing import Any

from src.core.map import Map
from src.core.map_hierarchy import MapHierarchy
from src.services.map_nesting_service import (
    MapNestingService,
    validate_registration_payload,
)


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

            def resolve(point: tuple[float, float]) -> tuple[float, float]:
                for registration in source_chain:
                    point = MapNestingService.detail_to_parent(point, registration)
                for registration in reversed(target_chain):
                    point = MapNestingService.parent_to_detail(point, registration)
                return point

            origin, x, y = resolve((0, 0)), resolve((1, 0)), resolve((0, 1))
            a, d = x[0] - origin[0], x[1] - origin[1]
            b, e = y[0] - origin[0], y[1] - origin[1]
            determinant = a * e - b * d
            if (
                not all(math.isfinite(v) for v in (*origin, a, b, d, e, determinant))
                or determinant <= 0
            ):
                raise ValueError("Saved alignment cannot be resolved reliably.")
            self._pairs[key] = a, b, d, e, *origin
        return self._pairs[key]

    def point(
        self, source: str, target: str, x: float, y: float
    ) -> tuple[float, float]:
        """Transform a normalized point; containment belongs to the display policy."""
        a, b, d, e, tx, ty = self.affine(source, target)
        return a * x + b * y + tx, d * x + e * y + ty
