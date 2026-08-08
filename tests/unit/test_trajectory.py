"""
Unit tests for trajectory interpolation logic.
"""

import math

import pytest

from src.core.trajectory import (
    KEYFRAME_TIME_EPSILON,
    EditableKeyframe,
    Keyframe,
    TrajectoryDistanceContext,
    clone_keyframes,
    cumulative_trajectory_distances,
    equalize_keyframe_times,
    infer_midpoint_time,
    interpolate_position,
    trajectory_segment_distance,
    validate_keyframes,
)


class TestKeyframe:
    """Tests for the Keyframe dataclass."""

    def test_keyframe_creation(self) -> None:
        """Test that Keyframe can be created with required fields."""
        kf = Keyframe(t=10.0, x=0.5, y=0.75)
        assert kf.t == 10.0
        assert kf.x == 0.5
        assert kf.y == 0.75


class TestCloneKeyframes:
    """Tests for independent trajectory snapshots."""

    def test_clones_mutable_keyframes_without_sharing_values(self) -> None:
        """Mutating a clone does not mutate the original keyframe."""
        original = [Keyframe(t=10.0, x=0.25, y=0.75)]

        cloned = clone_keyframes(original)
        cloned[0].x = 0.9

        assert cloned is not original
        assert cloned[0] is not original[0]
        assert original[0].x == 0.25

    def test_clones_editable_keyframes_and_preserves_identity(self) -> None:
        """Editable snapshots retain stable IDs but not object identity."""
        original = [
            EditableKeyframe(
                edit_id="edit-1",
                t=10.0,
                x=0.25,
                y=0.75,
            )
        ]

        cloned = clone_keyframes(original)

        assert cloned == original
        assert cloned[0] is not original[0]
        assert cloned[0].edit_id == "edit-1"


class TestValidateKeyframes:
    """Tests for trajectory-domain validation."""

    def test_empty_and_single_keyframe_trajectories_are_valid(self) -> None:
        """Partial trajectories remain valid edit-session states."""
        assert validate_keyframes([]) == []
        assert validate_keyframes([Keyframe(t=1.0, x=0.5, y=0.5)]) == []

    @pytest.mark.parametrize("invalid_time", [math.nan, math.inf, -math.inf])
    def test_rejects_non_finite_times(self, invalid_time: float) -> None:
        """Lore dates must be finite."""
        errors = validate_keyframes(
            [Keyframe(t=invalid_time, x=0.5, y=0.5)]
        )

        assert errors == ["Keyframe 1 time must be a finite number."]

    @pytest.mark.parametrize(
        ("x", "y", "coordinate_name"),
        [
            (math.nan, 0.5, "x-coordinate"),
            (0.5, math.inf, "y-coordinate"),
            (-0.01, 0.5, "x-coordinate"),
            (0.5, 1.01, "y-coordinate"),
        ],
    )
    def test_rejects_non_finite_or_out_of_range_coordinates(
        self,
        x: float,
        y: float,
        coordinate_name: str,
    ) -> None:
        """Coordinates must be finite and normalized."""
        errors = validate_keyframes([Keyframe(t=1.0, x=x, y=y)])

        assert len(errors) == 1
        assert coordinate_name in errors[0]

    def test_accepts_coordinate_boundaries(self) -> None:
        """Zero and one are valid normalized coordinate values."""
        keyframes = [
            Keyframe(t=0.0, x=0.0, y=1.0),
            Keyframe(t=1.0, x=1.0, y=0.0),
        ]

        assert validate_keyframes(keyframes) == []

    @pytest.mark.parametrize(
        "time_difference",
        [0.0, KEYFRAME_TIME_EPSILON / 2, KEYFRAME_TIME_EPSILON],
    )
    def test_rejects_duplicate_times_within_epsilon(
        self, time_difference: float
    ) -> None:
        """Timestamp collisions include the configured epsilon boundary."""
        keyframes = [
            Keyframe(t=5.0 + time_difference, x=0.0, y=0.0),
            Keyframe(t=5.0, x=1.0, y=1.0),
        ]

        errors = validate_keyframes(keyframes)

        assert len(errors) == 1
        assert "times within" in errors[0]

    def test_accepts_times_beyond_epsilon(self) -> None:
        """Dates separated by more than epsilon do not collide."""
        keyframes = [
            Keyframe(t=5.0, x=0.0, y=0.0),
            Keyframe(t=5.0 + KEYFRAME_TIME_EPSILON * 1.01, x=1.0, y=1.0),
        ]

        assert validate_keyframes(keyframes) == []


class TestInferMidpointTime:
    """Tests for midpoint insertion time inference."""

    def test_returns_temporal_midpoint(self) -> None:
        """The midpoint uses the surrounding keyframes' lore dates."""
        start = Keyframe(t=-10.0, x=0.0, y=0.0)
        end = Keyframe(t=30.0, x=1.0, y=1.0)

        assert infer_midpoint_time(start, end) == 10.0

    def test_rejects_equal_times(self) -> None:
        """An equal-time segment cannot supply a meaningful midpoint."""
        start = Keyframe(t=10.0, x=0.0, y=0.0)
        end = Keyframe(t=10.0, x=1.0, y=1.0)

        with pytest.raises(ValueError, match="later than start"):
            infer_midpoint_time(start, end)

    def test_rejects_reversed_times(self) -> None:
        """Neighbouring segment arguments must be chronological."""
        start = Keyframe(t=20.0, x=0.0, y=0.0)
        end = Keyframe(t=10.0, x=1.0, y=1.0)

        with pytest.raises(ValueError, match="later than start"):
            infer_midpoint_time(start, end)

    def test_rejects_non_finite_times(self) -> None:
        """Non-finite dates cannot produce a usable midpoint."""
        start = Keyframe(t=0.0, x=0.0, y=0.0)
        end = Keyframe(t=math.inf, x=1.0, y=1.0)

        with pytest.raises(ValueError, match="non-finite"):
            infer_midpoint_time(start, end)


class TestTrajectoryDistances:
    """Tests for aspect-corrected polyline distance calculations."""

    def test_segment_distance_uses_both_map_dimensions(self) -> None:
        """Normalized X and Y use their respective real dimensions."""
        context = TrajectoryDistanceContext(1000.0, 500.0, "m")
        start = Keyframe(t=0.0, x=0.0, y=0.0)
        end = Keyframe(t=1.0, x=0.3, y=0.8)

        distance = trajectory_segment_distance(start, end, context)

        assert distance == pytest.approx(500.0)

    def test_cumulative_distances_retain_every_vertex(self) -> None:
        """Each output entry measures distance from the first point."""
        context = TrajectoryDistanceContext(2.0, 1.0)
        keyframes = [
            Keyframe(t=0.0, x=0.0, y=0.0),
            Keyframe(t=1.0, x=0.5, y=0.0),
            Keyframe(t=2.0, x=0.5, y=1.0),
        ]

        assert cumulative_trajectory_distances(keyframes, context) == [
            0.0,
            1.0,
            2.0,
        ]

    @pytest.mark.parametrize(
        ("width", "height"),
        [(0.0, 1.0), (1.0, -1.0), (math.inf, 1.0)],
    )
    def test_distance_context_rejects_invalid_dimensions(
        self, width: float, height: float
    ) -> None:
        """Distance calculations require positive finite axis dimensions."""
        with pytest.raises(ValueError, match="positive"):
            TrajectoryDistanceContext(width, height)


class TestEqualizeKeyframeTimes:
    """Tests for constant-speed date redistribution."""

    def test_redistributes_dates_by_cumulative_distance(self) -> None:
        """Longer segments receive proportionally more elapsed time."""
        keyframes = [
            Keyframe(t=0.0, x=0.0, y=0.0),
            Keyframe(t=5.0, x=0.25, y=0.0),
            Keyframe(t=20.0, x=1.0, y=0.0),
        ]

        result = equalize_keyframe_times(
            keyframes,
            0,
            2,
            TrajectoryDistanceContext(1.0, 1.0),
        )

        assert [keyframe.t for keyframe in result] == [0.0, 5.0, 20.0]
        keyframes[1].t = 12.0
        result = equalize_keyframe_times(
            keyframes,
            0,
            2,
            TrajectoryDistanceContext(1.0, 1.0),
        )
        assert [keyframe.t for keyframe in result] == [0.0, 5.0, 20.0]

    def test_preserves_anchor_dates_positions_and_edit_identities(self) -> None:
        """Equalization changes only intermediate dates in copied values."""
        keyframes = [
            EditableKeyframe("a", 0.0, 0.0, 0.0),
            EditableKeyframe("b", 10.0, 0.5, 0.0),
            EditableKeyframe("c", 30.0, 0.5, 1.0),
            EditableKeyframe("d", 40.0, 1.0, 1.0),
        ]

        result = equalize_keyframe_times(
            keyframes,
            0,
            3,
            TrajectoryDistanceContext(2.0, 1.0),
        )

        assert result[0].t == 0.0
        assert result[-1].t == 40.0
        assert result[1].t == pytest.approx(40.0 / 3.0)
        assert result[2].t == pytest.approx(80.0 / 3.0)
        assert [(item.x, item.y) for item in result] == [
            (item.x, item.y) for item in keyframes
        ]
        assert [item.edit_id for item in result] == ["a", "b", "c", "d"]
        assert all(after is not before for after, before in zip(result, keyframes))

    def test_equalizes_only_the_selected_anchor_range(self) -> None:
        """Dates outside the anchors remain untouched."""
        keyframes = [
            Keyframe(t=-5.0, x=0.0, y=0.0),
            Keyframe(t=0.0, x=0.0, y=0.2),
            Keyframe(t=9.0, x=0.25, y=0.2),
            Keyframe(t=20.0, x=1.0, y=0.2),
            Keyframe(t=25.0, x=1.0, y=1.0),
        ]

        result = equalize_keyframe_times(
            keyframes,
            1,
            3,
            TrajectoryDistanceContext(1.0, 1.0),
        )

        assert [item.t for item in result] == [-5.0, 0.0, 5.0, 20.0, 25.0]

    def test_rejects_reversed_and_zero_distance_ranges(self) -> None:
        """Anchors must be ordered and span a non-zero polyline."""
        keyframes = [
            Keyframe(t=0.0, x=0.5, y=0.5),
            Keyframe(t=10.0, x=0.5, y=0.5),
            Keyframe(t=20.0, x=0.5, y=0.5),
        ]
        context = TrajectoryDistanceContext(1.0, 1.0)

        with pytest.raises(ValueError, match="chronological"):
            equalize_keyframe_times(keyframes, 2, 0, context)
        with pytest.raises(ValueError, match="zero-distance"):
            equalize_keyframe_times(keyframes, 0, 2, context)

    def test_handles_one_hundred_keyframes_without_changing_positions(self) -> None:
        """The active-trajectory calculation stays linear at target scale."""
        keyframes = [
            Keyframe(
                t=float(index * index),
                x=index / 99.0,
                y=(index % 5) / 4.0,
            )
            for index in range(100)
        ]

        result = equalize_keyframe_times(
            keyframes,
            0,
            99,
            TrajectoryDistanceContext(2.0, 1.0),
        )

        assert len(result) == 100
        assert result[0].t == keyframes[0].t
        assert result[-1].t == keyframes[-1].t
        assert [(item.x, item.y) for item in result] == [
            (item.x, item.y) for item in keyframes
        ]


class TestInterpolatePosition:
    """Tests for the interpolate_position function."""

    def test_empty_keyframes_returns_none(self) -> None:
        """Empty keyframe list returns None."""
        assert interpolate_position([], 50.0) is None

    def test_single_keyframe_returns_none(self) -> None:
        """Single keyframe is insufficient for interpolation."""
        keyframes = [Keyframe(t=0.0, x=0.5, y=0.5)]
        assert interpolate_position(keyframes, 0.0) is None

    def test_before_first_keyframe_clamps_to_start(self) -> None:
        """Time before first keyframe returns the first keyframe position."""
        keyframes = [Keyframe(t=10.0, x=0.0, y=0.0), Keyframe(t=20.0, x=1.0, y=1.0)]
        result = interpolate_position(keyframes, 5.0)
        assert result == (0.0, 0.0)

    def test_after_last_keyframe_clamps_to_end(self) -> None:
        """Time after last keyframe returns the last keyframe position."""
        keyframes = [Keyframe(t=10.0, x=0.0, y=0.0), Keyframe(t=20.0, x=1.0, y=1.0)]
        result = interpolate_position(keyframes, 25.0)
        assert result == (1.0, 1.0)

    def test_exact_first_keyframe_time(self) -> None:
        """Exact match on first keyframe returns its position."""
        keyframes = [Keyframe(t=0.0, x=0.2, y=0.3), Keyframe(t=100.0, x=0.8, y=0.9)]
        result = interpolate_position(keyframes, 0.0)
        assert result is not None
        assert result[0] == pytest.approx(0.2)
        assert result[1] == pytest.approx(0.3)

    def test_exact_last_keyframe_time(self) -> None:
        """Exact match on last keyframe returns interpolated (at end)."""
        keyframes = [Keyframe(t=0.0, x=0.0, y=0.0), Keyframe(t=100.0, x=1.0, y=1.0)]
        # At t=100, we're exactly at the boundary - bisect returns idx=2 (after last)
        # Our implementation returns None for this edge case
        result = interpolate_position(keyframes, 100.0)
        # This should return (1.0, 1.0) at exact end time
        assert result is not None
        assert result[0] == pytest.approx(1.0)
        assert result[1] == pytest.approx(1.0)

    def test_midpoint_interpolation(self) -> None:
        """Entity at midpoint between two keyframes."""
        keyframes = [Keyframe(t=0.0, x=0.0, y=0.0), Keyframe(t=100.0, x=1.0, y=1.0)]
        result = interpolate_position(keyframes, 50.0)
        assert result is not None
        assert result[0] == pytest.approx(0.5)
        assert result[1] == pytest.approx(0.5)

    def test_quarter_interpolation(self) -> None:
        """Entity at 25% between two keyframes."""
        keyframes = [Keyframe(t=0.0, x=0.0, y=0.0), Keyframe(t=100.0, x=1.0, y=1.0)]
        result = interpolate_position(keyframes, 25.0)
        assert result is not None
        assert result[0] == pytest.approx(0.25)
        assert result[1] == pytest.approx(0.25)

    def test_three_keyframes_first_segment(self) -> None:
        """With 3 keyframes, time in first segment uses first two."""
        keyframes = [
            Keyframe(t=0.0, x=0.0, y=0.0),
            Keyframe(t=50.0, x=0.5, y=0.0),
            Keyframe(t=100.0, x=0.5, y=1.0),
        ]
        result = interpolate_position(keyframes, 25.0)
        assert result is not None
        # Between kf0 and kf1: x goes 0->0.5, y stays 0
        assert result[0] == pytest.approx(0.25)
        assert result[1] == pytest.approx(0.0)

    def test_three_keyframes_second_segment(self) -> None:
        """With 3 keyframes, time in second segment uses last two."""
        keyframes = [
            Keyframe(t=0.0, x=0.0, y=0.0),
            Keyframe(t=50.0, x=0.5, y=0.0),
            Keyframe(t=100.0, x=0.5, y=1.0),
        ]
        result = interpolate_position(keyframes, 75.0)
        assert result is not None
        # Between kf1 and kf2: x stays 0.5, y goes 0->1
        assert result[0] == pytest.approx(0.5)
        assert result[1] == pytest.approx(0.5)

    def test_non_uniform_time_spacing(self) -> None:
        """Keyframes with non-uniform time intervals."""
        keyframes = [
            Keyframe(t=0.0, x=0.0, y=0.0),
            Keyframe(t=10.0, x=0.2, y=0.2),  # Short interval
            Keyframe(t=100.0, x=1.0, y=1.0),  # Long interval
        ]
        # At t=5 (midpoint of first segment)
        result = interpolate_position(keyframes, 5.0)
        assert result is not None
        assert result[0] == pytest.approx(0.1)
        assert result[1] == pytest.approx(0.1)

    def test_coincident_keyframe_times(self) -> None:
        """Two keyframes at the same time (edge case for division)."""
        keyframes = [
            Keyframe(t=50.0, x=0.0, y=0.0),
            Keyframe(t=50.0, x=1.0, y=1.0),  # Same time!
        ]
        # Should not crash, returns first keyframe position
        result = interpolate_position(keyframes, 50.0)
        assert result is not None
        # When dt=0, we return start position to avoid division by zero
        assert result[0] == pytest.approx(0.0)
        assert result[1] == pytest.approx(0.0)

    def test_negative_time_values(self) -> None:
        """Negative time values work correctly."""
        keyframes = [
            Keyframe(t=-100.0, x=0.0, y=0.0),
            Keyframe(t=0.0, x=1.0, y=1.0),
        ]
        result = interpolate_position(keyframes, -50.0)
        assert result is not None
        assert result[0] == pytest.approx(0.5)
        assert result[1] == pytest.approx(0.5)

    def test_large_keyframe_list_performance(self) -> None:
        """Binary search should handle large lists efficiently."""
        # Create 10000 keyframes
        keyframes = [
            Keyframe(t=float(i), x=i / 10000, y=i / 10000) for i in range(10001)
        ]

        # Query middle
        result = interpolate_position(keyframes, 5000.5)
        assert result is not None
        assert result[0] == pytest.approx(0.50005, rel=1e-4)


class TestMFJSONSerialization:
    """Tests for MF-JSON serialization helpers (TDD - tests written before impl)."""

    def test_keyframes_to_mfjson_basic(self) -> None:
        """Test basic serialization to MF-JSON format."""
        from src.core.trajectory import keyframes_to_mfjson

        keyframes = [
            Keyframe(t=0.0, x=0.1, y=0.2),
            Keyframe(t=100.0, x=0.9, y=0.8),
        ]
        result = keyframes_to_mfjson(keyframes)

        assert result["type"] == "MovingPoint"
        assert result["coordinates"] == [[0.1, 0.2], [0.9, 0.8]]
        assert result["datetimes"] == [0.0, 100.0]

    def test_keyframes_to_mfjson_empty_raises(self) -> None:
        """Empty keyframes should raise ValueError."""
        from src.core.trajectory import keyframes_to_mfjson

        with pytest.raises(ValueError, match="empty"):
            keyframes_to_mfjson([])

    def test_mfjson_to_keyframes_basic(self) -> None:
        """Test basic deserialization from MF-JSON format."""
        from src.core.trajectory import mfjson_to_keyframes

        mfjson = {
            "type": "MovingPoint",
            "coordinates": [[0.1, 0.2], [0.9, 0.8]],
            "datetimes": [0.0, 100.0],
        }
        result = mfjson_to_keyframes(mfjson)

        assert len(result) == 2
        assert result[0].t == 0.0
        assert result[0].x == 0.1
        assert result[0].y == 0.2
        assert result[1].t == 100.0
        assert result[1].x == 0.9
        assert result[1].y == 0.8

    def test_mfjson_roundtrip(self) -> None:
        """Serialization then deserialization should be identity."""
        from src.core.trajectory import keyframes_to_mfjson, mfjson_to_keyframes

        original = [
            Keyframe(t=10.0, x=0.25, y=0.75),
            Keyframe(t=50.0, x=0.5, y=0.5),
            Keyframe(t=90.0, x=0.75, y=0.25),
        ]
        mfjson = keyframes_to_mfjson(original)
        restored = mfjson_to_keyframes(mfjson)

        assert len(restored) == len(original)
        for orig, rest in zip(original, restored):
            assert rest.t == orig.t
            assert rest.x == orig.x
            assert rest.y == orig.y

    def test_mfjson_to_keyframes_missing_datetimes(self) -> None:
        """Missing datetimes should raise ValueError."""
        from src.core.trajectory import mfjson_to_keyframes

        mfjson = {
            "type": "MovingPoint",
            "coordinates": [[0.1, 0.2], [0.9, 0.8]],
            # No 'datetimes' key
        }
        with pytest.raises(ValueError, match="datetimes"):
            mfjson_to_keyframes(mfjson)

    def test_mfjson_to_keyframes_mismatched_lengths(self) -> None:
        """Mismatched coordinates and datetimes should raise ValueError."""
        from src.core.trajectory import mfjson_to_keyframes

        mfjson = {
            "type": "MovingPoint",
            "coordinates": [[0.1, 0.2], [0.9, 0.8]],
            "datetimes": [0.0],  # Only 1 time for 2 coords!
        }
        with pytest.raises(ValueError, match="mismatch"):
            mfjson_to_keyframes(mfjson)
