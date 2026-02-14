from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QWidget
from src.gui.widgets.toast_notification import ToastNotification


@pytest.fixture
def mock_theme_manager():
    with patch("src.core.theme_manager.ThemeManager") as mock:
        mock_instance = mock.return_value
        mock_instance.get_theme.return_value = {
            "surface": "#323232",
            "text_main": "#E0E0E0",
            "error": "#E74C3C",
            "primary": "#FF9900",
            "border": "#454545",
            "font_size_body": "10pt",
        }
        yield mock_instance


def test_toast_initialization(qtbot, mock_theme_manager):
    """Test standard initialization."""
    toast = ToastNotification("Test Message")
    qtbot.addWidget(toast)

    assert toast.message_label.text() == "Test Message"
    assert toast.undo_button is None
    assert toast._variant == "success"


def test_show_centered_with_parent(qtbot, mock_theme_manager):
    """Test centering logic with a parent."""
    # Create a parent widget
    parent = QWidget()
    parent.resize(800, 600)
    # parent.show()  # Must be shown to have geometry?

    # Mock geometry to be consistent across environments
    parent.setGeometry(100, 100, 800, 600)
    qtbot.addWidget(parent)

    toast = ToastNotification("Center Me", parent=parent)
    # Toast width is fixed at 280

    # Calculate Expected
    # Parent Center in Screen Coords (if parent is top level)
    # parent.geometry() -> (100, 100, 800, 600)
    # Center -> (500, 400)
    # Toast Width 280 -> Half 140
    # Expected X: 500 - 140 = 360
    # Toast Height depends, let's assume ~50 (from content)
    # We will check calculating relative to actual toast height

    with patch.object(ToastNotification, "show_at_bottom_right") as mock_fallback:
        toast.show_centered()
        mock_fallback.assert_not_called()

    # Check position
    pos = toast.pos()
    expected_x = 500 - (toast.width() // 2)
    expected_y = 400 - (toast.height() // 2)

    # Allow small tolerance
    assert abs(pos.x() - expected_x) < 2
    assert abs(pos.y() - expected_y) < 2


def test_show_centered_no_parent(qtbot, mock_theme_manager):
    """Test fallback when no parent."""
    toast = ToastNotification("Orphan Toast")
    qtbot.addWidget(toast)

    with patch.object(ToastNotification, "show_at_bottom_right") as mock_fallback:
        toast.show_centered()
        mock_fallback.assert_called_once()


def test_theming_variants(qtbot, mock_theme_manager):
    """Test that setting styles updates the variant and stylesheet."""
    toast = ToastNotification("Themed Toast")
    qtbot.addWidget(toast)

    # Default Success
    assert toast._variant == "success"
    assert "#4CAF50" in toast.styleSheet()  # Default green

    # Error
    toast.set_error_style()
    assert toast._variant == "error"
    # Should use theme error color #E74C3C
    assert "#E74C3C" in toast.styleSheet()
    assert "⚠" in toast.icon_label.text()

    # Warning
    toast.set_warning_style()
    assert toast._variant == "warning"
    # Should use theme primary or warning color
    # In mock, primary is #FF9900
    assert "#FF9900" in toast.styleSheet()
    assert "!" in toast.icon_label.text()
