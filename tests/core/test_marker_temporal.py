from src.core.marker import Marker


class TestMarkerTemporal:
    """Tests for temporal capabilities of the Marker class."""

    def test_add_keyframe_sorting(self):
        """Verify keyframes are always sorted by time."""
        marker = Marker(
            map_id="map1", object_id="obj1", object_type="entity", x=0.5, y=0.5
        )

        # Add out of order
        marker.add_keyframe(t=200.0, x=0.2, y=0.2)
        marker.add_keyframe(t=100.0, x=0.1, y=0.1)
        marker.add_keyframe(t=300.0, x=0.3, y=0.3)

        keyframes = marker.attributes["temporal"]["keyframes"]
        assert len(keyframes) == 3
        assert keyframes[0]["t"] == 100.0
        assert keyframes[1]["t"] == 200.0
        assert keyframes[2]["t"] == 300.0

    def test_get_state_static(self):
        """Verify default static behavior when no temporal data exists."""
        marker = Marker(
            map_id="map1", object_id="obj1", object_type="entity", x=0.5, y=0.5
        )

        state = marker.get_state_at(1000.0)
        assert state.x == 0.5
        assert state.y == 0.5
        assert state.visible is True

    def test_get_state_linear_interpolation(self):
        """Verify linear interpolation between two points."""
        marker = Marker(
            map_id="map1", object_id="obj1", object_type="entity", x=0.0, y=0.0
        )
        marker.add_keyframe(t=100.0, x=0.0, y=0.0, keyframe_type="path")
        marker.add_keyframe(t=200.0, x=1.0, y=1.0, keyframe_type="path")

        # Midpoint
        state = marker.get_state_at(150.0)
        assert state.x == 0.5
        assert state.y == 0.5
        assert state.visible is True

        # Quarter point
        state = marker.get_state_at(125.0)
        assert state.x == 0.25
        assert state.y == 0.25

    def test_existence_start_end(self):
        """Verify visibility rules for 'start' and 'end' keyframes."""
        marker = Marker(
            map_id="map1", object_id="obj1", object_type="entity", x=0.0, y=0.0
        )
        marker.add_keyframe(t=100.0, x=0.5, y=0.5, keyframe_type="start")
        marker.add_keyframe(t=200.0, x=0.5, y=0.5, keyframe_type="end")

        # Before start
        assert marker.get_state_at(50.0).visible is False

        # At start
        assert marker.get_state_at(100.0).visible is True

        # In between
        assert marker.get_state_at(150.0).visible is True

        # After end
        assert marker.get_state_at(201.0).visible is False

    def test_out_of_bounds_standard(self):
        """Verify behavior when t is outside keyframe range (but no start/end types)."""
        marker = Marker(
            map_id="map1", object_id="obj1", object_type="entity", x=0.0, y=0.0
        )
        marker.add_keyframe(t=100.0, x=0.2, y=0.2)
        marker.add_keyframe(t=200.0, x=0.4, y=0.4)

        # Before first keyframe -> Should hold first keyframe pos (clamped)
        state_pre = marker.get_state_at(50.0)
        assert state_pre.x == 0.2
        assert state_pre.visible is True  # Unless "start" type is used

        # After last keyframe -> Should hold last keyframe pos (clamped)
        state_post = marker.get_state_at(250.0)
        assert state_post.x == 0.4
        assert state_post.visible is True

    def test_single_keyframe(self):
        """Verify behavior with just one keyframe."""
        marker = Marker(
            map_id="map1", object_id="obj1", object_type="entity", x=0.0, y=0.0
        )
        marker.add_keyframe(t=100.0, x=0.8, y=0.8)

        assert marker.get_state_at(50.0).x == 0.8
        assert marker.get_state_at(200.0).x == 0.8
        assert marker.get_state_at(50.0).visible is True

    def test_remove_keyframe(self):
        """Verify keyframe removal."""
        marker = Marker(
            map_id="map1", object_id="obj1", object_type="entity", x=0.0, y=0.0
        )
        marker.add_keyframe(t=100.0, x=0.1, y=0.1)
        marker.add_keyframe(t=200.0, x=0.2, y=0.2)

        marker.remove_keyframe(100.0)
        keyframes = marker.attributes["temporal"]["keyframes"]
        assert len(keyframes) == 1
        assert keyframes[0]["t"] == 200.0

    def test_duplicate_time_update(self):
        """Verify adding a keyframe at existing time updates it."""
        marker = Marker(
            map_id="map1", object_id="obj1", object_type="entity", x=0.0, y=0.0
        )
        marker.add_keyframe(t=100.0, x=0.1, y=0.1)
        marker.add_keyframe(t=100.0, x=0.9, y=0.9)  # Update

        keyframes = marker.attributes["temporal"]["keyframes"]
        assert len(keyframes) == 1
        assert keyframes[0]["x"] == 0.9
