"""End-to-end integration test for raster display-mapping.

Exercises the full value-range pipeline:

    GeoTIFF on disk
      → RasterLayerDialog._apply_imported_file() pre-fills fields
      → dialog.result_data() payload
      → CreateRasterLayerCommand.execute() with those params
      → persisted color_map in DB carries display_min/max/unit
      → reloaded Map surfaces them downstream.

This guards the wiring between Phase 2 (inference), Phase 3 (command),
Phase 5 (dialog UI), and Phase 6 (handler) against future regressions.
"""

from __future__ import annotations

import tempfile
from typing import Generator

import numpy as np
import pytest
from PIL import Image as PilImage
from PIL import TiffImagePlugin
from pytestqt.qtbot import QtBot

from src.commands.raster_commands import CreateRasterLayerCommand
from src.core.map import Map, MapLayerNode
from src.gui.widgets.map.raster_layer_dialog import RasterLayerDialog
from src.services.db_service import DatabaseService


@pytest.fixture
def world_dir() -> Generator[str, None, None]:
    """Provide a temporary world root directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def map_obj(db_service: DatabaseService) -> Map:
    """Persist a simple map with a root layer group."""
    root = MapLayerNode(name="Root", layer_type="group")
    m = Map(name="E2E Map", image_path="assets/maps/e2e.png", layers=root)
    attrs = dict(m.attributes)
    attrs["layers"] = root.to_dict()
    m.attributes = attrs
    db_service.map_repo.insert_map(m)
    return m


def _write_geotiff(path: str, smin: float, smax: float, unit: str) -> None:
    """Write a float32 GeoTIFF with GDAL_METADATA statistics + UNITTYPE."""
    arr = np.full((8, 8), 1.0, dtype=np.float32)
    extra = TiffImagePlugin.ImageFileDirectory_v2()
    extra[42112] = (
        f'<GDALMetadata>'
        f'<Item name="STATISTICS_MINIMUM">{smin}</Item>'
        f'<Item name="STATISTICS_MAXIMUM">{smax}</Item>'
        f'<Item name="UNITTYPE">{unit}</Item>'
        f'</GDALMetadata>'
    )
    PilImage.fromarray(arr, mode="F").save(path, tiffinfo=extra)


def test_geotiff_to_persisted_color_map(
    qtbot: QtBot, db_service, map_obj, world_dir, tmp_path
) -> None:
    """Inferred DEM metadata reaches the persisted color_map via the dialog."""
    geotiff = str(tmp_path / "dem.tif")
    _write_geotiff(geotiff, smin=-4000.0, smax=8000.0, unit="metre")

    dlg = RasterLayerDialog()
    qtbot.addWidget(dlg)
    dlg._name_edit.setText("DEM")
    dlg._apply_imported_file(geotiff)

    assert dlg._mode_combo.currentData() == "continuous"
    data = dlg.result_data()
    assert data["display_min"] == pytest.approx(-4000.0)
    assert data["display_max"] == pytest.approx(8000.0)
    assert data["unit"] == "metre"

    cmd = CreateRasterLayerCommand(
        map_id=map_obj.id,
        name=data["name"],
        width=data["width"],
        height=data["height"],
        mode=data["mode"],
        default_value=data["default_value"],
        world_root=world_dir,
        import_path=data["import_path"],
        display_min=data["display_min"],
        display_max=data["display_max"],
        unit=data["unit"],
    )
    result = cmd.execute(db_service)
    assert result.success, result.message
    node_id = result.data["node_id"]

    saved = db_service.map_repo.get_map(map_obj.id)
    assert saved is not None
    raster_layers = (saved.attributes or {}).get("raster_layers", [])
    entry = next(r for r in raster_layers if r.get("node_id") == node_id)
    cmap = entry.get("color_map") or {}

    assert cmap.get("display_min") == pytest.approx(-4000.0)
    assert cmap.get("display_max") == pytest.approx(8000.0)
    assert cmap.get("unit") == "metre"


def test_user_override_beats_inference_end_to_end(
    qtbot: QtBot, db_service, map_obj, world_dir, tmp_path
) -> None:
    """User edits in the dialog win over inferred metadata all the way to DB."""
    geotiff = str(tmp_path / "dem.tif")
    _write_geotiff(geotiff, smin=-4000.0, smax=8000.0, unit="metre")

    dlg = RasterLayerDialog()
    qtbot.addWidget(dlg)
    dlg._name_edit.setText("Override")
    dlg._apply_imported_file(geotiff)

    dlg._display_min_edit.setText("0")
    dlg._display_max_edit.setText("100")
    dlg._display_unit_edit.setText("ft")

    data = dlg.result_data()
    cmd = CreateRasterLayerCommand(
        map_id=map_obj.id,
        name=data["name"],
        width=data["width"],
        height=data["height"],
        mode=data["mode"],
        default_value=data["default_value"],
        world_root=world_dir,
        import_path=data["import_path"],
        display_min=data["display_min"],
        display_max=data["display_max"],
        unit=data["unit"],
    )
    result = cmd.execute(db_service)
    assert result.success, result.message
    node_id = result.data["node_id"]

    saved = db_service.map_repo.get_map(map_obj.id)
    raster_layers = (saved.attributes or {}).get("raster_layers", [])
    cmap = next(
        r for r in raster_layers if r.get("node_id") == node_id
    ).get("color_map") or {}

    assert cmap.get("display_min") == pytest.approx(0.0)
    assert cmap.get("display_max") == pytest.approx(100.0)
    assert cmap.get("unit") == "ft"
