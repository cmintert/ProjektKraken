"""Phase-5 tests for the AI-aware spatial context advisory.

Covers:
* nesting_service=None preserves all existing build() behaviour.
* Master map + marker inside footprint → "Detail map available:" appended.
* Detail map active → no advisory (Decision 5).
* Master map + marker outside all footprints → no advisory.
* Multiple children: only the first hit is reported.
* Malformed registration is silently skipped (no crash, no advisory).
"""

from __future__ import annotations

from unittest.mock import MagicMock

from src.app.constants import MAP_ROLE_DETAIL, MAP_ROLE_MASTER
from src.core.map import Map, MapLayerNode
from src.core.marker import Marker
from src.services.map_nesting_service import MapNestingService
from src.services.spatial_context_builder import SpatialContextBuilder

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_marker(x: float = 0.5, y: float = 0.5) -> Marker:
    return Marker(
        id="marker-1",
        map_id="map-master",
        object_id="entity-1",
        object_type="entity",
        x=x,
        y=y,
        label="Hero",
    )


def _make_map(
    map_id: str,
    name: str,
    role: str | None = None,
    parent_id: str | None = None,
    registration: dict | None = None,
    layers: MapLayerNode | None = None,
) -> Map:
    attrs: dict = {}
    if role:
        attrs["map_role"] = role
    if parent_id:
        attrs["parent_map_id"] = parent_id
    if registration:
        attrs["registration"] = registration
    return Map(
        id=map_id,
        name=name,
        image_path=f"/{name}.png",
        attributes=attrs,
        layers=layers,
    )


def _affine(
    cx: float = 0.5,
    cy: float = 0.5,
    scale: float = 0.4,
    rotation: float = 0.0,
    aspect: float = 1.0,
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


def _layer_tree(marker_id: str = "marker-1") -> MapLayerNode:
    leaf = MapLayerNode(
        name="Leaf",
        layer_type="marker",
        id=marker_id,
        attributes={"notes": "at the crossroads"},
    )
    group = MapLayerNode(
        name="Settlements",
        layer_type="group",
        id="group-1",
        children=[leaf],
    )
    return MapLayerNode(
        name="root",
        layer_type="group",
        id="root",
        children=[group],
    )


def _make_repo(
    master_map: Map,
    all_maps: list,
    marker: Marker | None = None,
) -> MagicMock:
    repo = MagicMock()
    repo.get_marker_by_composite.return_value = marker
    repo.get_map.return_value = master_map
    repo.get_all_maps.return_value = all_maps
    return repo


# ---------------------------------------------------------------------------
# Baseline: nesting_service=None preserves existing behaviour
# ---------------------------------------------------------------------------


class TestNoNestingService:
    def test_build_returns_none_when_no_marker(self):
        master = _make_map("m1", "World", MAP_ROLE_MASTER, layers=_layer_tree())
        repo = _make_repo(master, [master], marker=None)
        builder = SpatialContextBuilder(repo, nesting_service=None)
        result = builder.build("entity-1", "entity", "m1")
        assert result is None

    def test_build_returns_context_when_marker_has_notes(self):
        marker = _make_marker(0.5, 0.5)
        master = _make_map("m1", "World", MAP_ROLE_MASTER, layers=_layer_tree("marker-1"))
        repo = _make_repo(master, [master], marker=marker)
        builder = SpatialContextBuilder(repo, nesting_service=None)
        result = builder.build("entity-1", "entity", "m1")
        assert result is not None
        assert "Detail map available" not in result


# ---------------------------------------------------------------------------
# Advisory appended when marker is inside a child footprint
# ---------------------------------------------------------------------------


class TestDetailAdvisory:
    def _builder_with_children(
        self,
        marker: Marker,
        master: Map,
        children: list,
        service: MapNestingService | None = None,
    ) -> SpatialContextBuilder:
        all_maps = [master] + children
        repo = _make_repo(master, all_maps, marker=marker)
        svc = service if service is not None else MapNestingService()
        return SpatialContextBuilder(repo, nesting_service=svc)

    def test_advisory_added_when_marker_inside_footprint(self):
        marker = _make_marker(0.5, 0.5)  # at centre
        master = _make_map("m1", "World", MAP_ROLE_MASTER, layers=_layer_tree("marker-1"))
        # Large footprint centred at (0.5, 0.5): scale=0.8 → covers most of [0,1]²
        reg = _affine(cx=0.5, cy=0.5, scale=0.8)
        child = _make_map("d1", "Capital", MAP_ROLE_DETAIL, "m1", reg)
        builder = self._builder_with_children(marker, master, [child])
        result = builder.build("entity-1", "entity", "m1")
        assert result is not None
        assert "Detail map available: Capital" in result

    def test_advisory_not_added_when_marker_outside_footprint(self):
        marker = _make_marker(0.01, 0.01)  # near corner
        master = _make_map("m1", "World", MAP_ROLE_MASTER, layers=_layer_tree("marker-1"))
        # Small footprint at centre
        reg = _affine(cx=0.5, cy=0.5, scale=0.1)
        child = _make_map("d1", "Capital", MAP_ROLE_DETAIL, "m1", reg)
        builder = self._builder_with_children(marker, master, [child])
        result = builder.build("entity-1", "entity", "m1")
        if result is not None:
            assert "Detail map available" not in result

    def test_no_advisory_when_active_map_is_detail(self):
        """Decision 5: detail map active → active map's context wins."""
        marker = _make_marker(0.5, 0.5)
        detail = _make_map(
            "d1", "Capital", MAP_ROLE_DETAIL, "m1",
            _affine(), layers=_layer_tree("marker-1")
        )
        repo = _make_repo(detail, [detail], marker=marker)
        builder = SpatialContextBuilder(repo, nesting_service=MapNestingService())
        result = builder.build("entity-1", "entity", "d1")
        if result is not None:
            assert "Detail map available" not in result

    def test_no_advisory_for_plain_map(self):
        marker = _make_marker(0.5, 0.5)
        plain = _make_map("p1", "Dungeon", layers=_layer_tree("marker-1"))
        repo = _make_repo(plain, [plain], marker=marker)
        builder = SpatialContextBuilder(repo, nesting_service=MapNestingService())
        result = builder.build("entity-1", "entity", "p1")
        if result is not None:
            assert "Detail map available" not in result

    def test_no_advisory_when_child_has_no_registration(self):
        marker = _make_marker(0.5, 0.5)
        master = _make_map("m1", "World", MAP_ROLE_MASTER, layers=_layer_tree("marker-1"))
        # Child without registration dict in attributes
        child = _make_map("d1", "Lost City", MAP_ROLE_DETAIL, "m1")
        builder = self._builder_with_children(marker, master, [child])
        result = builder.build("entity-1", "entity", "m1")
        if result is not None:
            assert "Detail map available" not in result

    def test_malformed_registration_skipped_silently(self):
        marker = _make_marker(0.5, 0.5)
        master = _make_map("m1", "World", MAP_ROLE_MASTER, layers=_layer_tree("marker-1"))
        bad_reg = {"mode": "aspect_locked_affine", "scale_norm": -1}
        child = _make_map("d1", "Broken", MAP_ROLE_DETAIL, "m1", bad_reg)
        builder = self._builder_with_children(marker, master, [child])
        # Must not raise; just silently skip the broken child.
        result = builder.build("entity-1", "entity", "m1")
        if result is not None:
            assert "Detail map available" not in result

    def test_first_hit_wins_with_multiple_children(self):
        marker = _make_marker(0.5, 0.5)
        master = _make_map("m1", "World", MAP_ROLE_MASTER, layers=_layer_tree("marker-1"))
        # Both children cover the centre — first child should be reported.
        reg = _affine(cx=0.5, cy=0.5, scale=0.8)
        c1 = _make_map("d1", "Alpha District", MAP_ROLE_DETAIL, "m1", reg)
        c2 = _make_map("d2", "Beta Sector", MAP_ROLE_DETAIL, "m1", reg)
        builder = self._builder_with_children(marker, master, [c1, c2])
        result = builder.build("entity-1", "entity", "m1")
        assert result is not None
        assert "Detail map available:" in result
        # Exactly one advisory line.
        advisory_lines = [ln for ln in result.splitlines() if "Detail map available" in ln]
        assert len(advisory_lines) == 1

    def test_advisory_appended_after_existing_context(self):
        """Advisory appears as the last line of the [Spatial Context] block."""
        marker = _make_marker(0.5, 0.5)
        master = _make_map("m1", "World", MAP_ROLE_MASTER, layers=_layer_tree("marker-1"))
        reg = _affine(cx=0.5, cy=0.5, scale=0.8)
        child = _make_map("d1", "Inner City", MAP_ROLE_DETAIL, "m1", reg)
        builder = self._builder_with_children(marker, master, [child])
        result = builder.build("entity-1", "entity", "m1")
        assert result is not None
        lines = result.splitlines()
        assert lines[0] == "[Spatial Context]"
        assert "Detail map available: Inner City" in lines[-1]
