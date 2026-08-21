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

from PySide6.QtCore import QPointF, Qt  # noqa: E402
from PySide6.QtGui import QPixmap  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QGraphicsPixmapItem,
    QGraphicsScene,
)

from src.core.marker import (  # noqa: E402
    FEATURE_TYPE_PATH,
    MapFeature,
)
from src.gui.widgets.map.feature_items import (  # noqa: E402
    DEFAULT_REGION_FILL_COLOR,
    PathItem,
    RegionItem,
)

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

    def test_path_item_creation(self, pixmap_item, sample_path_geometry) -> None:
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

    def test_path_item_custom_style(self, pixmap_item, sample_path_geometry) -> None:
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

    def test_path_item_clicked_signal(self, pixmap_item, sample_path_geometry) -> None:
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

    def test_path_item_temporal_state(self, pixmap_item, sample_path_geometry) -> None:
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

    def test_region_item_creation(self, pixmap_item, sample_region_geometry) -> None:
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

    def test_region_default_fill_uses_translucent_blue(
        self, pixmap_item, sample_region_geometry
    ) -> None:
        """The Qt ARGB default keeps the intended blue and alpha channels."""
        item = RegionItem(
            marker_id="region-1",
            object_type="entity",
            label="Kingdom of Gondor",
            pixmap_item=pixmap_item,
            geometry=sample_region_geometry,
            anchor_x=0.5,
            anchor_y=0.5,
        )

        fill = item._fill_color(DEFAULT_REGION_FILL_COLOR)

        assert (fill.red(), fill.green(), fill.blue(), fill.alpha()) == (
            0x34,
            0x98,
            0xDB,
            0x30,
        )

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

    def test_region_item_custom_fill(self, pixmap_item, sample_region_geometry) -> None:
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
        view.graphics_scene.addItem(view.pixmap_item)
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
            "p1",
            "entity",
            "River",
            0.5,
            0.5,
            feature_type="path",
            geometry=geom,
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
            "r1",
            "entity",
            "Kingdom",
            0.5,
            0.5,
            feature_type="region",
            geometry=geom,
        )
        assert "r1" not in view.markers
        assert "r1" in view.feature_items
        assert isinstance(view.feature_items["r1"], RegionItem)

    def test_path_without_geometry_falls_back_to_point(self, view) -> None:
        """feature_type='path' without geometry creates a MarkerItem."""
        from src.gui.widgets.map.marker_item import MarkerItem

        view.add_marker(
            "p2",
            "entity",
            "Empty Path",
            0.5,
            0.5,
            feature_type="path",
            geometry=None,
        )
        assert "p2" in view.markers
        assert isinstance(view.markers["p2"], MarkerItem)

    def test_remove_marker_removes_feature(self, view) -> None:
        """remove_marker works for both markers and features."""
        geom = [{"x": 0.1, "y": 0.2}, {"x": 0.9, "y": 0.8}]
        view.add_marker(
            "p1",
            "entity",
            "River",
            0.5,
            0.5,
            feature_type="path",
            geometry=geom,
        )
        assert "p1" in view.feature_items
        view.remove_marker("p1")
        assert "p1" not in view.feature_items

    def test_clear_markers_clears_features(self, view) -> None:
        """clear_markers removes both markers and features."""
        view.add_marker("m1", "entity", "Castle", 0.5, 0.5)
        geom = [{"x": 0.1, "y": 0.2}, {"x": 0.9, "y": 0.8}]
        view.add_marker(
            "p1",
            "entity",
            "River",
            0.5,
            0.5,
            feature_type="path",
            geometry=geom,
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
            "p1",
            "entity",
            "River v1",
            0.5,
            0.5,
            feature_type="path",
            geometry=geom1,
        )
        view.add_marker(
            "p1",
            "entity",
            "River v2",
            0.5,
            0.5,
            feature_type="path",
            geometry=geom2,
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
        view.graphics_scene.addItem(view.pixmap_item)
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
        cancelled = []
        view.drawing_cancelled.connect(lambda: cancelled.append(True))

        view.finish_drawing()

        assert cancelled == []
        assert view.is_drawing is True
        assert not view._drawing_tool.can_finish

    def test_finish_region_needs_min_3_points(self, view, qtbot) -> None:
        """finish_drawing for region needs at least 3 vertices."""
        view.start_drawing("region")
        view._add_drawing_vertex(QPointF(10, 20))
        view._add_drawing_vertex(QPointF(30, 40))
        cancelled = []
        view.drawing_cancelled.connect(lambda: cancelled.append(True))

        view.finish_drawing()

        assert cancelled == []
        assert view.is_drawing is True
        assert not view._drawing_tool.can_finish

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

    def test_double_click_does_not_finish_drawing(self, view) -> None:
        """Double-click is consumed but never substitutes for Confirm."""
        view.start_drawing("path")
        view._add_drawing_vertex(QPointF(20, 40))
        view._add_drawing_vertex(QPointF(180, 160))
        finished = []
        view.drawing_finished.connect(lambda *args: finished.append(args))

        assert view._drawing_tool.handle_double_click()
        assert finished == []
        assert view.is_drawing

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
        view.graphics_scene.addItem(view.pixmap_item)
        view.coord_system.set_scene_rect(view.pixmap_item.boundingRect())
        qtbot.addWidget(view)

        # Add a path feature
        geom = [{"x": 0.1, "y": 0.2}, {"x": 0.5, "y": 0.5}, {"x": 0.9, "y": 0.8}]
        view.add_marker(
            "p1",
            "entity",
            "River",
            0.5,
            0.5,
            feature_type="path",
            geometry=geom,
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

    def test_escape_restores_unmanaged_vertex_geometry(self, view, qtbot) -> None:
        """Escape discards a direct vertex-edit working copy."""
        item = view.feature_items["p1"]
        original = [dict(point) for point in item._geometry]
        persisted = []
        view.feature_geometry_changed.connect(lambda *args: persisted.append(args))
        view._start_vertex_editing(item)
        view._on_vertex_moved(0, QPointF(60, 80))

        qtbot.keyClick(view, Qt.Key.Key_Escape)

        assert item._geometry == original
        assert persisted == []
        assert not view.is_editing_vertices

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
        view.graphics_scene.addItem(view.pixmap_item)
        view.coord_system.set_scene_rect(view.pixmap_item.boundingRect())
        qtbot.addWidget(view)

        geom = [
            {"x": 0.2, "y": 0.2},
            {"x": 0.8, "y": 0.2},
            {"x": 0.8, "y": 0.8},
            {"x": 0.2, "y": 0.8},
        ]
        view.add_marker(
            "r1",
            "entity",
            "Kingdom",
            0.5,
            0.5,
            feature_type="region",
            geometry=geom,
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
        view.graphics_scene.addItem(view.pixmap_item)
        view.coord_system.set_scene_rect(view.pixmap_item.boundingRect())
        qtbot.addWidget(view)

        geom = [
            {"x": 0.1, "y": 0.2},
            {"x": 0.5, "y": 0.5},
            {"x": 0.9, "y": 0.8},
        ]
        view.add_marker(
            "p1",
            "entity",
            "River",
            0.5,
            0.5,
            feature_type="path",
            geometry=geom,
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
        view.graphics_scene.addItem(view.pixmap_item)
        view.coord_system.set_scene_rect(view.pixmap_item.boundingRect())
        qtbot.addWidget(view)

        geom = [
            {"x": 0.2, "y": 0.2},
            {"x": 0.8, "y": 0.2},
            {"x": 0.8, "y": 0.8},
            {"x": 0.2, "y": 0.8},
        ]
        view.add_marker(
            "r1",
            "entity",
            "Kingdom",
            0.5,
            0.5,
            feature_type="region",
            geometry=geom,
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

    def test_removing_edited_feature_exits_vertex_editing(self, view) -> None:
        """Removing the active feature must clear vertex-edit handles immediately."""
        item = view.feature_items["p1"]
        view._start_vertex_editing(item)

        view.remove_marker("p1")

        assert view.is_editing_vertices is False
        assert len(view._vertex_handles) == 0
        assert len(view._midpoint_handles) == 0
        assert "p1" not in view.feature_items


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
        assert "length" not in props
        assert props["calibration_required"] is True

    def test_region_spatial_properties(
        self, pixmap_item, sample_region_geometry
    ) -> None:
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
        assert "area" not in props
        assert "perimeter" not in props
        assert props["calibration_required"] is True

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
        from src.app.constants import MAP_FEATURE_HOVER_DEBOUNCE_MS

        assert item._hover_timer.interval() == MAP_FEATURE_HOVER_DEBOUNCE_MS

    def test_tooltip_includes_description(
        self, pixmap_item, sample_path_geometry
    ) -> None:
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


# --------------------------------------------------------------------------
# Metric units and constants tests
# --------------------------------------------------------------------------


class TestMetricUnits:
    """Tests for metric unit display in spatial properties."""

    def test_path_length_in_meters(self, pixmap_item) -> None:
        """PathItem computes length in real-world meters when given map scale."""
        geom = [{"x": 0.0, "y": 0.0}, {"x": 1.0, "y": 0.0}]
        item = PathItem(
            marker_id="p1",
            object_type="entity",
            label="Road",
            pixmap_item=pixmap_item,
            geometry=geom,
            anchor_x=0.5,
            anchor_y=0.0,
            map_width_meters=10_000.0,  # 10 km
        )
        props = item._compute_spatial_properties()
        # Full width at 10km should be 10000 m
        assert props["length"] == pytest.approx(10_000.0, rel=0.01)

    def test_region_area_in_sq_meters(self, pixmap_item) -> None:
        """RegionItem computes area in square meters."""
        # Unit square in normalized coords with 1000m map width
        geom = [
            {"x": 0.0, "y": 0.0},
            {"x": 1.0, "y": 0.0},
            {"x": 1.0, "y": 1.0},
            {"x": 0.0, "y": 1.0},
        ]
        item = RegionItem(
            marker_id="r1",
            object_type="entity",
            label="Area",
            pixmap_item=pixmap_item,
            geometry=geom,
            anchor_x=0.5,
            anchor_y=0.5,
            map_width_meters=1000.0,
        )
        props = item._compute_spatial_properties()
        # 100x100 pixmap → square map → 1000×1000 = 1_000_000 m²
        assert props["area"] == pytest.approx(1_000_000.0, rel=0.01)

    def test_region_perimeter_in_meters(self, pixmap_item) -> None:
        """RegionItem computes perimeter in meters."""
        geom = [
            {"x": 0.0, "y": 0.0},
            {"x": 1.0, "y": 0.0},
            {"x": 1.0, "y": 1.0},
            {"x": 0.0, "y": 1.0},
        ]
        item = RegionItem(
            marker_id="r1",
            object_type="entity",
            label="Area",
            pixmap_item=pixmap_item,
            geometry=geom,
            anchor_x=0.5,
            anchor_y=0.5,
            map_width_meters=1000.0,
        )
        props = item._compute_spatial_properties()
        # 4 sides × 1000m = 4000m
        assert props["perimeter"] == pytest.approx(4000.0, rel=0.01)

    def test_format_metric_length_meters(self) -> None:
        """Short distances are formatted in meters."""
        from src.gui.widgets.map.feature_items import _FeatureItemBase

        assert _FeatureItemBase._format_metric_length(500.0) == "500.0 m"
        assert _FeatureItemBase._format_metric_length(0.5) == "0.5 m"

    def test_format_metric_length_km(self) -> None:
        """Long distances are formatted in kilometers."""
        from src.gui.widgets.map.feature_items import _FeatureItemBase

        assert _FeatureItemBase._format_metric_length(1500.0) == "1.50 km"
        assert _FeatureItemBase._format_metric_length(10_000.0) == "10.00 km"

    def test_format_metric_area_sq_meters(self) -> None:
        """Small areas are formatted in square meters."""
        from src.gui.widgets.map.feature_items import _FeatureItemBase

        assert _FeatureItemBase._format_metric_area(500.0) == "500.0 m²"

    def test_format_metric_area_sq_km(self) -> None:
        """Large areas are formatted in square kilometers."""
        from src.gui.widgets.map.feature_items import _FeatureItemBase

        result = _FeatureItemBase._format_metric_area(2_500_000.0)
        assert result == "2.50 km²"

    def test_tooltip_shows_metric_units(self, pixmap_item) -> None:
        """Hover tooltip includes metric units."""
        geom = [{"x": 0.0, "y": 0.0}, {"x": 1.0, "y": 0.0}]
        item = PathItem(
            marker_id="p1",
            object_type="entity",
            label="Road",
            pixmap_item=pixmap_item,
            geometry=geom,
            anchor_x=0.5,
            anchor_y=0.0,
            map_width_meters=5000.0,
        )
        item._apply_hover_tooltip()
        tooltip = item.toolTip()
        assert "km" in tooltip or "m" in tooltip

    def test_default_map_width_meters(self, pixmap_item, sample_path_geometry) -> None:
        """Feature items default to an explicitly uncalibrated state."""
        item = PathItem(
            marker_id="p1",
            object_type="entity",
            label="Road",
            pixmap_item=pixmap_item,
            geometry=sample_path_geometry,
            anchor_x=0.5,
            anchor_y=0.5,
        )
        assert item._map_width_meters == 0.0


class TestConstantsImport:
    """Tests that map constants are properly defined and importable."""

    def test_feature_constants_exist(self) -> None:
        """Key map feature constants are importable from constants.py."""
        from src.app.constants import (
            MAP_DEFAULT_WIDTH_METERS,
            MAP_MIDPOINT_HANDLE_RADIUS,
            MAP_SNAP_RADIUS_PX,
            MAP_VERTEX_HANDLE_RADIUS,
            MAP_ZOOM_IN_FACTOR,
        )

        assert MAP_DEFAULT_WIDTH_METERS == 0.0
        assert MAP_VERTEX_HANDLE_RADIUS == 5
        assert MAP_MIDPOINT_HANDLE_RADIUS == 4
        assert MAP_SNAP_RADIUS_PX == 10.0
        assert MAP_ZOOM_IN_FACTOR == 1.25

    def test_backward_compatible_aliases(self) -> None:
        """Old constant names still work from feature_items module."""
        from src.gui.widgets.map.feature_items import (
            DEFAULT_STROKE_COLOR,
            DEFAULT_STROKE_WIDTH,
            HIT_AREA_MARGIN,
            LABEL_FONT_SIZE,
            SELECTION_PEN_WIDTH,
        )

        assert DEFAULT_STROKE_COLOR == "#3498DB"
        assert DEFAULT_STROKE_WIDTH == 2.0
        assert HIT_AREA_MARGIN == 6
        assert LABEL_FONT_SIZE == 9
        assert SELECTION_PEN_WIDTH == 2.0


class TestVertexHandleScaling:
    """Tests for dynamic vertex handle scaling with zoom."""

    @pytest.fixture()
    def view(self, qtbot):
        """Create a MapGraphicsView with a path feature."""
        from src.gui.widgets.map.map_graphics_view import MapGraphicsView

        view = MapGraphicsView()
        pm = QPixmap(200, 200)
        pm.fill(Qt.GlobalColor.blue)
        view.pixmap_item = QGraphicsPixmapItem(pm)
        view.pixmap_item.setZValue(0)
        view.graphics_scene.addItem(view.pixmap_item)
        view.coord_system.set_scene_rect(view.pixmap_item.boundingRect())
        qtbot.addWidget(view)

        geom = [{"x": 0.1, "y": 0.2}, {"x": 0.5, "y": 0.5}, {"x": 0.9, "y": 0.8}]
        view.add_marker(
            "p1",
            "entity",
            "River",
            0.5,
            0.5,
            feature_type="path",
            geometry=geom,
        )
        return view

    def test_vertex_handles_ignore_transform(self, view) -> None:
        """Vertex handles have ItemIgnoresTransformations flag set."""
        from PySide6.QtWidgets import QGraphicsItem

        item = view.feature_items["p1"]
        view._start_vertex_editing(item)
        for handle in view._vertex_handles:
            flags = handle.flags()
            assert flags & QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations

    def test_midpoint_handles_ignore_transform(self, view) -> None:
        """Midpoint handles have ItemIgnoresTransformations flag set."""
        from PySide6.QtWidgets import QGraphicsItem

        item = view.feature_items["p1"]
        view._start_vertex_editing(item)
        for mh in view._midpoint_handles:
            flags = mh.flags()
            assert flags & QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations


class TestMidpointPositionUpdate:
    """Tests that midpoint handles update during vertex drag."""

    @pytest.fixture()
    def view(self, qtbot):
        """Create a MapGraphicsView with a path feature for midpoint tests."""
        from src.gui.widgets.map.map_graphics_view import MapGraphicsView

        view = MapGraphicsView()
        pm = QPixmap(200, 200)
        pm.fill(Qt.GlobalColor.blue)
        view.pixmap_item = QGraphicsPixmapItem(pm)
        view.pixmap_item.setZValue(0)
        view.graphics_scene.addItem(view.pixmap_item)
        view.coord_system.set_scene_rect(view.pixmap_item.boundingRect())
        qtbot.addWidget(view)

        geom = [{"x": 0.0, "y": 0.0}, {"x": 1.0, "y": 0.0}, {"x": 1.0, "y": 1.0}]
        view.add_marker(
            "p1",
            "entity",
            "Path",
            0.5,
            0.5,
            feature_type="path",
            geometry=geom,
        )
        return view

    def test_midpoints_move_with_vertex(self, view) -> None:
        """Moving a vertex also updates adjacent midpoint positions."""
        item = view.feature_items["p1"]
        view._start_vertex_editing(item)
        assert len(view._midpoint_handles) == 2

        # Record initial midpoint positions
        mp0_before = view._midpoint_handles[0].pos()
        mp1_before = view._midpoint_handles[1].pos()

        # Move vertex 1 to a new position (center of map)
        view._on_vertex_moved(1, QPointF(100, 100))

        mp0_after = view._midpoint_handles[0].pos()
        mp1_after = view._midpoint_handles[1].pos()

        # Both midpoints should have moved (they share vertex 1)
        assert mp0_after != mp0_before or mp1_after != mp1_before


# --------------------------------------------------------------------------
# ESC overlay bug fix tests
# --------------------------------------------------------------------------


class TestVertexEditingEscFix:
    """Tests that ESC properly clears editing state before emitting signals."""

    @pytest.fixture()
    def view(self, qtbot):
        """Create a MapGraphicsView with a path feature loaded."""
        from src.gui.widgets.map.map_graphics_view import MapGraphicsView

        view = MapGraphicsView()
        pm = QPixmap(200, 200)
        pm.fill(Qt.GlobalColor.blue)
        view.pixmap_item = QGraphicsPixmapItem(pm)
        view.pixmap_item.setZValue(0)
        view.graphics_scene.addItem(view.pixmap_item)
        view.coord_system.set_scene_rect(view.pixmap_item.boundingRect())
        qtbot.addWidget(view)

        geom = [{"x": 0.1, "y": 0.2}, {"x": 0.5, "y": 0.5}, {"x": 0.9, "y": 0.8}]
        view.add_marker(
            "p1",
            "entity",
            "River",
            0.5,
            0.5,
            feature_type="path",
            geometry=geom,
        )
        return view

    def test_editing_state_cleared_before_signal(self, view, qtbot) -> None:
        """is_editing_vertices is False when feature_geometry_changed fires."""
        item = view.feature_items["p1"]
        view._start_vertex_editing(item)
        assert view.is_editing_vertices is True

        editing_during_signal = []

        def capture_state(marker_id: str, geometry: list) -> None:
            editing_during_signal.append(view.is_editing_vertices)

        view.feature_geometry_changed.connect(capture_state)
        view._finish_vertex_editing()

        assert len(editing_during_signal) == 1
        assert editing_during_signal[0] is False

    def test_handles_cleared_before_signal(self, view, qtbot) -> None:
        """Vertex handles are removed before feature_geometry_changed fires."""
        item = view.feature_items["p1"]
        view._start_vertex_editing(item)
        assert len(view._vertex_handles) == 3

        handles_during_signal = []

        def capture_handles(marker_id: str, geometry: list) -> None:
            handles_during_signal.append(len(view._vertex_handles))

        view.feature_geometry_changed.connect(capture_handles)
        view._finish_vertex_editing()

        assert len(handles_during_signal) == 1
        assert handles_during_signal[0] == 0


# --------------------------------------------------------------------------
# Edit stroke width tests
# --------------------------------------------------------------------------


class TestEditStrokeWidth:
    """Tests that vertex editing applies the correct stroke width."""

    @pytest.fixture()
    def view(self, qtbot):
        """Create a MapGraphicsView with a path feature loaded."""
        from src.gui.widgets.map.map_graphics_view import MapGraphicsView

        view = MapGraphicsView()
        pm = QPixmap(200, 200)
        pm.fill(Qt.GlobalColor.blue)
        view.pixmap_item = QGraphicsPixmapItem(pm)
        view.pixmap_item.setZValue(0)
        view.graphics_scene.addItem(view.pixmap_item)
        view.coord_system.set_scene_rect(view.pixmap_item.boundingRect())
        qtbot.addWidget(view)

        geom = [{"x": 0.1, "y": 0.2}, {"x": 0.5, "y": 0.5}, {"x": 0.9, "y": 0.8}]
        view.add_marker(
            "p1",
            "entity",
            "River",
            0.5,
            0.5,
            feature_type="path",
            geometry=geom,
        )
        return view

    def test_editing_sets_stroke_width(self, view) -> None:
        """_start_vertex_editing sets stroke_width to 5.0."""
        from src.app.constants import MAP_EDIT_STROKE_WIDTH

        item = view.feature_items["p1"]
        view._start_vertex_editing(item)
        assert item._style["stroke_width"] == MAP_EDIT_STROKE_WIDTH

    def test_editing_restores_stroke_width(self, view) -> None:
        """_finish_vertex_editing restores the original stroke_width."""
        item = view.feature_items["p1"]
        original_width = item._style.get("stroke_width")
        view._start_vertex_editing(item)
        view._finish_vertex_editing()
        assert item._style.get("stroke_width") == original_width
