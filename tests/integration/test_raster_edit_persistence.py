"""Integration tests for raster editing persistence.

Covers the full cycle: create layer → paint/edit → persist → reload →
verify data is intact.  Uses temp files + in-memory DB.
"""

import tempfile
from pathlib import Path

import numpy as np
import pytest

from src.commands.raster_commands import (
    CreateRasterLayerCommand,
    SetRasterMappingCommand,
)
from src.core.map import Map, MapLayerNode
from src.gui.widgets.map.map_data_buffer import ColorEntry, ColorMap, MapDataBuffer
from src.services.db_service import DatabaseService

# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def db_service():
    """In-memory database service."""
    svc = DatabaseService(":memory:")
    svc.connect()
    yield svc
    svc.close()


@pytest.fixture
def world_dir():
    """Temporary directory acting as world root."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def map_obj(db_service):
    """A persisted map in the DB."""
    root = MapLayerNode(name="Root", layer_type="group")
    m = Map(
        name="Test Map",
        image_path="assets/maps/test.png",
        layers=root,
    )
    attrs = dict(m.attributes)
    attrs["layers"] = root.to_dict()
    m.attributes = attrs
    db_service.map_repo.insert_map(m)
    return m


# ── paint-persist-reload cycle ─────────────────────────────────────────


class TestPaintPersistReload:
    """Create a raster, paint on it, save to disk, reload, verify edits."""

    def test_paint_and_reload_preserves_buffer(self, db_service, map_obj, world_dir):
        """Painting the buffer, saving to disk, and loading from disk must round-trip."""
        cmd = CreateRasterLayerCommand(
            map_id=map_obj.id,
            name="Biome",
            width=64,
            height=64,
            mode="discrete",
            default_value=0,
            world_root=world_dir,
        )
        result = cmd.execute(db_service)
        assert result.success
        file_path = result.data["file_path"]
        abs_path = str(Path(world_dir) / file_path)

        # Load the buffer from disk, paint on it, save it back
        buf = MapDataBuffer.from_file(abs_path)
        buf.paint_brush(0.5, 0.5, radius_px=5, value=42, falloff=0.0)
        buf.save(abs_path)

        # Reload from disk — edits must be present
        reloaded = MapDataBuffer.from_file(abs_path)
        # Center pixel should be 42
        center_val = reloaded.get_value_at(0.5, 0.5)
        assert center_val == 42

    def test_flood_fill_persist_and_reload(self, db_service, map_obj, world_dir):
        """Flood-fill result must survive a save/load round-trip."""
        cmd = CreateRasterLayerCommand(
            map_id=map_obj.id,
            name="Zones",
            width=32,
            height=32,
            mode="discrete",
            default_value=0,
            world_root=world_dir,
        )
        result = cmd.execute(db_service)
        assert result.success
        abs_path = str(Path(world_dir) / result.data["file_path"])

        buf = MapDataBuffer.from_file(abs_path)
        buf.flood_fill(0.5, 0.5, 100)
        buf.save(abs_path)

        reloaded = MapDataBuffer.from_file(abs_path)
        assert np.all(reloaded.data == 100)

    def test_gradient_persist_and_reload(self, db_service, map_obj, world_dir):
        """Gradient paint result must survive a save/load round-trip."""
        cmd = CreateRasterLayerCommand(
            map_id=map_obj.id,
            name="Height",
            width=64,
            height=1,
            mode="continuous",
            default_value=0,
            world_root=world_dir,
        )
        result = cmd.execute(db_service)
        assert result.success
        abs_path = str(Path(world_dir) / result.data["file_path"])

        buf = MapDataBuffer.from_file(abs_path)
        buf.paint_gradient(0.0, 0.5, 1.0, 0.5, 0, 60000, width_px=0)
        buf.save(abs_path)

        reloaded = MapDataBuffer.from_file(abs_path)
        # Left edge near 0, right edge near 60000
        assert reloaded.data[0, 0] < 1000
        assert reloaded.data[0, -1] > 55000


# ── Mapping persistence roundtrip ─────────────────────────────────────


class TestMappingPersistence:
    """SetRasterMappingCommand persists and re-reads value→entity mappings."""

    def test_mapping_roundtrip(self, db_service, map_obj, world_dir):
        """Mapping stored by command is readable from DB on reload."""
        # Create a raster layer first
        create_cmd = CreateRasterLayerCommand(
            map_id=map_obj.id,
            name="Biome",
            width=32,
            height=32,
            mode="discrete",
            default_value=0,
            world_root=world_dir,
        )
        result = create_cmd.execute(db_service)
        assert result.success
        node_id = result.data["node_id"]

        new_mapping = {
            "mode": "exact",
            "mappings": [
                {"value": 1, "entity_id": "entity-tundra", "label": "Tundra"},
                {"value": 2, "entity_id": "entity-forest", "label": "Forest"},
            ],
        }
        map_cmd = SetRasterMappingCommand(
            map_id=map_obj.id,
            node_id=node_id,
            new_mapping=new_mapping,
            old_mapping={},
        )
        map_result = map_cmd.execute(db_service)
        assert map_result.success

        # Re-read the map from DB
        saved = db_service.map_repo.get_map(map_obj.id)
        raster_layers = (saved.attributes or {}).get("raster_layers", [])
        meta = next((r for r in raster_layers if r["node_id"] == node_id), None)
        assert meta is not None
        mapping = meta["value_entity_map"]
        assert mapping["mode"] == "exact"
        assert len(mapping["mappings"]) == 2
        assert mapping["mappings"][0]["entity_id"] == "entity-tundra"

    def test_mapping_undo_restores_old_value(self, db_service, map_obj, world_dir):
        """Undoing SetRasterMappingCommand restores the previous mapping."""
        create_cmd = CreateRasterLayerCommand(
            map_id=map_obj.id,
            name="Biome",
            width=16,
            height=16,
            mode="discrete",
            default_value=0,
            world_root=world_dir,
        )
        result = create_cmd.execute(db_service)
        assert result.success
        node_id = result.data["node_id"]

        old_mapping: dict = {}
        new_mapping = {"mode": "exact", "mappings": [{"value": 1, "entity_id": "e1"}]}

        map_cmd = SetRasterMappingCommand(
            map_id=map_obj.id,
            node_id=node_id,
            new_mapping=new_mapping,
            old_mapping=old_mapping,
        )
        map_cmd.execute(db_service)

        # Undo
        map_cmd.undo(db_service)

        saved = db_service.map_repo.get_map(map_obj.id)
        raster_layers = (saved.attributes or {}).get("raster_layers", [])
        meta = next((r for r in raster_layers if r["node_id"] == node_id), None)
        assert meta is not None
        # Should be restored to empty mapping
        assert meta["value_entity_map"] == {}

    def test_default_color_map_is_gradient(self, db_service, map_obj, world_dir):
        """New raster layer should have gradient color_map (not empty palette)."""
        cmd = CreateRasterLayerCommand(
            map_id=map_obj.id,
            name="Test",
            width=8,
            height=8,
            mode="discrete",
            default_value=0,
            world_root=world_dir,
        )
        result = cmd.execute(db_service)
        assert result.success

        saved = db_service.map_repo.get_map(map_obj.id)
        meta = (saved.attributes or {}).get("raster_layers", [])[0]
        cmap = ColorMap.from_dict(meta["color_map"])
        assert cmap.type == "gradient", (
            "Default color_map must be gradient, not empty palette"
        )

    def test_color_map_persisted_by_command(self, db_service, map_obj, world_dir):
        """SetRasterMappingCommand should persist the colour map alongside the mapping."""
        create_cmd = CreateRasterLayerCommand(
            map_id=map_obj.id,
            name="Climate",
            width=16,
            height=16,
            mode="discrete",
            default_value=0,
            world_root=world_dir,
        )
        result = create_cmd.execute(db_service)
        assert result.success
        node_id = result.data["node_id"]

        new_cmap_dict = ColorMap(
            type="palette",
            entries=[
                ColorEntry(value=1, color="#FF0000"),
                ColorEntry(value=2, color="#00FF00"),
            ],
        ).to_dict()
        new_mapping = {
            "mode": "exact",
            "mappings": [
                {"value": 1, "entity_id": "e-hot", "label": "Hot"},
            ],
        }
        cmd = SetRasterMappingCommand(
            map_id=map_obj.id,
            node_id=node_id,
            new_mapping=new_mapping,
            old_mapping={},
            new_color_map=new_cmap_dict,
            old_color_map=None,
        )
        assert cmd.execute(db_service).success

        saved = db_service.map_repo.get_map(map_obj.id)
        raster_layers = (saved.attributes or {}).get("raster_layers", [])
        meta = next(r for r in raster_layers if r["node_id"] == node_id)
        cmap = ColorMap.from_dict(meta["color_map"])
        assert cmap.type == "palette"
        assert cmap.entries[0].color == "#FF0000"

    def test_color_map_undo_restores_old_color_map(
        self, db_service, map_obj, world_dir
    ):
        """Undoing SetRasterMappingCommand restores the previous colour map."""
        create_cmd = CreateRasterLayerCommand(
            map_id=map_obj.id,
            name="Terrain",
            width=8,
            height=8,
            mode="discrete",
            default_value=0,
            world_root=world_dir,
        )
        result = create_cmd.execute(db_service)
        assert result.success
        node_id = result.data["node_id"]

        from src.gui.widgets.map.map_data_buffer import GradientStop

        old_cmap_dict = ColorMap(
            type="gradient",
            gradient_stops=[GradientStop(0.0, "#000000"), GradientStop(1.0, "#FFFFFF")],
        ).to_dict()
        new_cmap_dict = ColorMap(
            type="palette", entries=[ColorEntry(value=1, color="#AABBCC")]
        ).to_dict()

        # First set old color map
        SetRasterMappingCommand(
            map_id=map_obj.id,
            node_id=node_id,
            new_mapping={},
            old_mapping={},
            new_color_map=old_cmap_dict,
            old_color_map=None,
        ).execute(db_service)

        # Now set the new color map
        cmd = SetRasterMappingCommand(
            map_id=map_obj.id,
            node_id=node_id,
            new_mapping={"mode": "exact", "mappings": []},
            old_mapping={},
            new_color_map=new_cmap_dict,
            old_color_map=old_cmap_dict,
        )
        cmd.execute(db_service)

        # Undo should restore old color map
        cmd.undo(db_service)

        saved = db_service.map_repo.get_map(map_obj.id)
        raster_layers = (saved.attributes or {}).get("raster_layers", [])
        meta = next(r for r in raster_layers if r["node_id"] == node_id)
        cmap = ColorMap.from_dict(meta["color_map"])
        assert cmap.type == "gradient"


# ── Session-restart persistence ────────────────────────────────────────


class TestSessionRestartPersistence:
    """Raster data (PNG + palette + VEM) must survive a full DB close/re-open.

    Uses a *file-based* SQLite database to simulate a real session restart.
    """

    def test_restart_preserves_raster_layer(self, world_dir):
        """Raster layer metadata must be intact after DB close and re-open."""
        import os

        db_path = os.path.join(world_dir, "world.kraken")

        # ── Session 1 ────────────────────────────────────────────────
        svc1 = DatabaseService(db_path)
        svc1.connect()

        root = MapLayerNode(name="Root", layer_type="group")
        m = Map(name="World", image_path="map.png", layers=root)
        m.attributes = {"layers": root.to_dict()}
        svc1.map_repo.insert_map(m)
        map_id = m.id

        cmd = CreateRasterLayerCommand(
            map_id=map_id,
            name="Biomes",
            width=32,
            height=32,
            mode="discrete",
            default_value=0,
            world_root=world_dir,
        )
        result = cmd.execute(svc1)
        assert result.success
        node_id = result.data["node_id"]
        svc1.close()

        # ── Session 2 ────────────────────────────────────────────────
        svc2 = DatabaseService(db_path)
        svc2.connect()
        reloaded = svc2.map_repo.get_map(map_id)
        assert reloaded is not None
        raster_layers = (reloaded.attributes or {}).get("raster_layers", [])
        assert len(raster_layers) == 1, "Raster layer must survive DB close/re-open"
        assert raster_layers[0]["node_id"] == node_id
        svc2.close()

    def test_restart_preserves_palette(self, world_dir):
        """Palette (color_map) must be readable from DB after restart."""
        import os

        db_path = os.path.join(world_dir, "world.kraken")

        svc1 = DatabaseService(db_path)
        svc1.connect()

        root = MapLayerNode(name="Root", layer_type="group")
        m = Map(name="World", image_path="map.png", layers=root)
        m.attributes = {"layers": root.to_dict()}
        svc1.map_repo.insert_map(m)
        map_id = m.id

        create_cmd = CreateRasterLayerCommand(
            map_id=map_id,
            name="Climate",
            width=32,
            height=32,
            mode="discrete",
            default_value=0,
            world_root=world_dir,
        )
        result = create_cmd.execute(svc1)
        assert result.success
        node_id = result.data["node_id"]

        new_cmap_dict = ColorMap(
            type="palette",
            entries=[ColorEntry(value=1, color="#FF0000")],
        ).to_dict()
        set_cmd = SetRasterMappingCommand(
            map_id=map_id,
            node_id=node_id,
            new_mapping={"mode": "exact", "mappings": [{"value": 1, "label": "Hot"}]},
            old_mapping={},
            new_color_map=new_cmap_dict,
            old_color_map=None,
        )
        assert set_cmd.execute(svc1).success
        svc1.close()

        # ── Session 2 ────────────────────────────────────────────────
        svc2 = DatabaseService(db_path)
        svc2.connect()
        reloaded = svc2.map_repo.get_map(map_id)
        raster_layers = (reloaded.attributes or {}).get("raster_layers", [])
        assert len(raster_layers) == 1
        meta = raster_layers[0]
        cmap = ColorMap.from_dict(meta["color_map"])
        assert cmap.type == "palette", "Palette type must persist across restart"
        assert cmap.entries[0].color == "#FF0000", "Palette colour must persist"
        svc2.close()

    def test_restart_preserves_pixel_data(self, world_dir):
        """Painted pixel data (PNG) must be readable after DB close/re-open."""
        import os
        from pathlib import Path

        db_path = os.path.join(world_dir, "world.kraken")

        svc1 = DatabaseService(db_path)
        svc1.connect()

        root = MapLayerNode(name="Root", layer_type="group")
        m = Map(name="World", image_path="map.png", layers=root)
        m.attributes = {"layers": root.to_dict()}
        svc1.map_repo.insert_map(m)
        map_id = m.id

        create_cmd = CreateRasterLayerCommand(
            map_id=map_id,
            name="Height",
            width=64,
            height=64,
            mode="continuous",
            default_value=0,
            world_root=world_dir,
        )
        result = create_cmd.execute(svc1)
        assert result.success
        abs_path = str(Path(world_dir) / result.data["file_path"])

        buf = MapDataBuffer.from_file(abs_path)
        buf.paint_brush(0.5, 0.5, radius_px=5, value=42, falloff=0.0)
        buf.save(abs_path)
        svc1.close()

        # ── Session 2 ────────────────────────────────────────────────
        reload_buf = MapDataBuffer.from_file(abs_path)
        center = reload_buf.get_value_at(0.5, 0.5)
        assert center == 42, "Painted pixel value must persist across restart"
