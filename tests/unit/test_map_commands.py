"""
Unit tests for map and marker commands.
"""

from src.commands.map_commands import (
    CreateMapCommand,
    CreateMarkerCommand,
    DeleteMapCommand,
    DeleteMarkerCommand,
    UpdateMapCommand,
    UpdateMarkerCommand,
)
from src.core.map import Map
from src.core.marker import Marker


def test_create_map_command(db_service):
    """Test creating a map via command."""
    cmd = CreateMapCommand({"name": "World Map", "image_path": "/world.png"})
    result = cmd.execute(db_service)

    assert result.success is True
    assert "World Map" in result.message
    assert "id" in result.data

    # Verify map exists in database
    map_obj = db_service.get_map(result.data["id"])
    assert map_obj is not None
    assert map_obj.name == "World Map"


def test_create_map_command_undo(db_service):
    """Test undoing map creation."""
    cmd = CreateMapCommand({"name": "Test Map", "image_path": "/test.png"})
    result = cmd.execute(db_service)
    map_id = result.data["id"]

    # Verify map exists
    assert db_service.get_map(map_id) is not None

    # Undo
    cmd.undo(db_service)

    # Verify map is deleted
    assert db_service.get_map(map_id) is None


def test_update_map_command(db_service):
    """Test updating a map via command."""
    # Create initial map
    map_obj = Map(name="Old Name", image_path="/old.png")
    db_service.insert_map(map_obj)

    # Update via command
    cmd = UpdateMapCommand(map_obj.id, {"name": "New Name"})
    result = cmd.execute(db_service)

    assert result.success is True

    # Verify update
    updated = db_service.get_map(map_obj.id)
    assert updated.name == "New Name"
    assert updated.image_path == "/old.png"  # Unchanged


def test_update_map_command_undo(db_service):
    """Test undoing map update."""
    # Create initial map
    map_obj = Map(name="Original", image_path="/orig.png")
    db_service.insert_map(map_obj)

    # Update
    cmd = UpdateMapCommand(map_obj.id, {"name": "Modified"})
    cmd.execute(db_service)

    # Verify update
    assert db_service.get_map(map_obj.id).name == "Modified"

    # Undo
    cmd.undo(db_service)

    # Verify restored
    assert db_service.get_map(map_obj.id).name == "Original"


def test_delete_map_command(db_service):
    """Test deleting a map via command."""
    # Create map with markers
    map_obj = Map(name="Test Map", image_path="/test.png")
    db_service.insert_map(map_obj)

    marker1 = Marker(
        map_id=map_obj.id, object_id="e1", object_type="entity", x=0.1, y=0.1
    )
    marker2 = Marker(
        map_id=map_obj.id, object_id="e2", object_type="entity", x=0.2, y=0.2
    )
    db_service.insert_marker(marker1)
    db_service.insert_marker(marker2)

    # Delete via command
    cmd = DeleteMapCommand(map_obj.id)
    result = cmd.execute(db_service)

    assert result.success is True

    # Verify deletion
    assert db_service.get_map(map_obj.id) is None
    assert len(db_service.get_markers_for_map(map_obj.id)) == 0


def test_delete_map_command_undo(db_service):
    """Test undoing map deletion."""
    # Create map with markers
    map_obj = Map(name="Test Map", image_path="/test.png")
    db_service.insert_map(map_obj)

    marker1 = Marker(
        map_id=map_obj.id, object_id="e1", object_type="entity", x=0.1, y=0.1
    )
    db_service.insert_marker(marker1)

    # Delete
    cmd = DeleteMapCommand(map_obj.id)
    cmd.execute(db_service)

    # Undo
    cmd.undo(db_service)

    # Verify restoration
    restored_map = db_service.get_map(map_obj.id)
    assert restored_map is not None
    assert restored_map.name == "Test Map"

    restored_markers = db_service.get_markers_for_map(map_obj.id)
    assert len(restored_markers) == 1


def test_create_marker_command(db_service):
    """Test creating a marker via command."""
    # Create map
    map_obj = Map(name="Test Map", image_path="/test.png")
    db_service.insert_map(map_obj)

    # Create marker via command
    cmd = CreateMarkerCommand(
        {
            "map_id": map_obj.id,
            "object_id": "entity-123",
            "object_type": "entity",
            "x": 0.5,
            "y": 0.5,
            "label": "Castle",
        }
    )
    result = cmd.execute(db_service)

    assert result.success is True
    assert "id" in result.data

    # Verify marker exists
    marker = db_service.get_marker(result.data["id"])
    assert marker is not None
    assert marker.x == 0.5
    assert marker.y == 0.5
    assert marker.label == "Castle"


def test_create_marker_command_upsert(db_service):
    """Test that CreateMarkerCommand handles upsert correctly."""
    # Create map
    map_obj = Map(name="Test Map", image_path="/test.png")
    db_service.insert_map(map_obj)

    # Create initial marker
    cmd1 = CreateMarkerCommand(
        {
            "map_id": map_obj.id,
            "object_id": "entity-456",
            "object_type": "entity",
            "x": 0.3,
            "y": 0.4,
        }
    )
    result1 = cmd1.execute(db_service)
    marker1_id = result1.data["id"]

    # Create another marker with same composite key
    cmd2 = CreateMarkerCommand(
        {
            "map_id": map_obj.id,
            "object_id": "entity-456",
            "object_type": "entity",
            "x": 0.8,
            "y": 0.9,
        }
    )
    result2 = cmd2.execute(db_service)

    # Should return same ID (upsert occurred)
    assert result2.data["id"] == marker1_id

    # Should only have one marker
    markers = db_service.get_markers_for_map(map_obj.id)
    assert len(markers) == 1

    # Position should be updated
    updated = db_service.get_marker(marker1_id)
    assert updated.x == 0.8
    assert updated.y == 0.9


def test_create_marker_command_undo(db_service):
    """Test undoing marker creation."""
    # Create map
    map_obj = Map(name="Test Map", image_path="/test.png")
    db_service.insert_map(map_obj)

    # Create marker
    cmd = CreateMarkerCommand(
        {
            "map_id": map_obj.id,
            "object_id": "entity-789",
            "object_type": "entity",
            "x": 0.6,
            "y": 0.7,
        }
    )
    result = cmd.execute(db_service)
    marker_id = result.data["id"]

    # Verify exists
    assert db_service.get_marker(marker_id) is not None

    # Undo
    cmd.undo(db_service)

    # Verify deleted
    assert db_service.get_marker(marker_id) is None


def test_update_marker_command(db_service):
    """Test updating a marker via command."""
    # Create map and marker
    map_obj = Map(name="Test Map", image_path="/test.png")
    db_service.insert_map(map_obj)

    marker = Marker(
        map_id=map_obj.id,
        object_id="entity-111",
        object_type="entity",
        x=0.2,
        y=0.3,
        label="Old Label",
    )
    marker_id = db_service.insert_marker(marker)

    # Update via command
    cmd = UpdateMarkerCommand(marker_id, {"x": 0.8, "y": 0.9, "label": "New Label"})
    result = cmd.execute(db_service)

    assert result.success is True

    # Verify update
    updated = db_service.get_marker(marker_id)
    assert updated.x == 0.8
    assert updated.y == 0.9
    assert updated.label == "New Label"


def test_update_marker_command_undo(db_service):
    """Test undoing marker update."""
    # Create map and marker
    map_obj = Map(name="Test Map", image_path="/test.png")
    db_service.insert_map(map_obj)

    marker = Marker(
        map_id=map_obj.id,
        object_id="entity-222",
        object_type="entity",
        x=0.4,
        y=0.5,
    )
    marker_id = db_service.insert_marker(marker)

    # Update
    cmd = UpdateMarkerCommand(marker_id, {"x": 0.9, "y": 0.8})
    cmd.execute(db_service)

    # Verify update
    assert db_service.get_marker(marker_id).x == 0.9

    # Undo
    cmd.undo(db_service)

    # Verify restored
    restored = db_service.get_marker(marker_id)
    assert restored.x == 0.4
    assert restored.y == 0.5


def test_delete_marker_command(db_service):
    """Test deleting a marker via command."""
    # Create map and marker
    map_obj = Map(name="Test Map", image_path="/test.png")
    db_service.insert_map(map_obj)

    marker = Marker(
        map_id=map_obj.id,
        object_id="entity-333",
        object_type="entity",
        x=0.1,
        y=0.2,
    )
    marker_id = db_service.insert_marker(marker)

    # Delete via command
    cmd = DeleteMarkerCommand(marker_id)
    result = cmd.execute(db_service)

    assert result.success is True

    # Verify deletion
    assert db_service.get_marker(marker_id) is None


def test_delete_marker_command_undo(db_service):
    """Test undoing marker deletion."""
    # Create map and marker
    map_obj = Map(name="Test Map", image_path="/test.png")
    db_service.insert_map(map_obj)

    marker = Marker(
        map_id=map_obj.id,
        object_id="entity-444",
        object_type="entity",
        x=0.7,
        y=0.8,
        label="Restored",
    )
    marker_id = db_service.insert_marker(marker)

    # Delete
    cmd = DeleteMarkerCommand(marker_id)
    cmd.execute(db_service)

    # Undo
    cmd.undo(db_service)

    # Verify restoration
    restored = db_service.get_marker(marker_id)
    assert restored is not None
    assert restored.x == 0.7
    assert restored.y == 0.8
    assert restored.label == "Restored"
