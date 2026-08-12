"""Focused tests for the unified map/raster foundation."""

from pathlib import Path

import numpy as np
from PIL import Image

from src.commands.raster_commands import StrokeRasterCommand
from src.commands.registry import get_command_types
from src.core.map_state import MapCalibration, RasterLayerState
from src.services.command_artifact_store import CommandArtifactStore
from src.services.raster_image_analysis import gradient_from_rgb_image
from src.services.raster_query_service import compute_resampled_query
from src.services.worker import DatabaseWorker


def test_legacy_raster_metadata_round_trips_unchanged() -> None:
    legacy = {
        "node_id": "raster-1",
        "file_path": "rasters/base.png",
        "resolution": [4, 2],
        "mode": "discrete",
        "snapshots": {"1.125": "rasters/dated.png"},
        "custom": "kept",
    }

    state = RasterLayerState.from_dict(legacy)

    assert state.schema_version == 1
    assert state.resolve_file(1.124) == "rasters/base.png"
    assert state.resolve_file(1.125) == "rasters/dated.png"
    assert state.to_dict() == legacy


def test_map_calibration_rejects_non_positive_width() -> None:
    assert MapCalibration().width_meters is None

    for invalid in (0.0, -1.0):
        try:
            MapCalibration(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError("Non-positive calibration was accepted")


def test_artifact_store_moves_and_restores_all_raster_states(
    tmp_path: Path,
) -> None:
    base = tmp_path / "rasters" / "base.png"
    dated = tmp_path / "rasters" / "snapshots" / "state.png"
    base.parent.mkdir(parents=True)
    dated.parent.mkdir(parents=True)
    base.write_bytes(b"base")
    dated.write_bytes(b"dated")
    store = CommandArtifactStore(tmp_path)

    manifest = store.stash(
        "command-1",
        ["rasters/base.png", "rasters/snapshots/state.png"],
    )

    assert not base.exists()
    assert not dated.exists()
    store.restore(manifest)
    assert base.read_bytes() == b"base"
    assert dated.read_bytes() == b"dated"


def test_query_resamples_mixed_discrete_and_continuous_grids() -> None:
    discrete = np.array([[0, 1], [1, 1]], dtype=np.uint16)
    continuous = np.full((4, 4), 10.0, dtype=np.float32)

    mask = compute_resampled_query(
        [discrete, continuous],
        ["discrete", "continuous"],
        [
            {"index": 0, "op": "eq", "value": 1},
            {"index": 1, "op": "gte", "value": 10},
        ],
    )

    assert mask.shape == (4, 4)
    assert mask.sum() == 12


def test_uniform_image_produces_deterministic_single_color_gradient() -> None:
    image = Image.new("RGB", (3, 2), (12, 34, 56))

    gradient = gradient_from_rgb_image(image)

    assert gradient["gradient_stops"] == [
        {"position": 0.0, "color": "#0C2238FF"},
        {"position": 1.0, "color": "#0C2238FF"},
    ]


def test_stroke_intent_crosses_worker_boundary_without_live_buffer() -> None:
    command = StrokeRasterCommand(
        map_id="map-1",
        node_id="raster-1",
        dirty_region=(1, 2, 2, 3),
        before_bytes=b"\x00\x00" * 4,
        after_bytes=b"\x01\x00" * 4,
        target_file="rasters/base.png",
    )
    payload = {
        "type": command.__class__.__name__,
        "data": command.to_dict(),
        "base": command.base_state_dict(),
    }

    worker = DatabaseWorker(":memory:", get_command_types())
    restored = worker._command_from_request(payload)

    assert isinstance(restored, StrokeRasterCommand)
    assert restored is not command
    assert restored.command_id == command.command_id
    assert restored._before_bytes == command._before_bytes
    assert restored._after_bytes == command._after_bytes
    assert restored.is_undoable
    assert not restored.persist_to_history
