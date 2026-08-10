"""Unit tests for SpatialContextBuilder.

These tests exercise the quality gate, coordinate-to-qualitative conversion,
layer-tree traversal, raster VEM sampling, and distance suppression logic
in isolation. MapRepository is mocked throughout; no database is required.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest
from PIL import Image as PilImage

from src.app.constants import MAP_DEFAULT_WIDTH_METERS
from src.core.feature_geometry_state import FeatureGeometryState
from src.core.map import Map, MapLayerNode
from src.core.marker import Marker
from src.services.spatial_context_builder import SpatialContextBuilder

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _make_marker(
    map_id: str = "map-1",
    object_id: str = "entity-1",
    object_type: str = "entity",
    x: float = 0.5,
    y: float = 0.5,
    label: str = "Target",
    marker_id: str = "marker-1",
) -> Marker:
    return Marker(
        id=marker_id,
        map_id=map_id,
        object_id=object_id,
        object_type=object_type,
        x=x,
        y=y,
        label=label,
    )


def _make_map(
    map_id: str = "map-1",
    name: str = "Northern Continent",
    attributes: dict | None = None,
    layers: MapLayerNode | None = None,
) -> Map:
    return Map(
        id=map_id,
        name=name,
        image_path="maps/northern.png",
        attributes=attributes or {},
        layers=layers,
    )


def _layer_tree_with_marker(
    marker_id: str,
    group_name: str = "Default",
    group_notes: str = "",
    leaf_notes: str = "",
) -> MapLayerNode:
    """Build a minimal layer tree with a single leaf under one group."""
    leaf_attrs = {"notes": leaf_notes} if leaf_notes else {}
    group_attrs = {"notes": group_notes} if group_notes else {}
    leaf = MapLayerNode(
        name="Target",
        layer_type="marker",
        id=marker_id,
        attributes=leaf_attrs,
    )
    group = MapLayerNode(
        name=group_name,
        layer_type="group",
        id="group-1",
        children=[leaf],
        attributes=group_attrs,
    )
    return MapLayerNode(
        name="Layers",
        layer_type="group",
        id="root",
        children=[group],
    )


def _write_discrete_raster(tmp_path: Path, filename: str = "biome.png") -> Path:
    """Create a 10x10 single-channel raster with three regions.

    Left third:   value 1
    Middle third: value 2
    Right third:  value 3
    """
    arr = np.zeros((10, 10), dtype=np.uint8)
    arr[:, 0:3] = 1
    arr[:, 3:7] = 2
    arr[:, 7:10] = 3
    img = PilImage.fromarray(arr, mode="L")
    path = tmp_path / filename
    img.save(str(path))
    return path


# ---------------------------------------------------------------------------
# Quality-gate and primary-map rules
# ---------------------------------------------------------------------------


def test_returns_none_when_active_map_id_missing() -> None:
    repo = MagicMock()
    builder = SpatialContextBuilder(repo)
    assert builder.build("entity-1", "entity", active_map_id=None) is None
    repo.get_marker_by_composite.assert_not_called()


def test_returns_none_when_entity_has_no_marker_on_active_map() -> None:
    repo = MagicMock()
    repo.get_marker_by_composite.return_value = None
    builder = SpatialContextBuilder(repo)
    assert builder.build("entity-1", "entity", active_map_id="map-1") is None
    repo.get_marker_by_composite.assert_called_once_with(
        "map-1", "entity-1", "entity"
    )


def test_returns_none_when_quality_gate_fails() -> None:
    """No layer notes, no raster facts, no named co-located entities."""
    marker = _make_marker()
    map_obj = _make_map(layers=_layer_tree_with_marker(marker.id))
    repo = MagicMock()
    repo.get_marker_by_composite.return_value = marker
    repo.get_map.return_value = map_obj
    repo.get_markers_by_map.return_value = [marker]  # only self

    builder = SpatialContextBuilder(repo)
    assert builder.build(marker.object_id, marker.object_type, "map-1") is None


# ---------------------------------------------------------------------------
# Signal-by-signal behaviour
# ---------------------------------------------------------------------------


def test_emits_context_with_layer_notes_only() -> None:
    marker = _make_marker()
    tree = _layer_tree_with_marker(
        marker.id,
        group_name="Mountain Passes",
        group_notes="Temperate uplands, contested border zone.",
    )
    map_obj = _make_map(layers=tree)

    repo = MagicMock()
    repo.get_marker_by_composite.return_value = marker
    repo.get_map.return_value = map_obj
    repo.get_markers_by_map.return_value = [marker]

    builder = SpatialContextBuilder(repo)
    result = builder.build(marker.object_id, marker.object_type, "map-1")

    assert result is not None
    assert "[Spatial Context]" in result
    assert 'map "Northern Continent"' in result
    assert 'layer "Mountain Passes"' in result
    assert "Temperate uplands" in result


def test_emits_context_with_co_located_entities_sorted_and_capped() -> None:
    marker = _make_marker(x=0.5, y=0.5, marker_id="center")
    # Seven others at increasing distances — builder should keep only 5 nearest.
    others = [
        Marker(
            id=f"m{i}",
            map_id="map-1",
            object_id=f"obj{i}",
            object_type="entity",
            x=0.5 + 0.01 * (i + 1),
            y=0.5,
            label=f"Place {i}",
        )
        for i in range(7)
    ]
    tree = _layer_tree_with_marker(marker.id)
    map_obj = _make_map(layers=tree)

    repo = MagicMock()
    repo.get_marker_by_composite.return_value = marker
    repo.get_map.return_value = map_obj
    repo.get_markers_by_map.return_value = [marker] + others

    builder = SpatialContextBuilder(repo)
    result = builder.build(marker.object_id, marker.object_type, "map-1")

    assert result is not None
    assert "Nearby:" in result
    # Closest 5 must appear; the two farthest must not.
    for i in range(5):
        assert f"Place {i}" in result
    assert "Place 5" not in result
    assert "Place 6" not in result


def test_skips_unnamed_co_located_markers() -> None:
    marker = _make_marker(marker_id="center", x=0.5, y=0.5)
    unnamed = Marker(
        id="m-unnamed",
        map_id="map-1",
        object_id="obj-x",
        object_type="entity",
        x=0.51,
        y=0.5,
        label="",
    )
    named = Marker(
        id="m-named",
        map_id="map-1",
        object_id="obj-y",
        object_type="entity",
        x=0.55,
        y=0.5,
        label="Thornwall Keep",
    )
    tree = _layer_tree_with_marker(marker.id)
    map_obj = _make_map(layers=tree)

    repo = MagicMock()
    repo.get_marker_by_composite.return_value = marker
    repo.get_map.return_value = map_obj
    repo.get_markers_by_map.return_value = [marker, unnamed, named]

    builder = SpatialContextBuilder(repo)
    result = builder.build(marker.object_id, marker.object_type, "map-1")

    assert result is not None
    assert "Thornwall Keep" in result
    assert "obj-x" not in result  # unnamed must never leak its object_id


# ---------------------------------------------------------------------------
# Distance handling
# ---------------------------------------------------------------------------


def test_uncalibrated_map_suppresses_distance_units() -> None:
    marker = _make_marker(x=0.5, y=0.5, marker_id="center")
    neighbour = Marker(
        id="m-n",
        map_id="map-1",
        object_id="obj-y",
        object_type="entity",
        x=0.55,
        y=0.5,
        label="Thornwall Keep",
    )
    tree = _layer_tree_with_marker(marker.id)
    # width_meters absent → uncalibrated
    map_obj = _make_map(layers=tree, attributes={})

    repo = MagicMock()
    repo.get_marker_by_composite.return_value = marker
    repo.get_map.return_value = map_obj
    repo.get_markers_by_map.return_value = [marker, neighbour]

    builder = SpatialContextBuilder(repo)
    result = builder.build(marker.object_id, marker.object_type, "map-1")

    assert result is not None
    assert "km" not in result
    assert " m " not in result  # space-delimited metres unit
    assert "m)" not in result


def test_default_width_is_treated_as_uncalibrated() -> None:
    marker = _make_marker(x=0.5, y=0.5, marker_id="center")
    neighbour = Marker(
        id="m-n",
        map_id="map-1",
        object_id="obj-y",
        object_type="entity",
        x=0.55,
        y=0.5,
        label="Thornwall Keep",
    )
    tree = _layer_tree_with_marker(marker.id)
    map_obj = _make_map(
        layers=tree, attributes={"width_meters": MAP_DEFAULT_WIDTH_METERS}
    )

    repo = MagicMock()
    repo.get_marker_by_composite.return_value = marker
    repo.get_map.return_value = map_obj
    repo.get_markers_by_map.return_value = [marker, neighbour]

    builder = SpatialContextBuilder(repo)
    result = builder.build(marker.object_id, marker.object_type, "map-1")

    assert result is not None
    assert "km" not in result


def test_calibrated_map_emits_distance_units() -> None:
    marker = _make_marker(x=0.5, y=0.5, marker_id="center")
    # 0.1 normalised units away on a 10km map → 1 km
    neighbour = Marker(
        id="m-n",
        map_id="map-1",
        object_id="obj-y",
        object_type="entity",
        x=0.6,
        y=0.5,
        label="Thornwall Keep",
    )
    tree = _layer_tree_with_marker(marker.id)
    map_obj = _make_map(layers=tree, attributes={"width_meters": 10_000.0})

    repo = MagicMock()
    repo.get_marker_by_composite.return_value = marker
    repo.get_map.return_value = map_obj
    repo.get_markers_by_map.return_value = [marker, neighbour]

    builder = SpatialContextBuilder(repo)
    result = builder.build(marker.object_id, marker.object_type, "map-1")

    assert result is not None
    assert "km" in result or " m " in result


# ---------------------------------------------------------------------------
# Raster VEM sampling
# ---------------------------------------------------------------------------


def test_raster_vem_hit_appears_in_context(tmp_path: Path) -> None:
    raster_path = _write_discrete_raster(tmp_path, "biome.png")
    marker = _make_marker(x=0.5, y=0.5, marker_id="center")  # middle region → value 2

    raster_meta = {
        "node_id": "raster-1",
        "file_path": raster_path.name,  # relative to world_root
        "mode": "discrete",
        "value_entity_map": {
            "mode": "exact",
            "mappings": [
                {"id": "a", "label": "Tundra", "value": 1},
                {"id": "b", "label": "Forest", "value": 2},
                {"id": "c", "label": "Desert", "value": 3},
            ],
        },
        "notes": "Biome classification (WWF scheme)",
    }
    # Register the raster layer's display name in the layer tree.
    raster_layer_node = MapLayerNode(
        name="Biome", layer_type="raster", id="raster-1"
    )
    leaf = MapLayerNode(name="Target", layer_type="marker", id=marker.id)
    root = MapLayerNode(
        name="Layers",
        layer_type="group",
        id="root",
        children=[
            MapLayerNode(
                name="Default",
                layer_type="group",
                id="group-1",
                children=[leaf],
            ),
            raster_layer_node,
        ],
    )
    map_obj = _make_map(
        layers=root, attributes={"raster_layers": [raster_meta]}
    )

    repo = MagicMock()
    repo.get_marker_by_composite.return_value = marker
    repo.get_map.return_value = map_obj
    repo.get_markers_by_map.return_value = [marker]

    builder = SpatialContextBuilder(repo, world_root=tmp_path)
    result = builder.build(marker.object_id, marker.object_type, "map-1")

    assert result is not None
    assert "Biome: Forest" in result
    assert "WWF" in result  # raster-level notes inlined


def test_raster_sampling_uses_dated_vector_anchor(tmp_path: Path) -> None:
    raster_path = _write_discrete_raster(tmp_path, "biome.png")
    marker = Marker(
        id="region",
        map_id="map-1",
        object_id="entity-1",
        object_type="entity",
        x=0.1,
        y=0.5,
        label="Border",
        feature_type="region",
        geometry=[
            {"x": 0.05, "y": 0.4},
            {"x": 0.15, "y": 0.4},
            {"x": 0.1, "y": 0.6},
        ],
    )
    raster_meta = {
        "node_id": "raster-1",
        "file_path": raster_path.name,
        "mode": "discrete",
        "value_entity_map": {
            "mode": "exact",
            "mappings": [
                {"id": "a", "label": "Tundra", "value": 1},
                {"id": "b", "label": "Forest", "value": 2},
                {"id": "c", "label": "Desert", "value": 3},
            ],
        },
    }
    tree = _layer_tree_with_marker(marker.id)
    tree.children.append(
        MapLayerNode(name="Biome", layer_type="raster", id="raster-1")
    )
    map_obj = _make_map(
        layers=tree, attributes={"raster_layers": [raster_meta]}
    )
    repo = MagicMock()
    repo.get_marker_by_composite.return_value = marker
    repo.get_map.return_value = map_obj
    repo.get_markers_by_map.return_value = [marker]
    state = FeatureGeometryState(
        marker_id=marker.id,
        effective_date=100.0,
        geometry=[
            {"x": 0.75, "y": 0.4},
            {"x": 0.85, "y": 0.4},
            {"x": 0.8, "y": 0.6},
        ],
        anchor_x=0.8,
        anchor_y=0.5,
    )
    geometry_repo = MagicMock()
    geometry_repo.get_states.return_value = [state]

    builder = SpatialContextBuilder(
        repo,
        world_root=tmp_path,
        feature_geometry_repo=geometry_repo,
    )
    base_result = builder.build(marker.object_id, marker.object_type, "map-1")
    dated_result = builder.build(
        marker.object_id, marker.object_type, "map-1", lore_date=100.0
    )

    assert base_result is not None and "Biome: Tundra" in base_result
    assert dated_result is not None and "Biome: Desert" in dated_result


def test_raster_layer_with_empty_vem_is_skipped(tmp_path: Path) -> None:
    raster_path = _write_discrete_raster(tmp_path, "biome.png")
    marker = _make_marker(x=0.5, y=0.5, marker_id="center")

    raster_meta = {
        "node_id": "raster-1",
        "file_path": raster_path.name,
        "mode": "discrete",
        "value_entity_map": {"mode": "exact", "mappings": []},  # empty
    }
    tree = _layer_tree_with_marker(marker.id)
    map_obj = _make_map(
        layers=tree, attributes={"raster_layers": [raster_meta]}
    )

    repo = MagicMock()
    repo.get_marker_by_composite.return_value = marker
    repo.get_map.return_value = map_obj
    repo.get_markers_by_map.return_value = [marker]

    builder = SpatialContextBuilder(repo, world_root=tmp_path)
    # With no other signals and empty VEM, quality gate should fail.
    assert builder.build(marker.object_id, marker.object_type, "map-1") is None


def test_name_lookup_callable_overrides_marker_label() -> None:
    marker = _make_marker(marker_id="center", x=0.5, y=0.5)
    neighbour = Marker(
        id="m-n",
        map_id="map-1",
        object_id="obj-y",
        object_type="entity",
        x=0.55,
        y=0.5,
        label="stale-label",
    )
    tree = _layer_tree_with_marker(marker.id)
    map_obj = _make_map(layers=tree)

    repo = MagicMock()
    repo.get_marker_by_composite.return_value = marker
    repo.get_map.return_value = map_obj
    repo.get_markers_by_map.return_value = [marker, neighbour]

    def lookup(object_id: str, object_type: str) -> str | None:
        if object_id == "obj-y":
            return "Fresh Name"
        return None

    builder = SpatialContextBuilder(repo, name_lookup=lookup)
    result = builder.build(marker.object_id, marker.object_type, "map-1")

    assert result is not None
    assert "Fresh Name" in result
    assert "stale-label" not in result


# ---------------------------------------------------------------------------
# Malformed / defensive input
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_raster",
    [
        None,
        "not-a-dict",
        {"node_id": "x"},  # missing file_path and vem
        {"node_id": "x", "file_path": "nope.png", "value_entity_map": "bad"},
    ],
)
def test_malformed_raster_entries_are_ignored(
    bad_raster: object, tmp_path: Path
) -> None:
    marker = _make_marker()
    tree = _layer_tree_with_marker(
        marker.id, group_name="Group A", group_notes="some notes"
    )
    map_obj = _make_map(
        layers=tree, attributes={"raster_layers": [bad_raster]}
    )
    repo = MagicMock()
    repo.get_marker_by_composite.return_value = marker
    repo.get_map.return_value = map_obj
    repo.get_markers_by_map.return_value = [marker]

    builder = SpatialContextBuilder(repo, world_root=tmp_path)
    result = builder.build(marker.object_id, marker.object_type, "map-1")
    # Layer notes still qualify the entity for the quality gate.
    assert result is not None
    assert "some notes" in result
