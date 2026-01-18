"""
Tests for the RoutingService.
"""

import pytest

from src.core.road import Road, RoadNetwork, RoadNode, RoadSegment
from src.services.routing_service import Route, RoutingService


@pytest.fixture
def simple_network():
    """Creates a simple linear road network for testing.

    Network:
    n1 --- s1 --- n2 --- s2 --- n3
    (0,0)        (100,0)       (200,0)
    """
    network = RoadNetwork()
    network.meta["px_per_meter"] = 1.0

    n1 = RoadNode(x=0.0, y=0.0, id="n1")
    n2 = RoadNode(x=100.0, y=0.0, id="n2")
    n3 = RoadNode(x=200.0, y=0.0, id="n3")

    network.add_node(n1)
    network.add_node(n2)
    network.add_node(n3)

    s1 = RoadSegment(
        id="s1",
        start_node_id="n1",
        end_node_id="n2",
        coords=[[0, 0], [100, 0]],
        length_px=100.0,
    )
    s2 = RoadSegment(
        id="s2",
        start_node_id="n2",
        end_node_id="n3",
        coords=[[100, 0], [200, 0]],
        length_px=100.0,
    )

    network.add_segment(s1)
    network.add_segment(s2)

    return network


@pytest.fixture
def grid_network():
    """Creates a 2x2 grid network for testing.

    Network:
    n1 --- n2
    |      |
    n3 --- n4
    """
    network = RoadNetwork()

    n1 = RoadNode(x=0.0, y=0.0, id="n1")
    n2 = RoadNode(x=100.0, y=0.0, id="n2")
    n3 = RoadNode(x=0.0, y=100.0, id="n3")
    n4 = RoadNode(x=100.0, y=100.0, id="n4")

    network.add_node(n1)
    network.add_node(n2)
    network.add_node(n3)
    network.add_node(n4)

    # Horizontal segments
    s1 = RoadSegment(
        id="s1",
        start_node_id="n1",
        end_node_id="n2",
        coords=[[0, 0], [100, 0]],
        length_px=100.0,
    )
    s3 = RoadSegment(
        id="s3",
        start_node_id="n3",
        end_node_id="n4",
        coords=[[0, 100], [100, 100]],
        length_px=100.0,
    )

    # Vertical segments
    s2 = RoadSegment(
        id="s2",
        start_node_id="n1",
        end_node_id="n3",
        coords=[[0, 0], [0, 100]],
        length_px=100.0,
    )
    s4 = RoadSegment(
        id="s4",
        start_node_id="n2",
        end_node_id="n4",
        coords=[[100, 0], [100, 100]],
        length_px=100.0,
    )

    network.add_segment(s1)
    network.add_segment(s2)
    network.add_segment(s3)
    network.add_segment(s4)

    return network


@pytest.fixture
def routing_service():
    """Creates a RoutingService instance."""
    return RoutingService()


def test_route_initialization():
    """Test Route object initialization."""
    route = Route(
        segment_ids=["s1", "s2"],
        node_ids=["n1", "n2", "n3"],
        total_distance_px=200.0,
        coords=[[0, 0], [100, 0], [200, 0]],
        px_per_meter=1.0,
        avg_speed_m_per_s=15.0,
    )

    assert len(route.segment_ids) == 2
    assert len(route.node_ids) == 3
    assert route.total_distance_px == 200.0
    assert route.total_distance_m == 200.0
    assert abs(route.estimated_time_s - 13.33) < 0.1


def test_route_to_dict():
    """Test Route serialization."""
    route = Route(
        segment_ids=["s1"],
        node_ids=["n1", "n2"],
        total_distance_px=100.0,
        coords=[[0, 0], [100, 0]],
    )

    data = route.to_dict()
    assert "segment_ids" in data
    assert "node_ids" in data
    assert "total_distance_px" in data
    assert "total_distance_m" in data
    assert "estimated_time_s" in data


def test_route_to_geojson():
    """Test Route GeoJSON export."""
    route = Route(
        segment_ids=["s1"],
        node_ids=["n1", "n2"],
        total_distance_px=100.0,
        coords=[[0, 0], [100, 0]],
    )

    geojson = route.to_geojson()
    assert geojson["type"] == "Feature"
    assert geojson["geometry"]["type"] == "LineString"
    assert len(geojson["geometry"]["coordinates"]) == 2
    assert "distance_px" in geojson["properties"]


def test_load_network_simple(routing_service, simple_network):
    """Test loading a simple network into graph."""
    graph = routing_service.load_network("test_map", simple_network)

    assert graph.number_of_nodes() == 3
    assert graph.number_of_edges() == 2
    assert graph.has_edge("n1", "n2")
    assert graph.has_edge("n2", "n3")


def test_load_network_caching(routing_service, simple_network):
    """Test that graphs are cached properly."""
    graph1 = routing_service.load_network("test_map", simple_network)
    graph2 = routing_service.load_network("test_map", simple_network)

    # Should return same cached instance
    assert graph1 is graph2


def test_invalidate_cache(routing_service, simple_network):
    """Test cache invalidation."""
    graph1 = routing_service.load_network("test_map", simple_network)
    routing_service.invalidate_cache("test_map")
    graph2 = routing_service.load_network("test_map", simple_network)

    # Should rebuild graph
    assert graph1 is not graph2


def test_find_nearest_node(routing_service, simple_network):
    """Test finding nearest node to a point."""
    # Point near n1
    node_id = routing_service.find_nearest_node(5, 5, simple_network, threshold=10.0)
    assert node_id == "n1"

    # Point near n2
    node_id = routing_service.find_nearest_node(95, 5, simple_network, threshold=10.0)
    assert node_id == "n2"

    # Point too far
    node_id = routing_service.find_nearest_node(500, 500, simple_network, threshold=10.0)
    assert node_id is None


def test_snap_point_to_segment(routing_service, simple_network):
    """Test snapping point to nearest segment."""
    # Point above segment s1
    result = routing_service.snap_point_to_segment(50, 10, simple_network, threshold=20.0)

    assert result is not None
    segment_id, snap_x, snap_y = result
    assert segment_id == "s1"
    assert abs(snap_x - 50.0) < 0.1
    assert abs(snap_y - 0.0) < 0.1


def test_route_between_nodes_simple(routing_service, simple_network):
    """Test routing between two nodes in simple network."""
    route = routing_service.route_between_nodes(
        "test_map", simple_network, "n1", "n3", algorithm="dijkstra"
    )

    assert route is not None
    assert len(route.node_ids) == 3
    assert route.node_ids == ["n1", "n2", "n3"]
    assert len(route.segment_ids) == 2
    assert route.total_distance_px == 200.0


def test_route_between_nodes_astar(routing_service, simple_network):
    """Test routing with A* algorithm."""
    route = routing_service.route_between_nodes(
        "test_map", simple_network, "n1", "n3", algorithm="astar"
    )

    assert route is not None
    assert route.node_ids == ["n1", "n2", "n3"]


def test_route_between_nodes_no_path(routing_service):
    """Test routing when no path exists."""
    # Create disconnected network
    network = RoadNetwork()
    n1 = RoadNode(x=0.0, y=0.0, id="n1")
    n2 = RoadNode(x=100.0, y=0.0, id="n2")
    network.add_node(n1)
    network.add_node(n2)
    # No segments connecting them

    route = routing_service.route_between_nodes("test_map", network, "n1", "n2")
    assert route is None


def test_route_between_points(routing_service, simple_network):
    """Test routing between arbitrary points."""
    # Points near n1 and n3
    route = routing_service.route_between_points(
        "test_map", simple_network, 5, 5, 195, 5, snap_threshold=10.0
    )

    assert route is not None
    assert route.node_ids[0] == "n1"
    assert route.node_ids[-1] == "n3"


def test_route_between_points_no_snap(routing_service, simple_network):
    """Test routing when points don't snap to network."""
    # Points too far from network
    route = routing_service.route_between_points(
        "test_map", simple_network, 500, 500, 600, 600, snap_threshold=10.0
    )

    assert route is None


def test_grid_network_shortest_path(routing_service, grid_network):
    """Test finding shortest path in grid network."""
    # Route from n1 to n4 (diagonal)
    route = routing_service.route_between_nodes("grid_map", grid_network, "n1", "n4")

    assert route is not None
    # Should find one of two equivalent paths
    assert len(route.node_ids) == 3
    assert route.node_ids[0] == "n1"
    assert route.node_ids[-1] == "n4"
    # Distance should be 200 (two edges of 100 each)
    assert route.total_distance_px == 200.0


def test_oneway_segment():
    """Test routing with one-way segments."""
    network = RoadNetwork()

    n1 = RoadNode(x=0.0, y=0.0, id="n1")
    n2 = RoadNode(x=100.0, y=0.0, id="n2")
    network.add_node(n1)
    network.add_node(n2)

    # One-way segment from n1 to n2
    s1 = RoadSegment(
        id="s1",
        start_node_id="n1",
        end_node_id="n2",
        coords=[[0, 0], [100, 0]],
        length_px=100.0,
        attributes={"oneway": True},
    )
    network.add_segment(s1)

    service = RoutingService()

    # Should work n1 -> n2
    route = service.route_between_nodes("oneway_map", network, "n1", "n2")
    assert route is not None

    # Should work n2 -> n1 (in undirected graph, both directions work)
    # NetworkX Graph is undirected, so this would work
    # For true one-way, would need DiGraph


def test_route_coordinates(routing_service, simple_network):
    """Test that route coordinates are built correctly."""
    route = routing_service.route_between_nodes("test_map", simple_network, "n1", "n2")

    assert route is not None
    assert len(route.coords) >= 2
    # First coordinate should be near n1
    assert route.coords[0] == [0, 0]
    # Last coordinate should be near n2
    assert route.coords[-1] == [100, 0]


def test_route_with_curved_segment(routing_service):
    """Test routing with curved (multi-coordinate) segments."""
    network = RoadNetwork()

    n1 = RoadNode(x=0.0, y=0.0, id="n1")
    n2 = RoadNode(x=100.0, y=0.0, id="n2")
    network.add_node(n1)
    network.add_node(n2)

    # Curved segment with intermediate points
    s1 = RoadSegment(
        id="s1",
        start_node_id="n1",
        end_node_id="n2",
        coords=[[0, 0], [25, 10], [50, 15], [75, 10], [100, 0]],
        length_px=110.0,
    )
    network.add_segment(s1)

    route = routing_service.route_between_nodes("curved_map", network, "n1", "n2")

    assert route is not None
    # Route should include all intermediate coordinates
    assert len(route.coords) == 5


def test_multiple_routes_caching(routing_service, grid_network):
    """Test that multiple routes use cached graph."""
    route1 = routing_service.route_between_nodes("grid", grid_network, "n1", "n2")
    route2 = routing_service.route_between_nodes("grid", grid_network, "n3", "n4")

    assert route1 is not None
    assert route2 is not None
    # Both should have used same cached graph
    assert "grid" in routing_service._graph_cache


def test_route_with_px_per_meter_conversion(routing_service):
    """Test distance conversion with px_per_meter."""
    network = RoadNetwork()
    network.meta["px_per_meter"] = 2.0  # 2 pixels = 1 meter

    n1 = RoadNode(x=0.0, y=0.0, id="n1")
    n2 = RoadNode(x=100.0, y=0.0, id="n2")
    network.add_node(n1)
    network.add_node(n2)

    s1 = RoadSegment(
        id="s1",
        start_node_id="n1",
        end_node_id="n2",
        coords=[[0, 0], [100, 0]],
        length_px=100.0,
    )
    network.add_segment(s1)

    route = routing_service.route_between_nodes("scale_map", network, "n1", "n2")

    assert route is not None
    assert route.total_distance_px == 100.0
    assert route.total_distance_m == 50.0  # 100 px / 2 px/m = 50 m
