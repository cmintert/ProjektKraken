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
        all_paths = [call.args[0] for call in mock_load.call_args_list]
        assert any("calendar.svg" in p for p in all_paths), (
            f"calendar.svg not found in icon paths: {all_paths}"
        )

        # Check if text is empty (we removed the unicode char)
        assert widget.btn_calendar.text() == "", "Calendar button text should be empty"


def test_icon_updates_on_theme_change(qtbot):
    """Test that the icon is refreshed after a theme-related update."""
    theme_manager = ThemeManager()

    with patch("src.gui.widgets.compact_date_widget.load_icon") as mock_load:
        mock_load.return_value = QIcon()

        widget = CompactDateWidget()
        qtbot.addWidget(widget)

        # Reset mock after init so later calls represent the refresh action.
        mock_load.reset_mock()

        theme = theme_manager.get_theme()
        theme_manager.theme_changed.emit(theme)

        # Verify a reload happened.
        assert mock_load.called

        all_calls = mock_load.call_args_list
        all_paths = [call.args[0] for call in all_calls]
        assert any("calendar.svg" in p for p in all_paths), (
            f"calendar.svg not found in icon paths: {all_paths}"
        )
        cal_call = next((c for c in all_calls if "calendar.svg" in c.args[0]), None)
        assert cal_call is not None, f"calendar.svg call missing from: {all_calls}"
        expected_color = theme.get("accent_secondary", theme.get("text_main", "#e0e0e0"))
        assert cal_call.kwargs["color"] == expected_color
