"""Mode-matrix coverage for the pure raster paint engine."""

import numpy as np

from src.core.raster_paint import (
    BrushSpec,
    FillSpec,
    GradientSpec,
    connected_fill,
    paint_continuous_brush,
    paint_discrete_brush,
    paint_gradient,
    paint_rgba_brush,
)
from src.gui.widgets.map.raster_edit_tool import _TiledStrokeJournal


def test_discrete_brush_writes_only_selected_class() -> None:
    array = np.full((16, 16), 3, dtype=np.uint16)

    paint_discrete_brush(array, 8, 8, 5, 42)

    assert set(np.unique(array)) == {3, 42}


def test_discrete_fill_is_exact() -> None:
    array = np.array(
        [[1, 1, 2], [1, 2, 2], [3, 3, 2]],
        dtype=np.uint16,
    )

    connected_fill(array, 0, 0, 9, FillSpec(tolerance=0))

    assert np.array_equal(
        array,
        np.array([[9, 9, 2], [9, 2, 2], [3, 3, 2]], dtype=np.uint16),
    )


def test_continuous_hardness_direction() -> None:
    hard = np.zeros((11, 11), dtype=np.uint16)
    soft = hard.copy()

    paint_continuous_brush(
        hard,
        5,
        5,
        65535,
        BrushSpec(radius_px=5, hardness=1.0),
    )
    paint_continuous_brush(
        soft,
        5,
        5,
        65535,
        BrushSpec(radius_px=5, hardness=0.0),
    )

    assert hard[5, 9] == 65535
    assert 0 < soft[5, 9] < hard[5, 9]


def test_continuous_fill_uses_tolerance() -> None:
    array = np.array([[100, 105, 130]], dtype=np.uint16)

    connected_fill(array, 0, 0, 500, FillSpec(tolerance=5))

    assert array.tolist() == [[500, 500, 130]]


def test_rgba_brush_uses_source_over_with_colour_alpha() -> None:
    array = np.zeros((3, 3, 4), dtype=np.uint8)

    paint_rgba_brush(
        array,
        1,
        1,
        (255, 0, 0, 128),
        BrushSpec(radius_px=1, hardness=1.0),
    )

    assert tuple(array[1, 1]) == (255, 0, 0, 128)


def test_rgba_fill_similarity_includes_alpha() -> None:
    array = np.array(
        [[[10, 20, 30, 40], [10, 20, 30, 50], [10, 20, 30, 90]]],
        dtype=np.uint8,
    )

    connected_fill(
        array,
        0,
        0,
        (200, 100, 50, 255),
        FillSpec(tolerance=10),
    )

    assert tuple(array[0, 0]) == (200, 100, 50, 255)
    assert tuple(array[0, 1]) == (200, 100, 50, 255)
    assert tuple(array[0, 2]) == (10, 20, 30, 90)


def test_rgba_gradient_interpolates_premultiplied_alpha() -> None:
    array = np.zeros((1, 3, 4), dtype=np.uint8)

    paint_gradient(
        array,
        (0.0, 0.0),
        (2.0, 0.0),
        GradientSpec(
            kind="linear",
            start=(255, 0, 0, 0),
            end=(0, 0, 255, 255),
        ),
    )

    assert tuple(array[0, 0]) == (0, 0, 0, 0)
    assert tuple(array[0, 1]) == (0, 0, 255, 128)
    assert tuple(array[0, 2]) == (0, 0, 255, 255)


def test_tile_journal_captures_only_intersecting_tiles() -> None:
    array = np.zeros((600, 600), dtype=np.uint16)
    journal = _TiledStrokeJournal(array)

    journal.capture_bounds(array, (250, 250, 260, 260))
    array[250:261, 250:261] = 7
    patches = journal.patches(array)

    assert len(journal._before) == 4
    assert len(patches) == 4
    assert {patch["region"] for patch in patches} == {
        (0, 0, 255, 255),
        (256, 0, 511, 255),
        (0, 256, 255, 511),
        (256, 256, 511, 511),
    }
