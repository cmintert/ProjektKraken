from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QDialog, QWidget

from src.gui.utils.window_utils import (
    DWMWA_CAPTION_COLOR,
    DWMWA_USE_IMMERSIVE_DARK_MODE,
    ModalWindowThemeFilter,
    apply_windows_title_bar_style,
)


@pytest.fixture
def mock_window():
    window = MagicMock(spec=QWidget)
    window.winId.return_value = 12345
    return window


def test_apply_style_calls_dwm(mock_window):
    """Test that DwmSetWindowAttribute is called with correct arguments."""
    with patch("src.gui.utils.window_utils.ctypes") as mock_ctypes:
        # Setup mock dwmapi
        mock_dwmapi = MagicMock()
        mock_ctypes.WinDLL.return_value = mock_dwmapi
        # Set return value to 0 (S_OK)
        mock_dwmapi.DwmSetWindowAttribute.return_value = 0

        # Test Dark Mode
        apply_windows_title_bar_style(mock_window, dark_mode=True)

        # Verify Dark Mode call
        # args: hwnd, attr, byref(value), sizeof(value)
        assert mock_dwmapi.DwmSetWindowAttribute.call_count >= 1
        call_args = mock_dwmapi.DwmSetWindowAttribute.call_args_list[0]
        assert call_args[0][0] == 12345
        assert call_args[0][1] == DWMWA_USE_IMMERSIVE_DARK_MODE


def test_apply_style_fallback(mock_window):
    """Test fallback to legacy attribute if primary fails."""
    with patch("src.gui.utils.window_utils.ctypes") as mock_ctypes:
        mock_dwmapi = MagicMock()
        mock_ctypes.WinDLL.return_value = mock_dwmapi

        # Fail first call (return 1), succeed second (return 0)
        mock_dwmapi.DwmSetWindowAttribute.side_effect = [1, 0, 0, 0]

        apply_windows_title_bar_style(mock_window, dark_mode=True)

        # Should have called it at least twice (primary + legacy)
        assert mock_dwmapi.DwmSetWindowAttribute.call_count >= 2

        # Second call should be legacy attribute 19
        call_args = mock_dwmapi.DwmSetWindowAttribute.call_args_list[1]
        assert call_args[0][1] == 19


def test_apply_style_color(mock_window):
    """Test setting caption color."""
    with patch("src.gui.utils.window_utils.ctypes") as mock_ctypes:
        mock_dwmapi = MagicMock()
        mock_ctypes.WinDLL.return_value = mock_dwmapi
        mock_dwmapi.DwmSetWindowAttribute.return_value = 0

        color = QColor(255, 0, 0)
        apply_windows_title_bar_style(mock_window, title_color=color)

        # Check for CAPTION_COLOR call
        calls = mock_dwmapi.DwmSetWindowAttribute.call_args_list
        caption_calls = [c for c in calls if c[0][1] == DWMWA_CAPTION_COLOR]
        assert len(caption_calls) == 1


def test_apply_style_graceful_failure(mock_window):
    """Test that it doesn't crash if ctypes fails (e.g. non-Windows)."""
    with patch("src.gui.utils.window_utils.ctypes") as mock_ctypes:
        mock_ctypes.WinDLL.side_effect = Exception("Not Windows")

        # Should not raise exception
        apply_windows_title_bar_style(mock_window)


def test_modal_theme_filter_styles_dialog_when_shown(qapp, qtbot):
    """A newly shown modal receives the current native title-bar colors."""
    theme_manager = MagicMock()
    theme_manager.get_theme.return_value = {
        "app_bg": "#202020",
        "text_main": "#f0f0f0",
    }
    theme_filter = ModalWindowThemeFilter(qapp, theme_manager)
    qapp.installEventFilter(theme_filter)
    dialog = QDialog()
    qtbot.addWidget(dialog)

    try:
        with patch(
            "src.gui.utils.window_utils.apply_windows_title_bar_style"
        ) as apply_style:
            dialog.show()
            qapp.processEvents()

        matching_calls = [
            call for call in apply_style.call_args_list if call.args[0] is dialog
        ]
        assert matching_calls
        assert matching_calls[-1].kwargs["dark_mode"] is True
        assert matching_calls[-1].kwargs["title_color"].name() == "#202020"
        assert matching_calls[-1].kwargs["text_color"].name() == "#f0f0f0"
    finally:
        qapp.removeEventFilter(theme_filter)


def test_modal_theme_filter_refreshes_open_dialogs(qapp, qtbot):
    """An active theme change restyles dialogs that are already open."""
    theme_manager = MagicMock()
    theme_filter = ModalWindowThemeFilter(qapp, theme_manager)
    dialog = QDialog()
    qtbot.addWidget(dialog)
    dialog.show()

    try:
        with patch(
            "src.gui.utils.window_utils.apply_windows_title_bar_style"
        ) as apply_style:
            theme_filter.refresh_open_dialogs(
                {"app_bg": "#fafafa", "text_main": "#101010"}
            )

        matching_calls = [
            call for call in apply_style.call_args_list if call.args[0] is dialog
        ]
        assert matching_calls
        assert matching_calls[-1].kwargs["dark_mode"] is False
        assert matching_calls[-1].kwargs["title_color"].name() == "#fafafa"
        assert matching_calls[-1].kwargs["text_color"].name() == "#101010"
    finally:
        qapp.removeEventFilter(theme_filter)
