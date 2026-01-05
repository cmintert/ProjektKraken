import pytest
import time
from src.core.marker import Marker


class TestTemporalMarker:
    """Tests for temporal logic in Marker class."""

    def test_static_marker_always_visible(self):
        """Test that a marker with no temporal data is static and visible."""
        marker = Marker(
            map_id="test_map",
            object_id="obj_1",
            object_type="entity",
            x=0.5,
            y=0.5,
            attributes={},
        )

        # Test various times
        for t in [-1000, 0, 1000, 2025]:
            state = marker.get_state_at(t)
            assert state.x == 0.5
            assert state.y == 0.5
            assert state.visible is True

    def test_auto_init_temporal(self):
        """Test that adding a keyframe auto-initializes temporal attributes."""
        marker = Marker(
            map_id="test_map", object_id="obj_1", object_type="entity", x=0.5, y=0.5
        )

        # Add keyframe
        marker.add_keyframe(t=100, x=0.6, y=0.6)

        assert "temporal" in marker.attributes
        assert marker.attributes["temporal"]["enabled"] is True
        assert len(marker.attributes["temporal"]["keyframes"]) == 1

    def test_interpolation_between_keyframes(self):
        """Test linear interpolation between two path keyframes."""
        marker = Marker(
            map_id="test_map", object_id="obj_1", object_type="entity", x=0.5, y=0.5
        )

        marker.add_keyframe(t=100, x=0.0, y=0.0)
        marker.add_keyframe(t=200, x=1.0, y=1.0)

        # Test middle point
        state = marker.get_state_at(150)
        assert state.x == 0.5
        assert state.y == 0.5
        assert state.visible is True

        # Test quarter point
        state = marker.get_state_at(125)
        assert state.x == 0.25
        assert state.y == 0.25

    def test_state_before_first_keyframe(self):
        """
        Test behavior before the first keyframe.
        Should hold first keyframe position.
        """
        marker = Marker(
            map_id="test_map", object_id="obj_1", object_type="entity", x=0.5, y=0.5
        )

        marker.add_keyframe(t=100, x=0.8, y=0.8)

        # Test time before keyframe
        state = marker.get_state_at(50)
        assert state.x == 0.8  # Should be at keyframe pos
        assert state.y == 0.8
        assert state.visible is True  # Should be visible by default

    def test_state_after_last_keyframe(self):
        """
        Test behavior after the last keyframe.
        Should hold last keyframe position.
        """
        marker = Marker(
            map_id="test_map", object_id="obj_1", object_type="entity", x=0.5, y=0.5
        )

        marker.add_keyframe(t=100, x=0.2, y=0.2)

        state = marker.get_state_at(200)
        assert state.x == 0.2
        assert state.y == 0.2
        assert state.visible is True

    def test_start_keyframe_visibility(self):
        """Test that 'start' keyframe makes marker invisible before it."""
        marker = Marker(
            map_id="test_map", object_id="obj_1", object_type="entity", x=0.5, y=0.5
        )

        # Create a 'start' keyframe
        marker.add_keyframe(t=100, x=0.5, y=0.5, keyframe_type="start")

        # Before start time -> Invisible
        state = marker.get_state_at(50)
        assert state.visible is False

        # At/After start time -> Visible
        state = marker.get_state_at(100)
        assert state.visible is True

        state = marker.get_state_at(150)
        assert state.visible is True

    def test_end_keyframe_visibility(self):
        """Test that 'end' keyframe makes marker invisible after it."""
        marker = Marker(
            map_id="test_map", object_id="obj_1", object_type="entity", x=0.5, y=0.5
        )

        marker.add_keyframe(t=100, x=0.5, y=0.5, keyframe_type="path")
        marker.add_keyframe(t=200, x=0.8, y=0.8, keyframe_type="end")

        # Before end -> Visible
        state = marker.get_state_at(150)
        assert state.visible is True

        # After end -> Invisible
        state = marker.get_state_at(250)
        assert state.visible is False

    def test_path_gap_visibility(self):
        """Test visibility gap functionality (end -> start sequence)."""
        marker = Marker(
            map_id="test_map", object_id="obj_1", object_type="entity", x=0.5, y=0.5
        )

        # Becomes invisible at 100, reappears at 200
        marker.add_keyframe(t=100, x=0.0, y=0.0, keyframe_type="end")
        marker.add_keyframe(t=200, x=1.0, y=1.0, keyframe_type="start")

        # In the gap (150)
        state = marker.get_state_at(150)
        assert state.visible is False

        # After reappearing (250)
        state = marker.get_state_at(250)
        assert state.visible is True
