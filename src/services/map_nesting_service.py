"""Transform service for the master-map nesting feature.

Owns all registration validation and coordinate-transform math.
The service is intentionally stateless — all methods are static or class
methods.  Callers should never implement transform math themselves.

Coordinate conventions
----------------------
- ``uv`` — normalised coordinates in the detail map's own space.
  (0, 0) is top-left, (1, 1) is bottom-right.
- ``xy`` — normalised coordinates in the parent map's space, same
  origin convention.
- Rotation sign: ``rotation_deg`` is clockwise-positive (Qt/screen
  convention).  This maps to the standard counterclockwise sin/cos
  math exactly as written in the design doc — do not invert the sign.
- ``aspect_ratio`` = detail_width / detail_height > 0.  The transform
  scales the x-axis by ``scale_norm`` and the y-axis by
  ``scale_norm / aspect_ratio`` so that the footprint preserves the
  detail image's proportions.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Iterator, List, Optional, Tuple

from src.app.constants import MAP_NESTING_DEPTH_CAP, MAP_ROLE_DETAIL, MAP_ROLE_MASTER
from src.core.map import Map


class NestingValidationError(ValueError):
    """Raised when a detail-map registration is rejected.

    Replaces the Phase-1 inline exception; the Phase-1 version in
    ``map_crud_commands`` re-exports this class for backwards
    compatibility.
    """


def _validate_payload(registration: Dict[str, Any]) -> None:
    """Validate the structural shape of a registration dict.

    Checks mode, required numeric keys, finiteness, and positivity.
    Extracted so both this module and :mod:`map_crud_commands` can reuse
    the same check without importing each other circularly.

    Raises:
        NestingValidationError: When the payload is malformed.

    """
    if not isinstance(registration, dict):
        raise NestingValidationError("Registration payload must be a dict.")
    if registration.get("mode") != "aspect_locked_affine":
        raise NestingValidationError(
            "Registration mode must be 'aspect_locked_affine'."
        )
    center = registration.get("master_center_norm") or {}
    fields: Dict[str, Any] = {
        "master_center_norm.x": center.get("x"),
        "master_center_norm.y": center.get("y"),
        "scale_norm": registration.get("scale_norm"),
        "aspect_ratio": registration.get("aspect_ratio"),
        "rotation_deg": registration.get("rotation_deg", 0.0),
    }
    for name, value in fields.items():
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise NestingValidationError(
                f"Registration field '{name}' must be a finite number."
            )
        if not math.isfinite(float(value)):
            raise NestingValidationError(
                f"Registration field '{name}' must be a finite number."
            )
    if float(fields["scale_norm"]) <= 0:
        raise NestingValidationError("scale_norm must be > 0.")
    if float(fields["aspect_ratio"]) <= 0:
        raise NestingValidationError("aspect_ratio must be > 0.")


class MapNestingService:
    """Pure-stateless service for nesting validation and coordinate math.

    All public methods are static/class methods so callers never need an
    instance; a module-level singleton is sufficient if convenient.

    The coordinate model is documented at the top of this module.  The
    design doc's "Resolved Design Decisions / Decision 3" section
    specifies the exact sin/cos sign convention — do not alter it.
    """

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    @staticmethod
    def validate_registration(
        detail_id: str,
        parent_id: str,
        registration: Dict[str, Any],
        all_maps: List[Map],
    ) -> None:
        """Validate a proposed detail-map registration fully.

        Checks all six failure modes defined in the design doc:

        1. Self-parent (``detail_id == parent_id``).
        2. Unknown parent.
        3. Parent without an eligible role (must be master or detail).
        4. Cycle in the existing chain (A → B → A).
        5. Depth overflow (resulting depth > ``MAP_NESTING_DEPTH_CAP``).
        6. Malformed payload (bad mode, wrong types, non-finite, ≤ 0).

        Args:
            detail_id: ID of the map being registered as a detail child.
            parent_id: ID of the proposed parent map.
            registration: Affine registration payload dict.
            all_maps: All maps in the current world (used for graph
                traversal).

        Raises:
            NestingValidationError: On any of the six failure modes.

        """
        if detail_id == parent_id:
            raise NestingValidationError("A map cannot be its own parent.")

        by_id: Dict[str, Map] = {m.id: m for m in all_maps}
        parent = by_id.get(parent_id)
        if parent is None:
            raise NestingValidationError(f"Parent map not found: {parent_id}")

        parent_role = (parent.attributes or {}).get("map_role")
        if parent_role not in (MAP_ROLE_MASTER, MAP_ROLE_DETAIL):
            raise NestingValidationError(
                "Parent map must already be designated as a master or detail map."
            )

        # Walk the parent chain: detect cycles and measure depth.
        visited: set = {parent_id}
        cursor: Optional[Map] = parent
        depth = 1  # parent occupies depth 1; detail would be depth+1
        while cursor is not None:
            attrs = cursor.attributes or {}
            next_id = attrs.get("parent_map_id")
            if not next_id:
                break
            if next_id == detail_id:
                raise NestingValidationError(
                    "Registration would create a cycle in the nesting chain."
                )
            if next_id in visited:
                raise NestingValidationError(
                    "Existing nesting chain already contains a cycle."
                )
            visited.add(next_id)
            cursor = by_id.get(next_id)
            if cursor is None:
                break
            depth += 1

        if depth + 1 > MAP_NESTING_DEPTH_CAP:
            raise NestingValidationError(
                f"Nesting depth would exceed cap of {MAP_NESTING_DEPTH_CAP} levels."
            )

        _validate_payload(registration)

    # ------------------------------------------------------------------
    # Forward transform: detail UV → parent XY
    # ------------------------------------------------------------------

    @staticmethod
    def detail_to_parent(
        uv: Tuple[float, float],
        registration: Dict[str, Any],
    ) -> Tuple[float, float]:
        """Transform a detail-space UV point into parent normalised space.

        Applies the aspect-locked affine:

            local = uv − (0.5, 0.5)
            scaled = (s · local.x,  (s / r) · local.y)
            rotated = R(θ) · scaled
            xy = rotated + center

        where ``s = scale_norm``, ``r = aspect_ratio``, ``θ = rotation_deg``
        (clockwise-positive, matching Qt's y-down screen convention).

        Args:
            uv: Point in detail normalised space ``[0, 1]²``.
            registration: Validated aspect-locked-affine dict.

        Returns:
            Point in parent normalised space.

        """
        s = float(registration["scale_norm"])
        r = float(registration["aspect_ratio"])
        theta = math.radians(float(registration.get("rotation_deg", 0.0)))
        center_d = registration["master_center_norm"]
        cx = float(center_d["x"])
        cy = float(center_d["y"])

        # Translate to origin, apply anisotropic scale.
        lx = (uv[0] - 0.5) * s
        ly = (uv[1] - 0.5) * (s / r)

        # Clockwise rotation (y-down): standard rotation matrix with
        # positive angle being clockwise.
        cos_t = math.cos(theta)
        sin_t = math.sin(theta)
        rx = cos_t * lx - sin_t * ly
        ry = sin_t * lx + cos_t * ly

        return (rx + cx, ry + cy)

    # ------------------------------------------------------------------
    # Inverse transform: parent XY → detail UV
    # ------------------------------------------------------------------

    @staticmethod
    def parent_to_detail(
        xy: Tuple[float, float],
        registration: Dict[str, Any],
    ) -> Tuple[float, float]:
        """Transform a parent-space XY point into detail normalised space.

        Closed-form inverse of :meth:`detail_to_parent`.

        Args:
            xy: Point in parent normalised space.
            registration: Validated aspect-locked-affine dict.

        Returns:
            Point in detail normalised space.

        """
        s = float(registration["scale_norm"])
        r = float(registration["aspect_ratio"])
        theta = math.radians(float(registration.get("rotation_deg", 0.0)))
        center_d = registration["master_center_norm"]
        cx = float(center_d["x"])
        cy = float(center_d["y"])

        # Translate by centre.
        dx = xy[0] - cx
        dy = xy[1] - cy

        # Inverse rotation (transpose of R since R is orthogonal).
        cos_t = math.cos(theta)
        sin_t = math.sin(theta)
        ux = cos_t * dx + sin_t * dy
        uy = -sin_t * dx + cos_t * dy

        # Inverse anisotropic scale.
        local_x = ux / s + 0.5
        local_y = uy / (s / r) + 0.5

        return (local_x, local_y)

    # ------------------------------------------------------------------
    # Multi-level chain resolution
    # ------------------------------------------------------------------

    @classmethod
    def resolve_to_root(
        cls,
        detail_id: str,
        local_uv: Tuple[float, float],
        all_maps: List[Map],
    ) -> Tuple[str, Tuple[float, float]]:
        """Walk the parent chain and express ``local_uv`` in root space.

        Composes transforms level by level until reaching a map with no
        parent (the master, or any map with no ``parent_map_id``).

        Args:
            detail_id: ID of the map in whose space ``local_uv`` is given.
            local_uv: Point in the detail map's own normalised space.
            all_maps: All maps in the world.

        Returns:
            A ``(root_map_id, root_uv)`` tuple where ``root_map_id`` is
            the ID of the topmost ancestor and ``root_uv`` is the point
            expressed in that map's normalised space.

        Raises:
            NestingValidationError: If the chain contains a cycle or an
                unknown map ID is encountered mid-chain.

        """
        by_id: Dict[str, Map] = {m.id: m for m in all_maps}
        current_id = detail_id
        current_uv = local_uv
        visited: set = {current_id}

        while True:
            current_map = by_id.get(current_id)
            if current_map is None:
                raise NestingValidationError(
                    f"Map not found during chain resolution: {current_id}"
                )
            attrs = current_map.attributes or {}
            parent_id = attrs.get("parent_map_id")
            if not parent_id:
                # Reached the root.
                return (current_id, current_uv)
            if parent_id in visited:
                raise NestingValidationError(
                    "Cycle detected during chain resolution."
                )
            registration = attrs.get("registration")
            if registration is None:
                raise NestingValidationError(
                    f"Map '{current_id}' has parent_map_id but no registration."
                )
            current_uv = cls.detail_to_parent(current_uv, registration)
            visited.add(parent_id)
            current_id = parent_id

    # ------------------------------------------------------------------
    # Footprint geometry
    # ------------------------------------------------------------------

    @staticmethod
    def footprint_corners(
        registration: Dict[str, Any],
    ) -> List[Tuple[float, float]]:
        """Return the four corners of the footprint in parent normalised space.

        Corners are returned in order: top-left, top-right, bottom-right,
        bottom-left (i.e. clockwise from top-left in screen coordinates).

        Args:
            registration: Validated aspect-locked-affine dict.

        Returns:
            List of four ``(x, y)`` tuples in parent normalised space.

        """
        unit_corners: List[Tuple[float, float]] = [
            (0.0, 0.0),  # top-left
            (1.0, 0.0),  # top-right
            (1.0, 1.0),  # bottom-right
            (0.0, 1.0),  # bottom-left
        ]
        svc = MapNestingService
        return [svc.detail_to_parent(c, registration) for c in unit_corners]

    @staticmethod
    def point_in_footprint(
        parent_xy: Tuple[float, float],
        registration: Dict[str, Any],
    ) -> bool:
        """Return ``True`` when ``parent_xy`` lies inside the footprint.

        Transforms ``parent_xy`` into the detail map's UV space and checks
        whether the result is within ``[0, 1]²`` — the footprint's unit
        square in its own coordinate system.

        Args:
            parent_xy: Point in parent normalised space.
            registration: Validated aspect-locked-affine dict.

        Returns:
            ``True`` if the point is inside the footprint, else ``False``.

        """
        svc = MapNestingService
        u, v = svc.parent_to_detail(parent_xy, registration)
        return 0.0 <= u <= 1.0 and 0.0 <= v <= 1.0

    # ------------------------------------------------------------------
    # Convenience iterator (mirrors MapRepository pattern)
    # ------------------------------------------------------------------

    @staticmethod
    def iter_ancestors(
        map_id: str,
        all_maps: List[Map],
    ) -> Iterator[Map]:
        """Yield maps in the parent chain from immediate parent to root.

        Args:
            map_id: ID of the map whose ancestors should be walked.
            all_maps: All maps in the world.

        Yields:
            Each ancestor ``Map`` from nearest to farthest.

        Raises:
            NestingValidationError: If a cycle is detected.

        """
        by_id: Dict[str, Map] = {m.id: m for m in all_maps}
        visited: set = {map_id}
        current_id = map_id
        while True:
            current = by_id.get(current_id)
            if current is None:
                break
            parent_id = (current.attributes or {}).get("parent_map_id")
            if not parent_id:
                break
            if parent_id in visited:
                raise NestingValidationError(
                    "Cycle detected while iterating ancestors."
                )
            parent = by_id.get(parent_id)
            if parent is None:
                break
            visited.add(parent_id)
            yield parent
            current_id = parent_id
