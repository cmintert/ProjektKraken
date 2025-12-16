"""Unit tests for map commands."""

import pytest
from src.commands.map_commands import (
    CreateMapCommand,
    UpdateMapCommand,
    DeleteMapCommand,
    AddMarkerCommand,
    UpdateMarkerCommand,
    DeleteMarkerCommand,
)
from src.core.maps import GameMap, MapMarker
from src.core.entities import Entity
from src.core.events import Event


class TestCreateMapCommand:
    """Tests for CreateMapCommand."""

    def test_create_map_success(self, db_service):
        """Test creating a map successfully."""
        map_data = {
            "name": "Test Map",
            "image_filename": "test.png",
            "real_width": 100.0,
            "distance_unit": "km",
            "reference_width": 1000,
            "reference_height": 800,
        }
        cmd = CreateMapCommand(map_data)
        result = cmd.execute(db_service)

        assert result.success is True
        assert "created" in result.message.lower()
        assert db_service.get_map(cmd.game_map.id) is not None

    def test_create_map_undo(self, db_service):
        """Test undoing map creation."""
        map_data = {
            "name": "Temporary Map",
            "image_filename": "temp.png",
            "real_width": 50.0,
            "distance_unit": "m",
            "reference_width": 500,
            "reference_height": 500,
        }
        cmd = CreateMapCommand(map_data)

        # Execute
        result = cmd.execute(db_service)
        assert result.success is True
        map_id = cmd.game_map.id
        assert db_service.get_map(map_id) is not None

        # Undo
        cmd.undo(db_service)
        assert db_service.get_map(map_id) is None


class TestUpdateMapCommand:
    """Tests for UpdateMapCommand."""

    def test_update_map_success(self, db_service):
        """Test updating a map successfully."""
        # Create initial map
        game_map = GameMap(
            name="Original",
            image_filename="original.png",
            real_width=100.0,
            distance_unit="m",
            reference_width=1000,
            reference_height=1000,
        )
        db_service.insert_map(game_map)

        # Update
        cmd = UpdateMapCommand(game_map.id, {"name": "Updated", "real_width": 200.0})
        result = cmd.execute(db_service)

        assert result.success is True
        updated = db_service.get_map(game_map.id)
        assert updated.name == "Updated"
        assert updated.real_width == 200.0

    def test_update_map_not_found(self, db_service):
        """Test updating a non-existent map."""
        cmd = UpdateMapCommand("non-existent-id", {"name": "Test"})
        result = cmd.execute(db_service)

        assert result.success is False
        assert "not found" in result.message.lower()

    def test_update_map_empty_name(self, db_service):
        """Test that empty names are rejected."""
        game_map = GameMap(
            name="Test",
            image_filename="test.png",
            real_width=100.0,
            distance_unit="m",
            reference_width=1000,
            reference_height=1000,
        )
        db_service.insert_map(game_map)

        cmd = UpdateMapCommand(game_map.id, {"name": ""})
        result = cmd.execute(db_service)

        assert result.success is False
        assert "empty" in result.message.lower()

    def test_update_map_undo(self, db_service):
        """Test undoing a map update."""
        game_map = GameMap(
            name="Original",
            image_filename="original.png",
            real_width=100.0,
            distance_unit="m",
            reference_width=1000,
            reference_height=1000,
        )
        db_service.insert_map(game_map)

        cmd = UpdateMapCommand(game_map.id, {"name": "Modified"})
        result = cmd.execute(db_service)
        assert result.success is True

        # Undo
        cmd.undo(db_service)
        restored = db_service.get_map(game_map.id)
        assert restored.name == "Original"


class TestDeleteMapCommand:
    """Tests for DeleteMapCommand."""

    def test_delete_map_success(self, db_service):
        """Test deleting a map successfully."""
        game_map = GameMap(
            name="To Delete",
            image_filename="delete.png",
            real_width=100.0,
            distance_unit="m",
            reference_width=1000,
            reference_height=1000,
        )
        db_service.insert_map(game_map)

        cmd = DeleteMapCommand(game_map.id)
        result = cmd.execute(db_service)

        assert result.success is True
        assert db_service.get_map(game_map.id) is None

    def test_delete_map_not_found(self, db_service):
        """Test deleting a non-existent map."""
        cmd = DeleteMapCommand("non-existent-id")
        result = cmd.execute(db_service)

        assert result.success is False
        assert "not found" in result.message.lower()

    def test_delete_map_undo(self, db_service):
        """Test undoing a map deletion."""
        game_map = GameMap(
            name="Test Map",
            image_filename="test.png",
            real_width=100.0,
            distance_unit="m",
            reference_width=1000,
            reference_height=1000,
        )
        db_service.insert_map(game_map)

        cmd = DeleteMapCommand(game_map.id)
        result = cmd.execute(db_service)
        assert result.success is True

        # Undo
        cmd.undo(db_service)
        restored = db_service.get_map(game_map.id)
        assert restored is not None
        assert restored.name == "Test Map"

    def test_delete_map_restores_markers(self, db_service):
        """Test that undoing map deletion also restores markers."""
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

        # Delete map (cascades to marker)
        cmd = DeleteMapCommand(game_map.id)
        result = cmd.execute(db_service)
        assert result.success is True
        assert db_service.get_marker(marker.id) is None

        # Undo
        cmd.undo(db_service)
        restored_marker = db_service.get_marker(marker.id)
        assert restored_marker is not None
        assert restored_marker.x == 0.5


class TestAddMarkerCommand:
    """Tests for AddMarkerCommand."""

    def test_add_marker_success(self, db_service):
        """Test adding a marker successfully."""
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

        # Add marker
        marker_data = {
            "map_id": game_map.id,
            "object_id": entity.id,
            "object_type": "entity",
            "x": 0.5,
            "y": 0.75,
        }
        cmd = AddMarkerCommand(marker_data)
        result = cmd.execute(db_service)

        assert result.success is True
        assert db_service.get_marker(cmd.marker.id) is not None

    def test_add_marker_map_not_found(self, db_service):
        """Test adding a marker to non-existent map fails."""
        marker_data = {
            "map_id": "non-existent-map",
            "object_id": "some-object",
            "object_type": "entity",
            "x": 0.5,
            "y": 0.5,
        }
        cmd = AddMarkerCommand(marker_data)
        result = cmd.execute(db_service)

        assert result.success is False
        assert "not found" in result.message.lower()

    def test_add_marker_undo(self, db_service):
        """Test undoing marker addition."""
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

        # Add marker
        marker_data = {
            "map_id": game_map.id,
            "object_id": entity.id,
            "object_type": "entity",
            "x": 0.5,
            "y": 0.5,
        }
        cmd = AddMarkerCommand(marker_data)
        result = cmd.execute(db_service)
        assert result.success is True
        marker_id = cmd.marker.id

        # Undo
        cmd.undo(db_service)
        assert db_service.get_marker(marker_id) is None


class TestUpdateMarkerCommand:
    """Tests for UpdateMarkerCommand."""

    def test_update_marker_position(self, db_service):
        """Test updating marker position."""
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

        # Update position
        cmd = UpdateMarkerCommand(marker.id, {"x": 0.7, "y": 0.3})
        result = cmd.execute(db_service)

        assert result.success is True
        updated = db_service.get_marker(marker.id)
        assert updated.x == 0.7
        assert updated.y == 0.3

    def test_update_marker_invalid_coordinates(self, db_service):
        """Test that invalid coordinates are rejected."""
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

        # Try invalid x
        cmd = UpdateMarkerCommand(marker.id, {"x": 1.5})
        result = cmd.execute(db_service)

        assert result.success is False
        assert "invalid" in result.message.lower()

    def test_update_marker_undo(self, db_service):
        """Test undoing marker update."""
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

        # Update
        cmd = UpdateMarkerCommand(marker.id, {"x": 0.8, "y": 0.2})
        result = cmd.execute(db_service)
        assert result.success is True

        # Undo
        cmd.undo(db_service)
        restored = db_service.get_marker(marker.id)
        assert restored.x == 0.5
        assert restored.y == 0.5


class TestDeleteMarkerCommand:
    """Tests for DeleteMarkerCommand."""

    def test_delete_marker_success(self, db_service):
        """Test deleting a marker successfully."""
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

        # Delete
        cmd = DeleteMarkerCommand(marker.id)
        result = cmd.execute(db_service)

        assert result.success is True
        assert db_service.get_marker(marker.id) is None

    def test_delete_marker_not_found(self, db_service):
        """Test deleting a non-existent marker."""
        cmd = DeleteMarkerCommand("non-existent-id")
        result = cmd.execute(db_service)

        assert result.success is False
        assert "not found" in result.message.lower()

    def test_delete_marker_undo(self, db_service):
        """Test undoing marker deletion."""
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

        # Delete
        cmd = DeleteMarkerCommand(marker.id)
        result = cmd.execute(db_service)
        assert result.success is True

        # Undo
        cmd.undo(db_service)
        restored = db_service.get_marker(marker.id)
        assert restored is not None
        assert restored.x == 0.5
        assert restored.y == 0.5
