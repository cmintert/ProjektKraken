"""
Unit tests for map and marker database operations.
"""

from src.core.map import Map
from src.core.marker import Marker


def test_map_crud(db_service):
    """Test Create, Read, Update, Delete for Maps."""
    # Create
    map_obj = Map(name="World Map", image_path="/path/to/map.png")
    map_obj.description = "Main world map"
    map_obj.attributes["scale"] = "1:1000"
    db_service.insert_map(map_obj)

    # Read
    fetched = db_service.get_map(map_obj.id)
    assert fetched is not None
    assert fetched.name == "World Map"
    assert fetched.image_path == "/path/to/map.png"
    assert fetched.description == "Main world map"
    assert fetched.attributes["scale"] == "1:1000"

    # Update
    map_obj.name = "Updated World Map"
    db_service.insert_map(map_obj)  # Should upsert
    fetched_updated = db_service.get_map(map_obj.id)
    assert fetched_updated.name == "Updated World Map"

    # Delete
    db_service.delete_map(map_obj.id)
    assert db_service.get_map(map_obj.id) is None


def test_get_all_maps(db_service):
    """Test fetching all maps ordered by name."""
    m1 = Map(name="Dungeon Map", image_path="/dungeon.png")
    m2 = Map(name="City Map", image_path="/city.png")
    m3 = Map(name="World Map", image_path="/world.png")

    db_service.insert_map(m1)
    db_service.insert_map(m2)
    db_service.insert_map(m3)

    maps = db_service.get_all_maps()
    assert len(maps) == 3
    assert maps[0].name == "City Map"
    assert maps[1].name == "Dungeon Map"
    assert maps[2].name == "World Map"


def test_marker_crud(db_service):
    """Test Create, Read, Update, Delete for Markers."""
    # Setup map
    map_obj = Map(name="Test Map", image_path="/test.png")
    db_service.insert_map(map_obj)

    # Create marker
    marker = Marker(
        map_id=map_obj.id,
        object_id="entity-123",
        object_type="entity",
        x=0.5,
        y=0.5,
        label="Castle",
    )
    marker.attributes["icon"] = "castle"
    marker_id = db_service.insert_marker(marker)
    assert marker_id is not None

    # Read
    fetched = db_service.get_marker(marker_id)
    assert fetched is not None
    assert fetched.map_id == map_obj.id
    assert fetched.object_id == "entity-123"
    assert fetched.object_type == "entity"
    assert fetched.x == 0.5
    assert fetched.y == 0.5
    assert fetched.label == "Castle"
    assert fetched.attributes["icon"] == "castle"

    # Update position
    marker.x = 0.6
    marker.y = 0.7
    updated_id = db_service.insert_marker(marker)
    fetched_updated = db_service.get_marker(updated_id)
    assert fetched_updated.x == 0.6
    assert fetched_updated.y == 0.7

    # Delete
    db_service.delete_marker(marker_id)
    assert db_service.get_marker(marker_id) is None


def test_marker_upsert_behavior(db_service):
    """
    Test that insert_marker upserts on UNIQUE(map_id, object_id, object_type).

    When a conflict occurs, the existing row is updated and its ID is retained.
    """
    # Setup map
    map_obj = Map(name="Test Map", image_path="/test.png")
    db_service.insert_map(map_obj)

    # Create initial marker
    marker1 = Marker(
        map_id=map_obj.id,
        object_id="entity-456",
        object_type="entity",
        x=0.3,
        y=0.4,
    )
    marker1_id = db_service.insert_marker(marker1)

    # Create another marker with same composite key but different ID
    marker2 = Marker(
        map_id=map_obj.id,
        object_id="entity-456",
        object_type="entity",
        x=0.8,
        y=0.9,
    )
    # marker2 has a different id than marker1
    assert marker2.id != marker1.id

    # Insert should update existing marker, not create new one
    returned_id = db_service.insert_marker(marker2)

    # The returned ID should be the original marker's ID
    assert returned_id == marker1_id

    # Verify only one marker exists
    markers = db_service.get_markers_for_map(map_obj.id)
    assert len(markers) == 1

    # Verify position was updated
    updated_marker = db_service.get_marker(marker1_id)
    assert updated_marker.x == 0.8
    assert updated_marker.y == 0.9


def test_get_markers_for_map(db_service):
    """Test retrieving all markers for a specific map."""
    # Setup maps
    map1 = Map(name="Map 1", image_path="/map1.png")
    map2 = Map(name="Map 2", image_path="/map2.png")
    db_service.insert_map(map1)
    db_service.insert_map(map2)

    # Add markers to map1
    m1 = Marker(map_id=map1.id, object_id="e1", object_type="entity", x=0.1, y=0.1)
    m2 = Marker(map_id=map1.id, object_id="e2", object_type="entity", x=0.2, y=0.2)
    # Add marker to map2
    m3 = Marker(map_id=map2.id, object_id="e3", object_type="entity", x=0.3, y=0.3)

    db_service.insert_marker(m1)
    db_service.insert_marker(m2)
    db_service.insert_marker(m3)

    # Verify map1 has 2 markers
    map1_markers = db_service.get_markers_for_map(map1.id)
    assert len(map1_markers) == 2

    # Verify map2 has 1 marker
    map2_markers = db_service.get_markers_for_map(map2.id)
    assert len(map2_markers) == 1


def test_get_markers_for_object(db_service):
    """Test retrieving all markers for a specific entity or event."""
    # Setup maps
    map1 = Map(name="Map 1", image_path="/map1.png")
    map2 = Map(name="Map 2", image_path="/map2.png")
    db_service.insert_map(map1)
    db_service.insert_map(map2)

    # Add markers for same entity on different maps
    m1 = Marker(
        map_id=map1.id, object_id="entity-999", object_type="entity", x=0.1, y=0.1
    )
    m2 = Marker(
        map_id=map2.id, object_id="entity-999", object_type="entity", x=0.2, y=0.2
    )
    # Add marker for different entity
    m3 = Marker(
        map_id=map1.id, object_id="entity-888", object_type="entity", x=0.3, y=0.3
    )

    db_service.insert_marker(m1)
    db_service.insert_marker(m2)
    db_service.insert_marker(m3)

    # Verify entity-999 has 2 markers
    entity_markers = db_service.get_markers_for_object("entity-999", "entity")
    assert len(entity_markers) == 2

    # Verify entity-888 has 1 marker
    other_markers = db_service.get_markers_for_object("entity-888", "entity")
    assert len(other_markers) == 1


def test_get_marker_by_composite(db_service):
    """Test retrieving marker by composite key."""
    # Setup map
    map_obj = Map(name="Test Map", image_path="/test.png")
    db_service.insert_map(map_obj)

    # Create marker
    marker = Marker(
        map_id=map_obj.id,
        object_id="entity-777",
        object_type="entity",
        x=0.5,
        y=0.5,
    )
    marker_id = db_service.insert_marker(marker)

    # Retrieve by composite key
    fetched = db_service.get_marker_by_composite(map_obj.id, "entity-777", "entity")
    assert fetched is not None
    assert fetched.id == marker_id
    assert fetched.x == 0.5
    assert fetched.y == 0.5

    # Try non-existent composite
    not_found = db_service.get_marker_by_composite(
        map_obj.id, "entity-nonexistent", "entity"
    )
    assert not_found is None


def test_cascade_delete_markers(db_service):
    """Test that deleting a map cascades to delete its markers."""
    # Setup map
    map_obj = Map(name="Test Map", image_path="/test.png")
    db_service.insert_map(map_obj)

    # Add markers
    m1 = Marker(map_id=map_obj.id, object_id="e1", object_type="entity", x=0.1, y=0.1)
    m2 = Marker(map_id=map_obj.id, object_id="e2", object_type="entity", x=0.2, y=0.2)
    id1 = db_service.insert_marker(m1)
    id2 = db_service.insert_marker(m2)

    # Verify markers exist
    assert db_service.get_marker(id1) is not None
    assert db_service.get_marker(id2) is not None

    # Delete map
    db_service.delete_map(map_obj.id)

    # Verify markers are deleted
    assert db_service.get_marker(id1) is None
    assert db_service.get_marker(id2) is None


def test_marker_normalized_coordinates(db_service):
    """Test that markers store normalized coordinates correctly."""
    # Setup map
    map_obj = Map(name="Test Map", image_path="/test.png")
    db_service.insert_map(map_obj)

    # Create markers at corners
    top_left = Marker(
        map_id=map_obj.id, object_id="tl", object_type="entity", x=0.0, y=0.0
    )
    bottom_right = Marker(
        map_id=map_obj.id, object_id="br", object_type="entity", x=1.0, y=1.0
    )
    center = Marker(
        map_id=map_obj.id, object_id="c", object_type="entity", x=0.5, y=0.5
    )

    db_service.insert_marker(top_left)
    db_service.insert_marker(bottom_right)
    db_service.insert_marker(center)

    # Verify coordinates
    tl = db_service.get_marker_by_composite(map_obj.id, "tl", "entity")
    assert tl.x == 0.0 and tl.y == 0.0

    br = db_service.get_marker_by_composite(map_obj.id, "br", "entity")
    assert br.x == 1.0 and br.y == 1.0

    c = db_service.get_marker_by_composite(map_obj.id, "c", "entity")
    assert c.x == 0.5 and c.y == 0.5
