"""Integration tests for MapGraphicsView + MapLayerModel.

Tests that the view correctly responds to layer model signals for
visibility, opacity, and Z-order changes.
"""

import pytest
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QGraphicsPixmapItem

from src.app.constants import (
    MAP_LAYER_TYPE_GROUP,
    MAP_LAYER_TYPE_MARKER,
)
from src.core.map import MapLayerNode
from src.gui.widgets.map.map_graphics_view import MapGraphicsView
from src.gui.widgets.map.map_layer_model import MapLayerModel


def _setup_view_with_marker(qtbot):
    """Create a view with a pixmap and a single marker, and a layer model.

    Returns:
        Tuple of (view, model, marker_id).
    """
    view = MapGraphicsView()
    qtbot.addWidget(view)

    # Create test pixmap
    test_image = QImage(100, 100, QImage.Format.Format_RGB32)
    test_image.fill(Qt.GlobalColor.white)
    pixmap = QPixmap.fromImage(test_image)

    view.pixmap_item = QGraphicsPixmapItem(pixmap)
    view.scene.addItem(view.pixmap_item)
    view.coord_system.set_scene_rect(QRectF(0, 0, 100, 100))

    # Add a marker
    marker_id = "test-marker-1"
    view.add_marker(
        marker_id=marker_id,
        object_type="entity",
        label="Test Marker",
        x=0.5,
        y=0.5,
    )

    # Build a simple layer tree that includes this marker
    marker_layer = MapLayerNode(
        name="Test Marker",
        layer_type=MAP_LAYER_TYPE_MARKER,
        id=marker_id,
    )
    group = MapLayerNode(
        name="Markers Group",
        layer_type=MAP_LAYER_TYPE_GROUP,
        id="markers-group",
        children=[marker_layer],
    )
    root = MapLayerNode(
        name="Root",
        layer_type=MAP_LAYER_TYPE_GROUP,
        id="root",
        children=[group],
    )

    model = MapLayerModel(root=root)
    view.set_layer_model(model)

    return view, model, marker_id


class TestViewLayerVisibility:
    """Test that the view responds to visibility signals."""

    def test_hiding_layer_hides_marker(self, qtbot) -> None:
        """When the layer model hides a marker's node, the graphics
        item becomes invisible."""
        view, model, mid = _setup_view_with_marker(qtbot)

        marker_item = view.markers[mid]
        assert marker_item.isVisible() is True

        node = model.find_node_by_id(mid)
        assert node is not None
        model.set_node_visible(node, False)

        assert marker_item.isVisible() is False

    def test_showing_layer_shows_marker(self, qtbot) -> None:
        """Re-showing the layer restores marker visibility."""
        view, model, mid = _setup_view_with_marker(qtbot)
        marker_item = view.markers[mid]

        node = model.find_node_by_id(mid)
        assert node is not None

        model.set_node_visible(node, False)
        assert marker_item.isVisible() is False

        model.set_node_visible(node, True)
        assert marker_item.isVisible() is True

    def test_hiding_parent_group_hides_marker(self, qtbot) -> None:
        """Hiding the parent group also hides the child marker."""
        view, model, mid = _setup_view_with_marker(qtbot)
        marker_item = view.markers[mid]

        group = model.find_node_by_id("markers-group")
        assert group is not None
        model.set_node_visible(group, False)

        assert marker_item.isVisible() is False


class TestViewLayerOpacity:
    """Test that the view responds to opacity signals."""

    def test_opacity_change_applied(self, qtbot) -> None:
        """When layer opacity changes, the marker's opacity is updated."""
        view, model, mid = _setup_view_with_marker(qtbot)
        marker_item = view.markers[mid]

        node = model.find_node_by_id(mid)
        assert node is not None
        model.set_node_opacity(node, 0.5)

        assert marker_item.opacity() == pytest.approx(0.5)

    def test_group_opacity_propagates(self, qtbot) -> None:
        """Group opacity multiplied with child opacity."""
        view, model, mid = _setup_view_with_marker(qtbot)
        marker_item = view.markers[mid]

        group = model.find_node_by_id("markers-group")
        assert group is not None
        model.set_node_opacity(group, 0.5)

        # Marker's effective opacity = 0.5 (group) × 1.0 (marker) = 0.5
        assert marker_item.opacity() == pytest.approx(0.5)


class TestViewLayerZOrder:
    """Test that Z-order changes are applied to graphics items."""

    def test_z_order_applied(self, qtbot) -> None:
        """After layer_order_changed, marker Z-values are updated."""
        view, model, mid = _setup_view_with_marker(qtbot)

        # Trigger z-order computation
        model.layer_order_changed.emit()

        z_map = model.compute_z_order()
        marker_item = view.markers[mid]
        assert marker_item.zValue() == pytest.approx(z_map[mid])


class TestViewLayerModelAttachment:
    """Test layer model attachment/detachment."""

    def test_layer_model_initially_none(self, qtbot) -> None:
        """View starts without a layer model."""
        view = MapGraphicsView()
        qtbot.addWidget(view)
        assert view.layer_model is None

    def test_set_layer_model(self, qtbot) -> None:
        """Attaching a model stores the reference."""
        view, model, _ = _setup_view_with_marker(qtbot)
        assert view.layer_model is model
