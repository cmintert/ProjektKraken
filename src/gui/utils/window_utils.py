import ctypes
import logging
from ctypes import byref, c_int, sizeof
from typing import Optional

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget

# DWM Constants
DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_CAPTION_COLOR = 35
DWMWA_TEXT_COLOR = 36

logger = logging.getLogger(__name__)


def apply_windows_title_bar_style(
    window: QWidget,
    dark_mode: bool = True,
    title_color: Optional[QColor] = None,
    text_color: Optional[QColor] = None,
) -> None:
    """Applies Windows 11 DWM styles to the window title bar.

    Args:
        window: The QWidget (usually MainWindow) to style.
        dark_mode: Whether to use immersive dark mode (affects window borders/menus).
        title_color: Custom background color for the title bar (Windows 11+).
        text_color: Custom text color for the title bar (Windows 11+).
    """
    try:
        from ctypes import HRESULT
    except ImportError:
        HRESULT = c_int

    try:
        hwnd = int(window.winId())
        dwm = ctypes.windll.dwmapi
        # Define argtypes/restype for proper 64-bit handling and HRESULT checking
        dwm.DwmSetWindowAttribute.restype = HRESULT
        dwm.DwmSetWindowAttribute.argtypes = [
            c_int,
            c_int,
            ctypes.POINTER(c_int),
            c_int,
        ]

        # 1. Immersive Dark Mode
        # Try Attribute 20 (Windows 11 / Windows 10 20H1+)
        value = c_int(1 if dark_mode else 0)
        result = dwm.DwmSetWindowAttribute(
            hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, byref(value), sizeof(value)
        )

        if result != 0:
            logger.debug(
                f"DWMWA_USE_IMMERSIVE_DARK_MODE (20) failed with HRESULT {result}. Trying legacy attribute 19."
            )
            # Failed, try legacy Attribute 19 (Windows 10 1809 - 1909)
            DWMWA_USE_IMMERSIVE_DARK_MODE_BEFORE_20H1 = 19
            result = dwm.DwmSetWindowAttribute(
                hwnd,
                DWMWA_USE_IMMERSIVE_DARK_MODE_BEFORE_20H1,
                byref(value),
                sizeof(value),
            )
            if result != 0:
                logger.warning(f"Failed to set Immersive Dark Mode. HRESULT: {result}")

        # 2. Caption Color (Windows 11 Build 22000+)
        if title_color and title_color.isValid():
            # COLORREF is 0x00BBGGRR
            r, g, b = title_color.red(), title_color.green(), title_color.blue()
            colorref = r | (g << 8) | (b << 16)
            value = c_int(colorref)
            dwm.DwmSetWindowAttribute(
                hwnd, DWMWA_CAPTION_COLOR, byref(value), sizeof(value)
            )

        # 3. Text Color (Windows 11 Build 22000+)
        if text_color and text_color.isValid():
            r, g, b = text_color.red(), text_color.green(), text_color.blue()
            colorref = r | (g << 8) | (b << 16)
            value = c_int(colorref)
            dwm.DwmSetWindowAttribute(
                hwnd, DWMWA_TEXT_COLOR, byref(value), sizeof(value)
            )

    except Exception as e:
        logger.warning(f"DWM styling failed: {e}")
