"""Unit tests for core map models."""

import pytest
from src.core.maps import GameMap, MapMarker


class TestGameMap:
    """Tests for the GameMap dataclass."""

    def test_game_map_creation(self):
        """Test that GameMap instances are created correctly."""
        game_map = GameMap(
            name="World Map",
            image_filename="assets/maps/world.png",
            real_width=1000.0,
            distance_unit="km",
            reference_width=2048,
            reference_height=1024,
        )

        assert game_map.name == "World Map"
        assert game_map.image_filename == "assets/maps/world.png"
        assert game_map.real_width == 1000.0
        assert game_map.distance_unit == "km"
        assert game_map.reference_width == 2048
        assert game_map.reference_height == 1024
        assert game_map.id is not None
        assert game_map.created_at > 0
        assert game_map.modified_at > 0
        assert isinstance(game_map.attributes, dict)

    def test_game_map_real_height(self):
        """Test that real_height is computed correctly from aspect ratio."""
        game_map = GameMap(
            name="Square Map",
            image_filename="square.png",
            real_width=100.0,
            distance_unit="m",
            reference_width=1000,
            reference_height=1000,
        )
        assert game_map.real_height == 100.0

        wide_map = GameMap(
            name="Wide Map",
            image_filename="wide.png",
            real_width=200.0,
            distance_unit="m",
            reference_width=2000,
            reference_height=1000,
        )
        assert wide_map.real_height == 100.0

        tall_map = GameMap(
            name="Tall Map",
            image_filename="tall.png",
            real_width=100.0,
            distance_unit="m",
            reference_width=1000,
            reference_height=2000,
        )
        assert tall_map.real_height == 200.0

    def test_game_map_to_dict(self):
        """Test GameMap serialization to dictionary."""
        game_map = GameMap(
            name="Test Map",
            image_filename="test.png",
            real_width=50.0,
            distance_unit="m",
            reference_width=500,
            reference_height=500,
        )
        game_map.attributes = {"checksum": "abc123"}

        data = game_map.to_dict()

        assert data["name"] == "Test Map"
        assert data["image_filename"] == "test.png"
        assert data["real_width"] == 50.0
        assert data["distance_unit"] == "m"
        assert data["reference_width"] == 500
        assert data["reference_height"] == 500
        assert data["attributes"]["checksum"] == "abc123"
        assert "id" in data
        assert "created_at" in data
        assert "modified_at" in data

    def test_game_map_from_dict(self):
        """Test GameMap deserialization from dictionary."""
        data = {
            "id": "test-id-123",
            "name": "Test Map",
            "image_filename": "test.png",
            "real_width": 75.0,
            "distance_unit": "km",
            "reference_width": 800,
            "reference_height": 600,
            "attributes": {"note": "test note"},
            "created_at": 1234567890.0,
            "modified_at": 1234567891.0,
        }

        game_map = GameMap.from_dict(data)

        assert game_map.id == "test-id-123"
        assert game_map.name == "Test Map"
        assert game_map.image_filename == "test.png"
        assert game_map.real_width == 75.0
        assert game_map.distance_unit == "km"
        assert game_map.reference_width == 800
        assert game_map.reference_height == 600
        assert game_map.attributes["note"] == "test note"
        assert game_map.created_at == 1234567890.0
        assert game_map.modified_at == 1234567891.0

    def test_game_map_round_trip(self):
        """Test that to_dict/from_dict round-trip preserves data."""
        original = GameMap(
            name="Original",
            image_filename="original.png",
            real_width=123.45,
            distance_unit="mi",
            reference_width=1920,
            reference_height=1080,
        )
        original.attributes = {"custom": "value"}

        data = original.to_dict()
        restored = GameMap.from_dict(data)

        assert restored.id == original.id
        assert restored.name == original.name
        assert restored.image_filename == original.image_filename
        assert restored.real_width == original.real_width
        assert restored.distance_unit == original.distance_unit
        assert restored.reference_width == original.reference_width
        assert restored.reference_height == original.reference_height
        assert restored.attributes == original.attributes
        assert restored.created_at == original.created_at
        assert restored.modified_at == original.modified_at

    def test_game_map_validation_reference_width(self):
        """Test that invalid reference_width raises error."""
        with pytest.raises(ValueError, match="Reference dimensions must be positive"):
            GameMap(
                name="Invalid",
                image_filename="test.png",
                real_width=100.0,
                distance_unit="m",
                reference_width=0,
                reference_height=1000,
            )

    def test_game_map_validation_reference_height(self):
        """Test that invalid reference_height raises error."""
        with pytest.raises(ValueError, match="Reference dimensions must be positive"):
            GameMap(
                name="Invalid",
                image_filename="test.png",
                real_width=100.0,
                distance_unit="m",
                reference_width=1000,
                reference_height=-1,
            )

    def test_game_map_validation_real_width(self):
        """Test that invalid real_width raises error."""
        with pytest.raises(ValueError, match="Real width must be positive"):
            GameMap(
                name="Invalid",
                image_filename="test.png",
                real_width=0.0,
                distance_unit="m",
                reference_width=1000,
                reference_height=1000,
            )


class TestMapMarker:
    """Tests for the MapMarker dataclass."""

    def test_map_marker_creation_entity(self):
        """Test that MapMarker for entity is created correctly."""
        marker = MapMarker(
            map_id="map-123",
            object_id="entity-456",
            object_type="entity",
            x=0.5,
            y=0.75,
        )

        assert marker.map_id == "map-123"
        assert marker.object_id == "entity-456"
        assert marker.object_type == "entity"
        assert marker.x == 0.5
        assert marker.y == 0.75
        assert marker.id is not None
        assert isinstance(marker.attributes, dict)

    def test_map_marker_creation_event(self):
        """Test that MapMarker for event is created correctly."""
        marker = MapMarker(
            map_id="map-789",
            object_id="event-012",
            object_type="event",
            x=0.1,
            y=0.9,
        )

        assert marker.object_type == "event"
        assert marker.object_id == "event-012"

    def test_map_marker_coordinate_validation(self):
        """Test that coordinates are validated to be in [0.0, 1.0]."""
        # Valid coordinates at boundaries
        marker = MapMarker(
            map_id="map-1",
            object_id="obj-1",
            object_type="entity",
            x=0.0,
            y=1.0,
        )
        assert marker.x == 0.0
        assert marker.y == 1.0

        # Invalid x coordinate
        with pytest.raises(ValueError, match="x coordinate must be in"):
            MapMarker(
                map_id="map-1",
                object_id="obj-1",
                object_type="entity",
                x=-0.1,
                y=0.5,
            )

        with pytest.raises(ValueError, match="x coordinate must be in"):
            MapMarker(
                map_id="map-1",
                object_id="obj-1",
                object_type="entity",
                x=1.1,
                y=0.5,
            )

        # Invalid y coordinate
        with pytest.raises(ValueError, match="y coordinate must be in"):
            MapMarker(
                map_id="map-1",
                object_id="obj-1",
                object_type="entity",
                x=0.5,
                y=-0.1,
            )

        with pytest.raises(ValueError, match="y coordinate must be in"):
            MapMarker(
                map_id="map-1",
                object_id="obj-1",
                object_type="entity",
                x=0.5,
                y=1.5,
            )

    def test_map_marker_object_type_validation(self):
        """Test that object_type is validated."""
        with pytest.raises(ValueError, match="object_type must be"):
            MapMarker(
                map_id="map-1",
                object_id="obj-1",
                object_type="invalid",
                x=0.5,
                y=0.5,
            )

    def test_map_marker_to_dict(self):
        """Test MapMarker serialization to dictionary."""
        marker = MapMarker(
            map_id="map-abc",
            object_id="entity-def",
            object_type="entity",
            x=0.25,
            y=0.75,
        )
        marker.attributes = {"icon": "castle", "label": "Capital"}

        data = marker.to_dict()

        assert data["map_id"] == "map-abc"
        assert data["object_id"] == "entity-def"
        assert data["object_type"] == "entity"
        assert data["x"] == 0.25
        assert data["y"] == 0.75
        assert data["attributes"]["icon"] == "castle"
        assert data["attributes"]["label"] == "Capital"
        assert "id" in data

    def test_map_marker_from_dict(self):
        """Test MapMarker deserialization from dictionary."""
        data = {
            "id": "marker-xyz",
            "map_id": "map-123",
            "object_id": "event-456",
            "object_type": "event",
            "x": 0.33,
            "y": 0.66,
            "attributes": {"visible": True},
        }

        marker = MapMarker.from_dict(data)

        assert marker.id == "marker-xyz"
        assert marker.map_id == "map-123"
        assert marker.object_id == "event-456"
        assert marker.object_type == "event"
        assert marker.x == 0.33
        assert marker.y == 0.66
        assert marker.attributes["visible"] is True

    def test_map_marker_round_trip(self):
        """Test that to_dict/from_dict round-trip preserves data."""
        original = MapMarker(
            map_id="map-original",
            object_id="object-original",
            object_type="entity",
            x=0.123,
            y=0.456,
        )
        original.attributes = {"custom": "data"}

        data = original.to_dict()
        restored = MapMarker.from_dict(data)

        assert restored.id == original.id
        assert restored.map_id == original.map_id
        assert restored.object_id == original.object_id
        assert restored.object_type == original.object_type
        assert restored.x == original.x
        assert restored.y == original.y
        assert restored.attributes == original.attributes
