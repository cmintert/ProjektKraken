"""
Map Math Utilities.

Provides utilities for coordinate conversion and spatial calculations:
- Pixel to normalized coordinate conversion
- Normalized to pixel coordinate conversion
- Distance calculations between markers
- Area calculations for polygons
- Aspect ratio change detection

All calculations respect map calibration (real_width, distance_unit).
"""

import math
from typing import List, Tuple
from src.core.maps import GameMap, MapMarker


def pixel_to_normalized(
    pixel_x: float, pixel_y: float, image_width: int, image_height: int
) -> Tuple[float, float]:
    """
    Converts pixel coordinates to normalized coordinates [0.0, 1.0].

    Args:
        pixel_x: X coordinate in pixels.
        pixel_y: Y coordinate in pixels.
        image_width: Current image width in pixels.
        image_height: Current image height in pixels.

    Returns:
        Tuple[float, float]: (normalized_x, normalized_y) in [0.0, 1.0]

    Raises:
        ValueError: If image dimensions are invalid.
    """
    if image_width <= 0 or image_height <= 0:
        raise ValueError("Image dimensions must be positive")

    normalized_x = pixel_x / image_width
    normalized_y = pixel_y / image_height

    # Clamp to [0.0, 1.0]
    normalized_x = max(0.0, min(1.0, normalized_x))
    normalized_y = max(0.0, min(1.0, normalized_y))

    return (normalized_x, normalized_y)


def normalized_to_pixel(
    normalized_x: float, normalized_y: float, image_width: int, image_height: int
) -> Tuple[float, float]:
    """
    Converts normalized coordinates [0.0, 1.0] to pixel coordinates.

    Args:
        normalized_x: X coordinate in [0.0, 1.0].
        normalized_y: Y coordinate in [0.0, 1.0].
        image_width: Current image width in pixels.
        image_height: Current image height in pixels.

    Returns:
        Tuple[float, float]: (pixel_x, pixel_y)

    Raises:
        ValueError: If normalized coordinates are out of range.
    """
    if not (0.0 <= normalized_x <= 1.0):
        raise ValueError(f"normalized_x must be in [0.0, 1.0], got {normalized_x}")
    if not (0.0 <= normalized_y <= 1.0):
        raise ValueError(f"normalized_y must be in [0.0, 1.0], got {normalized_y}")

    pixel_x = normalized_x * image_width
    pixel_y = normalized_y * image_height

    return (pixel_x, pixel_y)


def calculate_distance(
    marker1: MapMarker, marker2: MapMarker, game_map: GameMap
) -> float:
    """
    Calculates the real-world distance between two markers on the same map.

    Uses the map's calibration (real_width and aspect ratio) to convert
    normalized coordinates to real-world distances.

    Args:
        marker1: First marker.
        marker2: Second marker.
        game_map: The map both markers are on.

    Returns:
        float: Distance in the map's distance_unit.

    Raises:
        ValueError: If markers are not on the same map.
    """
    if marker1.map_id != game_map.id or marker2.map_id != game_map.id:
        raise ValueError("Both markers must be on the specified map")

    # Calculate deltas in normalized space
    dx_normalized = marker2.x - marker1.x
    dy_normalized = marker2.y - marker1.y

    # Convert to real-world space
    dx_real = dx_normalized * game_map.real_width
    dy_real = dy_normalized * game_map.real_height

    # Euclidean distance
    distance = math.sqrt(dx_real**2 + dy_real**2)

    return distance


def calculate_area(markers: List[MapMarker], game_map: GameMap) -> float:
    """
    Calculates the area of a polygon defined by markers on a map.

    Uses the shoelace formula to compute the area. Markers should be ordered
    clockwise or counter-clockwise around the polygon perimeter.

    Args:
        markers: List of markers defining the polygon vertices (ordered).
        game_map: The map the markers are on.

    Returns:
        float: Area in (distance_unit)^2.

    Raises:
        ValueError: If fewer than 3 markers provided or markers not on same map.
    """
    if len(markers) < 3:
        raise ValueError("Need at least 3 markers to define a polygon")

    # Verify all markers are on the same map
    for marker in markers:
        if marker.map_id != game_map.id:
            raise ValueError("All markers must be on the specified map")

    # Convert normalized coordinates to real-world coordinates
    real_coords = [
        (m.x * game_map.real_width, m.y * game_map.real_height) for m in markers
    ]

    # Shoelace formula
    area = 0.0
    n = len(real_coords)
    for i in range(n):
        x1, y1 = real_coords[i]
        x2, y2 = real_coords[(i + 1) % n]
        area += x1 * y2 - x2 * y1

    area = abs(area) / 2.0
    return area


def detect_aspect_ratio_change(
    old_width: int, old_height: int, new_width: int, new_height: int, tolerance: float = 0.01
) -> bool:
    """
    Detects if image dimensions changed aspect ratio beyond tolerance.

    Args:
        old_width: Previous image width in pixels.
        old_height: Previous image height in pixels.
        new_width: New image width in pixels.
        new_height: New image height in pixels.
        tolerance: Allowed aspect ratio difference (default 1%).

    Returns:
        bool: True if aspect ratio changed beyond tolerance, False otherwise.
    """
    if old_width <= 0 or old_height <= 0 or new_width <= 0 or new_height <= 0:
        raise ValueError("Image dimensions must be positive")

    old_ratio = old_width / old_height
    new_ratio = new_width / new_height

    relative_change = abs(new_ratio - old_ratio) / old_ratio
    return relative_change > tolerance


def compute_coordinate_migration(
    marker: MapMarker,
    old_width: int,
    old_height: int,
    new_width: int,
    new_height: int,
    crop_offset_x: int = 0,
    crop_offset_y: int = 0,
) -> Tuple[float, float]:
    """
    Computes new normalized coordinates after image crop/extend operation.

    When an image is cropped or extended (aspect ratio change), this function
    calculates where a marker should be positioned on the new image.

    Args:
        marker: The marker to migrate.
        old_width: Previous image width in pixels.
        old_height: Previous image height in pixels.
        new_width: New image width in pixels.
        new_height: New image height in pixels.
        crop_offset_x: Pixels cropped from left (negative if extended).
        crop_offset_y: Pixels cropped from top (negative if extended).

    Returns:
        Tuple[float, float]: (new_normalized_x, new_normalized_y)
    """
    # Convert to old pixel coordinates
    old_pixel_x = marker.x * old_width
    old_pixel_y = marker.y * old_height

    # Apply crop offset
    new_pixel_x = old_pixel_x - crop_offset_x
    new_pixel_y = old_pixel_y - crop_offset_y

    # Convert to new normalized coordinates
    new_normalized_x, new_normalized_y = pixel_to_normalized(
        new_pixel_x, new_pixel_y, new_width, new_height
    )

    return (new_normalized_x, new_normalized_y)


def calculate_scale_factor(
    old_width: int, old_height: int, new_width: int, new_height: int
) -> Tuple[float, float]:
    """
    Calculates the scale factor between old and new image dimensions.

    Args:
        old_width: Previous image width in pixels.
        old_height: Previous image height in pixels.
        new_width: New image width in pixels.
        new_height: New image height in pixels.

    Returns:
        Tuple[float, float]: (x_scale_factor, y_scale_factor)
    """
    if old_width <= 0 or old_height <= 0:
        raise ValueError("Old dimensions must be positive")
    if new_width <= 0 or new_height <= 0:
        raise ValueError("New dimensions must be positive")

    x_scale = new_width / old_width
    y_scale = new_height / old_height

    return (x_scale, y_scale)
