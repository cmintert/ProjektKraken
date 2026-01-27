import pytest
from PySide6.QtGui import QIcon
from unittest.mock import patch
from src.gui.widgets.compact_date_widget import CompactDateWidget
from src.core.theme_manager import ThemeManager


def test_calendar_icon_loaded(qtbot):
    """Test that the calendar button has an icon loaded."""
    # Mock load_icon to return a dummy icon
    with patch("src.gui.widgets.compact_date_widget.load_icon") as mock_load:
        mock_load.return_value = QIcon()

        # Ensure theme manager is initialized
        tm = ThemeManager()

        widget = CompactDateWidget()
        qtbot.addWidget(widget)

        # Check if load_icon was called
        assert mock_load.called
        args, kwargs = mock_load.call_args
        assert "calendar.svg" in args[0]

        # Check if text is empty (we removed the unicode char)
        assert widget.btn_calendar.text() == "", "Calendar button text should be empty"


def test_icon_updates_on_theme_change(qtbot):
    """Test that the icon is updated (reloaded) when theme changes."""
    # Ensure theme manager is initialized
    tm = ThemeManager()

    with patch("src.gui.widgets.compact_date_widget.load_icon") as mock_load:
        mock_load.return_value = QIcon()

        widget = CompactDateWidget()
        qtbot.addWidget(widget)

        # Reset mock after init
        mock_load.reset_mock()

        # Trigger theme change
        tm.theme_changed.emit({"text_main": "#FF0000"})

        # Verify load_icon was called
        assert mock_load.called

        # Check arguments
        args, kwargs = mock_load.call_args
        assert "calendar.svg" in args[0]
        assert kwargs.get("color") == "#FF0000"
