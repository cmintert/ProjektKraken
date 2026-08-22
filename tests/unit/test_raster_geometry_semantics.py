"""Tests for path and region raster-semantic summaries."""

from pathlib import Path

import numpy as np
from PIL import Image as PilImage

from src.services.raster_image_analysis import (
    sample_raster_path_semantics,
    sample_raster_region_semantics,
)


def _write_raster(path: Path, values: np.ndarray) -> None:
    PilImage.fromarray(values.astype(np.uint8), mode="L").save(path)


def _vem() -> dict:
    return {
        "mode": "exact",
        "mappings": [
            {"id": "forest", "label": "Forest", "value": 1},
            {"id": "marsh", "label": "Marsh", "value": 2},
            {"id": "desert", "label": "Desert", "value": 3},
        ],
    }


def test_path_summary_follows_geometry_transitions(tmp_path: Path) -> None:
    values = np.ones((10, 10), dtype=np.uint8)
    values[:, 3:7] = 2
    values[:, 7:] = 3
    raster = tmp_path / "classes.png"
    _write_raster(raster, values)

    result = sample_raster_path_semantics(
        str(raster), ((0.0, 0.5), (1.0, 0.5)), _vem()
    )

    assert result == "Forest → Marsh → Desert"


def test_path_summary_smooths_one_pixel_island(tmp_path: Path) -> None:
    values = np.ones((3, 7), dtype=np.uint8)
    values[1, 3] = 2
    raster = tmp_path / "noise.png"
    _write_raster(raster, values)

    result = sample_raster_path_semantics(
        str(raster), ((0.0, 0.5), (1.0, 0.5)), _vem()
    )

    assert result == "Forest"


def test_region_summary_reports_leading_covered_classes(tmp_path: Path) -> None:
    values = np.ones((10, 10), dtype=np.uint8)
    values[:, 5:] = 2
    raster = tmp_path / "coverage.png"
    _write_raster(raster, values)

    result = sample_raster_region_semantics(
        str(raster),
        ((0.0, 0.0), (0.75, 0.0), (0.75, 1.0), (0.0, 1.0)),
        _vem(),
    )

    assert result is not None
    assert result.startswith("Forest")
    assert "Marsh" in result


def test_extended_summary_rejects_out_of_bounds_geometry(tmp_path: Path) -> None:
    raster = tmp_path / "classes.png"
    _write_raster(raster, np.ones((4, 4), dtype=np.uint8))

    assert (
        sample_raster_path_semantics(
            str(raster), ((-0.1, 0.5), (0.5, 0.5)), _vem()
        )
        is None
    )
