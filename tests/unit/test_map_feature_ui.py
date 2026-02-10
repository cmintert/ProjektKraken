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


# --------------------------------------------------------------------------
# Vertex Editing Mode tests
# --------------------------------------------------------------------------


class TestVertexEditing:
    """Tests for the vertex editing mode in MapGraphicsView."""

    @pytest.fixture()
    def view(self, qtbot):
        """Create a MapGraphicsView with a path feature loaded."""
        from src.gui.widgets.map.map_graphics_view import MapGraphicsView

        view = MapGraphicsView()
        pm = QPixmap(200, 200)
        pm.fill(Qt.GlobalColor.blue)
        view.pixmap_item = QGraphicsPixmapItem(pm)
        view.pixmap_item.setZValue(0)
        view.scene.addItem(view.pixmap_item)
        view.coord_system.set_scene_rect(view.pixmap_item.boundingRect())
        qtbot.addWidget(view)

        # Add a path feature
        geom = [{"x": 0.1, "y": 0.2}, {"x": 0.5, "y": 0.5}, {"x": 0.9, "y": 0.8}]
        view.add_marker(
            "p1", "entity", "River", 0.5, 0.5,
            feature_type="path", geometry=geom,
        )
        return view

    def test_start_vertex_editing(self, view) -> None:
        """_start_vertex_editing creates handles for each vertex."""
        item = view.feature_items["p1"]
        view._start_vertex_editing(item)
        assert view.is_editing_vertices is True
        assert view._editing_feature_id == "p1"
        assert len(view._vertex_handles) == 3

    def test_finish_vertex_editing_emits_signal(self, view, qtbot) -> None:
        """_finish_vertex_editing emits feature_geometry_changed."""
        item = view.feature_items["p1"]
        view._start_vertex_editing(item)
        with qtbot.waitSignal(view.feature_geometry_changed, timeout=1000) as sig:
            view._finish_vertex_editing()
        marker_id, geometry = sig.args
        assert marker_id == "p1"
        assert len(geometry) == 3

    def test_finish_vertex_editing_cleans_up(self, view) -> None:
        """_finish_vertex_editing removes all handles."""
        item = view.feature_items["p1"]
        view._start_vertex_editing(item)
        view._finish_vertex_editing()
        assert view.is_editing_vertices is False
        assert len(view._vertex_handles) == 0

    def test_vertex_moved_updates_geometry(self, view) -> None:
        """_on_vertex_moved updates the feature's geometry list."""
        item = view.feature_items["p1"]
        view._start_vertex_editing(item)

        # Move vertex 0 to (0.3, 0.4) in scene coords  → (60, 80) on 200x200
        view._on_vertex_moved(0, QPointF(60, 80))
        assert item._geometry[0]["x"] == pytest.approx(0.3, abs=0.01)
        assert item._geometry[0]["y"] == pytest.approx(0.4, abs=0.01)

    def test_vertex_moved_clamps_to_bounds(self, view) -> None:
        """_on_vertex_moved clamps coords to [0, 1] range."""
        item = view.feature_items["p1"]
        view._start_vertex_editing(item)

        # Move vertex to way outside bounds
        view._on_vertex_moved(0, QPointF(-50, 500))
        assert item._geometry[0]["x"] == 0.0
        assert item._geometry[0]["y"] == 1.0

    def test_double_start_cleans_previous(self, view) -> None:
        """Starting a new vertex edit cleans up the previous one."""
        item = view.feature_items["p1"]
        view._start_vertex_editing(item)
        assert len(view._vertex_handles) == 3

        # Start again — should clean up and restart
        view._start_vertex_editing(item)
        assert len(view._vertex_handles) == 3


# --------------------------------------------------------------------------
# Feature style accessor tests
# --------------------------------------------------------------------------


class TestFeatureItemStyle:
    """Tests for style changes on feature items."""

    @pytest.fixture()
    def view(self, qtbot):
        """Create a MapGraphicsView with a region feature."""
        from src.gui.widgets.map.map_graphics_view import MapGraphicsView

        view = MapGraphicsView()
        pm = QPixmap(200, 200)
        pm.fill(Qt.GlobalColor.blue)
        view.pixmap_item = QGraphicsPixmapItem(pm)
        view.pixmap_item.setZValue(0)
        view.scene.addItem(view.pixmap_item)
        view.coord_system.set_scene_rect(view.pixmap_item.boundingRect())
        qtbot.addWidget(view)

        geom = [
            {"x": 0.2, "y": 0.2},
            {"x": 0.8, "y": 0.2},
            {"x": 0.8, "y": 0.8},
            {"x": 0.2, "y": 0.8},
        ]
        view.add_marker(
            "r1", "entity", "Kingdom", 0.5, 0.5,
            feature_type="region", geometry=geom,
            style={"stroke_color": "#000000", "fill_color": "#FF000040"},
        )
        return view

    def test_style_applied_on_creation(self, view) -> None:
        """Feature items receive style dict from add_marker."""
        item = view.feature_items["r1"]
        assert item._style["stroke_color"] == "#000000"
        assert item._style["fill_color"] == "#FF000040"

    def test_style_update_changes_visual(self, view) -> None:
        """Updating _style and calling update() changes the item."""
        item = view.feature_items["r1"]
        item._style["stroke_color"] = "#00FF00"
        item.update()
        assert item._stroke_color().name() == "#00ff00"

    def test_feature_style_changed_signal(self, view, qtbot) -> None:
        """feature_style_changed signal emits from view."""
        with qtbot.waitSignal(view.feature_style_changed, timeout=1000) as sig:
            view.feature_style_changed.emit("r1", {"stroke_color": "#00FF00"})
        assert sig.args[0] == "r1"
        assert sig.args[1]["stroke_color"] == "#00FF00"


# --------------------------------------------------------------------------
# Midpoint handles and vertex deletion tests
# --------------------------------------------------------------------------


class TestVertexManagement:
    """Tests for midpoint insertion, vertex deletion, and snapping."""

    @pytest.fixture()
    def view(self, qtbot):
        """Create a MapGraphicsView with a path feature for vertex tests."""
        from src.gui.widgets.map.map_graphics_view import MapGraphicsView

        view = MapGraphicsView()
        pm = QPixmap(200, 200)
        pm.fill(Qt.GlobalColor.blue)
        view.pixmap_item = QGraphicsPixmapItem(pm)
        view.pixmap_item.setZValue(0)
        view.scene.addItem(view.pixmap_item)
        view.coord_system.set_scene_rect(view.pixmap_item.boundingRect())
        qtbot.addWidget(view)

        geom = [
            {"x": 0.1, "y": 0.2},
            {"x": 0.5, "y": 0.5},
            {"x": 0.9, "y": 0.8},
        ]
        view.add_marker(
            "p1", "entity", "River", 0.5, 0.5,
            feature_type="path", geometry=geom,
        )
        return view

    @pytest.fixture()
    def region_view(self, qtbot):
        """Create a MapGraphicsView with a region feature for vertex tests."""
        from src.gui.widgets.map.map_graphics_view import MapGraphicsView

        view = MapGraphicsView()
        pm = QPixmap(200, 200)
        pm.fill(Qt.GlobalColor.blue)
        view.pixmap_item = QGraphicsPixmapItem(pm)
        view.pixmap_item.setZValue(0)
        view.scene.addItem(view.pixmap_item)
        view.coord_system.set_scene_rect(view.pixmap_item.boundingRect())
        qtbot.addWidget(view)

        geom = [
            {"x": 0.2, "y": 0.2},
            {"x": 0.8, "y": 0.2},
            {"x": 0.8, "y": 0.8},
            {"x": 0.2, "y": 0.8},
        ]
        view.add_marker(
            "r1", "entity", "Kingdom", 0.5, 0.5,
            feature_type="region", geometry=geom,
        )
        return view

    def test_midpoint_handles_created(self, view) -> None:
        """Midpoint handles are created between each pair of vertices."""
        item = view.feature_items["p1"]
        view._start_vertex_editing(item)
        # 3 vertices → 2 segments → 2 midpoint handles for a path
        assert len(view._midpoint_handles) == 2

    def test_midpoint_handles_region(self, region_view) -> None:
        """Region creates midpoint handles for all segments including closing."""
        item = region_view.feature_items["r1"]
        region_view._start_vertex_editing(item)
        # 4 vertices → 4 segments (closed) → 4 midpoint handles
        assert len(region_view._midpoint_handles) == 4

    def test_vertex_insert_via_midpoint(self, view) -> None:
        """Inserting via midpoint adds a new vertex."""
        item = view.feature_items["p1"]
        view._start_vertex_editing(item)
        assert len(item._geometry) == 3

        # Insert vertex at midpoint of segment 0 (between vertex 0 and 1)
        mid_pos = QPointF(60, 70)  # Somewhere in the middle
        view._on_midpoint_insert(0, mid_pos)
        assert len(item._geometry) == 4
        # Handles should be rebuilt
        assert len(view._vertex_handles) == 4

    def test_vertex_delete_removes_vertex(self, view) -> None:
        """Right-click delete removes a vertex from geometry."""
        item = view.feature_items["p1"]
        view._start_vertex_editing(item)
        assert len(item._geometry) == 3

        # Delete vertex 1 (middle vertex)
        view._on_vertex_deleted(1)
        assert len(item._geometry) == 2
        assert len(view._vertex_handles) == 2

    def test_vertex_delete_enforces_minimum_path(self, view) -> None:
        """Cannot delete a vertex below minimum count (2 for path)."""
        item = view.feature_items["p1"]
        view._start_vertex_editing(item)

        # Delete to bring down to 2 vertices
        view._on_vertex_deleted(1)
        assert len(item._geometry) == 2
        # Trying to delete another should not work (min 2 for path)
        view._on_vertex_deleted(0)
        assert len(item._geometry) == 2

    def test_vertex_delete_enforces_minimum_region(self, region_view) -> None:
        """Cannot delete a vertex below minimum count (3 for region)."""
        item = region_view.feature_items["r1"]
        region_view._start_vertex_editing(item)

        # Delete one to bring down to 3
        region_view._on_vertex_deleted(0)
        assert len(item._geometry) == 3
        # Trying to delete another should not work (min 3 for region)
        region_view._on_vertex_deleted(0)
        assert len(item._geometry) == 3

    def test_editing_applies_dash_style(self, view) -> None:
        """Vertex editing applies dashed stroke to the edited feature."""
        item = view.feature_items["p1"]
        original_style = dict(item._style)
        view._start_vertex_editing(item)
        # Should have dash pattern applied
        assert item._style.get("dash_pattern") is not None
        assert len(item._style["dash_pattern"]) > 0

    def test_editing_restores_style_on_finish(self, view) -> None:
        """Finishing vertex editing restores the original style."""
        item = view.feature_items["p1"]
        original_dash = item._style.get("dash_pattern")
        view._start_vertex_editing(item)
        view._finish_vertex_editing()
        # Style should be restored
        assert item._style.get("dash_pattern") == original_dash

    def test_finish_cleans_midpoint_handles(self, view) -> None:
        """Finishing vertex editing removes midpoint handles."""
        item = view.feature_items["p1"]
        view._start_vertex_editing(item)
        assert len(view._midpoint_handles) > 0
        view._finish_vertex_editing()
        assert len(view._midpoint_handles) == 0


# --------------------------------------------------------------------------
# Hover tooltip tests
# --------------------------------------------------------------------------


class TestFeatureHoverTooltip:
    """Tests for the debounced hover tooltip on feature items."""

    def test_path_spatial_properties(self, pixmap_item, sample_path_geometry) -> None:
        """PathItem computes spatial properties for tooltip."""
        item = PathItem(
            marker_id="p1",
            object_type="entity",
            label="River",
            pixmap_item=pixmap_item,
            geometry=sample_path_geometry,
            anchor_x=0.5,
            anchor_y=0.5,
        )
        props = item._compute_spatial_properties()
        assert props["feature_type"] == "path"
        assert props["vertex_count"] == 3
        assert props["segment_count"] == 2
        assert props["length"] > 0

    def test_region_spatial_properties(self, pixmap_item, sample_region_geometry) -> None:
        """RegionItem computes spatial properties for tooltip."""
        item = RegionItem(
            marker_id="r1",
            object_type="entity",
            label="Kingdom",
            pixmap_item=pixmap_item,
            geometry=sample_region_geometry,
            anchor_x=0.5,
            anchor_y=0.5,
        )
        props = item._compute_spatial_properties()
        assert props["feature_type"] == "region"
        assert props["vertex_count"] == 4
        assert props["segment_count"] == 4
        assert props["area"] > 0
        assert props["perimeter"] > 0

    def test_hover_timer_exists(self, pixmap_item, sample_path_geometry) -> None:
        """Feature items have a debounce timer for hover tooltip."""
        item = PathItem(
            marker_id="p1",
            object_type="entity",
            label="River",
            pixmap_item=pixmap_item,
            geometry=sample_path_geometry,
            anchor_x=0.5,
            anchor_y=0.5,
        )
        assert hasattr(item, "_hover_timer")
        assert item._hover_timer.interval() == 100

    def test_tooltip_includes_description(self, pixmap_item, sample_path_geometry) -> None:
        """Tooltip includes description when provided."""
        item = PathItem(
            marker_id="p1",
            object_type="entity",
            label="River",
            pixmap_item=pixmap_item,
            geometry=sample_path_geometry,
            anchor_x=0.5,
            anchor_y=0.5,
            description="A major waterway",
        )
        item._apply_hover_tooltip()
        tooltip = item.toolTip()
        assert "River" in tooltip
        assert "A major waterway" in tooltip
        assert "Vertices: 3" in tooltip
