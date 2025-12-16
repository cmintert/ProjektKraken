"""Unit tests for map database operations."""

import pytest
from src.core.maps import GameMap, MapMarker
from src.core.entities import Entity
from src.core.events import Event


def test_map_crud(db_service):
    """Test Create, Read, Update, Delete for Maps."""
    # Create
    game_map = GameMap(
        name="World Map",
        image_filename="assets/maps/world.png",
        real_width=1000.0,
        distance_unit="km",
        reference_width=2048,
        reference_height=1024,
    )
    game_map.attributes["checksum"] = "abc123"
    db_service.insert_map(game_map)

    # Read
    fetched = db_service.get_map(game_map.id)
    assert fetched is not None
    assert fetched.name == "World Map"
    assert fetched.image_filename == "assets/maps/world.png"
    assert fetched.real_width == 1000.0
    assert fetched.distance_unit == "km"
    assert fetched.reference_width == 2048
    assert fetched.reference_height == 1024
    assert fetched.attributes["checksum"] == "abc123"

    # Update
    game_map.name = "Updated World Map"
    game_map.real_width = 1500.0
    db_service.insert_map(game_map)
    fetched_updated = db_service.get_map(game_map.id)
    assert fetched_updated.name == "Updated World Map"
    assert fetched_updated.real_width == 1500.0

    # Delete
    db_service.delete_map(game_map.id)
    assert db_service.get_map(game_map.id) is None


def test_get_all_maps(db_service):
    """Test fetching all maps ordered by name."""
    map1 = GameMap(
        name="Zeta Region",
        image_filename="zeta.png",
        real_width=100.0,
        distance_unit="km",
        reference_width=1000,
        reference_height=1000,
    )
    map2 = GameMap(
        name="Alpha City",
        image_filename="alpha.png",
        real_width=50.0,
        distance_unit="km",
        reference_width=1000,
        reference_height=1000,
    )
    map3 = GameMap(
        name="Beta Continent",
        image_filename="beta.png",
        real_width=5000.0,
        distance_unit="km",
        reference_width=2000,
        reference_height=1500,
    )

    db_service.insert_map(map1)
    db_service.insert_map(map2)
    db_service.insert_map(map3)

    maps = db_service.get_all_maps()
    assert len(maps) == 3
    assert maps[0].name == "Alpha City"
    assert maps[1].name == "Beta Continent"
    assert maps[2].name == "Zeta Region"


def test_marker_crud(db_service):
    """Test Create, Read, Update, Delete for MapMarkers."""
    # Setup: Create a map and an entity
    game_map = GameMap(
        name="Test Map",
        image_filename="test.png",
        real_width=100.0,
        distance_unit="m",
        reference_width=1000,
        reference_height=1000,
    )
    db_service.insert_map(game_map)

    entity = Entity(name="Test City", type="location")
    db_service.insert_entity(entity)

    # Create marker
    marker = MapMarker(
        map_id=game_map.id,
        object_id=entity.id,
        object_type="entity",
        x=0.5,
        y=0.75,
    )
    marker.attributes["icon"] = "castle"
    db_service.insert_marker(marker)

    # Read
    fetched = db_service.get_marker(marker.id)
    assert fetched is not None
    assert fetched.map_id == game_map.id
    assert fetched.object_id == entity.id
    assert fetched.object_type == "entity"
    assert fetched.x == 0.5
    assert fetched.y == 0.75
    assert fetched.attributes["icon"] == "castle"

    # Update
    marker.x = 0.6
    marker.y = 0.8
    marker.attributes["icon"] = "city"
    db_service.insert_marker(marker)
    fetched_updated = db_service.get_marker(marker.id)
    assert fetched_updated.x == 0.6
    assert fetched_updated.y == 0.8
    assert fetched_updated.attributes["icon"] == "city"

    # Delete
    db_service.delete_marker(marker.id)
    assert db_service.get_marker(marker.id) is None


def test_get_markers_for_map(db_service):
    """Test retrieving all markers on a specific map."""
    # Setup: Create a map
    game_map = GameMap(
        name="Test Map",
        image_filename="test.png",
        real_width=100.0,
        distance_unit="m",
        reference_width=1000,
        reference_height=1000,
    )
    db_service.insert_map(game_map)

    # Create entities and events
    entity1 = Entity(name="City A", type="location")
    entity2 = Entity(name="City B", type="location")
    event1 = Event(name="Battle", lore_date=100.0)

    db_service.insert_entity(entity1)
    db_service.insert_entity(entity2)
    db_service.insert_event(event1)

    # Create markers
    marker1 = MapMarker(
        map_id=game_map.id, object_id=entity1.id, object_type="entity", x=0.1, y=0.1
    )
    marker2 = MapMarker(
        map_id=game_map.id, object_id=entity2.id, object_type="entity", x=0.2, y=0.2
    )
    marker3 = MapMarker(
        map_id=game_map.id, object_id=event1.id, object_type="event", x=0.3, y=0.3
    )

    db_service.insert_marker(marker1)
    db_service.insert_marker(marker2)
    db_service.insert_marker(marker3)

    # Retrieve all markers for the map
    markers = db_service.get_markers_for_map(game_map.id)
    assert len(markers) == 3

    # Verify different object types
    entity_markers = [m for m in markers if m.object_type == "entity"]
    event_markers = [m for m in markers if m.object_type == "event"]
    assert len(entity_markers) == 2
    assert len(event_markers) == 1


def test_get_markers_for_object(db_service):
    """Test retrieving all markers for a specific object across multiple maps."""
    # Setup: Create two maps
    map1 = GameMap(
        name="Map 1",
        image_filename="map1.png",
        real_width=100.0,
        distance_unit="m",
        reference_width=1000,
        reference_height=1000,
    )
    map2 = GameMap(
        name="Map 2",
        image_filename="map2.png",
        real_width=200.0,
        distance_unit="m",
        reference_width=1000,
        reference_height=1000,
    )
    db_service.insert_map(map1)
    db_service.insert_map(map2)

    # Create an entity
    entity = Entity(name="Important Location", type="location")
    db_service.insert_entity(entity)

    # Place the entity on both maps
    marker1 = MapMarker(
        map_id=map1.id, object_id=entity.id, object_type="entity", x=0.5, y=0.5
    )
    marker2 = MapMarker(
        map_id=map2.id, object_id=entity.id, object_type="entity", x=0.7, y=0.3
    )
    db_service.insert_marker(marker1)
    db_service.insert_marker(marker2)

    # Retrieve all markers for the entity
    markers = db_service.get_markers_for_object(entity.id, "entity")
    assert len(markers) == 2

    map_ids = {m.map_id for m in markers}
    assert map1.id in map_ids
    assert map2.id in map_ids


def test_delete_map_cascades_markers(db_service):
    """Test that deleting a map also deletes all its markers (CASCADE)."""
    # Setup
    game_map = GameMap(
        name="Test Map",
        image_filename="test.png",
        real_width=100.0,
        distance_unit="m",
        reference_width=1000,
        reference_height=1000,
    )
    db_service.insert_map(game_map)

    entity = Entity(name="Test Entity", type="location")
    db_service.insert_entity(entity)

    marker = MapMarker(
        map_id=game_map.id, object_id=entity.id, object_type="entity", x=0.5, y=0.5
    )
    db_service.insert_marker(marker)

    # Verify marker exists
    assert db_service.get_marker(marker.id) is not None

    # Delete map
    db_service.delete_map(game_map.id)

    # Verify marker was also deleted
    assert db_service.get_marker(marker.id) is None


def test_delete_markers_for_object(db_service):
    """Test deleting all markers for a specific object."""
    # Setup
    map1 = GameMap(
        name="Map 1",
        image_filename="map1.png",
        real_width=100.0,
        distance_unit="m",
        reference_width=1000,
        reference_height=1000,
    )
    map2 = GameMap(
        name="Map 2",
        image_filename="map2.png",
        real_width=100.0,
        distance_unit="m",
        reference_width=1000,
        reference_height=1000,
    )
    db_service.insert_map(map1)
    db_service.insert_map(map2)

    entity = Entity(name="Test Entity", type="location")
    db_service.insert_entity(entity)

    marker1 = MapMarker(
        map_id=map1.id, object_id=entity.id, object_type="entity", x=0.5, y=0.5
    )
    marker2 = MapMarker(
        map_id=map2.id, object_id=entity.id, object_type="entity", x=0.7, y=0.3
    )
    db_service.insert_marker(marker1)
    db_service.insert_marker(marker2)

    # Verify both markers exist
    assert len(db_service.get_markers_for_object(entity.id, "entity")) == 2

    # Delete all markers for the entity
    db_service.delete_markers_for_object(entity.id, "entity")

    # Verify markers are gone
    assert len(db_service.get_markers_for_object(entity.id, "entity")) == 0


def test_marker_unique_constraint(db_service):
    """Test that the UNIQUE constraint on (map_id, object_id, object_type) works."""
    # Setup
    game_map = GameMap(
        name="Test Map",
        image_filename="test.png",
        real_width=100.0,
        distance_unit="m",
        reference_width=1000,
        reference_height=1000,
    )
    db_service.insert_map(game_map)

    entity = Entity(name="Test Entity", type="location")
    db_service.insert_entity(entity)

    # Create first marker
    marker1 = MapMarker(
        map_id=game_map.id, object_id=entity.id, object_type="entity", x=0.5, y=0.5
    )
    db_service.insert_marker(marker1)

    # Try to create a second marker for the same object on the same map
    # This should update instead of creating a duplicate
    marker2 = MapMarker(
        map_id=game_map.id, object_id=entity.id, object_type="entity", x=0.7, y=0.3
    )
    db_service.insert_marker(marker2)

    # Should only be one marker
    markers = db_service.get_markers_for_object(entity.id, "entity")
    assert len(markers) == 1
    # Should have the updated position
    assert markers[0].x == 0.7
    assert markers[0].y == 0.3


def test_map_real_height_property(db_service):
    """Test that GameMap.real_height works correctly with database round-trip."""
    game_map = GameMap(
        name="Aspect Test",
        image_filename="aspect.png",
        real_width=200.0,
        distance_unit="km",
        reference_width=2000,
        reference_height=1000,
    )
    db_service.insert_map(game_map)

    fetched = db_service.get_map(game_map.id)
    assert fetched.real_height == 100.0
