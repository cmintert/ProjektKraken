"""
Integration tests for road commands and database integration.
"""

import pytest

from src.commands.road_commands import ClearMapRoadsCommand, UpdateMapRoadsCommand
from src.core.map import Map
from src.core.road import Road, RoadNetwork, RoadNode, RoadSegment
from src.services.db_service import DatabaseService


@pytest.fixture
def db_service():
    """Creates an in-memory database service for testing."""
    db = DatabaseService(":memory:")
    db.connect()
    yield db
    db.close()


@pytest.fixture
def test_map(db_service):
    """Creates a test map in the database."""
    map_obj = Map(name="Test Map", image_path="/path/to/image.png")
    db_service.insert_map(map_obj)
    return map_obj


def test_update_road_network_command(db_service, test_map):
    """Test UpdateMapRoadsCommand execution."""
    # Create a simple road network
    network = RoadNetwork()
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

    # Execute command
    cmd = UpdateMapRoadsCommand(test_map.id, network)
    result = cmd.execute(db_service)

    assert result.success is True
    assert "Roads updated" in result.message

    # Verify roads are stored
    retrieved_map = db_service.get_map(test_map.id)
    assert retrieved_map is not None
    assert "_roads" in retrieved_map.attributes

    # Verify roads can be deserialized
    stored_network = RoadNetwork.from_dict(retrieved_map.attributes["_roads"])
    assert len(stored_network.nodes) == 2
    assert len(stored_network.segments) == 1


def test_update_road_network_command_undo(db_service, test_map):
    """Test UpdateMapRoadsCommand undo functionality."""
    # Create initial network
    network1 = RoadNetwork()
    node1 = RoadNode(x=10.0, y=20.0)
    network1.add_node(node1)

    # Execute first command
    cmd1 = UpdateMapRoadsCommand(test_map.id, network1)
    cmd1.execute(db_service)

    # Create second network
    network2 = RoadNetwork()
    node2 = RoadNode(x=30.0, y=40.0)
    network2.add_node(node2)

    # Execute second command
    cmd2 = UpdateMapRoadsCommand(test_map.id, network2)
    cmd2.execute(db_service)

    # Verify second network is stored
    retrieved_map = db_service.get_map(test_map.id)
    stored_network = RoadNetwork.from_dict(retrieved_map.attributes["_roads"])
    assert len(stored_network.nodes) == 1
    assert list(stored_network.nodes.values())[0].x == 30.0

    # Undo second command
    cmd2.undo(db_service)

    # Verify first network is restored
    retrieved_map = db_service.get_map(test_map.id)
    stored_network = RoadNetwork.from_dict(retrieved_map.attributes["_roads"])
    assert len(stored_network.nodes) == 1
    assert list(stored_network.nodes.values())[0].x == 10.0


def test_clear_map_roads_command(db_service, test_map):
    """Test ClearMapRoadsCommand execution."""
    # Add roads first
    network = RoadNetwork()
    node = RoadNode(x=5.0, y=10.0)
    network.add_node(node)

    cmd_update = UpdateMapRoadsCommand(test_map.id, network)
    cmd_update.execute(db_service)

    # Verify roads exist
    retrieved_map = db_service.get_map(test_map.id)
    assert "_roads" in retrieved_map.attributes

    # Clear roads
    cmd_clear = ClearMapRoadsCommand(test_map.id)
    result = cmd_clear.execute(db_service)

    assert result.success is True
    assert "cleared" in result.message.lower()

    # Verify roads are removed
    retrieved_map = db_service.get_map(test_map.id)
    assert "_roads" not in retrieved_map.attributes


def test_clear_map_roads_command_undo(db_service, test_map):
    """Test ClearMapRoadsCommand undo functionality."""
    # Add roads
    network = RoadNetwork()
    node = RoadNode(x=15.0, y=25.0)
    network.add_node(node)

    cmd_update = UpdateMapRoadsCommand(test_map.id, network)
    cmd_update.execute(db_service)

    # Clear roads
    cmd_clear = ClearMapRoadsCommand(test_map.id)
    cmd_clear.execute(db_service)

    # Undo clear
    cmd_clear.undo(db_service)

    # Verify roads are restored
    retrieved_map = db_service.get_map(test_map.id)
    assert "_roads" in retrieved_map.attributes

    stored_network = RoadNetwork.from_dict(retrieved_map.attributes["_roads"])
    assert len(stored_network.nodes) == 1
    assert list(stored_network.nodes.values())[0].x == 15.0


def test_get_road_network_helper(db_service, test_map):
    """Test DatabaseService.get_road_network helper method."""
    # Test with no roads
    network = db_service.get_road_network(test_map.id)
    assert network is None

    # Add roads
    new_network = RoadNetwork()
    node = RoadNode(x=50.0, y=50.0)
    new_network.add_node(node)

    db_service.update_road_network(test_map.id, new_network)

    # Retrieve roads
    retrieved_network = db_service.get_road_network(test_map.id)
    assert retrieved_network is not None
    assert len(retrieved_network.nodes) == 1


def test_update_road_network_helper(db_service, test_map):
    """Test DatabaseService.update_road_network helper method."""
    network = RoadNetwork()
    node = RoadNode(x=100.0, y=200.0)
    network.add_node(node)

    # Update using helper
    db_service.update_road_network(test_map.id, network)

    # Verify
    retrieved_map = db_service.get_map(test_map.id)
    assert "_roads" in retrieved_map.attributes

    stored_network = RoadNetwork.from_dict(retrieved_map.attributes["_roads"])
    assert len(stored_network.nodes) == 1


def test_road_network_with_complete_structure(db_service, test_map):
    """Test storing and retrieving a complete road network."""
    # Create a more complex network
    network = RoadNetwork()
    network.meta["px_per_meter"] = 2.0

    # Add nodes
    node1 = RoadNode(x=0.0, y=0.0, attributes={"type": "intersection"})
    node2 = RoadNode(x=100.0, y=0.0, attributes={"type": "endpoint"})
    node3 = RoadNode(x=100.0, y=100.0, attributes={"type": "intersection"})
    network.add_node(node1)
    network.add_node(node2)
    network.add_node(node3)

    # Add segments
    seg1 = RoadSegment(
        start_node_id=node1.id,
        end_node_id=node2.id,
        coords=[[0, 0], [100, 0]],
        length_px=100.0,
        attributes={"speed": 50, "oneway": False},
    )
    seg2 = RoadSegment(
        start_node_id=node2.id,
        end_node_id=node3.id,
        coords=[[100, 0], [100, 100]],
        length_px=100.0,
        attributes={"speed": 30, "oneway": True},
    )
    network.add_segment(seg1)
    network.add_segment(seg2)

    # Add road
    road = Road(
        name="Main Street", segment_ids=[seg1.id, seg2.id], attributes={"type": "urban"}
    )
    network.add_road(road)

    # Store
    cmd = UpdateMapRoadsCommand(test_map.id, network)
    cmd.execute(db_service)

    # Retrieve and verify
    retrieved_network = db_service.get_road_network(test_map.id)
    assert retrieved_network is not None
    assert len(retrieved_network.nodes) == 3
    assert len(retrieved_network.segments) == 2
    assert len(retrieved_network.roads) == 1
    assert retrieved_network.meta["px_per_meter"] == 2.0
    assert retrieved_network.roads[0].name == "Main Street"
    assert retrieved_network.segments[0].attributes["speed"] == 50
