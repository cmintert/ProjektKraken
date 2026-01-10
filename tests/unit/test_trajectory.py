"""
Unit tests for trajectory interpolation logic.
"""

import pytest

from src.core.trajectory import Keyframe, interpolate_position


class TestKeyframe:
    """Tests for the Keyframe dataclass."""

    def test_keyframe_creation(self) -> None:
        """Test that Keyframe can be created with required fields."""
        kf = Keyframe(t=10.0, x=0.5, y=0.75)
        assert kf.t == 10.0
        assert kf.x == 0.5
        assert kf.y == 0.75


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
