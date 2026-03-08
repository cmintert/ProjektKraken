from unittest.mock import patch

from PySide6.QtGui import QIcon

from src.core.theme_manager import ThemeManager
from src.gui.widgets.compact_date_widget import CompactDateWidget


def test_calendar_icon_loaded(qtbot):
    """Test that the calendar button has an icon loaded."""
    # Mock load_icon to return a dummy icon
    with patch("src.gui.widgets.compact_date_widget.load_icon") as mock_load:
        mock_load.return_value = QIcon()

        # Ensure theme manager is initialized

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

        # Trigger theme change - include all required keys
        tm.theme_changed.emit(
            {
                "text_main": "#FF0000",
                "destructive": "#ff4444",
                "app_bg": "#000000",
                "surface": "#000000",
                "border": "#333333",
                "text_dim": "#888888",
            }
        )

        # Verify load_icon was called
        assert mock_load.called

        # Check arguments
        args, kwargs = mock_load.call_args
        assert "calendar.svg" in args[0]
        assert kwargs.get("color") == "#FF0000"
