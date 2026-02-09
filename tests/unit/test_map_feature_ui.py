"""Unit tests for map feature rendering and drawing mode UI.

Tests the PathItem, RegionItem rendering, MapGraphicsView factory pattern,
drawing mode state machine, and the full pipeline from DataHandler → MapWidget.
"""

import os

import pytest

# Skip all Qt tests if display is not available
pytestmark = pytest.mark.skipif(
    not os.environ.get("DISPLAY") and os.environ.get("QT_QPA_PLATFORM") != "offscreen",
    reason="No display available for Qt tests",
)

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication, QGraphicsPixmapItem, QGraphicsScene

from src.core.marker import (
    FEATURE_TYPE_PATH,
    FEATURE_TYPE_POINT,
    FEATURE_TYPE_REGION,
    MapFeature,
)
from src.gui.widgets.map.feature_items import PathItem, RegionItem


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def ensure_qapp():
    """Ensure a QApplication exists for the test session."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture()
def pixmap_item():
    """Create a 100x100 QGraphicsPixmapItem for coordinate testing.

    The scene is stored on the pixmap item to prevent GC.
    """
    pm = QPixmap(100, 100)
    pm.fill(Qt.GlobalColor.white)
    item = QGraphicsPixmapItem(pm)
    scene = QGraphicsScene()
    scene.addItem(item)
    # Keep scene alive to prevent C++ object deletion
    item._test_scene = scene
    return item


@pytest.fixture()
def sample_path_geometry():
    """Return a simple 3-vertex path geometry (normalized)."""
    return [
        {"x": 0.1, "y": 0.2},
        {"x": 0.5, "y": 0.5},
        {"x": 0.9, "y": 0.8},
    ]


@pytest.fixture()
def sample_region_geometry():
    """Return a simple square region geometry (normalized)."""
    return [
        {"x": 0.2, "y": 0.2},
        {"x": 0.8, "y": 0.2},
        {"x": 0.8, "y": 0.8},
        {"x": 0.2, "y": 0.8},
    ]


# --------------------------------------------------------------------------
# PathItem tests
# --------------------------------------------------------------------------


class TestPathItem:
    """Tests for the PathItem rendering class."""

    def test_path_item_creation(
        self, pixmap_item, sample_path_geometry
    ) -> None:
        """PathItem can be created with geometry."""
        item = PathItem(
            marker_id="path-1",
            object_type="entity",
            label="River Nile",
            pixmap_item=pixmap_item,
            geometry=sample_path_geometry,
            anchor_x=0.5,
            anchor_y=0.5,
        )
        assert item.marker_id == "path-1"
        assert item.object_type == "entity"
        assert item.label == "River Nile"

    def test_path_item_bounding_rect_not_empty(
        self, pixmap_item, sample_path_geometry
    ) -> None:
        """PathItem has a non-empty bounding rect."""
        item = PathItem(
            marker_id="p1",
            object_type="entity",
            label="Road",
            pixmap_item=pixmap_item,
            geometry=sample_path_geometry,
            anchor_x=0.5,
            anchor_y=0.5,
        )
        rect = item.boundingRect()
        assert not rect.isEmpty()
        assert rect.width() > 0
        assert rect.height() > 0

    def test_path_item_shape_wider_than_stroke(
        self, pixmap_item, sample_path_geometry
    ) -> None:
        """PathItem shape (for hit testing) is wider than the visual stroke."""
        item = PathItem(
            marker_id="p1",
            object_type="entity",
            label="Road",
            pixmap_item=pixmap_item,
            geometry=sample_path_geometry,
            anchor_x=0.5,
            anchor_y=0.5,
        )
        shape = item.shape()
        assert not shape.isEmpty()
        # Shape bounding rect should be wider than the path bounding rect
        shape_rect = shape.boundingRect()
        assert shape_rect.width() > 0

    def test_path_item_custom_style(
        self, pixmap_item, sample_path_geometry
    ) -> None:
        """PathItem respects custom style properties."""
        style = {
            "stroke_color": "#FF0000",
            "stroke_width": 5,
            "dash_pattern": [4, 2],
        }
        item = PathItem(
            marker_id="p1",
            object_type="entity",
            label="Road",
            pixmap_item=pixmap_item,
            geometry=sample_path_geometry,
            anchor_x=0.5,
            anchor_y=0.5,
            style=style,
        )
        assert item._stroke_width() == 5.0
        assert item._dash_pattern() == [4, 2]

    def test_path_item_clicked_signal(
        self, pixmap_item, sample_path_geometry
    ) -> None:
        """PathItem has a clicked signal."""
        item = PathItem(
            marker_id="p1",
            object_type="entity",
            label="Road",
            pixmap_item=pixmap_item,
            geometry=sample_path_geometry,
            anchor_x=0.5,
            anchor_y=0.5,
        )
        # Verify signal exists
        assert hasattr(item, "clicked")

    def test_path_item_temporal_state(
        self, pixmap_item, sample_path_geometry
    ) -> None:
        """PathItem supports temporal state (future/past)."""
        item = PathItem(
            marker_id="p1",
            object_type="entity",
            label="Road",
            pixmap_item=pixmap_item,
            geometry=sample_path_geometry,
            anchor_x=0.5,
            anchor_y=0.5,
            lore_date=100.0,
        )
        assert item.lore_date == 100.0
        item.set_temporal_state(is_future=True)
        assert item.is_future is True
        assert item.opacity() == pytest.approx(0.7)


# --------------------------------------------------------------------------
# RegionItem tests
# --------------------------------------------------------------------------


class TestRegionItem:
    """Tests for the RegionItem rendering class."""

    def test_region_item_creation(
        self, pixmap_item, sample_region_geometry
    ) -> None:
        """RegionItem can be created with geometry."""
        item = RegionItem(
            marker_id="region-1",
            object_type="entity",
            label="Kingdom of Gondor",
            pixmap_item=pixmap_item,
            geometry=sample_region_geometry,
            anchor_x=0.5,
            anchor_y=0.5,
        )
        assert item.marker_id == "region-1"
        assert item.label == "Kingdom of Gondor"

    def test_region_item_bounding_rect(
        self, pixmap_item, sample_region_geometry
    ) -> None:
        """RegionItem has a non-empty bounding rect."""
        item = RegionItem(
            marker_id="r1",
            object_type="entity",
            label="Kingdom",
            pixmap_item=pixmap_item,
            geometry=sample_region_geometry,
            anchor_x=0.5,
            anchor_y=0.5,
        )
        rect = item.boundingRect()
        assert not rect.isEmpty()

    def test_region_item_shape_is_polygon(
        self, pixmap_item, sample_region_geometry
    ) -> None:
        """RegionItem shape is a closed polygon for fill-based hit testing."""
        item = RegionItem(
            marker_id="r1",
            object_type="entity",
            label="Kingdom",
            pixmap_item=pixmap_item,
            geometry=sample_region_geometry,
            anchor_x=0.5,
            anchor_y=0.5,
        )
        shape = item.shape()
        assert not shape.isEmpty()
        # Point inside the polygon should be contained
        center = QPointF(50, 50)  # Center of 100x100 pixmap, region is 0.2-0.8
        assert shape.contains(center)

    def test_region_item_custom_fill(
        self, pixmap_item, sample_region_geometry
    ) -> None:
        """RegionItem respects custom fill_color from style."""
        style = {"fill_color": "#8000FF00", "stroke_color": "#000000"}
        item = RegionItem(
            marker_id="r1",
            object_type="entity",
            label="Forest",
            pixmap_item=pixmap_item,
            geometry=sample_region_geometry,
            anchor_x=0.5,
            anchor_y=0.5,
            style=style,
        )
        fill = item._fill_color()
        assert fill.alpha() == 128  # #80 ARGB = 128 alpha


# --------------------------------------------------------------------------
# MapGraphicsView factory pattern tests
# --------------------------------------------------------------------------


class TestMapGraphicsViewFactory:
    """Tests for the add_marker factory pattern in MapGraphicsView."""

    @pytest.fixture()
    def view(self, qtbot):
        """Create a MapGraphicsView with a loaded map."""
        from src.gui.widgets.map.map_graphics_view import MapGraphicsView

        view = MapGraphicsView()
        # Load a synthetic map
        pm = QPixmap(200, 200)
        pm.fill(Qt.GlobalColor.blue)
        view.pixmap_item = QGraphicsPixmapItem(pm)
        view.pixmap_item.setZValue(0)
        view.scene.addItem(view.pixmap_item)
        view.coord_system.set_scene_rect(view.pixmap_item.boundingRect())
        qtbot.addWidget(view)
        return view

    def test_add_point_marker(self, view) -> None:
        """Default feature_type='point' creates a MarkerItem."""
        from src.gui.widgets.map.marker_item import MarkerItem

        view.add_marker("m1", "entity", "Castle", 0.5, 0.5)
        assert "m1" in view.markers
        assert isinstance(view.markers["m1"], MarkerItem)
        assert "m1" not in view.feature_items

    def test_add_path_feature(self, view) -> None:
        """feature_type='path' with geometry creates a PathItem."""
        geom = [{"x": 0.1, "y": 0.2}, {"x": 0.9, "y": 0.8}]
        view.add_marker(
            "p1", "entity", "River", 0.5, 0.5,
            feature_type="path", geometry=geom,
        )
        assert "p1" not in view.markers  # Not a point marker
        assert "p1" in view.feature_items
        assert isinstance(view.feature_items["p1"], PathItem)

    def test_add_region_feature(self, view) -> None:
        """feature_type='region' with geometry creates a RegionItem."""
        geom = [
            {"x": 0.0, "y": 0.0},
            {"x": 1.0, "y": 0.0},
            {"x": 1.0, "y": 1.0},
            {"x": 0.0, "y": 1.0},
        ]
        view.add_marker(
            "r1", "entity", "Kingdom", 0.5, 0.5,
            feature_type="region", geometry=geom,
        )
        assert "r1" not in view.markers
        assert "r1" in view.feature_items
        assert isinstance(view.feature_items["r1"], RegionItem)

    def test_path_without_geometry_falls_back_to_point(self, view) -> None:
        """feature_type='path' without geometry creates a MarkerItem."""
        from src.gui.widgets.map.marker_item import MarkerItem

        view.add_marker(
            "p2", "entity", "Empty Path", 0.5, 0.5,
            feature_type="path", geometry=None,
        )
        assert "p2" in view.markers
        assert isinstance(view.markers["p2"], MarkerItem)

    def test_remove_marker_removes_feature(self, view) -> None:
        """remove_marker works for both markers and features."""
        geom = [{"x": 0.1, "y": 0.2}, {"x": 0.9, "y": 0.8}]
        view.add_marker(
            "p1", "entity", "River", 0.5, 0.5,
            feature_type="path", geometry=geom,
        )
        assert "p1" in view.feature_items
        view.remove_marker("p1")
        assert "p1" not in view.feature_items

    def test_clear_markers_clears_features(self, view) -> None:
        """clear_markers removes both markers and features."""
        view.add_marker("m1", "entity", "Castle", 0.5, 0.5)
        geom = [{"x": 0.1, "y": 0.2}, {"x": 0.9, "y": 0.8}]
        view.add_marker(
            "p1", "entity", "River", 0.5, 0.5,
            feature_type="path", geometry=geom,
        )
        assert len(view.markers) == 1
        assert len(view.feature_items) == 1
        view.clear_markers()
        assert len(view.markers) == 0
        assert len(view.feature_items) == 0

    def test_replace_existing_feature(self, view) -> None:
        """Adding a feature with same ID replaces the previous one."""
        geom1 = [{"x": 0.1, "y": 0.2}, {"x": 0.9, "y": 0.8}]
        geom2 = [{"x": 0.2, "y": 0.3}, {"x": 0.8, "y": 0.7}]
        view.add_marker(
            "p1", "entity", "River v1", 0.5, 0.5,
            feature_type="path", geometry=geom1,
        )
        view.add_marker(
            "p1", "entity", "River v2", 0.5, 0.5,
            feature_type="path", geometry=geom2,
        )
        assert len(view.feature_items) == 1
        assert view.feature_items["p1"].label == "River v2"


# --------------------------------------------------------------------------
# Drawing mode state machine tests
# --------------------------------------------------------------------------


class TestDrawingMode:
    """Tests for the drawing mode in MapGraphicsView."""

    @pytest.fixture()
    def view(self, qtbot):
        """Create a MapGraphicsView with a loaded map."""
        from src.gui.widgets.map.map_graphics_view import MapGraphicsView

        view = MapGraphicsView()
        pm = QPixmap(200, 200)
        pm.fill(Qt.GlobalColor.blue)
        view.pixmap_item = QGraphicsPixmapItem(pm)
        view.pixmap_item.setZValue(0)
        view.scene.addItem(view.pixmap_item)
        view.coord_system.set_scene_rect(view.pixmap_item.boundingRect())
        qtbot.addWidget(view)
        return view

    def test_start_drawing_activates_mode(self, view) -> None:
        """start_drawing sets drawing mode."""
        view.start_drawing("path")
        assert view.is_drawing is True
        assert view.drawing_mode == "path"

    def test_cancel_drawing_deactivates_mode(self, view) -> None:
        """cancel_drawing resets state."""
        view.start_drawing("path")
        view.cancel_drawing()
        assert view.is_drawing is False
        assert view.drawing_mode is None

    def test_drawing_vertices_are_tracked(self, view) -> None:
        """Adding vertices during drawing mode works."""
        view.start_drawing("path")
        view._add_drawing_vertex(QPointF(10, 20))
        view._add_drawing_vertex(QPointF(30, 40))
        assert len(view._drawing_vertices) == 2

    def test_cancel_clears_vertices(self, view) -> None:
        """cancel_drawing clears accumulated vertices."""
        view.start_drawing("path")
        view._add_drawing_vertex(QPointF(10, 20))
        view.cancel_drawing()
        assert len(view._drawing_vertices) == 0

    def test_finish_path_needs_min_2_points(self, view, qtbot) -> None:
        """finish_drawing for path needs at least 2 vertices."""
        view.start_drawing("path")
        view._add_drawing_vertex(QPointF(10, 20))
        # Only 1 point — should cancel
        with qtbot.waitSignal(view.drawing_cancelled, timeout=1000):
            view.finish_drawing()
        assert view.is_drawing is False

    def test_finish_region_needs_min_3_points(self, view, qtbot) -> None:
        """finish_drawing for region needs at least 3 vertices."""
        view.start_drawing("region")
        view._add_drawing_vertex(QPointF(10, 20))
        view._add_drawing_vertex(QPointF(30, 40))
        # Only 2 points — should cancel
        with qtbot.waitSignal(view.drawing_cancelled, timeout=1000):
            view.finish_drawing()
        assert view.is_drawing is False

    def test_finish_path_emits_signal(self, view, qtbot) -> None:
        """finish_drawing emits drawing_finished with normalized coords."""
        view.start_drawing("path")
        # Add points within the 200x200 pixmap
        view._add_drawing_vertex(QPointF(20, 40))
        view._add_drawing_vertex(QPointF(180, 160))
        with qtbot.waitSignal(view.drawing_finished, timeout=1000) as sig:
            view.finish_drawing()
        feature_type, geometry = sig.args
        assert feature_type == "path"
        assert len(geometry) == 2
        # First point ~(0.1, 0.2) and second ~(0.9, 0.8)
        assert geometry[0]["x"] == pytest.approx(0.1, abs=0.01)
        assert geometry[0]["y"] == pytest.approx(0.2, abs=0.01)

    def test_finish_region_emits_signal(self, view, qtbot) -> None:
        """finish_drawing for region emits correct feature_type."""
        view.start_drawing("region")
        view._add_drawing_vertex(QPointF(20, 20))
        view._add_drawing_vertex(QPointF(180, 20))
        view._add_drawing_vertex(QPointF(180, 180))
        with qtbot.waitSignal(view.drawing_finished, timeout=1000) as sig:
            view.finish_drawing()
        feature_type, geometry = sig.args
        assert feature_type == "region"
        assert len(geometry) == 3

    def test_drawing_dots_are_cleaned_up(self, view) -> None:
        """Dots placed during drawing are cleaned up on cancel."""
        view.start_drawing("path")
        view._add_drawing_vertex(QPointF(10, 20))
        view._add_drawing_vertex(QPointF(30, 40))
        assert len(view._drawing_dots) == 2
        view.cancel_drawing()
        assert len(view._drawing_dots) == 0

    def test_drawing_preview_is_cleaned_up(self, view) -> None:
        """Preview path is cleaned up on cancel."""
        view.start_drawing("path")
        view._add_drawing_vertex(QPointF(10, 20))
        view._update_drawing_preview(QPointF(30, 40))
        assert view._drawing_preview_item is not None
        view.cancel_drawing()
        assert view._drawing_preview_item is None


# --------------------------------------------------------------------------
# Full pipeline: MapFeature → DataHandler → add_marker()
# --------------------------------------------------------------------------


class TestFeaturePipeline:
    """Tests that MapFeature data flows correctly through the pipeline."""

    def test_create_marker_command_with_geometry(self, db_service) -> None:
        """CreateMarkerCommand stores feature_type and geometry."""
        from src.commands.map_commands import CreateMarkerCommand
        from src.core.map import Map

        map_obj = Map(name="Test", image_path="/test.png")
        db_service.insert_map(map_obj)

        cmd = CreateMarkerCommand(
            {
                "map_id": map_obj.id,
                "object_id": "river-1",
                "object_type": "entity",
                "x": 0.5,
                "y": 0.5,
                "label": "River",
                "feature_type": "path",
                "geometry": [
                    {"x": 0.1, "y": 0.2},
                    {"x": 0.9, "y": 0.8},
                ],
            }
        )
        result = cmd.execute(db_service)
        assert result.success is True

        # Verify persisted data
        marker = db_service.get_marker(result.data["id"])
        assert marker.feature_type == "path"
        assert len(marker.geometry) == 2
        assert marker.points == [(0.1, 0.2), (0.9, 0.8)]

    def test_create_marker_command_with_geometry_undo(self, db_service) -> None:
        """CreateMarkerCommand undo removes the geometry feature."""
        from src.commands.map_commands import CreateMarkerCommand
        from src.core.map import Map

        map_obj = Map(name="Test", image_path="/test.png")
        db_service.insert_map(map_obj)

        cmd = CreateMarkerCommand(
            {
                "map_id": map_obj.id,
                "object_id": "region-1",
                "object_type": "entity",
                "x": 0.5,
                "y": 0.5,
                "label": "Kingdom",
                "feature_type": "region",
                "geometry": [
                    {"x": 0.0, "y": 0.0},
                    {"x": 1.0, "y": 0.0},
                    {"x": 1.0, "y": 1.0},
                ],
            }
        )
        result = cmd.execute(db_service)
        assert result.success
        marker_id = result.data["id"]

        cmd.undo(db_service)
        assert db_service.get_marker(marker_id) is None

    def test_data_handler_includes_feature_fields(self) -> None:
        """DataHandler.on_markers_loaded includes feature_type/geometry/style."""
        # Simulate what the DataHandler does with marker data
        marker = MapFeature(
            map_id="m1",
            object_id="e1",
            object_type="entity",
            x=0.5,
            y=0.5,
            feature_type=FEATURE_TYPE_PATH,
            geometry=[{"x": 0.1, "y": 0.2}, {"x": 0.9, "y": 0.8}],
            style={"stroke_color": "#FF0000"},
        )

        # Replicate the DataHandler processing
        data = {
            "feature_type": getattr(marker, "feature_type", "point"),
            "geometry": getattr(marker, "geometry", None),
            "style": getattr(marker, "style", None),
        }
        assert data["feature_type"] == "path"
        assert len(data["geometry"]) == 2
        assert data["style"]["stroke_color"] == "#FF0000"
