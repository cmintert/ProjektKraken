"""Unit tests for the MapFeature data model (Hybrid Anchor/Geometry pattern)."""

import json

import pytest

from src.core.marker import (
    FEATURE_TYPE_MULTIPOINT,
    FEATURE_TYPE_PATH,
    FEATURE_TYPE_POINT,
    FEATURE_TYPE_REGION,
    MapFeature,
    Marker,
)

# --------------------------------------------------------------------------
# Backward compatibility
# --------------------------------------------------------------------------


class TestBackwardCompatibility:
    """Verify that Marker alias and existing usage patterns still work."""

    def test_marker_alias_is_map_feature(self) -> None:
        """Marker is an alias for MapFeature."""
        assert Marker is MapFeature

    def test_marker_constructor_unchanged(self) -> None:
        """Old-style Marker(**kwargs) still works."""
        m = Marker(
            map_id="map-1",
            object_id="e-1",
            object_type="entity",
            x=0.5,
            y=0.5,
        )
        assert m.x == 0.5
        assert m.y == 0.5
        assert m.feature_type == FEATURE_TYPE_POINT
        assert m.geometry is None
        assert m.style is None

    def test_marker_from_dict_without_new_fields(self) -> None:
        """from_dict with old-style data (no feature_type/geometry/style)."""
        data = {
            "map_id": "map-1",
            "object_id": "e-1",
            "object_type": "entity",
            "x": 0.3,
            "y": 0.4,
        }
        m = Marker.from_dict(data)
        assert m.feature_type == FEATURE_TYPE_POINT
        assert m.geometry is None
        assert m.style is None

    def test_to_dict_includes_new_fields(self) -> None:
        """to_dict always emits the three new fields."""
        m = Marker(
            map_id="map-1",
            object_id="e-1",
            object_type="entity",
            x=0.5,
            y=0.5,
        )
        d = m.to_dict()
        assert "feature_type" in d
        assert "geometry" in d
        assert "style" in d
        assert d["feature_type"] == "point"
        assert d["geometry"] is None
        assert d["style"] is None


# --------------------------------------------------------------------------
# Property accessors
# --------------------------------------------------------------------------


class TestPropertyAccessors:
    """Verify .is_point, .is_path, .is_region, .is_multipoint."""

    def test_is_point_default(self) -> None:
        f = MapFeature(map_id="m", object_id="o", object_type="entity", x=0.5, y=0.5)
        assert f.is_point is True
        assert f.is_path is False
        assert f.is_region is False
        assert f.is_multipoint is False

    def test_is_path(self) -> None:
        f = MapFeature(
            map_id="m",
            object_id="o",
            object_type="entity",
            x=0.5,
            y=0.5,
            feature_type=FEATURE_TYPE_PATH,
        )
        assert f.is_path is True
        assert f.is_point is False

    def test_is_region(self) -> None:
        f = MapFeature(
            map_id="m",
            object_id="o",
            object_type="entity",
            x=0.5,
            y=0.5,
            feature_type=FEATURE_TYPE_REGION,
        )
        assert f.is_region is True
        assert f.is_point is False

    def test_is_multipoint(self) -> None:
        f = MapFeature(
            map_id="m",
            object_id="o",
            object_type="entity",
            x=0.5,
            y=0.5,
            feature_type=FEATURE_TYPE_MULTIPOINT,
        )
        assert f.is_multipoint is True
        assert f.is_point is False


# --------------------------------------------------------------------------
# .points property
# --------------------------------------------------------------------------


class TestPointsProperty:
    """Verify .points deserialization and fallback."""

    def test_points_fallback_to_anchor(self) -> None:
        """When geometry is None, .points returns [(x, y)]."""
        f = MapFeature(map_id="m", object_id="o", object_type="entity", x=0.3, y=0.7)
        assert f.points == [(0.3, 0.7)]

    def test_points_from_geometry(self) -> None:
        """When geometry is set, .points returns the coordinate list."""
        coords = [{"x": 0.1, "y": 0.2}, {"x": 0.3, "y": 0.4}]
        f = MapFeature(
            map_id="m",
            object_id="o",
            object_type="entity",
            x=0.0,
            y=0.0,
            feature_type=FEATURE_TYPE_PATH,
            geometry=coords,
        )
        assert f.points == [(0.1, 0.2), (0.3, 0.4)]

    def test_points_empty_geometry_falls_back(self) -> None:
        """Empty geometry list falls back to anchor."""
        f = MapFeature(
            map_id="m",
            object_id="o",
            object_type="entity",
            x=0.5,
            y=0.5,
            geometry=[],
        )
        assert f.points == [(0.5, 0.5)]


# --------------------------------------------------------------------------
# set_geometry & anchor recalculation
# --------------------------------------------------------------------------


class TestSetGeometry:
    """Verify that set_geometry updates geometry and recalculates the anchor."""

    def test_set_geometry_recalculates_anchor(self) -> None:
        f = MapFeature(map_id="m", object_id="o", object_type="entity", x=0.0, y=0.0)
        coords = [{"x": 0.2, "y": 0.4}, {"x": 0.6, "y": 0.8}]
        f.set_geometry(coords)

        assert f.geometry == coords
        assert f.x == pytest.approx(0.4)
        assert f.y == pytest.approx(0.6)

    def test_set_geometry_none_clears(self) -> None:
        f = MapFeature(
            map_id="m",
            object_id="o",
            object_type="entity",
            x=0.5,
            y=0.5,
            geometry=[{"x": 0.1, "y": 0.1}],
        )
        f.set_geometry(None)
        assert f.geometry is None
        # Anchor should remain unchanged
        assert f.x == 0.5
        assert f.y == 0.5

    def test_set_geometry_empty_clears(self) -> None:
        f = MapFeature(
            map_id="m",
            object_id="o",
            object_type="entity",
            x=0.5,
            y=0.5,
            geometry=[{"x": 0.1, "y": 0.1}],
        )
        f.set_geometry([])
        assert f.geometry is None

    def test_set_geometry_triangle_centroid(self) -> None:
        """Centroid of a triangle at (0,0), (1,0), (0.5,1)."""
        f = MapFeature(
            map_id="m",
            object_id="o",
            object_type="entity",
            x=0.0,
            y=0.0,
            feature_type=FEATURE_TYPE_REGION,
        )
        coords = [
            {"x": 0.0, "y": 0.0},
            {"x": 1.0, "y": 0.0},
            {"x": 0.5, "y": 1.0},
        ]
        f.set_geometry(coords)
        assert f.x == pytest.approx(0.5)
        assert f.y == pytest.approx(1.0 / 3.0)


# --------------------------------------------------------------------------
# get_bounding_box
# --------------------------------------------------------------------------


class TestBoundingBox:
    """Verify bounding box calculations."""

    def test_bbox_point_feature(self) -> None:
        """Point feature bbox is a zero-area box at the anchor."""
        f = MapFeature(map_id="m", object_id="o", object_type="entity", x=0.3, y=0.7)
        assert f.get_bounding_box() == (0.3, 0.7, 0.3, 0.7)

    def test_bbox_path_feature(self) -> None:
        coords = [{"x": 0.1, "y": 0.2}, {"x": 0.5, "y": 0.8}, {"x": 0.3, "y": 0.4}]
        f = MapFeature(
            map_id="m",
            object_id="o",
            object_type="entity",
            x=0.0,
            y=0.0,
            feature_type=FEATURE_TYPE_PATH,
            geometry=coords,
        )
        min_x, min_y, max_x, max_y = f.get_bounding_box()
        assert min_x == pytest.approx(0.1)
        assert min_y == pytest.approx(0.2)
        assert max_x == pytest.approx(0.5)
        assert max_y == pytest.approx(0.8)

    def test_bbox_region_feature(self) -> None:
        coords = [
            {"x": 0.0, "y": 0.0},
            {"x": 1.0, "y": 0.0},
            {"x": 1.0, "y": 1.0},
            {"x": 0.0, "y": 1.0},
        ]
        f = MapFeature(
            map_id="m",
            object_id="o",
            object_type="entity",
            x=0.5,
            y=0.5,
            feature_type=FEATURE_TYPE_REGION,
            geometry=coords,
        )
        assert f.get_bounding_box() == (0.0, 0.0, 1.0, 1.0)


# --------------------------------------------------------------------------
# Serialization round-trip
# --------------------------------------------------------------------------


class TestSerialization:
    """Verify to_dict / from_dict round-trip with new fields."""

    def test_round_trip_point(self) -> None:
        original = MapFeature(
            map_id="m",
            object_id="o",
            object_type="entity",
            x=0.5,
            y=0.5,
            label="Castle",
        )
        d = original.to_dict()
        restored = MapFeature.from_dict(d)

        assert restored.feature_type == FEATURE_TYPE_POINT
        assert restored.geometry is None
        assert restored.style is None
        assert restored.x == 0.5
        assert restored.label == "Castle"

    def test_round_trip_path_with_geometry(self) -> None:
        coords = [{"x": 0.1, "y": 0.2}, {"x": 0.9, "y": 0.8}]
        style = {"stroke_width": 2, "stroke_color": "#FF0000"}
        original = MapFeature(
            map_id="m",
            object_id="o",
            object_type="entity",
            x=0.5,
            y=0.5,
            feature_type=FEATURE_TYPE_PATH,
            geometry=coords,
            style=style,
        )
        d = original.to_dict()
        restored = MapFeature.from_dict(d)

        assert restored.feature_type == FEATURE_TYPE_PATH
        assert restored.geometry == coords
        assert restored.style == style

    def test_from_dict_json_string_geometry(self) -> None:
        """from_dict handles JSON-encoded strings (as returned from SQLite)."""
        coords = [{"x": 0.1, "y": 0.2}]
        style = {"fill_color": "#00FF00"}
        data = {
            "map_id": "m",
            "object_id": "o",
            "object_type": "entity",
            "x": 0.1,
            "y": 0.2,
            "feature_type": "region",
            "geometry": json.dumps(coords),
            "style": json.dumps(style),
        }
        f = MapFeature.from_dict(data)
        assert f.geometry == coords
        assert f.style == style

    def test_from_dict_invalid_json_geometry(self) -> None:
        """Malformed JSON geometry degrades gracefully to None."""
        data = {
            "map_id": "m",
            "object_id": "o",
            "object_type": "entity",
            "x": 0.1,
            "y": 0.2,
            "geometry": "not-valid-json{{{",
            "style": "also-broken{{{",
        }
        f = MapFeature.from_dict(data)
        assert f.geometry is None
        assert f.style is None


# --------------------------------------------------------------------------
# Database integration tests (require db_service fixture)
# --------------------------------------------------------------------------


class TestMapFeatureDatabase:
    """Test that MapFeature new fields persist through the database layer."""

    def test_point_feature_roundtrip(self, db_service) -> None:
        """Default point feature survives insert/read."""
        from src.core.map import Map

        map_obj = Map(name="Test", image_path="/test.png")
        db_service.insert_map(map_obj)

        f = MapFeature(
            map_id=map_obj.id,
            object_id="e-1",
            object_type="entity",
            x=0.5,
            y=0.5,
        )
        fid = db_service.insert_marker(f)
        fetched = db_service.get_marker(fid)

        assert fetched is not None
        assert fetched.feature_type == FEATURE_TYPE_POINT
        assert fetched.geometry is None
        assert fetched.style is None

    def test_path_feature_roundtrip(self, db_service) -> None:
        """Path feature with geometry and style survives insert/read."""
        from src.core.map import Map

        map_obj = Map(name="Test", image_path="/test.png")
        db_service.insert_map(map_obj)

        coords = [{"x": 0.1, "y": 0.2}, {"x": 0.9, "y": 0.8}]
        style = {"stroke_width": 3, "stroke_color": "#FF0000"}
        f = MapFeature(
            map_id=map_obj.id,
            object_id="river-1",
            object_type="entity",
            x=0.5,
            y=0.5,
            feature_type=FEATURE_TYPE_PATH,
            geometry=coords,
            style=style,
        )
        fid = db_service.insert_marker(f)
        fetched = db_service.get_marker(fid)

        assert fetched is not None
        assert fetched.feature_type == FEATURE_TYPE_PATH
        assert fetched.geometry == coords
        assert fetched.style == style

    def test_region_feature_roundtrip(self, db_service) -> None:
        """Region feature with polygon geometry survives insert/read."""
        from src.core.map import Map

        map_obj = Map(name="Test", image_path="/test.png")
        db_service.insert_map(map_obj)

        coords = [
            {"x": 0.0, "y": 0.0},
            {"x": 1.0, "y": 0.0},
            {"x": 1.0, "y": 1.0},
            {"x": 0.0, "y": 1.0},
        ]
        f = MapFeature(
            map_id=map_obj.id,
            object_id="kingdom-1",
            object_type="entity",
            x=0.5,
            y=0.5,
            feature_type=FEATURE_TYPE_REGION,
            geometry=coords,
            style={"fill_color": "#00FF0080"},
        )
        fid = db_service.insert_marker(f)
        fetched = db_service.get_marker(fid)

        assert fetched is not None
        assert fetched.feature_type == FEATURE_TYPE_REGION
        assert fetched.geometry == coords
        assert fetched.is_region is True
        assert len(fetched.points) == 4

    def test_feature_type_default_migration(self, db_service) -> None:
        """Existing rows with NULL feature_type default to 'point'."""
        from src.core.map import Map

        map_obj = Map(name="Test", image_path="/test.png")
        db_service.insert_map(map_obj)

        # Insert using old-style Marker (backward compat)
        m = Marker(
            map_id=map_obj.id,
            object_id="old-e-1",
            object_type="entity",
            x=0.5,
            y=0.5,
        )
        mid = db_service.insert_marker(m)
        fetched = db_service.get_marker(mid)

        assert fetched.feature_type == FEATURE_TYPE_POINT
        assert fetched.is_point is True

    def test_get_markers_for_map_with_mixed_types(self, db_service) -> None:
        """get_markers_for_map returns both points and path features."""
        from src.core.map import Map

        map_obj = Map(name="Mixed", image_path="/test.png")
        db_service.insert_map(map_obj)

        point = MapFeature(
            map_id=map_obj.id,
            object_id="e-1",
            object_type="entity",
            x=0.5,
            y=0.5,
        )
        path = MapFeature(
            map_id=map_obj.id,
            object_id="e-2",
            object_type="entity",
            x=0.5,
            y=0.5,
            feature_type=FEATURE_TYPE_PATH,
            geometry=[{"x": 0.1, "y": 0.1}, {"x": 0.9, "y": 0.9}],
        )
        db_service.insert_marker(point)
        db_service.insert_marker(path)

        markers = db_service.get_markers_for_map(map_obj.id)
        assert len(markers) == 2

        types = {m.feature_type for m in markers}
        assert FEATURE_TYPE_POINT in types
        assert FEATURE_TYPE_PATH in types


# --------------------------------------------------------------------------
# GIS spatial computations
# --------------------------------------------------------------------------


class TestComputeLength:
    """Verify compute_length() for paths."""

    def test_horizontal_line_unit_length(self) -> None:
        """Horizontal path from (0,0) to (1,0) has length 1.0."""
        f = MapFeature(
            map_id="m",
            object_id="o",
            object_type="entity",
            x=0.5,
            y=0.0,
            feature_type=FEATURE_TYPE_PATH,
            geometry=[{"x": 0.0, "y": 0.0}, {"x": 1.0, "y": 0.0}],
        )
        assert f.compute_length() == pytest.approx(1.0)

    def test_length_with_map_scale(self) -> None:
        """Path length scales with map_width / map_height."""
        f = MapFeature(
            map_id="m",
            object_id="o",
            object_type="entity",
            x=0.5,
            y=0.0,
            feature_type=FEATURE_TYPE_PATH,
            geometry=[{"x": 0.0, "y": 0.0}, {"x": 1.0, "y": 0.0}],
        )
        assert f.compute_length(map_width=1000) == pytest.approx(1000.0)

    def test_multi_segment_path(self) -> None:
        """Length of a multi-segment path is sum of segments."""
        f = MapFeature(
            map_id="m",
            object_id="o",
            object_type="entity",
            x=0.5,
            y=0.5,
            feature_type=FEATURE_TYPE_PATH,
            geometry=[
                {"x": 0.0, "y": 0.0},
                {"x": 1.0, "y": 0.0},
                {"x": 1.0, "y": 1.0},
            ],
        )
        # 1.0 + 1.0 = 2.0
        assert f.compute_length() == pytest.approx(2.0)

    def test_point_returns_zero_length(self) -> None:
        """Points have no length."""
        f = MapFeature(
            map_id="m",
            object_id="o",
            object_type="entity",
            x=0.5,
            y=0.5,
        )
        assert f.compute_length() == 0.0

    def test_region_returns_zero_length(self) -> None:
        """Regions use compute_perimeter, not compute_length."""
        f = MapFeature(
            map_id="m",
            object_id="o",
            object_type="entity",
            x=0.5,
            y=0.5,
            feature_type=FEATURE_TYPE_REGION,
            geometry=[
                {"x": 0.0, "y": 0.0},
                {"x": 1.0, "y": 0.0},
                {"x": 0.5, "y": 1.0},
            ],
        )
        assert f.compute_length() == 0.0


class TestComputeArea:
    """Verify compute_area() using the Shoelace formula."""

    def test_unit_square_area(self) -> None:
        """A unit square has area 1.0."""
        f = MapFeature(
            map_id="m",
            object_id="o",
            object_type="entity",
            x=0.5,
            y=0.5,
            feature_type=FEATURE_TYPE_REGION,
            geometry=[
                {"x": 0.0, "y": 0.0},
                {"x": 1.0, "y": 0.0},
                {"x": 1.0, "y": 1.0},
                {"x": 0.0, "y": 1.0},
            ],
        )
        assert f.compute_area() == pytest.approx(1.0)

    def test_area_with_map_scale(self) -> None:
        """Area scales with map_width * map_height."""
        f = MapFeature(
            map_id="m",
            object_id="o",
            object_type="entity",
            x=0.5,
            y=0.5,
            feature_type=FEATURE_TYPE_REGION,
            geometry=[
                {"x": 0.0, "y": 0.0},
                {"x": 1.0, "y": 0.0},
                {"x": 1.0, "y": 1.0},
                {"x": 0.0, "y": 1.0},
            ],
        )
        assert f.compute_area(1000, 1000) == pytest.approx(1_000_000.0)

    def test_triangle_area(self) -> None:
        """Triangle (0,0), (1,0), (0,1) has area 0.5."""
        f = MapFeature(
            map_id="m",
            object_id="o",
            object_type="entity",
            x=0.33,
            y=0.33,
            feature_type=FEATURE_TYPE_REGION,
            geometry=[
                {"x": 0.0, "y": 0.0},
                {"x": 1.0, "y": 0.0},
                {"x": 0.0, "y": 1.0},
            ],
        )
        assert f.compute_area() == pytest.approx(0.5)

    def test_path_returns_zero_area(self) -> None:
        """Paths have no area."""
        f = MapFeature(
            map_id="m",
            object_id="o",
            object_type="entity",
            x=0.5,
            y=0.5,
            feature_type=FEATURE_TYPE_PATH,
            geometry=[{"x": 0.0, "y": 0.0}, {"x": 1.0, "y": 1.0}],
        )
        assert f.compute_area() == 0.0


class TestComputePerimeter:
    """Verify compute_perimeter() for regions."""

    def test_unit_square_perimeter(self) -> None:
        """A unit square has perimeter 4.0."""
        f = MapFeature(
            map_id="m",
            object_id="o",
            object_type="entity",
            x=0.5,
            y=0.5,
            feature_type=FEATURE_TYPE_REGION,
            geometry=[
                {"x": 0.0, "y": 0.0},
                {"x": 1.0, "y": 0.0},
                {"x": 1.0, "y": 1.0},
                {"x": 0.0, "y": 1.0},
            ],
        )
        assert f.compute_perimeter() == pytest.approx(4.0)

    def test_perimeter_with_map_scale(self) -> None:
        """Perimeter scales with map dimensions."""
        f = MapFeature(
            map_id="m",
            object_id="o",
            object_type="entity",
            x=0.5,
            y=0.5,
            feature_type=FEATURE_TYPE_REGION,
            geometry=[
                {"x": 0.0, "y": 0.0},
                {"x": 1.0, "y": 0.0},
                {"x": 1.0, "y": 1.0},
                {"x": 0.0, "y": 1.0},
            ],
        )
        assert f.compute_perimeter(1000, 1000) == pytest.approx(4000.0)

    def test_path_returns_zero_perimeter(self) -> None:
        """Paths have no perimeter."""
        f = MapFeature(
            map_id="m",
            object_id="o",
            object_type="entity",
            x=0.5,
            y=0.5,
            feature_type=FEATURE_TYPE_PATH,
            geometry=[{"x": 0.0, "y": 0.0}, {"x": 1.0, "y": 0.0}],
        )
        assert f.compute_perimeter() == 0.0


class TestSegmentCount:
    """Verify compute_segment_count()."""

    def test_path_segments(self) -> None:
        """A 3-vertex path has 2 segments."""
        f = MapFeature(
            map_id="m",
            object_id="o",
            object_type="entity",
            x=0.5,
            y=0.5,
            feature_type=FEATURE_TYPE_PATH,
            geometry=[
                {"x": 0.0, "y": 0.0},
                {"x": 0.5, "y": 0.5},
                {"x": 1.0, "y": 1.0},
            ],
        )
        assert f.compute_segment_count() == 2

    def test_region_segments(self) -> None:
        """A 4-vertex region has 4 segments (closed polygon)."""
        f = MapFeature(
            map_id="m",
            object_id="o",
            object_type="entity",
            x=0.5,
            y=0.5,
            feature_type=FEATURE_TYPE_REGION,
            geometry=[
                {"x": 0.0, "y": 0.0},
                {"x": 1.0, "y": 0.0},
                {"x": 1.0, "y": 1.0},
                {"x": 0.0, "y": 1.0},
            ],
        )
        assert f.compute_segment_count() == 4

    def test_single_point_zero_segments(self) -> None:
        """A single point has 0 segments."""
        f = MapFeature(
            map_id="m",
            object_id="o",
            object_type="entity",
            x=0.5,
            y=0.5,
        )
        assert f.compute_segment_count() == 0


class TestSpatialProperties:
    """Verify the spatial_properties dict accessor."""

    def test_path_spatial_properties(self) -> None:
        """Path spatial_properties includes length."""
        f = MapFeature(
            map_id="m",
            object_id="o",
            object_type="entity",
            x=0.5,
            y=0.0,
            feature_type=FEATURE_TYPE_PATH,
            geometry=[{"x": 0.0, "y": 0.0}, {"x": 1.0, "y": 0.0}],
        )
        sp = f.spatial_properties
        assert sp["feature_type"] == "path"
        assert sp["length"] == pytest.approx(1.0)
        assert sp["vertex_count"] == 2
        assert sp["segment_count"] == 1
        assert "area" not in sp
        assert "perimeter" not in sp

    def test_region_spatial_properties(self) -> None:
        """Region spatial_properties includes area and perimeter."""
        f = MapFeature(
            map_id="m",
            object_id="o",
            object_type="entity",
            x=0.5,
            y=0.5,
            feature_type=FEATURE_TYPE_REGION,
            geometry=[
                {"x": 0.0, "y": 0.0},
                {"x": 1.0, "y": 0.0},
                {"x": 1.0, "y": 1.0},
                {"x": 0.0, "y": 1.0},
            ],
        )
        sp = f.spatial_properties
        assert sp["area"] == pytest.approx(1.0)
        assert sp["perimeter"] == pytest.approx(4.0)
        assert "length" not in sp

    def test_spatial_properties_merge_attributes(self) -> None:
        """spatial_properties merges user attributes (road quality, etc.)."""
        f = MapFeature(
            map_id="m",
            object_id="o",
            object_type="entity",
            x=0.5,
            y=0.0,
            feature_type=FEATURE_TYPE_PATH,
            geometry=[{"x": 0.0, "y": 0.0}, {"x": 1.0, "y": 0.0}],
            attributes={"road_quality": "paved", "river_depth": 3.5},
        )
        sp = f.spatial_properties
        assert sp["road_quality"] == "paved"
        assert sp["river_depth"] == 3.5
        assert sp["length"] == pytest.approx(1.0)
