"""Integration tests for raster layer command persistence.

Verifies that CreateRasterLayerCommand and DeleteRasterLayerCommand
correctly persist raster metadata in ``maps.attributes["raster_layers"]``
and manage the 16-bit PNG file on disk.
"""

import os
import tempfile
from pathlib import Path
from typing import Generator

import numpy as np
import pytest

from src.commands.raster_commands import (
    CreateRasterLayerCommand,
    DeleteRasterLayerCommand,
    StrokeRasterCommand,
)
from src.core.map import Map, MapLayerNode
from src.core.map_state import RasterPatch
from src.core.raster_grid import load_rgba_grid
from src.services.db_service import DatabaseService


@pytest.fixture
def world_dir() -> Generator[str, None, None]:
    """Provide a temporary directory as the world root."""
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
    # Persist layer tree in attributes
    attrs = dict(map_obj.attributes)
    attrs["layers"] = root.to_dict()
    map_obj.attributes = attrs
    db_service.map_repo.insert_map(map_obj)
    return map_obj


class TestCreateRasterLayerCommand:
    """Tests for CreateRasterLayerCommand."""

    def test_raster_metadata_saved_in_map_attributes(
        self, db_service, map_with_layers, world_dir
    ):
        """After execute, maps.attributes should contain raster_layers entry."""
        cmd = CreateRasterLayerCommand(
            map_id=map_with_layers.id,
            name="Biome Map",
            width=64,
            height=64,
            mode="discrete",
            default_value=0,
            world_root=world_dir,
        )
        result = cmd.execute(db_service)
        assert result.success, result.message

        # Re-read from DB
        saved_map = db_service.map_repo.get_map(map_with_layers.id)
        assert saved_map is not None

        raster_layers = saved_map.attributes.get("raster_layers", [])
        assert len(raster_layers) == 1
        meta = raster_layers[0]
        assert meta["node_id"] == result.data["node_id"]
        assert meta["resolution"] == [64, 64]
        assert meta["mode"] == "discrete"
        assert meta["default_value"] == 0

    def test_raster_file_created_on_disk(self, db_service, map_with_layers, world_dir):
        """The command should create a 16-bit PNG file in the world's rasters/ dir."""
        cmd = CreateRasterLayerCommand(
            map_id=map_with_layers.id,
            name="Height Map",
            width=32,
            height=32,
            world_root=world_dir,
        )
        result = cmd.execute(db_service)
        assert result.success

        file_path = result.data["file_path"]
        abs_path = os.path.join(world_dir, file_path)
        assert os.path.exists(abs_path)

    def test_layer_node_added_to_tree(self, db_service, map_with_layers, world_dir):
        """The raster layer node should appear in the map's layer tree."""
        cmd = CreateRasterLayerCommand(
            map_id=map_with_layers.id,
            name="Temperature",
            width=16,
            height=16,
            world_root=world_dir,
        )
        result = cmd.execute(db_service)
        assert result.success

        saved_map = db_service.map_repo.get_map(map_with_layers.id)
        assert saved_map.layers is not None
        raster_nodes = [
            c for c in saved_map.layers.children if c.layer_type == "raster"
        ]
        assert len(raster_nodes) == 1
        assert raster_nodes[0].name == "Temperature"
        assert raster_nodes[0].id == result.data["node_id"]

    def test_undo_removes_raster(self, db_service, map_with_layers, world_dir):
        """Undo should remove the file, the layer node, and the metadata."""
        cmd = CreateRasterLayerCommand(
            map_id=map_with_layers.id,
            name="To Delete",
            width=16,
            height=16,
            world_root=world_dir,
        )
        result = cmd.execute(db_service)
        assert result.success

        file_path = result.data["file_path"]
        abs_path = os.path.join(world_dir, file_path)
        assert os.path.exists(abs_path)

        # Undo
        cmd.undo(db_service)

        # File removed
        assert not os.path.exists(abs_path)

        # Metadata removed
        saved_map = db_service.map_repo.get_map(map_with_layers.id)
        raster_layers = saved_map.attributes.get("raster_layers", [])
        assert len(raster_layers) == 0

        # Layer node removed
        raster_nodes = [
            c for c in saved_map.layers.children if c.layer_type == "raster"
        ]
        assert len(raster_nodes) == 0


class TestDeleteRasterLayerCommand:
    """Tests for DeleteRasterLayerCommand."""

    def test_delete_removes_raster(self, db_service, map_with_layers, world_dir):
        """Delete should remove file, node, and metadata."""
        # First create a raster
        create_cmd = CreateRasterLayerCommand(
            map_id=map_with_layers.id,
            name="Doomed Layer",
            width=16,
            height=16,
            world_root=world_dir,
        )
        create_result = create_cmd.execute(db_service)
        assert create_result.success
        node_id = create_result.data["node_id"]
        file_path = create_result.data["file_path"]

        # Now delete
        del_cmd = DeleteRasterLayerCommand(
            map_id=map_with_layers.id,
            node_id=node_id,
            world_root=world_dir,
        )
        result = del_cmd.execute(db_service)
        assert result.success

        # Verify deletion
        saved_map = db_service.map_repo.get_map(map_with_layers.id)
        raster_layers = saved_map.attributes.get("raster_layers", [])
        assert len(raster_layers) == 0
        assert not os.path.exists(os.path.join(world_dir, file_path))

    def test_undo_delete_restores_raster(
        self, db_service: DatabaseService, map_with_layers: Map, world_dir: str
    ) -> None:
        """Undo of delete should restore file, node, and metadata."""
        create_cmd = CreateRasterLayerCommand(
            map_id=map_with_layers.id,
            name="Restorable",
            width=16,
            height=16,
            world_root=world_dir,
        )
        create_result = create_cmd.execute(db_service)
        assert create_result.success, f"Create failed: {create_result.message}"
        node_id = create_result.data["node_id"]
        file_path = create_result.data["file_path"]

        # Delete
        del_cmd = DeleteRasterLayerCommand(
            map_id=map_with_layers.id,
            node_id=node_id,
            world_root=world_dir,
        )
        del_cmd.execute(db_service)

        # Undo delete
        del_cmd.undo(db_service)

        # Verify restoration
        saved_map = db_service.map_repo.get_map(map_with_layers.id)
        raster_layers = saved_map.attributes.get("raster_layers", [])
        assert len(raster_layers) == 1
        assert raster_layers[0]["node_id"] == node_id
        assert os.path.exists(os.path.join(world_dir, file_path))


class TestCreateRasterLayerSerialization:
    """Tests for command serialisation."""

    def test_to_dict_from_dict_roundtrip(self):
        """Command should serialise and deserialise correctly."""
        cmd = CreateRasterLayerCommand(
            map_id="map-123",
            name="Test Layer",
            width=256,
            height=128,
            mode="continuous",
            default_value=100,
            world_root="/tmp/world",
        )
        d = cmd.to_dict()
        restored = CreateRasterLayerCommand.from_dict(d)
        assert restored.map_id == "map-123"
        assert restored.name == "Test Layer"
        assert restored.width == 256
        assert restored.height == 128
        assert restored.mode == "continuous"
        assert restored.default_value == 100


def test_rgba_stroke_persists_and_undoes(
    db_service: DatabaseService,
    map_with_layers: Map,
    world_dir: str,
) -> None:
    """RGBA tile patches use straight-alpha PNG persistence in both directions."""
    db_service.db_path = str(Path(world_dir) / "test.kraken")
    world_root = world_dir
    create = CreateRasterLayerCommand(
        map_id=map_with_layers.id,
        name="Visual overlay",
        width=4,
        height=4,
        mode="color",
        world_root=world_root,
    )
    created = create.execute(db_service)
    assert created.success, created.message
    node_id = created.data["node_id"]
    relative_path = created.data["file_path"]
    absolute_path = str(Path(world_root) / relative_path)
    before = load_rgba_grid(absolute_path)[1:3, 1:3].copy()
    after = np.full((2, 2, 4), (12, 34, 56, 78), dtype=np.uint8)
    patch = RasterPatch(
        map_id=map_with_layers.id,
        node_id=node_id,
        target_file=relative_path,
        region=(1, 1, 2, 2),
        shape=(2, 2, 4),
        dtype="uint8",
        before_data=before.tobytes(),
        after_data=after.tobytes(),
    )
    stroke = StrokeRasterCommand(
        map_id=map_with_layers.id,
        node_id=node_id,
        target_file=relative_path,
        patches=[patch],
    )

    result = stroke.execute(db_service)
    assert result.success, result.message
    assert np.array_equal(load_rgba_grid(absolute_path)[1:3, 1:3], after)

    undone = stroke.undo(db_service)
    assert undone.success, undone.message
    assert np.array_equal(load_rgba_grid(absolute_path)[1:3, 1:3], before)
