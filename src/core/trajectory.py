"""
Trajectory Interpolation Module.

Provides utilities for interpolating entity positions along temporal trajectories.
Uses binary search (bisect) for O(log N) keyframe lookup.
"""

import bisect
from dataclasses import dataclass


@dataclass
class Keyframe:
    """
    A position snapshot at a specific time.

    Attributes:
        t: Time in lore_date units.
        x: Normalized X coordinate [0.0, 1.0].
        y: Normalized Y coordinate [0.0, 1.0].
    """

    t: float
    x: float
    y: float


# Shared tolerance for comparing keyframe timestamps
# (e.g. for UI selection vs DB lookup)
KEYFRAME_TIME_EPSILON: float = 0.01


def interpolate_position(
    keyframes: list[Keyframe], t: float
) -> tuple[float, float] | None:
    """
    Returns the interpolated (x, y) position at time t.

    Uses binary search (bisect) for O(log N) lookup, then linear interpolation
    between the two surrounding keyframes.

    Args:
        keyframes: List of Keyframe objects, must be sorted by time.
        t: The time at which to calculate the position.

    Returns:
        Tuple of (x, y) normalized coordinates, or None if t is outside
        the keyframe range or there are fewer than 2 keyframes.

    Example:
        >>> keyframes = [Keyframe(0, 0.0, 0.0), Keyframe(100, 1.0, 1.0)]
        >>> interpolate_position(keyframes, 50)
        (0.5, 0.5)
    """
    if not keyframes or len(keyframes) < 2:
        return None

    # Extract times for binary search
    times = [kf.t for kf in keyframes]

    # Use bisect_left to find first keyframe at or after t
    idx_left = bisect.bisect_left(times, t)

    # Check for exact match on a keyframe
    if idx_left < len(keyframes) and times[idx_left] == t:
        # Exact match - return this keyframe's position
        return (keyframes[idx_left].x, keyframes[idx_left].y)

    # Use bisect_right to find insertion point for interpolation
    idx = bisect.bisect_right(times, t)

    if idx == 0:
        # Before first keyframe: clamp to start
        return (keyframes[0].x, keyframes[0].y)
    if idx >= len(keyframes):
        # After last keyframe: clamp to end
        return (keyframes[-1].x, keyframes[-1].y)

    # Get surrounding keyframes
    kf_start = keyframes[idx - 1]
    kf_end = keyframes[idx]

    # Calculate interpolation factor (alpha: 0.0 to 1.0)
    dt = kf_end.t - kf_start.t
    if dt == 0:
        # Coincident keyframes: return start position to avoid division by zero
        return (kf_start.x, kf_start.y)

    alpha = (t - kf_start.t) / dt

    # Linear interpolation (Lerp)
    x = kf_start.x + (kf_end.x - kf_start.x) * alpha
    y = kf_start.y + (kf_end.y - kf_start.y) * alpha

    return (x, y)


def keyframes_to_mfjson(keyframes: list[Keyframe]) -> dict:
    """
    Serialize a list of Keyframes to an OGC MF-JSON MovingPoint structure.

    Args:
        keyframes: List of Keyframe objects.

    Returns:
        A dict representing an MF-JSON TemporalPrimitiveGeometry (MovingPoint).

    Raises:
        ValueError: If keyframes list is empty.

    Example:
        >>> kfs = [Keyframe(t=0, x=0.1, y=0.2), Keyframe(t=100, x=0.9, y=0.8)]
        >>> keyframes_to_mfjson(kfs)  # doctest: +NORMALIZE_WHITESPACE
        {'type': 'MovingPoint', 'coordinates': [[0.1, 0.2], [0.9, 0.8]],
         'datetimes': [0, 100]}
    """
    if not keyframes:
        raise ValueError("Cannot serialize an empty keyframes list.")

    return {
        "type": "MovingPoint",
        "coordinates": [[kf.x, kf.y] for kf in keyframes],
        "datetimes": [kf.t for kf in keyframes],
    }


def mfjson_to_keyframes(data: dict) -> list[Keyframe]:
    """
    Deserialize an OGC MF-JSON MovingPoint structure to a list of Keyframes.

    Args:
        data: A dict representing an MF-JSON TemporalPrimitiveGeometry.

    Returns:
        A list of Keyframe objects.

    Raises:
        ValueError: If 'datetimes' key is missing or lengths mismatch.

    Example:
        >>> mfjson = {'type': 'MovingPoint', 'coordinates': [[0.1, 0.2]],
        ...           'datetimes': [0]}
        >>> mfjson_to_keyframes(mfjson)
        [Keyframe(t=0, x=0.1, y=0.2)]
    """
    if "datetimes" not in data:
        raise ValueError("MF-JSON data is missing 'datetimes' key.")

    coords = data.get("coordinates", [])
    times = data["datetimes"]

    if len(coords) != len(times):
        raise ValueError(
            f"Coordinates/datetimes length mismatch: {len(coords)} vs {len(times)}."
        )

    return [Keyframe(t=t, x=coord[0], y=coord[1]) for t, coord in zip(times, coords)]
