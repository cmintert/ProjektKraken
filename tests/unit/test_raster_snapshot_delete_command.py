"""Tests for RemoveRasterSnapshotCommand file + metadata lifecycle."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from src.commands.raster_commands import (
    CreateRasterLayerCommand,
    RemoveRasterSnapshotCommand,
)
from src.core.map import Map, MapLayerNode
from src.services.db_service import DatabaseService


@pytest.fixture
def db_service():
    """In-memory database service."""
    svc = DatabaseService(":memory:")
    svc.connect()
    yield svc
    svc.close()


@pytest.fixture
def world_dir():
    """Temporary world directory for raster files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def map_obj(db_service):
    """Persist a minimal map object and return it."""
    root = MapLayerNode(name="Root", layer_type="group")
    m = Map(name="Test Map", image_path="assets/maps/test.png", layers=root)
    attrs = dict(m.attributes)
    attrs["layers"] = root.to_dict()
    m.attributes = attrs
    db_service.map_repo.insert_map(m)
    return m


def test_remove_snapshot_command_execute_and_undo(db_service, world_dir, map_obj) -> None:
    """Execute should remove snapshot from DB+disk, undo should restore both."""
    create_cmd = CreateRasterLayerCommand(
        map_id=map_obj.id,
        name="Rainfall",
        width=8,
        height=8,
        mode="discrete",
        default_value=0,
        world_root=world_dir,
    )
    created = create_cmd.execute(db_service)
    assert created.success

    node_id = created.data["node_id"]
    base_rel = created.data["file_path"]
    base_abs = Path(world_dir) / base_rel
    snap_rel = f"rasters/{Path(base_rel).stem}_snap_12.00.png"
    snap_abs = Path(world_dir) / snap_rel
    snap_abs.parent.mkdir(parents=True, exist_ok=True)
    snap_abs.write_bytes(base_abs.read_bytes())

    loaded = db_service.map_repo.get_map(map_obj.id)
    layers = (loaded.attributes or {}).get("raster_layers", [])
    for rl in layers:
        if rl.get("node_id") == node_id:
            rl["snapshots"] = {"12.0": snap_rel}
            break
    loaded.attributes["raster_layers"] = layers
    db_service.map_repo.insert_map(loaded)

    cmd = RemoveRasterSnapshotCommand(
        map_id=map_obj.id,
        node_id=node_id,
        lore_date=12.0,
        world_root=world_dir,
        old_snapshots={"12.0": snap_rel},
    )

    result = cmd.execute(db_service)
    assert result.success
    assert not snap_abs.exists()

    after_delete = db_service.map_repo.get_map(map_obj.id)
    updated_layers = (after_delete.attributes or {}).get("raster_layers", [])
    target = next(rl for rl in updated_layers if rl.get("node_id") == node_id)
    assert "12.0" not in target.get("snapshots", {})

    cmd.undo(db_service)

    assert snap_abs.exists()
    after_undo = db_service.map_repo.get_map(map_obj.id)
    undone_layers = (after_undo.attributes or {}).get("raster_layers", [])
    target_after_undo = next(rl for rl in undone_layers if rl.get("node_id") == node_id)
    assert target_after_undo.get("snapshots", {}).get("12.0") == snap_rel
