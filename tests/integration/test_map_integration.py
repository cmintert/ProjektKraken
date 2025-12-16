"""Integration tests for map system.

Tests end-to-end workflows including:
- Map creation with asset import
- Marker placement on maps
- Multiple maps per entity/event
- CASCADE deletion behavior
- Coordinate persistence and retrieval
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from src.core.maps import GameMap, MapMarker
from src.core.entities import Entity
from src.core.events import Event
from src.core.asset_manager import AssetManager
from src.commands.map_commands import (
    CreateMapCommand,
    AddMarkerCommand,
    DeleteMapCommand,
)


@pytest.fixture
def temp_project_dir():
    """Create a temporary project directory for integration tests."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def asset_manager(temp_project_dir):
    """Create an AssetManager instance."""
    return AssetManager(temp_project_dir)


@pytest.fixture
def temp_image():
    """Create a temporary test image file."""
    temp_file = tempfile.NamedTemporaryFile(
        mode="wb", suffix=".png", delete=False
    )
    temp_file.write(b"fake PNG image data")
    temp_file.close()
    yield temp_file.name
    Path(temp_file.name).unlink(missing_ok=True)


class TestEndToEndMapCreation:
    """Integration tests for complete map creation workflow."""

    def test_create_map_with_asset(self, db_service, asset_manager, temp_image):
        """Test creating a map and importing its image asset."""
        # Import the image
        relative_path, checksum = asset_manager.import_image(temp_image, "world.png")

        # Create map with the imported image
        map_data = {
            "name": "World Map",
            "image_filename": relative_path,
            "real_width": 1000.0,
            "distance_unit": "km",
            "reference_width": 2048,
            "reference_height": 1024,
        }

        cmd = CreateMapCommand(map_data)
        result = cmd.execute(db_service)

        assert result.success is True

        # Verify map in database
        retrieved_map = db_service.get_map(cmd.game_map.id)
        assert retrieved_map is not None
        assert retrieved_map.name == "World Map"
        assert retrieved_map.image_filename == relative_path

        # Verify image file exists
        abs_path = asset_manager.get_absolute_path(relative_path)
        assert abs_path.exists()

        # Verify checksum
        assert asset_manager.verify_checksum(relative_path, checksum)

    def test_create_map_add_markers_end_to_end(self, db_service):
        """Test complete workflow: create map, create entities, add markers."""
        # 1. Create a map
        game_map = GameMap(
            name="Region Map",
            image_filename="assets/maps/region.png",
            real_width=500.0,
            distance_unit="km",
            reference_width=1000,
            reference_height=1000,
        )
        db_service.insert_map(game_map)

        # 2. Create entities
        city1 = Entity(name="Capital City", type="location")
        city2 = Entity(name="Port Town", type="location")
        db_service.insert_entity(city1)
        db_service.insert_entity(city2)

        # 3. Add markers
        marker1 = MapMarker(
            map_id=game_map.id, object_id=city1.id, object_type="entity", x=0.3, y=0.4
        )
        marker2 = MapMarker(
            map_id=game_map.id, object_id=city2.id, object_type="entity", x=0.7, y=0.8
        )
        db_service.insert_marker(marker1)
        db_service.insert_marker(marker2)

        # 4. Verify retrieval
        markers = db_service.get_markers_for_map(game_map.id)
        assert len(markers) == 2

        # 5. Verify we can get markers by object
        city1_markers = db_service.get_markers_for_object(city1.id, "entity")
        assert len(city1_markers) == 1
        assert city1_markers[0].x == 0.3


class TestMultipleMapsPerObject:
    """Integration tests for objects appearing on multiple maps."""

    def test_entity_on_multiple_maps(self, db_service):
        """Test placing the same entity on multiple maps."""
        # Create entity
        castle = Entity(name="Ancient Castle", type="location")
        db_service.insert_entity(castle)

        # Create multiple maps at different scales
        world_map = GameMap(
            name="World Map",
            image_filename="world.png",
            real_width=10000.0,
            distance_unit="km",
            reference_width=2000,
            reference_height=1000,
        )
        region_map = GameMap(
            name="Region Map",
            image_filename="region.png",
            real_width=500.0,
            distance_unit="km",
            reference_width=1000,
            reference_height=1000,
        )
        local_map = GameMap(
            name="Local Map",
            image_filename="local.png",
            real_width=10.0,
            distance_unit="km",
            reference_width=1000,
            reference_height=1000,
        )

        db_service.insert_map(world_map)
        db_service.insert_map(region_map)
        db_service.insert_map(local_map)

        # Place castle on all three maps
        world_marker = MapMarker(
            map_id=world_map.id,
            object_id=castle.id,
            object_type="entity",
            x=0.45,
            y=0.62,
        )
        region_marker = MapMarker(
            map_id=region_map.id,
            object_id=castle.id,
            object_type="entity",
            x=0.32,
            y=0.78,
        )
        local_marker = MapMarker(
            map_id=local_map.id,
            object_id=castle.id,
            object_type="entity",
            x=0.5,
            y=0.5,
        )

        db_service.insert_marker(world_marker)
        db_service.insert_marker(region_marker)
        db_service.insert_marker(local_marker)

        # Verify castle appears on all maps
        castle_markers = db_service.get_markers_for_object(castle.id, "entity")
        assert len(castle_markers) == 3

        # Verify each map has the castle
        world_markers = db_service.get_markers_for_map(world_map.id)
        assert len(world_markers) == 1
        assert world_markers[0].object_id == castle.id

    def test_event_on_multiple_maps(self, db_service):
        """Test placing the same event on multiple maps."""
        # Create event
        battle = Event(name="Great Battle", lore_date=1000.0)
        db_service.insert_event(battle)

        # Create maps
        strategic_map = GameMap(
            name="Strategic Overview",
            image_filename="strategic.png",
            real_width=1000.0,
            distance_unit="km",
            reference_width=1000,
            reference_height=1000,
        )
        tactical_map = GameMap(
            name="Tactical Map",
            image_filename="tactical.png",
            real_width=50.0,
            distance_unit="km",
            reference_width=1000,
            reference_height=1000,
        )

        db_service.insert_map(strategic_map)
        db_service.insert_map(tactical_map)

        # Place battle on both maps
        strategic_marker = MapMarker(
            map_id=strategic_map.id,
            object_id=battle.id,
            object_type="event",
            x=0.6,
            y=0.4,
        )
        tactical_marker = MapMarker(
            map_id=tactical_map.id,
            object_id=battle.id,
            object_type="event",
            x=0.5,
            y=0.5,
        )

        db_service.insert_marker(strategic_marker)
        db_service.insert_marker(tactical_marker)

        # Verify event appears on both maps
        battle_markers = db_service.get_markers_for_object(battle.id, "event")
        assert len(battle_markers) == 2


class TestCascadeDeletion:
    """Integration tests for CASCADE deletion behavior."""

    def test_delete_map_cascades_to_markers(self, db_service):
        """Test that deleting a map also deletes all its markers."""
        # Setup: Create map with multiple markers
        game_map = GameMap(
            name="Test Map",
            image_filename="test.png",
            real_width=100.0,
            distance_unit="km",
            reference_width=1000,
            reference_height=1000,
        )
        db_service.insert_map(game_map)

        # Create entities and markers
        entities = []
        markers = []
        for i in range(5):
            entity = Entity(name=f"Location {i}", type="location")
            db_service.insert_entity(entity)
            entities.append(entity)

            marker = MapMarker(
                map_id=game_map.id,
                object_id=entity.id,
                object_type="entity",
                x=i * 0.2,
                y=i * 0.2,
            )
            db_service.insert_marker(marker)
            markers.append(marker)

        # Verify markers exist
        assert len(db_service.get_markers_for_map(game_map.id)) == 5

        # Delete map
        db_service.delete_map(game_map.id)

        # Verify all markers were deleted
        for marker in markers:
            assert db_service.get_marker(marker.id) is None

        # Verify entities still exist (not cascaded)
        for entity in entities:
            assert db_service.get_entity(entity.id) is not None

    def test_delete_map_command_with_undo(self, db_service):
        """Test that undoing map deletion restores markers."""
        # Setup
        game_map = GameMap(
            name="Test Map",
            image_filename="test.png",
            real_width=100.0,
            distance_unit="km",
            reference_width=1000,
            reference_height=1000,
        )
        db_service.insert_map(game_map)

        entity = Entity(name="City", type="location")
        db_service.insert_entity(entity)

        marker = MapMarker(
            map_id=game_map.id, object_id=entity.id, object_type="entity", x=0.5, y=0.5
        )
        db_service.insert_marker(marker)

        # Delete using command
        cmd = DeleteMapCommand(game_map.id)
        result = cmd.execute(db_service)
        assert result.success is True

        # Verify deletion
        assert db_service.get_map(game_map.id) is None
        assert db_service.get_marker(marker.id) is None

        # Undo
        cmd.undo(db_service)

        # Verify restoration
        restored_map = db_service.get_map(game_map.id)
        assert restored_map is not None
        assert restored_map.name == "Test Map"

        restored_marker = db_service.get_marker(marker.id)
        assert restored_marker is not None
        assert restored_marker.x == 0.5

    def test_manual_cleanup_markers_on_entity_delete(self, db_service):
        """Test application-level cleanup of markers when entity deleted."""
        # Setup
        game_map = GameMap(
            name="Test Map",
            image_filename="test.png",
            real_width=100.0,
            distance_unit="km",
            reference_width=1000,
            reference_height=1000,
        )
        db_service.insert_map(game_map)

        entity = Entity(name="Temporary City", type="location")
        db_service.insert_entity(entity)

        marker = MapMarker(
            map_id=game_map.id, object_id=entity.id, object_type="entity", x=0.5, y=0.5
        )
        db_service.insert_marker(marker)

        # Verify marker exists
        assert db_service.get_marker(marker.id) is not None

        # Delete entity and clean up markers
        db_service.delete_entity(entity.id)
        db_service.delete_markers_for_object(entity.id, "entity")

        # Verify marker is gone
        assert db_service.get_marker(marker.id) is None

        # Verify map still exists
        assert db_service.get_map(game_map.id) is not None


class TestCoordinatePersistence:
    """Integration tests for coordinate storage and retrieval."""

    def test_normalized_coordinates_persist_correctly(self, db_service):
        """Test that normalized coordinates round-trip through database."""
        game_map = GameMap(
            name="Test Map",
            image_filename="test.png",
            real_width=100.0,
            distance_unit="m",
            reference_width=1000,
            reference_height=1000,
        )
        db_service.insert_map(game_map)

        entity = Entity(name="Test", type="location")
        db_service.insert_entity(entity)

        # Create marker with precise coordinates
        original_x = 0.123456789
        original_y = 0.987654321

        marker = MapMarker(
            map_id=game_map.id,
            object_id=entity.id,
            object_type="entity",
            x=original_x,
            y=original_y,
        )
        db_service.insert_marker(marker)

        # Retrieve and verify precision
        retrieved = db_service.get_marker(marker.id)
        assert abs(retrieved.x - original_x) < 1e-9
        assert abs(retrieved.y - original_y) < 1e-9

    def test_marker_attributes_persist(self, db_service):
        """Test that marker attributes are stored and retrieved correctly."""
        game_map = GameMap(
            name="Test Map",
            image_filename="test.png",
            real_width=100.0,
            distance_unit="m",
            reference_width=1000,
            reference_height=1000,
        )
        db_service.insert_map(game_map)

        entity = Entity(name="Test", type="location")
        db_service.insert_entity(entity)

        marker = MapMarker(
            map_id=game_map.id, object_id=entity.id, object_type="entity", x=0.5, y=0.5
        )
        marker.attributes = {
            "icon": "castle",
            "label": "Capital",
            "visible": True,
            "color": "#FF0000",
        }
        db_service.insert_marker(marker)

        # Retrieve and verify
        retrieved = db_service.get_marker(marker.id)
        assert retrieved.attributes["icon"] == "castle"
        assert retrieved.attributes["label"] == "Capital"
        assert retrieved.attributes["visible"] is True
        assert retrieved.attributes["color"] == "#FF0000"
