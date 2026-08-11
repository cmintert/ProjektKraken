import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QGraphicsPixmapItem

from src.gui.widgets.map.feature_items import PathItem
from src.gui.widgets.map.label_manager import LabelManager
from src.gui.widgets.map.map_label_item import MapLabelItem
from src.gui.widgets.map.marker_item import MarkerItem, MarkerLabelItem


@pytest.fixture
def mock_pixmap_item():
    item = QGraphicsPixmapItem()
    return item


def test_marker_item_label_creation(qapp, mock_pixmap_item):
    """Test that MarkerItem creates a label item correctly."""
    marker = MarkerItem(
        marker_id="m1",
        object_type="entity",
        label="Test Entity",
        pixmap_item=mock_pixmap_item,
    )

    # Check that _label_item was created as MarkerLabelItem
    assert hasattr(marker, "_label_item")
    assert isinstance(marker._label_item, MarkerLabelItem)

    # Check parenting
    assert marker._label_item.parentItem() == marker


def test_marker_item_label_hidden_by_default(mock_pixmap_item):
    """Test that labels are hidden until a layout pass runs."""
    marker = MarkerItem(
        marker_id="m1",
        object_type="entity",
        label="Test Entity",
        pixmap_item=mock_pixmap_item,
    )

    assert marker._label_item.isVisible() is False


def test_marker_item_apply_label_position(mock_pixmap_item):
    """Test that apply_label_position sets position and visibility."""
    marker = MarkerItem(
        marker_id="m1",
        object_type="entity",
        label="Test Entity",
        pixmap_item=mock_pixmap_item,
    )

    marker.apply_label_position(10.0, 20.0, True)
    assert marker._label_item.pos().x() == 10.0
    assert marker._label_item.pos().y() == 20.0
    assert marker._label_item.isVisible() is True

    marker.apply_label_position(0.0, 0.0, False)
    assert marker._label_item.isVisible() is False


def test_marker_item_connection_count_default(mock_pixmap_item):
    """Test that connection_count defaults to 0."""
    marker = MarkerItem(
        marker_id="m1",
        object_type="entity",
        label="Test Entity",
        pixmap_item=mock_pixmap_item,
    )

    assert marker.connection_count == 0


def test_geometry_labels_share_themed_pill_and_avoid_each_other(qapp):
    """Path labels use the shared pill and deterministic collision layout."""
    image = QImage(100, 100, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.white)
    pixmap_item = QGraphicsPixmapItem(QPixmap.fromImage(image))
    geometry = [{"x": 0.4, "y": 0.5}, {"x": 0.6, "y": 0.5}]
    first = PathItem("p1", "entity", "First", pixmap_item, geometry, 0.5, 0.5)
    second = PathItem("p2", "entity", "Second", pixmap_item, geometry, 0.5, 0.5)

    manager = LabelManager()
    manager.run_layout_pass([first, second], 1.0)

    assert isinstance(first._label_item, MapLabelItem)
    assert isinstance(second._label_item, MapLabelItem)
    assert first._label_item.isVisible()
    assert second._label_item.isVisible()
    first_label, second_label = manager._occupied_rects[-2:]
    assert not first_label.intersects(second_label)
