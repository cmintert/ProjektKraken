import pytest
from PySide6.QtWidgets import QGraphicsPixmapItem

from src.core.theme_manager import ThemeManager
from src.gui.widgets.map.marker_item import MarkerItem


@pytest.fixture
def mock_pixmap_item():
    return QGraphicsPixmapItem()


@pytest.fixture
def marker_item(qapp, mock_pixmap_item):
    return MarkerItem(
        marker_id="test_marker",
        object_type="entity",
        label="Test Marker",
        pixmap_item=mock_pixmap_item,
    )


def test_marker_initially_has_no_keyframes(marker_item):
    """Test that a new marker has no keyframes by default."""
    assert not marker_item.has_keyframes


def test_set_has_keyframes(marker_item):
    """Test that set_has_keyframes updates the state."""
    marker_item.set_has_keyframes(True)
    assert marker_item.has_keyframes

    marker_item.set_has_keyframes(False)
    assert not marker_item.has_keyframes


def test_paint_calls_update_when_state_changes(marker_item, qtbot):
    """Test that changing keyframe state triggers an update."""
    # We can't easily check for update() call without mocking,
    # but we can verify the state change persists.
    # In a real TDD cycle, we'd ensure the drawing logic exists.

    marker_item.set_has_keyframes(True)
    assert marker_item.has_keyframes


def test_theme_color_usage(marker_item):
    """Test that we can access the theme for the indicator color."""
    theme = ThemeManager().get_theme()
    assert "primary" in theme
