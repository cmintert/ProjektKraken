"""Phase-2 tests for MapNestingService.

Covers:
* validate_registration — all six failure modes.
* detail_to_parent / parent_to_detail round-trip identity.
* resolve_to_root — multi-level chain composition.
* footprint_corners — geometry sanity.
* point_in_footprint — boundary and interior checks.
* iter_ancestors — chain walking and cycle detection.
"""

from __future__ import annotations

import pytest

from src.app.constants import MAP_NESTING_DEPTH_CAP, MAP_ROLE_DETAIL, MAP_ROLE_MASTER
from src.core.map import Map
from src.services.map_nesting_service import MapNestingService, NestingValidationError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_map(name: str, **attrs) -> Map:
    return Map(name=name, image_path=f"/{name}.png", attributes=dict(attrs))


def _affine(
    cx: float = 0.5,
    cy: float = 0.5,
    scale: float = 0.25,
    rotation: float = 0.0,
    aspect: float = 1.5,
) -> dict:
    return {
        "mode": "aspect_locked_affine",
        "version": 1,
        "master_center_norm": {"x": cx, "y": cy},
        "scale_norm": scale,
        "rotation_deg": rotation,
        "aspect_ratio": aspect,
        "confidence": "user_confirmed",
    }


# ---------------------------------------------------------------------------
# Validation — six failure modes
# ---------------------------------------------------------------------------


def test_validate_rejects_self_parent():
    a = _make_map("A", map_role=MAP_ROLE_MASTER)
    with pytest.raises(NestingValidationError, match="own parent"):
        MapNestingService.validate_registration(a.id, a.id, _affine(), [a])


def test_validate_rejects_unknown_parent():
    a = _make_map("A")
    with pytest.raises(NestingValidationError, match="not found"):
        MapNestingService.validate_registration(
            a.id, "nonexistent", _affine(), [a]
        )


def test_validate_rejects_parent_without_role():
    parent = _make_map("Parent")  # no map_role
    detail = _make_map("Detail")
    with pytest.raises(NestingValidationError, match="master or detail"):
        MapNestingService.validate_registration(
            detail.id, parent.id, _affine(), [parent, detail]
        )


def test_validate_rejects_cycle():
    a = _make_map("A", map_role=MAP_ROLE_MASTER)
    b = _make_map(
        "B",
        map_role=MAP_ROLE_DETAIL,
        parent_map_id=a.id,
        registration=_affine(),
    )
    with pytest.raises(NestingValidationError, match="cycle"):
        MapNestingService.validate_registration(a.id, b.id, _affine(), [a, b])


def test_validate_rejects_depth_overflow():
    chain = [_make_map("R", map_role=MAP_ROLE_MASTER)]
    for i in range(MAP_NESTING_DEPTH_CAP - 1):
        prev = chain[-1]
        chain.append(
            _make_map(
                f"L{i}",
                map_role=MAP_ROLE_DETAIL,
                parent_map_id=prev.id,
                registration=_affine(),
            )
        )
    new_detail = _make_map("Extra")
    with pytest.raises(NestingValidationError, match="depth"):
        MapNestingService.validate_registration(
            new_detail.id, chain[-1].id, _affine(), chain + [new_detail]
        )


@pytest.mark.parametrize(
    "mutator",
    [
        lambda r: r.update({"mode": "freeform"}),
        lambda r: r.update({"scale_norm": 0}),
        lambda r: r.update({"aspect_ratio": -2}),
        lambda r: r.update({"rotation_deg": float("nan")}),
        lambda r: r.update({"master_center_norm": {"x": "oops", "y": 0.5}}),
    ],
)
def test_validate_rejects_malformed_payload(mutator):
    parent = _make_map("Parent", map_role=MAP_ROLE_MASTER)
    detail = _make_map("Detail")
    reg = _affine()
    mutator(reg)
    with pytest.raises(NestingValidationError):
        MapNestingService.validate_registration(
            detail.id, parent.id, reg, [parent, detail]
        )


def test_validate_accepts_valid_registration():
    parent = _make_map("Parent", map_role=MAP_ROLE_MASTER)
    detail = _make_map("Detail")
    MapNestingService.validate_registration(
        detail.id, parent.id, _affine(), [parent, detail]
    )  # should not raise


# ---------------------------------------------------------------------------
# detail_to_parent / parent_to_detail round-trip
# ---------------------------------------------------------------------------


def _approx_tuple(a: tuple, b: tuple, tol: float = 1e-9) -> bool:
    return abs(a[0] - b[0]) < tol and abs(a[1] - b[1]) < tol


@pytest.mark.parametrize(
    "uv",
    [
        (0.5, 0.5),  # centre
        (0.0, 0.0),  # top-left
        (1.0, 1.0),  # bottom-right
        (0.25, 0.75),
        (0.9, 0.1),
    ],
)
@pytest.mark.parametrize(
    "reg",
    [
        _affine(),  # identity-ish: centre=(0.5,0.5), scale=0.25, rot=0, aspect=1.5
        _affine(cx=0.3, cy=0.7, scale=0.4, rotation=45.0, aspect=2.0),
        _affine(cx=0.1, cy=0.9, scale=0.1, rotation=-30.0, aspect=0.5),
        _affine(cx=0.5, cy=0.5, scale=0.5, rotation=90.0, aspect=1.0),
        _affine(cx=0.8, cy=0.2, scale=0.3, rotation=135.0, aspect=1.333),
    ],
)
def test_round_trip_identity(uv, reg):
    """detail_to_parent followed by parent_to_detail is the identity."""
    parent_xy = MapNestingService.detail_to_parent(uv, reg)
    recovered = MapNestingService.parent_to_detail(parent_xy, reg)
    assert _approx_tuple(recovered, uv), (
        f"Round-trip failed for uv={uv}, reg={reg}\n"
        f"  parent_xy={parent_xy}, recovered={recovered}"
    )


def test_centre_maps_to_centre():
    """UV (0.5, 0.5) must land on master_center_norm."""
    reg = _affine(cx=0.3, cy=0.7, scale=0.5, rotation=37.0, aspect=1.8)
    xy = MapNestingService.detail_to_parent((0.5, 0.5), reg)
    assert _approx_tuple(xy, (0.3, 0.7))


def test_no_rotation_maps_corners_symmetrically():
    """With rotation=0, left/right corners must be symmetric around cx."""
    reg = _affine(cx=0.5, cy=0.5, scale=0.4, rotation=0.0, aspect=2.0)
    tl = MapNestingService.detail_to_parent((0.0, 0.0), reg)
    tr = MapNestingService.detail_to_parent((1.0, 0.0), reg)
    assert abs(0.5 - tl[0] - (tr[0] - 0.5)) < 1e-9  # symmetric around 0.5


# ---------------------------------------------------------------------------
# resolve_to_root
# ---------------------------------------------------------------------------


def test_resolve_to_root_single_level():
    master = _make_map("Master", map_role=MAP_ROLE_MASTER)
    reg = _affine(cx=0.5, cy=0.5, scale=0.25, rotation=0.0, aspect=1.0)
    detail = _make_map(
        "Detail",
        map_role=MAP_ROLE_DETAIL,
        parent_map_id=master.id,
        registration=reg,
    )
    root_id, root_uv = MapNestingService.resolve_to_root(
        detail.id, (0.5, 0.5), [master, detail]
    )
    assert root_id == master.id
    # centre of detail maps to cx,cy in parent (which is the root here)
    expected = MapNestingService.detail_to_parent((0.5, 0.5), reg)
    assert _approx_tuple(root_uv, expected)


def test_resolve_to_root_two_levels():
    """root → mid → leaf; resolve leaf UV all the way to root."""
    root = _make_map("Root", map_role=MAP_ROLE_MASTER)
    reg_mid = _affine(cx=0.5, cy=0.5, scale=0.5, rotation=0.0, aspect=1.0)
    mid = _make_map(
        "Mid",
        map_role=MAP_ROLE_DETAIL,
        parent_map_id=root.id,
        registration=reg_mid,
    )
    reg_leaf = _affine(cx=0.5, cy=0.5, scale=0.5, rotation=0.0, aspect=1.0)
    leaf = _make_map(
        "Leaf",
        map_role=MAP_ROLE_DETAIL,
        parent_map_id=mid.id,
        registration=reg_leaf,
    )

    local_uv = (0.5, 0.5)
    root_id, root_uv = MapNestingService.resolve_to_root(
        leaf.id, local_uv, [root, mid, leaf]
    )
    assert root_id == root.id

    # Manually compose: leaf→mid, mid→root
    mid_uv = MapNestingService.detail_to_parent(local_uv, reg_leaf)
    expected_root_uv = MapNestingService.detail_to_parent(mid_uv, reg_mid)
    assert _approx_tuple(root_uv, expected_root_uv)


def test_resolve_to_root_for_root_map_is_identity():
    root = _make_map("Root", map_role=MAP_ROLE_MASTER)
    uv = (0.3, 0.7)
    root_id, root_uv = MapNestingService.resolve_to_root(root.id, uv, [root])
    assert root_id == root.id
    assert _approx_tuple(root_uv, uv)


def test_resolve_to_root_three_levels_matches_manual_composition():
    root = _make_map("R", map_role=MAP_ROLE_MASTER)
    r1 = _affine(cx=0.6, cy=0.4, scale=0.4, rotation=15.0, aspect=1.5)
    m1 = _make_map(
        "M1", map_role=MAP_ROLE_DETAIL, parent_map_id=root.id, registration=r1
    )
    r2 = _affine(cx=0.3, cy=0.7, scale=0.3, rotation=-20.0, aspect=2.0)
    m2 = _make_map(
        "M2", map_role=MAP_ROLE_DETAIL, parent_map_id=m1.id, registration=r2
    )
    r3 = _affine(cx=0.5, cy=0.5, scale=0.5, rotation=0.0, aspect=1.0)
    m3 = _make_map(
        "M3", map_role=MAP_ROLE_DETAIL, parent_map_id=m2.id, registration=r3
    )

    local = (0.25, 0.75)
    root_id, root_uv = MapNestingService.resolve_to_root(
        m3.id, local, [root, m1, m2, m3]
    )
    assert root_id == root.id

    expected = MapNestingService.detail_to_parent(
        MapNestingService.detail_to_parent(
            MapNestingService.detail_to_parent(local, r3), r2
        ),
        r1,
    )
    assert _approx_tuple(root_uv, expected)


# ---------------------------------------------------------------------------
# footprint_corners
# ---------------------------------------------------------------------------


def test_footprint_corners_returns_four_points():
    corners = MapNestingService.footprint_corners(_affine())
    assert len(corners) == 4


def test_footprint_corners_centre_of_no_rotation():
    """With rotation=0 the centre of the footprint should equal (cx, cy)."""
    reg = _affine(cx=0.4, cy=0.6, scale=0.3, rotation=0.0, aspect=1.0)
    corners = MapNestingService.footprint_corners(reg)
    cx = sum(p[0] for p in corners) / 4
    cy = sum(p[1] for p in corners) / 4
    assert abs(cx - 0.4) < 1e-9
    assert abs(cy - 0.6) < 1e-9


def test_footprint_corners_centre_with_rotation():
    """Rotation should not shift the centre."""
    reg_no_rot = _affine(cx=0.5, cy=0.5, scale=0.3, rotation=0.0, aspect=1.2)
    reg_rot = _affine(cx=0.5, cy=0.5, scale=0.3, rotation=45.0, aspect=1.2)
    c0 = MapNestingService.footprint_corners(reg_no_rot)
    c1 = MapNestingService.footprint_corners(reg_rot)
    cx0 = sum(p[0] for p in c0) / 4
    cy0 = sum(p[1] for p in c0) / 4
    cx1 = sum(p[0] for p in c1) / 4
    cy1 = sum(p[1] for p in c1) / 4
    assert abs(cx0 - cx1) < 1e-9
    assert abs(cy0 - cy1) < 1e-9


# ---------------------------------------------------------------------------
# point_in_footprint
# ---------------------------------------------------------------------------


def test_point_in_footprint_centre_always_inside():
    reg = _affine(cx=0.5, cy=0.5, scale=0.3, rotation=0.0, aspect=1.5)
    assert MapNestingService.point_in_footprint((0.5, 0.5), reg)


def test_point_in_footprint_corner_outside():
    """A parent-space corner far from the footprint should be outside."""
    reg = _affine(cx=0.5, cy=0.5, scale=0.1, rotation=0.0, aspect=1.0)
    assert not MapNestingService.point_in_footprint((0.0, 0.0), reg)


def test_point_in_footprint_interior_and_exterior_consistency():
    """A UV slightly inside the footprint round-trips as inside; slightly
    outside round-trips as outside.  We avoid exact-corner UVs (0 / 1)
    because floating-point drift makes boundary membership undefined."""
    reg = _affine(cx=0.5, cy=0.5, scale=0.3, rotation=0.0, aspect=1.0)
    inside_uv = (0.1, 0.1)
    inside_parent = MapNestingService.detail_to_parent(inside_uv, reg)
    assert MapNestingService.point_in_footprint(inside_parent, reg)

    outside_uv = (-0.1, 0.5)  # outside the [0,1]² box
    outside_parent = MapNestingService.detail_to_parent(outside_uv, reg)
    assert not MapNestingService.point_in_footprint(outside_parent, reg)


def test_point_in_footprint_no_rotation_respects_rect():
    """With zero rotation and aspect=1 the footprint is axis-aligned."""
    reg = _affine(cx=0.5, cy=0.5, scale=0.4, rotation=0.0, aspect=1.0)
    # The footprint spans roughly [0.3, 0.7] in each axis.
    assert MapNestingService.point_in_footprint((0.5, 0.5), reg)
    assert not MapNestingService.point_in_footprint((0.1, 0.5), reg)
    assert not MapNestingService.point_in_footprint((0.9, 0.5), reg)


# ---------------------------------------------------------------------------
# iter_ancestors
# ---------------------------------------------------------------------------


def test_iter_ancestors_single_parent():
    master = _make_map("Master", map_role=MAP_ROLE_MASTER)
    detail = _make_map(
        "Detail",
        map_role=MAP_ROLE_DETAIL,
        parent_map_id=master.id,
        registration=_affine(),
    )
    ancestors = list(MapNestingService.iter_ancestors(detail.id, [master, detail]))
    assert ancestors == [master]


def test_iter_ancestors_chain():
    root = _make_map("Root", map_role=MAP_ROLE_MASTER)
    mid = _make_map(
        "Mid", map_role=MAP_ROLE_DETAIL, parent_map_id=root.id, registration=_affine()
    )
    leaf = _make_map(
        "Leaf", map_role=MAP_ROLE_DETAIL, parent_map_id=mid.id, registration=_affine()
    )
    ancestors = list(
        MapNestingService.iter_ancestors(leaf.id, [root, mid, leaf])
    )
    assert ancestors == [mid, root]


def test_iter_ancestors_root_has_none():
    root = _make_map("Root", map_role=MAP_ROLE_MASTER)
    assert list(MapNestingService.iter_ancestors(root.id, [root])) == []


def test_iter_ancestors_detects_cycle():
    a = _make_map("A", map_role=MAP_ROLE_MASTER)
    # Manually forge a cycle: A.parent_map_id -> A (impossible via normal
    # registration but tests the guard).
    a.attributes["parent_map_id"] = a.id
    with pytest.raises(NestingValidationError, match="Cycle"):
        list(MapNestingService.iter_ancestors(a.id, [a]))
