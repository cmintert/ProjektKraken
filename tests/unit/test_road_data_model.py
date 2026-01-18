"""
Tests for the Road data model.
"""

import time

import pytest

from src.core.road import Road, RoadNetwork, RoadNode, RoadSegment


def test_road_node_creation():
    """Test that RoadNode instances are created correctly."""
    node = RoadNode(x=100.0, y=200.0)
    assert node.x == 100.0
    assert node.y == 200.0
    assert node.id is not None
    assert isinstance(node.attributes, dict)


def test_road_node_to_dict():
    """Test RoadNode serialization to dictionary."""
    node = RoadNode(x=50.0, y=75.0, attributes={"type": "intersection"})
    data = node.to_dict()

    assert data["x"] == 50.0
    assert data["y"] == 75.0
    assert data["attributes"]["type"] == "intersection"
    assert "id" in data


def test_road_node_from_dict():
    """Test RoadNode deserialization from dictionary."""
    data = {"id": "node-1", "x": 10.0, "y": 20.0, "attributes": {"name": "Corner"}}
    node = RoadNode.from_dict(data)

    assert node.id == "node-1"
    assert node.x == 10.0
    assert node.y == 20.0
    assert node.attributes["name"] == "Corner"


def test_road_node_distance():
    """Test distance calculation between nodes."""
    node1 = RoadNode(x=0.0, y=0.0)
    node2 = RoadNode(x=3.0, y=4.0)

    distance = node1.distance_to(node2)
    assert abs(distance - 5.0) < 0.001  # 3-4-5 triangle


def test_road_segment_creation():
    """Test that RoadSegment instances are created correctly."""
    segment = RoadSegment(
        start_node_id="node-1",
        end_node_id="node-2",
        coords=[[0.0, 0.0], [10.0, 10.0]],
    )

    assert segment.start_node_id == "node-1"
    assert segment.end_node_id == "node-2"
    assert len(segment.coords) == 2
    assert segment.id is not None


def test_road_segment_to_dict():
    """Test RoadSegment serialization."""
    segment = RoadSegment(
        start_node_id="n1",
        end_node_id="n2",
        coords=[[0, 0], [5, 5]],
        length_px=7.07,
        attributes={"speed": 50, "oneway": False},
    )
    data = segment.to_dict()

    assert data["start_node_id"] == "n1"
    assert data["end_node_id"] == "n2"
    assert data["length_px"] == 7.07
    assert data["attributes"]["speed"] == 50
    assert "id" in data


def test_road_segment_from_dict():
    """Test RoadSegment deserialization."""
    data = {
        "id": "seg-1",
        "start_node_id": "a",
        "end_node_id": "b",
        "coords": [[0, 0], [10, 0]],
        "length_px": 10.0,
        "road_id": "road-1",
        "attributes": {"surface": "asphalt"},
    }
    segment = RoadSegment.from_dict(data)

    assert segment.id == "seg-1"
    assert segment.start_node_id == "a"
    assert segment.end_node_id == "b"
    assert segment.road_id == "road-1"
    assert segment.length_px == 10.0
    assert segment.attributes["surface"] == "asphalt"


def test_road_creation():
    """Test that Road instances are created correctly."""
    road = Road(name="Main Street", segment_ids=["seg-1", "seg-2"])

    assert road.name == "Main Street"
    assert len(road.segment_ids) == 2
    assert road.id is not None


def test_road_to_dict():
    """Test Road serialization."""
    road = Road(
        name="Highway 101",
        segment_ids=["s1", "s2", "s3"],
        attributes={"type": "highway"},
    )
    data = road.to_dict()

    assert data["name"] == "Highway 101"
    assert len(data["segment_ids"]) == 3
    assert data["attributes"]["type"] == "highway"


def test_road_from_dict():
    """Test Road deserialization."""
    data = {
        "id": "road-1",
        "name": "Oak Avenue",
        "segment_ids": ["s1"],
        "attributes": {"lanes": 2},
    }
    road = Road.from_dict(data)

    assert road.id == "road-1"
    assert road.name == "Oak Avenue"
    assert road.segment_ids == ["s1"]
    assert road.attributes["lanes"] == 2


def test_road_network_creation():
    """Test RoadNetwork creation with defaults."""
    network = RoadNetwork()

    assert isinstance(network.nodes, dict)
    assert isinstance(network.segments, list)
    assert isinstance(network.roads, list)
    assert "created_at" in network.meta
    assert "modified_at" in network.meta
    assert "px_per_meter" in network.meta
    assert "units" in network.meta


def test_road_network_add_node():
    """Test adding nodes to network."""
    network = RoadNetwork()
    node1 = RoadNode(x=10.0, y=20.0)
    node2 = RoadNode(x=30.0, y=40.0)

    network.add_node(node1)
    network.add_node(node2)

    assert len(network.nodes) == 2
    assert node1.id in network.nodes
    assert node2.id in network.nodes


def test_road_network_add_segment():
    """Test adding segments to network."""
    network = RoadNetwork()
    segment = RoadSegment(
        start_node_id="n1", end_node_id="n2", coords=[[0, 0], [10, 10]]
    )

    network.add_segment(segment)

    assert len(network.segments) == 1
    assert network.segments[0].id == segment.id


def test_road_network_add_road():
    """Test adding roads to network."""
    network = RoadNetwork()
    road = Road(name="Test Road")

    network.add_road(road)

    assert len(network.roads) == 1
    assert network.roads[0].name == "Test Road"


def test_road_network_get_node():
    """Test retrieving nodes by ID."""
    network = RoadNetwork()
    node = RoadNode(x=5.0, y=10.0)
    network.add_node(node)

    retrieved = network.get_node(node.id)
    assert retrieved is not None
    assert retrieved.id == node.id
    assert retrieved.x == 5.0


def test_road_network_get_segment():
    """Test retrieving segments by ID."""
    network = RoadNetwork()
    segment = RoadSegment(
        start_node_id="a", end_node_id="b", coords=[[0, 0], [5, 5]]
    )
    network.add_segment(segment)

    retrieved = network.get_segment(segment.id)
    assert retrieved is not None
    assert retrieved.id == segment.id


def test_road_network_get_road():
    """Test retrieving roads by ID."""
    network = RoadNetwork()
    road = Road(name="Sample Road")
    network.add_road(road)

    retrieved = network.get_road(road.id)
    assert retrieved is not None
    assert retrieved.name == "Sample Road"


def test_road_network_remove_node():
    """Test removing nodes from network."""
    network = RoadNetwork()
    node = RoadNode(x=1.0, y=2.0)
    network.add_node(node)

    assert node.id in network.nodes
    network.remove_node(node.id)
    assert node.id not in network.nodes


def test_road_network_remove_segment():
    """Test removing segments from network."""
    network = RoadNetwork()
    segment = RoadSegment(
        start_node_id="x", end_node_id="y", coords=[[0, 0], [1, 1]]
    )
    network.add_segment(segment)

    assert len(network.segments) == 1
    network.remove_segment(segment.id)
    assert len(network.segments) == 0


def test_road_network_remove_road():
    """Test removing roads from network."""
    network = RoadNetwork()
    road = Road(name="Temp Road")
    network.add_road(road)

    assert len(network.roads) == 1
    network.remove_road(road.id)
    assert len(network.roads) == 0


def test_road_network_to_dict():
    """Test RoadNetwork serialization to dictionary."""
    network = RoadNetwork()
    node = RoadNode(x=10.0, y=20.0)
    network.add_node(node)

    segment = RoadSegment(
        start_node_id=node.id, end_node_id=node.id, coords=[[10, 20], [30, 40]]
    )
    network.add_segment(segment)

    road = Road(name="Test Road", segment_ids=[segment.id])
    network.add_road(road)

    data = network.to_dict()

    assert "meta" in data
    assert "nodes" in data
    assert "segments" in data
    assert "roads" in data
    assert len(data["nodes"]) == 1
    assert len(data["segments"]) == 1
    assert len(data["roads"]) == 1


def test_road_network_from_dict():
    """Test RoadNetwork deserialization from dictionary."""
    data = {
        "meta": {"px_per_meter": 2.0, "units": "meters"},
        "nodes": {
            "n1": {"id": "n1", "x": 0.0, "y": 0.0, "attributes": {}},
            "n2": {"id": "n2", "x": 10.0, "y": 10.0, "attributes": {}},
        },
        "segments": [
            {
                "id": "s1",
                "start_node_id": "n1",
                "end_node_id": "n2",
                "coords": [[0, 0], [10, 10]],
                "length_px": 14.14,
                "attributes": {},
            }
        ],
        "roads": [{"id": "r1", "name": "Main St", "segment_ids": ["s1"], "attributes": {}}],
    }

    network = RoadNetwork.from_dict(data)

    assert len(network.nodes) == 2
    assert len(network.segments) == 1
    assert len(network.roads) == 1
    assert network.meta["px_per_meter"] == 2.0
    assert "n1" in network.nodes
    assert network.segments[0].id == "s1"
    assert network.roads[0].name == "Main St"


def test_road_network_roundtrip():
    """Test that serialization/deserialization is lossless."""
    # Create a complete network
    network = RoadNetwork()
    network.meta["px_per_meter"] = 1.5

    node1 = RoadNode(x=0.0, y=0.0)
    node2 = RoadNode(x=100.0, y=100.0)
    network.add_node(node1)
    network.add_node(node2)

    segment = RoadSegment(
        start_node_id=node1.id,
        end_node_id=node2.id,
        coords=[[0, 0], [100, 100]],
        length_px=141.42,
    )
    network.add_segment(segment)

    road = Road(name="Diagonal Road", segment_ids=[segment.id])
    network.add_road(road)

    # Serialize
    data = network.to_dict()

    # Deserialize
    restored = RoadNetwork.from_dict(data)

    # Verify
    assert len(restored.nodes) == 2
    assert len(restored.segments) == 1
    assert len(restored.roads) == 1
    assert restored.meta["px_per_meter"] == 1.5
    assert restored.roads[0].name == "Diagonal Road"


def test_road_network_modified_at_updates():
    """Test that modified_at timestamp updates on changes."""
    network = RoadNetwork()
    original_time = network.meta["modified_at"]

    time.sleep(0.01)  # Ensure time passes

    node = RoadNode(x=1.0, y=1.0)
    network.add_node(node)

    assert network.meta["modified_at"] > original_time
