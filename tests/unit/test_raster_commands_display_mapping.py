"""Tests for display-mapping parameters on CreateRasterLayerCommand.

Covers the plumbing that carries real-world value-range parameters from
the import dialog into the stored ``color_map`` of a newly created raster
layer.
"""

from __future__ import annotations

import tempfile
from typing import Generator

import pytest

from src.commands.raster_commands import CreateRasterLayerCommand
from src.core.map import Map, MapLayerNode
from src.services.db_service import DatabaseService


@pytest.fixture
def world_dir() -> Generator[str, None, None]:
    """Provide a temporary world root directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def map_with_layers(db_service: DatabaseService) -> Map:
    """Insert a map with a basic layer tree into the DB."""
    root = MapLayerNode(name="Root", layer_type="group")
    map_obj = Map(
        name="Test Map",
        image_path="assets/maps/test.png",
        layers=root,
    )
    attrs = dict(map_obj.attributes)
    attrs["layers"] = root.to_dict()
    map_obj.attributes = attrs
    db_service.map_repo.insert_map(map_obj)
    return map_obj


def _get_raster_color_map(
    db_service: DatabaseService,
    map_id: str,
    node_id: str,
) -> dict:
    """Fetch the color_map sub-dict for the given raster layer."""
    saved = db_service.map_repo.get_map(map_id)
    assert saved is not None
    raster_layers = (saved.attributes or {}).get("raster_layers", [])
    for r in raster_layers:
        if r.get("node_id") == node_id:
            return r.get("color_map") or {}
    raise AssertionError(f"Raster layer {node_id!r} not found")


# ---------------------------------------------------------------------------
# Constructor accepts display-mapping params
# ---------------------------------------------------------------------------


def test_command_accepts_display_mapping_params(world_dir):
    """Constructor must accept optional display_min/max/unit/format/scale."""
    cmd = CreateRasterLayerCommand(
        map_id="m1",
        name="DEM",
        width=32,
        height=32,
        mode="continuous",
        world_root=world_dir,
        display_min=-4000.0,
        display_max=8000.0,
        unit="m",
        format_str="{:.0f}",
        scale="linear",
    )
    assert cmd.display_min == -4000.0
    assert cmd.display_max == 8000.0
    assert cmd.unit == "m"
    assert cmd.format_str == "{:.0f}"
    assert cmd.scale == "linear"


def test_command_display_params_default_to_none(world_dir):
    """Omitting the new params yields None / defaults (backward-compat)."""
    cmd = CreateRasterLayerCommand(
        map_id="m1",
        name="X",
        width=16,
        height=16,
        world_root=world_dir,
    )
    assert cmd.display_min is None
    assert cmd.display_max is None
    assert cmd.unit == ""
    assert cmd.format_str == ""
    assert cmd.scale == ""


# ---------------------------------------------------------------------------
# Execute: display mapping lands in persisted color_map
# ---------------------------------------------------------------------------


def test_execute_writes_display_mapping_into_color_map(
    db_service, map_with_layers, world_dir
):
    """display_min/max/unit should be persisted in color_map after execute."""
    cmd = CreateRasterLayerCommand(
        map_id=map_with_layers.id,
        name="DEM",
        width=32,
        height=32,
        mode="continuous",
        world_root=world_dir,
        display_min=-4000.0,
        display_max=8000.0,
        unit="m",
        format_str="{:.0f}",
        scale="linear",
    )
    result = cmd.execute(db_service)
    assert result.success, result.message

    cmap = _get_raster_color_map(db_service, map_with_layers.id, result.data["node_id"])
    assert cmap.get("display_min") == pytest.approx(-4000.0)
    assert cmap.get("display_max") == pytest.approx(8000.0)
    assert cmap.get("unit") == "m"


def test_execute_without_display_mapping_omits_fields(
    db_service, map_with_layers, world_dir
):
    """If display_min is None, the color_map must not carry a display_min key."""
    cmd = CreateRasterLayerCommand(
        map_id=map_with_layers.id,
        name="Plain",
        width=16,
        height=16,
        mode="continuous",
        world_root=world_dir,
    )
    result = cmd.execute(db_service)
    assert result.success, result.message

    cmap = _get_raster_color_map(db_service, map_with_layers.id, result.data["node_id"])
    assert "display_min" not in cmap
    assert "display_max" not in cmap
    # unit/format_str/scale default to "" and are omitted by ColorMap.to_dict
    assert "unit" not in cmap


def test_execute_log_scale_propagates(db_service, map_with_layers, world_dir):
    """scale='log' must round-trip through the persisted color_map."""
    cmd = CreateRasterLayerCommand(
        map_id=map_with_layers.id,
        name="Rainfall",
        width=16,
        height=16,
        mode="continuous",
        world_root=world_dir,
        display_min=1.0,
        display_max=10000.0,
        unit="mm",
        format_str="{:.0f}",
        scale="log",
    )
    result = cmd.execute(db_service)
    assert result.success

    cmap = _get_raster_color_map(db_service, map_with_layers.id, result.data["node_id"])
    assert cmap.get("scale") == "log"


# ---------------------------------------------------------------------------
# Serialization round-trip (undo/redo persistence)
# ---------------------------------------------------------------------------


def test_to_dict_from_dict_roundtrip_preserves_display_mapping(world_dir):
    """Serialising the command preserves display_* fields for undo/redo."""
    cmd = CreateRasterLayerCommand(
        map_id="m1",
        name="DEM",
        width=32,
        height=32,
        mode="continuous",
        world_root=world_dir,
        display_min=-4000.0,
        display_max=8000.0,
        unit="m",
        format_str="{:.1f}",
        scale="log",
    )
    restored = CreateRasterLayerCommand.from_dict(cmd.to_dict())
    assert restored.display_min == -4000.0
    assert restored.display_max == 8000.0
    assert restored.unit == "m"
    assert restored.format_str == "{:.1f}"
    assert restored.scale == "log"


def test_from_dict_without_display_keys_is_backward_compatible():
    """Old serialized commands (no display_* keys) still deserialise."""
    # Legacy dict — missing all display_* keys
    legacy = {
        "map_id": "m1",
        "name": "Legacy",
        "width": 8,
        "height": 8,
        "mode": "continuous",
        "default_value": 0,
        "world_root": "",
        "node_id": "n1",
        "file_path": "",
    }
    cmd = CreateRasterLayerCommand.from_dict(legacy)
    assert cmd.display_min is None
    assert cmd.display_max is None
    assert cmd.unit == ""


# ---------------------------------------------------------------------------
# Import-path inference fallback (Phase 4)
# ---------------------------------------------------------------------------


def _make_geotiff_with_stats(path: str) -> None:
    """Helper: write a float TIFF with GDAL_METADATA statistics."""
    import numpy as np
    from PIL import Image as PilImage
    from PIL import TiffImagePlugin

    arr = np.full((8, 8), 1.0, dtype=np.float32)
    extra = TiffImagePlugin.ImageFileDirectory_v2()
    extra[42112] = (
        '<GDALMetadata>'
        '<Item name="STATISTICS_MINIMUM">-4000</Item>'
        '<Item name="STATISTICS_MAXIMUM">8000</Item>'
        '<Item name="UNITTYPE">metre</Item>'
        '</GDALMetadata>'
    )
    PilImage.fromarray(arr, mode="F").save(path, tiffinfo=extra)


def _make_plain_float_tiff(path: str, lo: float, hi: float) -> None:
    """Helper: float TIFF with raw pixel values spanning lo..hi (no tags)."""
    import numpy as np
    from PIL import Image as PilImage

    arr = np.linspace(lo, hi, 64, dtype=np.float32).reshape(8, 8)
    PilImage.fromarray(arr, mode="F").save(path)


def test_import_geotiff_auto_populates_display_mapping(
    db_service, map_with_layers, world_dir, tmp_path
):
    """Importing a GeoTIFF with stats, without explicit display_min, infers them."""
    geotiff = str(tmp_path / "dem.tif")
    _make_geotiff_with_stats(geotiff)

    cmd = CreateRasterLayerCommand(
        map_id=map_with_layers.id,
        name="DEM",
        width=8,
        height=8,
        mode="continuous",
        world_root=world_dir,
        import_path=geotiff,
        # no display_min/max supplied — command should infer
    )
    result = cmd.execute(db_service)
    assert result.success, result.message

    cmap = _get_raster_color_map(db_service, map_with_layers.id, result.data["node_id"])
    assert cmap.get("display_min") == pytest.approx(-4000.0)
    assert cmap.get("display_max") == pytest.approx(8000.0)
    assert cmap.get("unit") == "metre"


def test_import_float_tiff_without_metadata_uses_pixel_range(
    db_service, map_with_layers, world_dir, tmp_path
):
    """Float TIFF without GDAL tags: pixel min/max becomes display_min/max."""
    ftiff = str(tmp_path / "raw.tif")
    _make_plain_float_tiff(ftiff, lo=-1.5, hi=3.25)

    cmd = CreateRasterLayerCommand(
        map_id=map_with_layers.id,
        name="Raw float",
        width=8,
        height=8,
        mode="continuous",
        world_root=world_dir,
        import_path=ftiff,
    )
    result = cmd.execute(db_service)
    assert result.success, result.message

    cmap = _get_raster_color_map(db_service, map_with_layers.id, result.data["node_id"])
    assert cmap.get("display_min") == pytest.approx(-1.5, rel=1e-3)
    assert cmap.get("display_max") == pytest.approx(3.25, rel=1e-3)


def test_explicit_display_params_override_inference(
    db_service, map_with_layers, world_dir, tmp_path
):
    """User-supplied display_min/max must win over inferred metadata."""
    geotiff = str(tmp_path / "dem.tif")
    _make_geotiff_with_stats(geotiff)  # would infer -4000..8000

    cmd = CreateRasterLayerCommand(
        map_id=map_with_layers.id,
        name="Override",
        width=8,
        height=8,
        mode="continuous",
        world_root=world_dir,
        import_path=geotiff,
        display_min=0.0,
        display_max=100.0,
        unit="ft",
    )
    result = cmd.execute(db_service)
    assert result.success

    cmap = _get_raster_color_map(db_service, map_with_layers.id, result.data["node_id"])
    assert cmap.get("display_min") == pytest.approx(0.0)
    assert cmap.get("display_max") == pytest.approx(100.0)
    assert cmap.get("unit") == "ft"


def test_discrete_import_does_not_auto_infer(
    db_service, map_with_layers, world_dir, tmp_path
):
    """Discrete mode rasters must not get display mapping (no scalar meaning)."""
    ftiff = str(tmp_path / "discrete.tif")
    _make_plain_float_tiff(ftiff, lo=0, hi=10)

    cmd = CreateRasterLayerCommand(
        map_id=map_with_layers.id,
        name="Cats",
        width=8,
        height=8,
        mode="discrete",
        world_root=world_dir,
        import_path=ftiff,
    )
    result = cmd.execute(db_service)
    assert result.success

    cmap = _get_raster_color_map(db_service, map_with_layers.id, result.data["node_id"])
    assert "display_min" not in cmap
    assert "display_max" not in cmap
