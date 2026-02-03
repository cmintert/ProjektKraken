from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget

from src.gui.utils.window_utils import (
    DWMWA_CAPTION_COLOR,
    DWMWA_USE_IMMERSIVE_DARK_MODE,
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
        mock_ctypes.windll.dwmapi = mock_dwmapi
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
        mock_ctypes.windll.dwmapi = mock_dwmapi

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
        mock_ctypes.windll.dwmapi = mock_dwmapi
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
        mock_ctypes.windll.dwmapi.DwmSetWindowAttribute.side_effect = Exception(
            "Not Windows"
        )

        # Should not raise exception
        apply_windows_title_bar_style(mock_window)
