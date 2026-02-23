import pytest
from PySide6.QtWidgets import QGraphicsPixmapItem

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
