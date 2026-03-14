"""Unit tests for the SnappingManager.

Tests geometry math (point-to-segment distance), vertex snapping,
edge snapping, priority ordering, and enable/disable toggling.
"""

import math
import os

import pytest

# Skip all Qt tests if display is not available
pytestmark = pytest.mark.skipif(
    not os.environ.get("DISPLAY") and os.environ.get("QT_QPA_PLATFORM") != "offscreen",
    reason="No display available for Qt tests",
)

from PySide6.QtCore import QPointF, Qt  # noqa: E402
from PySide6.QtGui import QPixmap, QTransform  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QGraphicsPixmapItem,
    QGraphicsScene,
)

from src.gui.widgets.map.snapping_manager import (  # noqa: E402
    SnappingManager,
    SnapResult,
    SnapType,
    point_to_segment_distance,
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
def scene_with_path():
    """Create a QGraphicsScene with a PathItem for snap testing.

    Returns (scene, path_item, pixmap_item).
    """
    from src.gui.widgets.map.feature_items import PathItem

    scene = QGraphicsScene()
    pm = QPixmap(100, 100)
    pm.fill(Qt.GlobalColor.white)
    pixmap_item = QGraphicsPixmapItem(pm)
    scene.addItem(pixmap_item)

    # Create a path from (10,10) to (90,10) to (90,90) in scene coords
    # which is (0.1,0.1) to (0.9,0.1) to (0.9,0.9) normalised
    geometry = [
        {"x": 0.1, "y": 0.1},
        {"x": 0.9, "y": 0.1},
        {"x": 0.9, "y": 0.9},
    ]
    path_item = PathItem(
        marker_id="test-path",
        object_type="entity",
        label="Test Path",
        pixmap_item=pixmap_item,
        geometry=geometry,
        anchor_x=0.5,
        anchor_y=0.5,
    )
    scene.addItem(path_item)
    return scene, path_item, pixmap_item


@pytest.fixture()
def scene_with_region():
    """Create a QGraphicsScene with a RegionItem for snap testing.

    Returns (scene, region_item, pixmap_item).
    """
    from src.gui.widgets.map.feature_items import RegionItem

    scene = QGraphicsScene()
    pm = QPixmap(100, 100)
    pm.fill(Qt.GlobalColor.white)
    pixmap_item = QGraphicsPixmapItem(pm)
    scene.addItem(pixmap_item)

    geometry = [
        {"x": 0.2, "y": 0.2},
        {"x": 0.8, "y": 0.2},
        {"x": 0.8, "y": 0.8},
        {"x": 0.2, "y": 0.8},
    ]
    region_item = RegionItem(
        marker_id="test-region",
        object_type="entity",
        label="Test Region",
        pixmap_item=pixmap_item,
        geometry=geometry,
        anchor_x=0.5,
        anchor_y=0.5,
    )
    scene.addItem(region_item)
    return scene, region_item, pixmap_item


# --------------------------------------------------------------------------
# Point-to-Segment Distance Tests
# --------------------------------------------------------------------------


class TestPointToSegmentDistance:
    """Tests for the point_to_segment_distance utility function."""

    def test_point_on_segment_start(self) -> None:
        """Point at the start of the segment has distance 0."""
        a = QPointF(0, 0)
        b = QPointF(10, 0)
        p = QPointF(0, 0)
        dist, closest = point_to_segment_distance(p, a, b)
        assert dist == pytest.approx(0.0, abs=1e-9)
        assert closest.x() == pytest.approx(0.0, abs=1e-6)

    def test_point_on_segment_end(self) -> None:
        """Point at the end of the segment has distance 0."""
        a = QPointF(0, 0)
        b = QPointF(10, 0)
        p = QPointF(10, 0)
        dist, closest = point_to_segment_distance(p, a, b)
        assert dist == pytest.approx(0.0, abs=1e-9)

    def test_point_perpendicular_to_segment(self) -> None:
        """Point perpendicular to a horizontal segment snaps to projection."""
        a = QPointF(0, 0)
        b = QPointF(10, 0)
        p = QPointF(5, 3)
        dist, closest = point_to_segment_distance(p, a, b)
        assert dist == pytest.approx(3.0, abs=1e-6)
        assert closest.x() == pytest.approx(5.0, abs=1e-6)
        assert closest.y() == pytest.approx(0.0, abs=1e-6)

    def test_point_beyond_start_clamps(self) -> None:
        """Point before segment start clamps to start."""
        a = QPointF(0, 0)
        b = QPointF(10, 0)
        p = QPointF(-5, 3)
        dist, closest = point_to_segment_distance(p, a, b)
        assert closest.x() == pytest.approx(0.0, abs=1e-6)
        assert closest.y() == pytest.approx(0.0, abs=1e-6)
        expected_dist = math.sqrt(25 + 9)
        assert dist == pytest.approx(expected_dist, abs=1e-6)

    def test_point_beyond_end_clamps(self) -> None:
        """Point past segment end clamps to end."""
        a = QPointF(0, 0)
        b = QPointF(10, 0)
        p = QPointF(15, 4)
        dist, closest = point_to_segment_distance(p, a, b)
        assert closest.x() == pytest.approx(10.0, abs=1e-6)
        assert closest.y() == pytest.approx(0.0, abs=1e-6)

    def test_degenerate_segment(self) -> None:
        """Degenerate segment (A == B) returns distance to that point."""
        a = QPointF(5, 5)
        b = QPointF(5, 5)
        p = QPointF(8, 9)
        dist, closest = point_to_segment_distance(p, a, b)
        # Distance = sqrt((8-5)² + (9-5)²) = sqrt(9+16) = 5.0
        assert dist == pytest.approx(math.sqrt(3 * 3 + 4 * 4), abs=1e-6)
        assert closest.x() == pytest.approx(5.0, abs=1e-6)
        assert closest.y() == pytest.approx(5.0, abs=1e-6)

    def test_diagonal_segment(self) -> None:
        """Point distance to a diagonal segment is correct."""
        a = QPointF(0, 0)
        b = QPointF(10, 10)
        p = QPointF(0, 10)
        dist, closest = point_to_segment_distance(p, a, b)
        # Closest point on the diagonal from (0,0) to (10,10) to (0,10) is (5,5)
        assert closest.x() == pytest.approx(5.0, abs=1e-6)
        assert closest.y() == pytest.approx(5.0, abs=1e-6)
        expected_dist = math.sqrt(50)
        assert dist == pytest.approx(expected_dist, abs=1e-6)


# --------------------------------------------------------------------------
# SnapResult Tests
# --------------------------------------------------------------------------


class TestSnapResult:
    """Tests for the SnapResult dataclass."""

    def test_default_snap_result(self) -> None:
        """Default SnapResult is not snapped."""
        result = SnapResult()
        assert result.snapped is False
        assert result.snap_type == SnapType.NONE
        assert result.distance == float("inf")

    def test_vertex_snap_result(self) -> None:
        """Vertex snap result has correct type."""
        result = SnapResult(
            snapped=True,
            pos=QPointF(1, 2),
            snap_type=SnapType.VERTEX,
            distance=3.0,
        )
        assert result.snapped is True
        assert result.snap_type == SnapType.VERTEX
        assert result.distance == 3.0


# --------------------------------------------------------------------------
# SnappingManager Tests
# --------------------------------------------------------------------------


class TestSnappingManager:
    """Tests for the SnappingManager class."""

    def test_disabled_snapping_returns_original(self, scene_with_path) -> None:
        """When disabled, snap_point returns the original position."""
        scene, path_item, _ = scene_with_path
        manager = SnappingManager(scene)
        manager.enabled = False
        query = QPointF(10, 10)  # Exactly on a vertex
        result = manager.snap_point(query, QTransform())
        assert result.snapped is False
        assert result.pos.x() == pytest.approx(10.0, abs=1e-6)
        assert result.pos.y() == pytest.approx(10.0, abs=1e-6)

    def test_snap_to_vertex(self, scene_with_path) -> None:
        """Snaps to a nearby vertex within radius."""
        scene, path_item, _ = scene_with_path
        manager = SnappingManager(scene, snap_radius_px=15.0)
        # Query near vertex at (10, 10) — within 15px
        query = QPointF(12, 12)
        result = manager.snap_point(query, QTransform())
        assert result.snapped is True
        assert result.snap_type == SnapType.VERTEX
        assert result.pos.x() == pytest.approx(10.0, abs=1e-6)
        assert result.pos.y() == pytest.approx(10.0, abs=1e-6)

    def test_snap_to_edge(self, scene_with_path) -> None:
        """Snaps to a nearby edge when no vertex is in range."""
        scene, path_item, _ = scene_with_path
        manager = SnappingManager(scene, snap_radius_px=15.0)
        # The path has a horizontal segment from (10,10) to (90,10).
        # Query at (50, 14) — 4px from the edge, no vertex nearby.
        query = QPointF(50, 14)
        result = manager.snap_point(query, QTransform())
        assert result.snapped is True
        assert result.snap_type == SnapType.EDGE
        # Should snap to (50, 10) — projection onto the horizontal edge
        assert result.pos.x() == pytest.approx(50.0, abs=1e-6)
        assert result.pos.y() == pytest.approx(10.0, abs=1e-6)

    def test_vertex_priority_over_edge(self, scene_with_path) -> None:
        """Vertex snap takes priority over edge snap."""
        scene, path_item, _ = scene_with_path
        manager = SnappingManager(scene, snap_radius_px=15.0)
        # Query very near vertex (10, 10) — should snap vertex, not edge
        query = QPointF(11, 11)
        result = manager.snap_point(query, QTransform())
        assert result.snapped is True
        assert result.snap_type == SnapType.VERTEX

    def test_no_snap_outside_radius(self, scene_with_path) -> None:
        """Returns unsnapped result when nothing is within radius."""
        scene, path_item, _ = scene_with_path
        manager = SnappingManager(scene, snap_radius_px=5.0)
        # Query far from any feature
        query = QPointF(50, 50)
        result = manager.snap_point(query, QTransform())
        assert result.snapped is False

    def test_exclude_items(self, scene_with_path) -> None:
        """Excluded items are not considered for snapping."""
        scene, path_item, _ = scene_with_path
        manager = SnappingManager(scene, snap_radius_px=15.0)
        query = QPointF(12, 12)
        result = manager.snap_point(query, QTransform(), exclude_items={path_item})
        assert result.snapped is False

    def test_region_closing_edge(self, scene_with_region) -> None:
        """Region items include the closing edge for snapping."""
        scene, region_item, _ = scene_with_region
        manager = SnappingManager(scene, snap_radius_px=10.0)
        # The closing edge goes from (20,80) to (20,20).
        # Query near the closing edge midpoint at (18, 50) → should snap to (20, 50)
        query = QPointF(18, 50)
        result = manager.snap_point(query, QTransform())
        assert result.snapped is True
        assert result.pos.x() == pytest.approx(20.0, abs=1e-6)
        assert result.pos.y() == pytest.approx(50.0, abs=1e-6)

    def test_enable_disable_toggle(self) -> None:
        """Manager can be enabled and disabled."""
        scene = QGraphicsScene()
        manager = SnappingManager(scene)
        assert manager.enabled is True
        manager.enabled = False
        assert manager.enabled is False
        manager.enabled = True
        assert manager.enabled is True

    def test_snap_radius_setter(self) -> None:
        """Snap radius can be updated and is clamped to minimum 1."""
        scene = QGraphicsScene()
        manager = SnappingManager(scene, snap_radius_px=10.0)
        assert manager.snap_radius_px == 10.0
        manager.snap_radius_px = 20.0
        assert manager.snap_radius_px == 20.0
        manager.snap_radius_px = -5.0
        assert manager.snap_radius_px == 1.0

    def test_zoom_scales_radius(self, scene_with_path) -> None:
        """View zoom affects the snap radius in scene units."""
        scene, path_item, _ = scene_with_path
        manager = SnappingManager(scene, snap_radius_px=5.0)
        # At identity transform, radius = 5 scene units.
        # Point at (12, 12) is ~2.8 px from vertex (10, 10) - within 5.
        query = QPointF(12, 12)
        result_1x = manager.snap_point(query, QTransform())
        assert result_1x.snapped is True

        # At 0.25x zoom (4x zoomed out), 5px = 20 scene units → still snaps
        zoom_out = QTransform()
        zoom_out.scale(0.25, 0.25)
        result_zoom_out = manager.snap_point(query, zoom_out)
        assert result_zoom_out.snapped is True

        # At 10x zoom, 5px = 0.5 scene units → too far
        zoom_in = QTransform()
        zoom_in.scale(10.0, 10.0)
        result_zoom_in = manager.snap_point(query, zoom_in)
        assert result_zoom_in.snapped is False


# --------------------------------------------------------------------------
# Integration with MapGraphicsView
# --------------------------------------------------------------------------


class TestSnapIndicator:
    """Tests for snap indicator in MapGraphicsView."""

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

    def test_snap_indicator_show_hide(self, view) -> None:
        """Snap indicator can be shown and hidden."""
        view._show_snap_indicator(QPointF(50, 50), SnapType.VERTEX)
        assert view._snap_indicator is not None
        view._hide_snap_indicator()
        assert view._snap_indicator is None

    def test_snap_indicator_vertex_color(self, view) -> None:
        """Vertex snap indicator uses yellow."""
        from src.app.constants import MAP_SNAP_INDICATOR_VERTEX_COLOR

        view._show_snap_indicator(QPointF(50, 50), SnapType.VERTEX)
        assert view._snap_indicator is not None
        brush_color = view._snap_indicator.brush().color().name()
        assert brush_color == MAP_SNAP_INDICATOR_VERTEX_COLOR.lower()

    def test_snap_indicator_edge_color(self, view) -> None:
        """Edge snap indicator uses blue."""
        from src.app.constants import MAP_SNAP_INDICATOR_EDGE_COLOR

        view._show_snap_indicator(QPointF(50, 50), SnapType.EDGE)
        assert view._snap_indicator is not None
        brush_color = view._snap_indicator.brush().color().name()
        assert brush_color == MAP_SNAP_INDICATOR_EDGE_COLOR.lower()

    def test_snapping_toggle(self, view) -> None:
        """Snapping can be toggled on and off."""
        assert view.snapping_enabled is True
        view.snapping_enabled = False
        assert view.snapping_enabled is False
        view.snapping_enabled = True
        assert view.snapping_enabled is True

    def test_snap_indicator_cleaned_on_finish_editing(self, view) -> None:
        """Snap indicator is removed when vertex editing finishes."""
        # Add a feature to edit
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
        item = view.feature_items["p1"]
        view._start_vertex_editing(item)
        # Manually show a snap indicator
        view._show_snap_indicator(QPointF(50, 50), SnapType.VERTEX)
        assert view._snap_indicator is not None
        # Finish editing should clean it up
        view._finish_vertex_editing()
        assert view._snap_indicator is None

    def test_snap_indicator_cleaned_on_cancel_drawing(self, view) -> None:
        """Snap indicator is removed when drawing is cancelled."""
        view.start_drawing("path")
        view._show_snap_indicator(QPointF(50, 50), SnapType.EDGE)
        assert view._snap_indicator is not None
        view.cancel_drawing()
        assert view._snap_indicator is None
