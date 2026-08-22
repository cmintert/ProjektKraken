"""Tests for pure geometry-aware spatial relations."""

from __future__ import annotations

import math

import pytest

from src.core.spatial_geometry import (
    GeometryMetric,
    SpatialGeometry,
    relate_geometries,
)


def point(x: float, y: float) -> SpatialGeometry:
    return SpatialGeometry("point", ((x, y),))


def path(*points: tuple[float, float]) -> SpatialGeometry:
    return SpatialGeometry("path", points)


def region(*points: tuple[float, float]) -> SpatialGeometry:
    return SpatialGeometry("region", points)


@pytest.mark.parametrize(
    ("source", "target", "expected"),
    [
        (point(0.0, 0.0), point(1.0, 0.0), "separate"),
        (point(0.5, 0.5), path((0.0, 0.5), (1.0, 0.5)), "touches"),
        (
            point(0.5, 0.5),
            region((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)),
            "inside",
        ),
        (
            path((0.0, 0.5), (1.0, 0.5)),
            path((0.5, 0.0), (0.5, 1.0)),
            "crosses",
        ),
        (
            path((0.1, 0.1), (0.9, 0.9)),
            region((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)),
            "inside",
        ),
        (
            path((-0.5, 0.5), (1.5, 0.5)),
            region((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)),
            "crosses",
        ),
        (
            region((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)),
            region((0.5, 0.5), (1.5, 0.5), (1.5, 1.5), (0.5, 1.5)),
            "overlaps",
        ),
        (
            region((0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 2.0)),
            region((0.5, 0.5), (1.0, 0.5), (1.0, 1.0), (0.5, 1.0)),
            "contains",
        ),
    ],
)
def test_shape_pair_relations(
    source: SpatialGeometry, target: SpatialGeometry, expected: str
) -> None:
    assert relate_geometries(source, target).kind == expected


def test_relation_is_directed_for_containment() -> None:
    area = region((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))
    location = point(0.5, 0.5)

    assert relate_geometries(location, area).kind == "inside"
    assert relate_geometries(area, location).kind == "contains"


def test_closest_points_use_path_instead_of_anchor() -> None:
    road = path((0.0, 0.0), (1.0, 0.0))
    location = point(0.9, 0.2)

    relation = relate_geometries(road, location)

    assert relation.kind == "separate"
    assert relation.distance == pytest.approx(0.2)
    assert relation.source_point == pytest.approx((0.9, 0.0))
    assert relation.target_point == pytest.approx((0.9, 0.2))


def test_metric_respects_non_square_map() -> None:
    source = point(0.0, 0.0)
    target = point(0.0, 1.0)

    relation = relate_geometries(
        source,
        target,
        GeometryMetric(x_scale=10_000.0, y_scale=5_000.0, tolerance=1.0),
    )

    assert relation.distance == pytest.approx(5_000.0)


def test_metric_tolerance_does_not_expand_segment_parameters() -> None:
    first = path((0.0, 0.0), (0.1, 0.0))
    distant = path((0.5, 0.5), (0.5, 1.0))

    relation = relate_geometries(
        first,
        distant,
        GeometryMetric(x_scale=10_000.0, y_scale=5_000.0, tolerance=25.0),
    )

    assert relation.kind == "separate"
    assert relation.distance > 4_000.0


def test_resolution_tolerance_turns_subpixel_gap_into_contact() -> None:
    first = path((0.0, 0.0), (0.5, 0.0))
    second = path((0.5004, 0.0), (1.0, 0.0))

    relation = relate_geometries(
        first,
        second,
        GeometryMetric(tolerance=0.0005),
    )

    assert relation.kind == "touches"


@pytest.mark.parametrize(
    ("feature_type", "geometry"),
    [
        ("path", None),
        ("path", [{"x": 0.0, "y": 0.0}]),
        ("path", [{"x": 0.2, "y": 0.2}, {"x": 0.2, "y": 0.2}]),
        ("region", [{"x": 0.0, "y": 0.0}, {"x": 1.0, "y": 0.0}]),
        (
            "region",
            [
                {"x": 0.0, "y": 0.0},
                {"x": 0.5, "y": 0.0},
                {"x": 1.0, "y": 0.0},
            ],
        ),
        (
            "region",
            [
                {"x": -0.1, "y": 0.0},
                {"x": 0.5, "y": 0.0},
                {"x": 0.5, "y": 0.5},
            ],
        ),
        ("region", [{"x": math.nan, "y": 0.0}] * 3),
    ],
)
def test_malformed_extended_geometry_is_rejected(
    feature_type: str, geometry: list[dict[str, float]] | None
) -> None:
    assert SpatialGeometry.from_feature(feature_type, 0.5, 0.5, geometry) is None
