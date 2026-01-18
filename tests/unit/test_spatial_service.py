"""
Tests for the SpatialService.
"""

import pytest

from src.services.spatial_service import SpatialService


@pytest.fixture
def spatial_service():
    """Creates a SpatialService instance."""
    return SpatialService()


def test_distance():
    """Test distance calculation between two points."""
    dist = SpatialService.distance(0, 0, 3, 4)
    assert abs(dist - 5.0) < 0.001  # 3-4-5 triangle


def test_polyline_length():
    """Test polyline length calculation."""
    coords = [[0, 0], [10, 0], [10, 10]]
    length = SpatialService.polyline_length(coords)
    assert abs(length - 20.0) < 0.001  # 10 + 10


def test_polyline_length_empty():
    """Test polyline length with empty or single point."""
    assert SpatialService.polyline_length([]) == 0.0
    assert SpatialService.polyline_length([[5, 5]]) == 0.0


def test_bbox():
    """Test bounding box calculation."""
    coords = [[10, 20], [5, 30], [15, 25]]
    min_x, min_y, max_x, max_y = SpatialService.bbox(coords)

    assert min_x == 5
    assert min_y == 20
    assert max_x == 15
    assert max_y == 30


def test_bbox_empty():
    """Test bounding box with empty coordinates."""
    bbox = SpatialService.bbox([])
    assert bbox == (0.0, 0.0, 0.0, 0.0)


def test_point_to_segment_distance():
    """Test distance from point to segment."""
    # Point perpendicular to segment midpoint
    dist, cx, cy = SpatialService.point_to_segment_distance(5, 5, 0, 0, 10, 0)
    assert abs(dist - 5.0) < 0.001
    assert abs(cx - 5.0) < 0.001
    assert abs(cy - 0.0) < 0.001


def test_point_to_segment_distance_endpoint():
    """Test distance when closest point is segment endpoint."""
    # Point closest to start
    dist, cx, cy = SpatialService.point_to_segment_distance(-5, 5, 0, 0, 10, 0)
    assert abs(cx - 0.0) < 0.001
    assert abs(cy - 0.0) < 0.001

    # Point closest to end
    dist, cx, cy = SpatialService.point_to_segment_distance(15, 5, 0, 0, 10, 0)
    assert abs(cx - 10.0) < 0.001
    assert abs(cy - 0.0) < 0.001


def test_segment_intersection():
    """Test segment intersection calculation."""
    # Crossing segments
    intersection = SpatialService.segment_intersection(0, 0, 10, 10, 0, 10, 10, 0)

    assert intersection is not None
    ix, iy = intersection
    assert abs(ix - 5.0) < 0.001
    assert abs(iy - 5.0) < 0.001


def test_segment_intersection_parallel():
    """Test parallel segments don't intersect."""
    intersection = SpatialService.segment_intersection(0, 0, 10, 0, 0, 5, 10, 5)
    assert intersection is None


def test_segment_intersection_no_overlap():
    """Test non-overlapping segments."""
    intersection = SpatialService.segment_intersection(0, 0, 5, 0, 10, 0, 15, 0)
    assert intersection is None


def test_find_polyline_intersections(spatial_service):
    """Test finding intersections between two polylines."""
    # Two crossing polylines
    coords1 = [[0, 0], [10, 10]]
    coords2 = [[0, 10], [10, 0]]

    intersections = spatial_service.find_polyline_intersections(coords1, coords2)

    assert len(intersections) == 1
    ix, iy, seg1, seg2 = intersections[0]
    assert abs(ix - 5.0) < 0.001
    assert abs(iy - 5.0) < 0.001
    assert seg1 == 0
    assert seg2 == 0


def test_find_polyline_intersections_multiple(spatial_service):
    """Test finding multiple intersections."""
    # Grid pattern
    coords1 = [[0, 5], [10, 5]]
    coords2 = [[5, 0], [5, 10]]

    intersections = spatial_service.find_polyline_intersections(coords1, coords2)

    assert len(intersections) == 1
    ix, iy, _, _ = intersections[0]
    assert abs(ix - 5.0) < 0.001
    assert abs(iy - 5.0) < 0.001


def test_split_polyline_at_point(spatial_service):
    """Test splitting a polyline at a point."""
    coords = [[0, 0], [10, 0], [20, 0]]
    point = (5, 0)
    seg_idx = 0

    before, after = spatial_service.split_polyline_at_point(coords, point, seg_idx)

    assert len(before) == 2
    assert before[0] == [0, 0]
    assert before[1] == [5, 0]

    assert len(after) == 3
    assert after[0] == [5, 0]
    assert after[1] == [10, 0]
    assert after[2] == [20, 0]


def test_split_polyline_at_middle_segment(spatial_service):
    """Test splitting at middle segment of polyline."""
    coords = [[0, 0], [10, 0], [20, 0], [30, 0]]
    point = (15, 0)
    seg_idx = 1  # Second segment (10,0) to (20,0)

    before, after = spatial_service.split_polyline_at_point(coords, point, seg_idx)

    assert before[-1] == [15, 0]
    assert after[0] == [15, 0]
    assert after[-1] == [30, 0]


def test_snap_to_nearest_node(spatial_service):
    """Test snapping to nearest node."""
    nodes = [(0, 0), (10, 0), (20, 0)]

    # Point near first node
    idx = spatial_service.snap_to_nearest_node(2, 1, nodes, threshold=5.0)
    assert idx == 0

    # Point near second node
    idx = spatial_service.snap_to_nearest_node(11, 1, nodes, threshold=5.0)
    assert idx == 1

    # Point too far from any node
    idx = spatial_service.snap_to_nearest_node(50, 50, nodes, threshold=5.0)
    assert idx is None


def test_snap_to_nearest_node_empty(spatial_service):
    """Test snapping with no nodes."""
    idx = spatial_service.snap_to_nearest_node(5, 5, [], threshold=10.0)
    assert idx is None


def test_simplify_polyline(spatial_service):
    """Test polyline simplification."""
    # Line with unnecessary middle point
    coords = [[0, 0], [5, 0], [10, 0]]
    simplified = spatial_service.simplify_polyline(coords, tolerance=1.0)

    # Middle point should be removed (it's on the line)
    assert len(simplified) == 2
    assert simplified[0] == [0, 0]
    assert simplified[-1] == [10, 0]


def test_simplify_polyline_zigzag(spatial_service):
    """Test simplification of zigzag line."""
    # Zigzag that should be simplified
    coords = [[0, 0], [1, 0.1], [2, 0], [3, 0.1], [4, 0]]
    simplified = spatial_service.simplify_polyline(coords, tolerance=0.5)

    # Small deviations should be removed
    assert len(simplified) < len(coords)


def test_simplify_polyline_minimal(spatial_service):
    """Test that two-point lines are not simplified."""
    coords = [[0, 0], [10, 10]]
    simplified = spatial_service.simplify_polyline(coords, tolerance=10.0)

    assert len(simplified) == 2
    assert simplified == coords


def test_merge_nearby_nodes(spatial_service):
    """Test finding nodes that should be merged."""
    nodes = [
        (0, 0, "node1"),
        (2, 1, "node2"),  # Close to node1
        (100, 100, "node3"),  # Far away
        (101, 101, "node4"),  # Close to node3
    ]

    merge_pairs = spatial_service.merge_nearby_nodes(nodes, threshold=5.0)

    assert len(merge_pairs) == 2
    # Check that close pairs are identified
    pair_ids = {(pair[0], pair[1]) for pair in merge_pairs}
    assert ("node1", "node2") in pair_ids
    assert ("node3", "node4") in pair_ids


def test_merge_nearby_nodes_none(spatial_service):
    """Test when no nodes need merging."""
    nodes = [
        (0, 0, "node1"),
        (100, 100, "node2"),
        (200, 200, "node3"),
    ]

    merge_pairs = spatial_service.merge_nearby_nodes(nodes, threshold=5.0)
    assert len(merge_pairs) == 0


def test_douglas_peucker_complex(spatial_service):
    """Test Douglas-Peucker with complex polyline."""
    # Create a polyline with significant deviations
    coords = [
        [0, 0],
        [10, 2],  # Small deviation
        [20, 0],
        [30, 10],  # Large deviation
        [40, 0],
    ]

    simplified = spatial_service._douglas_peucker(coords, tolerance=3.0)

    # Should keep significant deviation but remove small one
    assert len(simplified) < len(coords)
    assert [0, 0] in simplified
    assert [40, 0] in simplified
    assert [30, 10] in simplified  # Large deviation kept


def test_spatial_service_with_scipy():
    """Test spatial service preferring scipy when available."""
    service = SpatialService(use_scipy=True)
    # Just verify it initializes without error
    assert service is not None


def test_spatial_service_without_scipy():
    """Test spatial service without scipy."""
    service = SpatialService(use_scipy=False)
    assert service is not None
    assert service.use_scipy is False

    # Verify it still works
    nodes = [(0, 0), (10, 10), (20, 20)]
    idx = service.snap_to_nearest_node(11, 11, nodes, threshold=5.0)
    assert idx == 1


def test_segment_intersection_edge_cases():
    """Test segment intersection edge cases."""
    # Segments sharing an endpoint
    intersection = SpatialService.segment_intersection(0, 0, 10, 0, 10, 0, 20, 0)
    assert intersection is not None
    ix, iy = intersection
    assert abs(ix - 10.0) < 0.001
    assert abs(iy - 0.0) < 0.001

    # Very short segments
    intersection = SpatialService.segment_intersection(
        0, 0, 0.01, 0.01, 0.01, 0, 0, 0.01
    )
    assert intersection is not None


def test_point_to_segment_distance_zero_length():
    """Test distance calculation for zero-length segment."""
    dist, cx, cy = SpatialService.point_to_segment_distance(5, 5, 10, 10, 10, 10)

    # Should treat as point-to-point distance
    expected_dist = SpatialService.distance(5, 5, 10, 10)
    assert abs(dist - expected_dist) < 0.001
    assert abs(cx - 10.0) < 0.001
    assert abs(cy - 10.0) < 0.001
