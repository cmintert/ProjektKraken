import pytest
from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsSimpleTextItem

from src.gui.widgets.map.marker_item import MarkerItem


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

    # Check that _label_item was created
    assert hasattr(marker, "_label_item")
    assert isinstance(marker._label_item, QGraphicsSimpleTextItem)

    # Check text content
    assert marker._label_item.text() == "Test Entity"

    # Check parenting
    assert marker._label_item.parentItem() == marker


def test_marker_item_label_styling(mock_pixmap_item):
    """Test that the label has correct styling."""
    marker = MarkerItem(
        marker_id="m1",
        object_type="entity",
        label="Test Entity",
        pixmap_item=mock_pixmap_item,
    )

    label_item = marker._label_item

    # Check color (dark grey)
    brush = label_item.brush()
    assert brush.color().name() == "#333333"

    # Check font
    font = label_item.font()
    assert font.family() == "Segoe UI"
    assert font.bold() is True
    assert font.pointSize() == 8


def test_marker_item_label_positioning(mock_pixmap_item):
    """Test that the label is positioned below the marker."""
    marker = MarkerItem(
        marker_id="m1",
        object_type="entity",
        label="Test Entity",
        pixmap_item=mock_pixmap_item,
    )

    label_item = marker._label_item
    pos = label_item.pos()

    # Y should be positive (below 0)
    # MARKER_SIZE is 24. Half is 12. + 2 padding = 14.
    assert pos.y() == 14.0

    # X should be negative (centered)
    assert pos.x() < 0
