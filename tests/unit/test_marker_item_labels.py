import pytest
from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsSimpleTextItem

from src.gui.widgets.map.marker_item import MarkerItem


@pytest.fixture
def mock_pixmap_item(qtbot):
    """Returns a mock QGraphicsPixmapItem."""
    from PySide6.QtWidgets import QGraphicsPixmapItem

    return QGraphicsPixmapItem()


def test_marker_item_label_structure(qapp, mock_pixmap_item):
    """Test that MarkerItem creates a label background and text item correctly."""
    marker = MarkerItem(
        marker_id="m1",
        object_type="entity",
        label="Test Entity",
        pixmap_item=mock_pixmap_item,
    )

    # Check for Label Background (The Pill)
    assert hasattr(marker, "_label_bg")
    assert isinstance(marker._label_bg, QGraphicsRectItem)
    assert marker._label_bg.parentItem() == marker

    # Check for Label Text
    assert hasattr(marker, "_label_text")
    assert isinstance(marker._label_text, QGraphicsSimpleTextItem)

    # Text should be child of Background for grouping
    assert marker._label_text.parentItem() == marker._label_bg
    assert marker._label_text.text() == "Test Entity"


def test_marker_item_label_styling(mock_pixmap_item):
    """Test that the label has high-contrast styling."""
    marker = MarkerItem(
        marker_id="m1",
        object_type="entity",
        label="Test Entity",
        pixmap_item=mock_pixmap_item,
    )

    # Check Background Style
    bg_brush = marker._label_bg.brush()
    # Should be semi-transparent black
    assert bg_brush.color().alpha() < 255
    assert bg_brush.color().red() == 0

    # Check Text Style
    text_brush = marker._label_text.brush()
    # Should be white
    assert text_brush.color().name() == "#ffffff"


def test_marker_item_temporal_opacity(mock_pixmap_item):
    """Test that label opacity fades for future events."""
    marker = MarkerItem(
        marker_id="m1",
        object_type="event",
        label="Future Event",
        pixmap_item=mock_pixmap_item,
    )

    # Default State (Present/Past)
    assert marker.opacity() == 1.0
    assert marker._label_bg.opacity() == 1.0

    # Future State
    marker.set_temporal_state(is_future=True)

    # Marker itself fades
    assert marker.opacity() < 1.0

    # Label background should also fade (opacity is multiplicative if child,
    # but we set it explicitly to ensure visibility control)
    assert marker._label_bg.opacity() == 0.7

    # Back to Present
    marker.set_temporal_state(is_future=False)
    # Reset
    assert marker._label_bg.opacity() == 1.0


def test_marker_item_theme_update(mock_pixmap_item):
    """Test that label styling updates with theme."""
    marker = MarkerItem(
        marker_id="m1",
        object_type="entity",
        label="Test Entity",
        pixmap_item=mock_pixmap_item,
    )

    # Mock Theme Data
    theme_data = {"surface": "#FF0000", "text_main": "#00FF00"}  # Red  # Green

    marker.update_theme(theme_data)

    # Check Background
    bg_color = marker._label_bg.brush().color()
    assert bg_color.red() == 255  # Should match surface
    assert bg_color.alpha() == 200  # Should have forced opacity

    # Check Text
    text_color = marker._label_text.brush().color()
    assert text_color.name() == "#00ff00"  # Should match text_main


def test_marker_item_label_anchoring(mock_pixmap_item):
    """Test setting label anchors (Top, Bottom, Left, Right)."""
    marker = MarkerItem(
        marker_id="m1",
        object_type="entity",
        label="Anchor Test",
        pixmap_item=mock_pixmap_item,
    )

    # 1. Default (Bottom)
    # Check that Y is positive (below marker)
    assert marker._label_bg.y() > 0
    assert marker._label_bg.x() == -marker._label_bg.rect().width() / 2

    # 2. Top
    marker.set_label_anchor("top")
    # Y should be negative (above marker)
    # y = -bg_height - padding
    assert marker._label_bg.y() < 0
    # X should still be centered
    assert marker._label_bg.x() == -marker._label_bg.rect().width() / 2

    # 3. Right
    marker.set_label_anchor("right")
    # X should be positive (right of marker)
    # It must be at least marker radius to the right
    assert marker._label_bg.x() > 0
    # Y should be centered vertically (approx 0 or slightly adjusted for text visual center)
    # In center alignment, y should be roughly -height/2 to center on 0
    scene_center_y = marker._label_bg.y() + marker._label_bg.rect().height() / 2
    assert abs(scene_center_y) < 5  # close to 0

    # 4. Left
    marker.set_label_anchor("left")
    # X should be negative and further left than width
    assert marker._label_bg.x() < 0
    # Specifically, x should be -width - padding
    assert marker._label_bg.x() <= -marker._label_bg.rect().width()
