"""Unit tests for map math utilities."""

import pytest
import math
from src.core.map_math import (
    pixel_to_normalized,
    normalized_to_pixel,
    calculate_distance,
    calculate_area,
    detect_aspect_ratio_change,
    compute_coordinate_migration,
    calculate_scale_factor,
)
from src.core.maps import GameMap, MapMarker


class TestCoordinateConversion:
    """Tests for coordinate conversion functions."""

    def test_pixel_to_normalized_center(self):
        """Test converting center pixel to normalized coordinates."""
        nx, ny = pixel_to_normalized(500, 400, 1000, 800)
        assert nx == 0.5
        assert ny == 0.5

    def test_pixel_to_normalized_corners(self):
        """Test converting corner pixels to normalized coordinates."""
        # Top-left
        nx, ny = pixel_to_normalized(0, 0, 1000, 800)
        assert nx == 0.0
        assert ny == 0.0

        # Bottom-right
        nx, ny = pixel_to_normalized(1000, 800, 1000, 800)
        assert nx == 1.0
        assert ny == 1.0

    def test_pixel_to_normalized_clamps(self):
        """Test that out-of-bounds pixels are clamped to [0.0, 1.0]."""
        # Negative coordinates
        nx, ny = pixel_to_normalized(-10, -10, 1000, 800)
        assert nx == 0.0
        assert ny == 0.0

        # Beyond bounds
        nx, ny = pixel_to_normalized(1500, 1000, 1000, 800)
        assert nx == 1.0
        assert ny == 1.0

    def test_pixel_to_normalized_invalid_dimensions(self):
        """Test that invalid image dimensions raise error."""
        with pytest.raises(ValueError):
            pixel_to_normalized(100, 100, 0, 800)

        with pytest.raises(ValueError):
            pixel_to_normalized(100, 100, 1000, -1)

    def test_normalized_to_pixel_center(self):
        """Test converting center normalized to pixel coordinates."""
        px, py = normalized_to_pixel(0.5, 0.5, 1000, 800)
        assert px == 500.0
        assert py == 400.0

    def test_normalized_to_pixel_corners(self):
        """Test converting corner normalized to pixel coordinates."""
        # Top-left
        px, py = normalized_to_pixel(0.0, 0.0, 1000, 800)
        assert px == 0.0
        assert py == 0.0

        # Bottom-right
        px, py = normalized_to_pixel(1.0, 1.0, 1000, 800)
        assert px == 1000.0
        assert py == 800.0

    def test_normalized_to_pixel_invalid_coordinates(self):
        """Test that out-of-range normalized coordinates raise error."""
        with pytest.raises(ValueError):
            normalized_to_pixel(-0.1, 0.5, 1000, 800)

        with pytest.raises(ValueError):
            normalized_to_pixel(0.5, 1.5, 1000, 800)

    def test_coordinate_round_trip(self):
        """Test that pixel -> normalized -> pixel preserves coordinates."""
        original_x, original_y = 750, 300
        width, height = 1000, 500

        nx, ny = pixel_to_normalized(original_x, original_y, width, height)
        px, py = normalized_to_pixel(nx, ny, width, height)

        assert px == original_x
        assert py == original_y


class TestDistanceCalculation:
    """Tests for distance calculation."""

    def test_calculate_distance_horizontal(self):
        """Test distance calculation for horizontal line."""
        game_map = GameMap(
            name="Test",
            image_filename="test.png",
            real_width=100.0,
            distance_unit="m",
            reference_width=1000,
            reference_height=1000,
        )

        marker1 = MapMarker(
            map_id=game_map.id, object_id="1", object_type="entity", x=0.0, y=0.5
        )
        marker2 = MapMarker(
            map_id=game_map.id, object_id="2", object_type="entity", x=1.0, y=0.5
        )

        distance = calculate_distance(marker1, marker2, game_map)
        assert distance == 100.0

    def test_calculate_distance_vertical(self):
        """Test distance calculation for vertical line."""
        game_map = GameMap(
            name="Test",
            image_filename="test.png",
            real_width=100.0,
            distance_unit="m",
            reference_width=1000,
            reference_height=1000,
        )

        marker1 = MapMarker(
            map_id=game_map.id, object_id="1", object_type="entity", x=0.5, y=0.0
        )
        marker2 = MapMarker(
            map_id=game_map.id, object_id="2", object_type="entity", x=0.5, y=1.0
        )

        distance = calculate_distance(marker1, marker2, game_map)
        assert distance == 100.0  # real_height = real_width for square map

    def test_calculate_distance_diagonal(self):
        """Test distance calculation for diagonal line."""
        game_map = GameMap(
            name="Test",
            image_filename="test.png",
            real_width=100.0,
            distance_unit="m",
            reference_width=1000,
            reference_height=1000,
        )

        marker1 = MapMarker(
            map_id=game_map.id, object_id="1", object_type="entity", x=0.0, y=0.0
        )
        marker2 = MapMarker(
            map_id=game_map.id, object_id="2", object_type="entity", x=1.0, y=1.0
        )

        distance = calculate_distance(marker1, marker2, game_map)
        expected = math.sqrt(100.0**2 + 100.0**2)
        assert abs(distance - expected) < 0.001

    def test_calculate_distance_aspect_ratio(self):
        """Test distance calculation respects aspect ratio."""
        # Wide map: real_height = real_width * (height/width) = 100 * (500/1000) = 50
        game_map = GameMap(
            name="Wide",
            image_filename="wide.png",
            real_width=100.0,
            distance_unit="m",
            reference_width=1000,
            reference_height=500,
        )

        marker1 = MapMarker(
            map_id=game_map.id, object_id="1", object_type="entity", x=0.5, y=0.0
        )
        marker2 = MapMarker(
            map_id=game_map.id, object_id="2", object_type="entity", x=0.5, y=1.0
        )

        distance = calculate_distance(marker1, marker2, game_map)
        assert distance == 50.0  # Full height = 50m

    def test_calculate_distance_same_point(self):
        """Test distance calculation for same point is zero."""
        game_map = GameMap(
            name="Test",
            image_filename="test.png",
            real_width=100.0,
            distance_unit="m",
            reference_width=1000,
            reference_height=1000,
        )

        marker = MapMarker(
            map_id=game_map.id, object_id="1", object_type="entity", x=0.5, y=0.5
        )

        distance = calculate_distance(marker, marker, game_map)
        assert distance == 0.0

    def test_calculate_distance_different_maps_raises(self):
        """Test that calculating distance between markers on different maps raises error."""
        map1 = GameMap(
            name="Map1",
            image_filename="map1.png",
            real_width=100.0,
            distance_unit="m",
            reference_width=1000,
            reference_height=1000,
        )
        map2 = GameMap(
            name="Map2",
            image_filename="map2.png",
            real_width=100.0,
            distance_unit="m",
            reference_width=1000,
            reference_height=1000,
        )

        marker1 = MapMarker(
            map_id=map1.id, object_id="1", object_type="entity", x=0.0, y=0.0
        )
        marker2 = MapMarker(
            map_id=map2.id, object_id="2", object_type="entity", x=1.0, y=1.0
        )

        with pytest.raises(ValueError):
            calculate_distance(marker1, marker2, map1)


class TestAreaCalculation:
    """Tests for area calculation."""

    def test_calculate_area_square(self):
        """Test area calculation for a square."""
        game_map = GameMap(
            name="Test",
            image_filename="test.png",
            real_width=100.0,
            distance_unit="m",
            reference_width=1000,
            reference_height=1000,
        )

        # Unit square in normalized coordinates = 100m x 100m in real coordinates
        markers = [
            MapMarker(
                map_id=game_map.id, object_id="1", object_type="entity", x=0.0, y=0.0
            ),
            MapMarker(
                map_id=game_map.id, object_id="2", object_type="entity", x=1.0, y=0.0
            ),
            MapMarker(
                map_id=game_map.id, object_id="3", object_type="entity", x=1.0, y=1.0
            ),
            MapMarker(
                map_id=game_map.id, object_id="4", object_type="entity", x=0.0, y=1.0
            ),
        ]

        area = calculate_area(markers, game_map)
        assert area == 10000.0  # 100m * 100m

    def test_calculate_area_triangle(self):
        """Test area calculation for a triangle."""
        game_map = GameMap(
            name="Test",
            image_filename="test.png",
            real_width=100.0,
            distance_unit="m",
            reference_width=1000,
            reference_height=1000,
        )

        # Right triangle: base=1.0 (100m), height=1.0 (100m)
        markers = [
            MapMarker(
                map_id=game_map.id, object_id="1", object_type="entity", x=0.0, y=0.0
            ),
            MapMarker(
                map_id=game_map.id, object_id="2", object_type="entity", x=1.0, y=0.0
            ),
            MapMarker(
                map_id=game_map.id, object_id="3", object_type="entity", x=0.0, y=1.0
            ),
        ]

        area = calculate_area(markers, game_map)
        assert area == 5000.0  # (100 * 100) / 2

    def test_calculate_area_too_few_markers(self):
        """Test that area calculation requires at least 3 markers."""
        game_map = GameMap(
            name="Test",
            image_filename="test.png",
            real_width=100.0,
            distance_unit="m",
            reference_width=1000,
            reference_height=1000,
        )

        markers = [
            MapMarker(
                map_id=game_map.id, object_id="1", object_type="entity", x=0.0, y=0.0
            ),
            MapMarker(
                map_id=game_map.id, object_id="2", object_type="entity", x=1.0, y=0.0
            ),
        ]

        with pytest.raises(ValueError):
            calculate_area(markers, game_map)

    def test_calculate_area_aspect_ratio(self):
        """Test area calculation respects aspect ratio."""
        # Wide map: real_height = 50m
        game_map = GameMap(
            name="Wide",
            image_filename="wide.png",
            real_width=100.0,
            distance_unit="m",
            reference_width=1000,
            reference_height=500,
        )

        # Unit square in normalized coordinates = 100m x 50m
        markers = [
            MapMarker(
                map_id=game_map.id, object_id="1", object_type="entity", x=0.0, y=0.0
            ),
            MapMarker(
                map_id=game_map.id, object_id="2", object_type="entity", x=1.0, y=0.0
            ),
            MapMarker(
                map_id=game_map.id, object_id="3", object_type="entity", x=1.0, y=1.0
            ),
            MapMarker(
                map_id=game_map.id, object_id="4", object_type="entity", x=0.0, y=1.0
            ),
        ]

        area = calculate_area(markers, game_map)
        assert area == 5000.0  # 100m * 50m


class TestAspectRatioDetection:
    """Tests for aspect ratio change detection."""

    def test_detect_aspect_ratio_no_change(self):
        """Test that same aspect ratio returns False."""
        # Same ratio: 1000/800 = 1.25
        changed = detect_aspect_ratio_change(1000, 800, 2000, 1600)
        assert changed is False

    def test_detect_aspect_ratio_slight_change_within_tolerance(self):
        """Test that changes within tolerance return False."""
        # Slightly different but within 1% tolerance
        changed = detect_aspect_ratio_change(1000, 800, 1005, 804, tolerance=0.01)
        assert changed is False

    def test_detect_aspect_ratio_change_beyond_tolerance(self):
        """Test that changes beyond tolerance return True."""
        # From 1.25 to 2.0 - significant change
        changed = detect_aspect_ratio_change(1000, 800, 1000, 500)
        assert changed is True

    def test_detect_aspect_ratio_invalid_dimensions(self):
        """Test that invalid dimensions raise error."""
        with pytest.raises(ValueError):
            detect_aspect_ratio_change(0, 800, 1000, 800)

        with pytest.raises(ValueError):
            detect_aspect_ratio_change(1000, -1, 1000, 800)


class TestCoordinateMigration:
    """Tests for coordinate migration after image changes."""

    def test_compute_coordinate_migration_no_crop(self):
        """Test migration when image is just resized (no crop)."""
        marker = MapMarker(
            map_id="test", object_id="1", object_type="entity", x=0.5, y=0.5
        )

        # When there's no crop (offset=0) and aspect ratio is preserved,
        # normalized coordinates stay the same through pixel conversion
        # Old pixel: (0.5 * 1000, 0.5 * 1000) = (500, 500)
        # New pixel: (500, 500) [no offset applied]
        # New normalized: (500/1000, 500/1000) = (0.5, 0.5)
        new_x, new_y = compute_coordinate_migration(
            marker, 1000, 1000, 1000, 1000, crop_offset_x=0, crop_offset_y=0
        )

        # Should remain at center when same dimensions
        assert new_x == 0.5
        assert new_y == 0.5

    def test_compute_coordinate_migration_with_crop(self):
        """Test migration when image is cropped."""
        # Marker at center of original image
        marker = MapMarker(
            map_id="test", object_id="1", object_type="entity", x=0.5, y=0.5
        )

        # Crop 100 pixels from left and top
        new_x, new_y = compute_coordinate_migration(
            marker, 1000, 1000, 900, 900, crop_offset_x=100, crop_offset_y=100
        )

        # Original center was at (500, 500)
        # After cropping 100px from left/top, it's at (400, 400) in new image
        # Normalized: 400/900 = 0.444...
        assert abs(new_x - 0.4444) < 0.001
        assert abs(new_y - 0.4444) < 0.001


class TestScaleFactor:
    """Tests for scale factor calculation."""

    def test_calculate_scale_factor_upscale(self):
        """Test calculating scale factor for upscaling."""
        x_scale, y_scale = calculate_scale_factor(1000, 800, 2000, 1600)
        assert x_scale == 2.0
        assert y_scale == 2.0

    def test_calculate_scale_factor_downscale(self):
        """Test calculating scale factor for downscaling."""
        x_scale, y_scale = calculate_scale_factor(2000, 1600, 1000, 800)
        assert x_scale == 0.5
        assert y_scale == 0.5

    def test_calculate_scale_factor_different_axes(self):
        """Test scale factor when x and y scale differently."""
        x_scale, y_scale = calculate_scale_factor(1000, 1000, 2000, 1000)
        assert x_scale == 2.0
        assert y_scale == 1.0

    def test_calculate_scale_factor_invalid_dimensions(self):
        """Test that invalid dimensions raise error."""
        with pytest.raises(ValueError):
            calculate_scale_factor(0, 800, 1000, 800)

        with pytest.raises(ValueError):
            calculate_scale_factor(1000, 800, -1, 800)
