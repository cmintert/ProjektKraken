"""Trajectory Interpolation Module.

Provides utilities for interpolating entity positions along temporal trajectories. Uses
binary search (bisect) for O(log N) keyframe lookup.
"""

import bisect
import copy
import math
import uuid
from dataclasses import dataclass
from dataclasses import replace as dataclass_replace
from typing import Any, Iterable, Literal, Mapping, Sequence, TypeVar, cast


@dataclass
class Keyframe:
    """A position snapshot at a specific time.

    Attributes:
        t: Time in lore_date units.
        x: Normalized X coordinate [0.0, 1.0].
        y: Normalized Y coordinate [0.0, 1.0].

    """

    t: float
    x: float
    y: float
    keyframe_id: str | None = None


@dataclass(frozen=True)
class EditableKeyframe:
    """A keyframe with stable persisted identity.

    ``edit_id`` is stored beside MF-JSON in trajectory metadata. The immutable
    value object makes working-copy updates explicit and prevents a selected
    keyframe from losing its identity when temporal edits re-sort the track.

    Attributes:
        edit_id: Stable identifier within one trajectory edit session.
        t: Time in lore-date units.
        x: Normalized X coordinate in the inclusive range ``[0.0, 1.0]``.
        y: Normalized Y coordinate in the inclusive range ``[0.0, 1.0]``.

    """

    edit_id: str
    t: float
    x: float
    y: float


# Shared tolerance for comparing keyframe timestamps
# (e.g. for UI selection vs DB lookup)
KEYFRAME_TIME_EPSILON: float = 0.01
SEGMENT_MODE_LINEAR: Literal["linear"] = "linear"
SEGMENT_MODE_STEP: Literal["step"] = "step"
SegmentMode = Literal["linear", "step"]
SegmentKey = tuple[str, str]
TRAJECTORY_METADATA_KEY = "kraken_trajectory"
TRAJECTORY_METADATA_VERSION = 1

KeyframeValue = Keyframe | EditableKeyframe
_KeyframeT = TypeVar("_KeyframeT", Keyframe, EditableKeyframe)


@dataclass(frozen=True)
class TrajectoryDistanceContext:
    """Physical or relative dimensions used for trajectory distances.

    Normalized map coordinates only become geometrically meaningful after
    scaling each axis. Calibrated callers supply meters; uncalibrated callers
    supply aspect-corrected relative dimensions.

    Attributes:
        width: Distance represented by the normalized X axis.
        height: Distance represented by the normalized Y axis.
        unit: Display unit for the dimensions, or ``None`` for relative units.

    """

    width: float
    height: float
    unit: str | None = None

    def __post_init__(self) -> None:
        """Reject unusable dimensions at the calculation boundary."""
        if (
            not _is_finite_number(self.width)
            or not _is_finite_number(self.height)
            or self.width <= 0.0
            or self.height <= 0.0
        ):
            raise ValueError("Trajectory distance dimensions must be positive.")


def clone_keyframes(keyframes: Iterable[_KeyframeT]) -> list[_KeyframeT]:
    """Return independent copies of all supplied keyframe values.

    The concrete keyframe type is preserved. For editable keyframes this also
    preserves ``edit_id`` so selection remains stable across snapshots.

    Args:
        keyframes: Keyframe values to copy.

    Returns:
        A new list containing newly constructed keyframe instances.

    """
    clones: list[_KeyframeT] = []
    for keyframe in keyframes:
        if isinstance(keyframe, EditableKeyframe):
            clone = cast(
                _KeyframeT,
                EditableKeyframe(
                    edit_id=keyframe.edit_id,
                    t=keyframe.t,
                    x=keyframe.x,
                    y=keyframe.y,
                ),
            )
        else:
            clone = cast(
                _KeyframeT,
                Keyframe(
                    t=keyframe.t,
                    x=keyframe.x,
                    y=keyframe.y,
                    keyframe_id=keyframe.keyframe_id,
                ),
            )
        clones.append(clone)
    return clones


def validate_keyframes(keyframes: Iterable[KeyframeValue]) -> list[str]:
    """Validate trajectory values without mutating or reordering them.

    Empty and one-keyframe trajectories are valid domain states. Errors are
    returned together so an editor can present complete feedback in one pass.

    Args:
        keyframes: Keyframes in any iterable container.

    Returns:
        Human-readable validation errors. An empty list means the trajectory
        is valid.

    """
    values = tuple(keyframes)
    errors: list[str] = []
    finite_times: list[tuple[float, int]] = []

    for index, keyframe in enumerate(values, start=1):
        if _is_finite_number(keyframe.t):
            finite_times.append((float(keyframe.t), index))
        else:
            errors.append(f"Keyframe {index} time must be a finite number.")

        for coordinate_name, coordinate in (("x", keyframe.x), ("y", keyframe.y)):
            if not _is_finite_number(coordinate):
                errors.append(
                    f"Keyframe {index} {coordinate_name}-coordinate must be a "
                    "finite number."
                )
            elif not 0.0 <= float(coordinate) <= 1.0:
                errors.append(
                    f"Keyframe {index} {coordinate_name}-coordinate must be "
                    "between 0.0 and 1.0."
                )

    finite_times.sort(key=lambda item: item[0])
    for (first_time, first_index), (second_time, second_index) in zip(
        finite_times, finite_times[1:]
    ):
        if second_time - first_time <= KEYFRAME_TIME_EPSILON:
            errors.append(
                f"Keyframes {first_index} and {second_index} have times within "
                f"{KEYFRAME_TIME_EPSILON:g} days of each other."
            )

    return errors


def infer_midpoint_time(start: KeyframeValue, end: KeyframeValue) -> float:
    """Infer the fixed temporal midpoint between neighbouring keyframes.

    Args:
        start: Earlier keyframe in the segment.
        end: Later keyframe in the segment.

    Returns:
        The arithmetic midpoint between the two lore dates.

    Raises:
        ValueError: If either time is non-finite or the segment is not ordered
            from an earlier time to a later time.

    """
    if not _is_finite_number(start.t) or not _is_finite_number(end.t):
        raise ValueError("Cannot infer a midpoint from non-finite times.")
    if end.t <= start.t:
        raise ValueError("Midpoint end time must be later than start time.")
    return start.t / 2.0 + end.t / 2.0


def trajectory_segment_distance(
    start: KeyframeValue,
    end: KeyframeValue,
    context: TrajectoryDistanceContext,
) -> float:
    """Return aspect-corrected distance between two keyframes.

    Args:
        start: First spatial point.
        end: Second spatial point.
        context: Dimensions represented by the two normalized map axes.

    Returns:
        Segment distance in the context's physical or relative unit.

    Raises:
        ValueError: If either point has invalid normalized coordinates.

    """
    for keyframe in (start, end):
        if (
            not _is_finite_number(keyframe.x)
            or not _is_finite_number(keyframe.y)
            or not 0.0 <= keyframe.x <= 1.0
            or not 0.0 <= keyframe.y <= 1.0
        ):
            raise ValueError("Trajectory distance requires normalized coordinates.")
    dx = (end.x - start.x) * context.width
    dy = (end.y - start.y) * context.height
    return math.hypot(dx, dy)


def cumulative_trajectory_distances(
    keyframes: Sequence[KeyframeValue],
    context: TrajectoryDistanceContext,
) -> list[float]:
    """Return cumulative aspect-corrected distance at every keyframe."""
    if not keyframes:
        return []
    distances = [0.0]
    for start, end in zip(keyframes, keyframes[1:]):
        distances.append(
            distances[-1] + trajectory_segment_distance(start, end, context)
        )
    return distances


def equalize_keyframe_times(
    keyframes: Sequence[_KeyframeT],
    start_index: int,
    end_index: int,
    context: TrajectoryDistanceContext,
) -> list[_KeyframeT]:
    """Redistribute intermediate dates for constant polyline speed.

    Anchor dates and every spatial coordinate remain unchanged. Dates outside
    the inclusive anchor range are also left untouched.

    Args:
        keyframes: Chronologically ordered trajectory values.
        start_index: Inclusive start-anchor index.
        end_index: Inclusive end-anchor index.
        context: Aspect-corrected physical or relative dimensions.

    Returns:
        Independent keyframe values with redistributed intermediate dates.

    Raises:
        ValueError: If the trajectory or anchor range is invalid, or the
            selected polyline has zero total distance.

    """
    if not 0 <= start_index < end_index < len(keyframes):
        raise ValueError("Speed anchors must be in chronological order.")
    errors = validate_keyframes(keyframes)
    if errors:
        raise ValueError(errors[0])

    start = keyframes[start_index]
    end = keyframes[end_index]
    if end.t <= start.t:
        raise ValueError("The end anchor date must be later than the start anchor.")

    anchor_range = keyframes[start_index : end_index + 1]
    cumulative = cumulative_trajectory_distances(anchor_range, context)
    total_distance = cumulative[-1]
    if math.isclose(total_distance, 0.0, abs_tol=1e-12):
        raise ValueError("Cannot equalize speed across a zero-distance route.")

    equalized = clone_keyframes(keyframes)
    duration = end.t - start.t
    for relative_index in range(1, len(anchor_range) - 1):
        fraction = cumulative[relative_index] / total_distance
        index = start_index + relative_index
        equalized[index] = cast(
            _KeyframeT,
            dataclass_replace(
                equalized[index],
                t=start.t + fraction * duration,
            ),
        )
    return equalized


def _is_finite_number(value: object) -> bool:
    """Return whether *value* is a finite, non-boolean real number."""
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def interpolate_position(
    keyframes: list[Keyframe],
    t: float,
    *,
    segment_modes: Mapping[SegmentKey, SegmentMode] | None = None,
    base_position: tuple[float, float] | None = None,
) -> tuple[float, float] | None:
    """Returns the interpolated (x, y) position at time t.

    Uses binary search (bisect) for O(log N) lookup, then linear interpolation
    between the two surrounding keyframes.

    Args:
        keyframes: List of Keyframe objects, must be sorted by time.
        t: The time at which to calculate the position.

    Returns:
        Tuple of normalized coordinates. Before the first keyframe the
        ordinary marker position is returned when supplied. After the first
        keyframe, single-point tracks hold that point. Step segments hold the
        earlier point until the later timestamp.

    Example:
        >>> keyframes = [Keyframe(0, 0.0, 0.0), Keyframe(100, 1.0, 1.0)]
        >>> interpolate_position(keyframes, 50)
        (0.5, 0.5)

    """
    if not keyframes:
        return None

    # Extract times for binary search
    times = [kf.t for kf in keyframes]

    # Use bisect_left to find first keyframe at or after t
    idx_left = bisect.bisect_left(times, t)

    if idx_left == 0 and t < times[0]:
        return base_position

    # Check for exact match on a keyframe
    if idx_left < len(keyframes) and times[idx_left] == t:
        # Exact match - return this keyframe's position
        return (keyframes[idx_left].x, keyframes[idx_left].y)

    # Use bisect_right to find insertion point for interpolation
    idx = bisect.bisect_right(times, t)

    if idx >= len(keyframes):
        # After last keyframe: clamp to end
        return (keyframes[-1].x, keyframes[-1].y)

    # Get surrounding keyframes
    kf_start = keyframes[idx - 1]
    kf_end = keyframes[idx]

    if segment_mode(kf_start, kf_end, segment_modes) == SEGMENT_MODE_STEP:
        return (kf_start.x, kf_start.y)

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


def segment_mode(
    start: KeyframeValue,
    end: KeyframeValue,
    segment_modes: Mapping[SegmentKey, SegmentMode] | None,
) -> SegmentMode:
    """Return the stored movement mode for one adjacent pair."""
    if segment_modes is None:
        return SEGMENT_MODE_LINEAR
    start_id = _keyframe_identity(start)
    end_id = _keyframe_identity(end)
    if start_id is None or end_id is None:
        return SEGMENT_MODE_LINEAR
    return segment_modes.get((start_id, end_id), SEGMENT_MODE_LINEAR)


def is_stay_segment(start: KeyframeValue, end: KeyframeValue) -> bool:
    """Return whether two dated locations occupy the same map position."""
    return math.isclose(start.x, end.x, abs_tol=1e-12) and math.isclose(
        start.y, end.y, abs_tol=1e-12
    )


def _keyframe_identity(keyframe: KeyframeValue) -> str | None:
    if isinstance(keyframe, EditableKeyframe):
        return keyframe.edit_id
    return keyframe.keyframe_id


def apply_trajectory_metadata(
    keyframes: Sequence[Keyframe], properties: object
) -> tuple[list[Keyframe], dict[SegmentKey, SegmentMode], dict[str, Any], bool]:
    """Attach durable identities and segment modes from stored properties.

    Malformed or legacy metadata falls back to fresh identities and linear
    segments while preserving unrelated property values.
    """
    preserved = copy.deepcopy(properties) if isinstance(properties, dict) else {}
    metadata = preserved.get(TRAJECTORY_METADATA_KEY)
    repaired = False
    if not isinstance(metadata, dict) or metadata.get("schema_version") != (
        TRAJECTORY_METADATA_VERSION
    ):
        metadata = None
        repaired = bool(keyframes)
    ids: list[str] = []
    if isinstance(metadata, dict):
        raw_ids = metadata.get("keyframe_ids")
        if (
            isinstance(raw_ids, list)
            and len(raw_ids) == len(keyframes)
            and all(isinstance(value, str) and value for value in raw_ids)
            and len(set(raw_ids)) == len(raw_ids)
        ):
            ids = list(raw_ids)
    if not ids:
        ids = [str(uuid.uuid4()) for _ in keyframes]
        repaired = bool(keyframes)

    enriched = [
        Keyframe(
            t=keyframe.t,
            x=keyframe.x,
            y=keyframe.y,
            keyframe_id=keyframe_id,
        )
        for keyframe, keyframe_id in zip(keyframes, ids)
    ]
    adjacent = {
        (start.keyframe_id, end.keyframe_id)
        for start, end in zip(enriched, enriched[1:])
        if start.keyframe_id is not None and end.keyframe_id is not None
    }
    modes: dict[SegmentKey, SegmentMode] = {
        cast(SegmentKey, pair): SEGMENT_MODE_LINEAR for pair in adjacent
    }
    if isinstance(metadata, dict):
        raw_segments = metadata.get("segments")
        if isinstance(raw_segments, list):
            for item in raw_segments:
                if not isinstance(item, dict):
                    repaired = True
                    continue
                pair = (item.get("from_id"), item.get("to_id"))
                mode = item.get("mode")
                if pair in adjacent and mode in {
                    SEGMENT_MODE_LINEAR,
                    SEGMENT_MODE_STEP,
                }:
                    modes[cast(SegmentKey, pair)] = cast(SegmentMode, mode)
                else:
                    repaired = True
        elif "segments" in metadata:
            repaired = True
    return enriched, modes, preserved, repaired


def build_trajectory_properties(
    base_properties: object,
    keyframes: Sequence[Keyframe],
    segment_modes: Mapping[SegmentKey, SegmentMode],
) -> dict[str, Any]:
    """Merge versioned editor metadata into independent base properties."""
    properties = (
        copy.deepcopy(base_properties) if isinstance(base_properties, dict) else {}
    )
    ids = [
        keyframe.keyframe_id or str(uuid.uuid4()) for keyframe in keyframes
    ]
    pairs = list(zip(ids, ids[1:]))
    properties[TRAJECTORY_METADATA_KEY] = {
        "schema_version": TRAJECTORY_METADATA_VERSION,
        "keyframe_ids": ids,
        "segments": [
            {
                "from_id": start_id,
                "to_id": end_id,
                "mode": segment_modes.get(
                    (start_id, end_id), SEGMENT_MODE_LINEAR
                ),
            }
            for start_id, end_id in pairs
        ],
    }
    return properties


def keyframes_to_mfjson(keyframes: list[Keyframe]) -> dict[str, Any]:
    """Serialize a list of Keyframes to an OGC MF-JSON MovingPoint structure.

    Args:
        keyframes: List of Keyframe objects.

    Returns:
        Dict[str, Any]: MF-JSON TemporalPrimitiveGeometry (MovingPoint) with keys:
            - 'type' (str): Always "MovingPoint"
            - 'coordinates' (list): List of [x, y] coordinate pairs
            - 'datetimes' (list): List of time values matching coordinates

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
    """Deserialize an OGC MF-JSON MovingPoint structure to a list of Keyframes.

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
