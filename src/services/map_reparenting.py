"""Exact reparent proposals over detached registrations; no Qt or persistence."""

import math
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from src.core.map import Map
from src.core.map_hierarchy import MapHierarchy, hierarchy_attributes
from src.services.map_nesting_service import validate_registration_payload

_RELATIVE_TOLERANCE = 1e-10
_ABSOLUTE_TOLERANCE = 1e-12
_PRECISION_MARGIN = 32


class PlacementPreservationError(ValueError):
    """A saved relationship cannot safely determine an exact new placement."""


@dataclass(frozen=True)
class _Affine:
    """Normalized-space matrix [[a, c, tx], [b, d, ty], [0, 0, 1]]."""

    a: float = 1.0
    b: float = 0.0
    c: float = 0.0
    d: float = 1.0
    tx: float = 0.0
    ty: float = 0.0

    def __post_init__(self) -> None:
        if not all(math.isfinite(value) for value in self.values()):
            raise PlacementPreservationError(
                "The saved alignment is numerically unstable. Place the map manually."
            )
        x, y = math.hypot(self.a, self.b), math.hypot(self.c, self.d)
        # Reject footprints smaller than translation precision or with unusable
        # axis conditioning before cancellation can masquerade as exact placement.
        resolution = max(math.ulp(self.tx), math.ulp(self.ty)) * _PRECISION_MARGIN
        if (
            not math.isfinite(x + y)
            or min(x, y) <= resolution
            or min(x, y) / max(x, y) <= _ABSOLUTE_TOLERANCE
        ):
            raise PlacementPreservationError(
                "The saved alignment is numerically unstable. Place the map manually."
            )

    def values(self) -> tuple[float, ...]:
        return self.a, self.b, self.c, self.d, self.tx, self.ty

    def compose(self, inner: "_Affine") -> "_Affine":
        """Apply inner first, then this transform (left matrix multiplication)."""
        return _Affine(
            self.a * inner.a + self.c * inner.b,
            self.b * inner.a + self.d * inner.b,
            self.a * inner.c + self.c * inner.d,
            self.b * inner.c + self.d * inner.d,
            self.a * inner.tx + self.c * inner.ty + self.tx,
            self.b * inner.tx + self.d * inner.ty + self.ty,
        )

    def inverse(self) -> "_Affine":
        """Invert using normalized columns to avoid determinant overflow."""
        x, y = math.hypot(self.a, self.b), math.hypot(self.c, self.d)
        if not x or not y:
            raise PlacementPreservationError(
                "The saved alignment is not invertible. Place the map manually."
            )
        determinant = (self.a / x) * (self.d / y) - (self.b / x) * (self.c / y)
        if abs(determinant) <= _ABSOLUTE_TOLERANCE:
            raise PlacementPreservationError(
                "The saved alignment is numerically unstable. Place the map manually."
            )
        a, c = (self.d / y) / (x * determinant), -(self.c / y) / (x * determinant)
        b, d = -(self.b / x) / (y * determinant), (self.a / x) / (y * determinant)
        return _Affine(
            a, b, c, d, -(a * self.tx + c * self.ty), -(b * self.tx + d * self.ty)
        )


def _from_registration(registration: dict[str, Any]) -> _Affine:
    validate_registration_payload(registration)
    angle = math.radians(registration.get("rotation_deg", 0.0))
    x = float(registration["scale_norm"])
    y = x / float(registration["aspect_ratio"])
    a, b = x * math.cos(angle), x * math.sin(angle)
    c, d = -y * math.sin(angle), y * math.cos(angle)
    center = registration["master_center_norm"]
    return _Affine(a, b, c, d, center["x"] - (a + c) / 2, center["y"] - (b + d) / 2)


def _to_registration(transform: _Affine) -> dict[str, Any]:
    x = math.hypot(transform.a, transform.b)
    y = math.hypot(transform.c, transform.d)
    if not x or not y:
        raise PlacementPreservationError(
            "The saved alignment is not invertible. Place the map manually."
        )
    dot = (transform.a / x) * (transform.c / y) + (transform.b / x) * (transform.d / y)
    determinant = (transform.a / x) * (transform.d / y) - (transform.b / x) * (
        transform.c / y
    )
    if abs(dot) > _RELATIVE_TOLERANCE or determinant <= 0:
        raise PlacementPreservationError(
            "Keeping this placement would require skewing or reflecting the image, "
            "which the current registration format cannot store. Place the map manually."
        )
    registration = {
        "mode": "aspect_locked_affine",
        "version": 1,
        "master_center_norm": {
            "x": transform.tx + (transform.a + transform.c) / 2,
            "y": transform.ty + (transform.b + transform.d) / 2,
        },
        "scale_norm": x,
        "aspect_ratio": x / y,
        "rotation_deg": math.degrees(math.atan2(transform.b, transform.a)) % 360,
        "confidence": "user_confirmed",
    }
    reconstructed = _from_registration(registration)
    if not all(
        math.isclose(a, b, rel_tol=_RELATIVE_TOLERANCE, abs_tol=_ABSOLUTE_TOLERANCE)
        for a, b in zip(transform.values(), reconstructed.values(), strict=True)
    ):
        raise PlacementPreservationError(
            "Exact placement cannot be represented reliably. Place the map manually."
        )
    return registration


@dataclass(frozen=True)
class PreservedReparentPlan:
    """Independent registration and dependency snapshots for worker validation."""

    registration: dict[str, Any]
    expected_context: dict[str, dict[str, Any]]


def plan_preserved_reparent(
    maps: list[Map], map_id: str, parent_id: str
) -> PreservedReparentPlan:
    """Compose a same-root move and reject unsupported or unstable placement.

    Coordinates use the saved v1 normalized-space convention. The reconstructed
    transform must agree within 1e-10 relative / 1e-12 absolute floating precision;
    genuine shear is never approximated. No map or descendant is mutated.
    """
    return _plan_preserved_reparent(
        MapHierarchy(maps), {record.id: record for record in maps}, map_id, parent_id
    )


def _plan_preserved_reparent(
    hierarchy: MapHierarchy, records: dict[str, Map], map_id: str, parent_id: str
) -> PreservedReparentPlan:
    hierarchy.validate_change_parent(map_id, parent_id)
    source_path = [records[map_id], *hierarchy.ancestors(map_id)]
    target_path = [records[parent_id], *hierarchy.ancestors(parent_id)]
    if source_path[-1].id != target_path[-1].id:
        raise PlacementPreservationError(
            "These maps have no shared registered ancestor. Place the map manually."
        )
    context = {
        record.id: hierarchy_attributes(record.attributes)
        for record in source_path + target_path
    }
    try:

        def to_root(path: list[Map]) -> _Affine:
            transform = _Affine()
            for record in path[:-1]:
                registration = (record.attributes or {}).get("registration")
                if not isinstance(registration, dict):
                    raise PlacementPreservationError(
                        "A saved parent alignment is missing. Place the map manually."
                    )
                transform = _from_registration(registration).compose(transform)
            return transform

        transform = to_root(target_path).inverse().compose(to_root(source_path))
        registration = _to_registration(transform)
    except (OverflowError, ZeroDivisionError) as exc:
        raise PlacementPreservationError(
            "The saved alignment is numerically unstable. Place the map manually."
        ) from exc
    return PreservedReparentPlan(deepcopy(registration), deepcopy(context))


def preservation_options(
    maps: list[Map], map_id: str, parents: list[Map]
) -> dict[str, str | None]:
    """Return availability or an explanation for the parent picker's choices."""
    if not parents:
        return {}
    hierarchy = MapHierarchy(maps)
    records = {record.id: record for record in maps}
    result: dict[str, str | None] = {}
    for parent in parents:
        try:
            _plan_preserved_reparent(hierarchy, records, map_id, parent.id)
        except (ValueError, TypeError, KeyError) as exc:
            result[parent.id] = str(exc)
        else:
            result[parent.id] = None
    return result
