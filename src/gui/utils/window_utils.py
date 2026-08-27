"""Window Utilities Module.

Provides platform-specific window styling utilities, particularly for Windows title bars.
"""

from __future__ import annotations

import ctypes
import logging
import sys
from ctypes import byref, c_int, sizeof
from typing import TYPE_CHECKING, Any, Optional

from PySide6.QtCore import QEvent, QObject, Slot
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QDialog, QWidget

if TYPE_CHECKING:
    from src.core.theme_manager import ThemeManager

# DWM Constants
DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_CAPTION_COLOR = 35
DWMWA_TEXT_COLOR = 36

logger = logging.getLogger(__name__)

_COLOR_LIGHTNESS_MIDPOINT = 128


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
    if sys.platform != "win32":
        return

    try:
        hwnd = int(window.winId())
        dwm: Any = ctypes.WinDLL("dwmapi")
        # Define argtypes/restype for proper 64-bit handling and HRESULT checking
        dwm.DwmSetWindowAttribute.restype = c_int
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


class ModalWindowThemeFilter(QObject):
    """Apply the active theme to native modal-window chrome."""

    def __init__(
        self,
        app: QApplication,
        theme_manager: ThemeManager,
    ) -> None:
        """Watch dialogs and refresh their title bars when the theme changes."""
        super().__init__(app)
        self._app = app
        self._theme_manager = theme_manager
        self._theme_manager.theme_changed.connect(self.refresh_open_dialogs)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Theme a dialog after Qt creates its native window handle."""
        if (
            event.type() == QEvent.Type.Show
            and isinstance(watched, QDialog)
            and watched.isWindow()
        ):
            self._apply_dialog_theme(watched, self._theme_manager.get_theme())
        return super().eventFilter(watched, event)

    @Slot(dict)
    def refresh_open_dialogs(self, theme_data: dict[str, Any]) -> None:
        """Reapply native chrome colors to every open top-level dialog."""
        for widget in self._app.topLevelWidgets():
            if isinstance(widget, QDialog):
                self._apply_dialog_theme(widget, theme_data)

    @staticmethod
    def _apply_dialog_theme(
        dialog: QDialog,
        theme_data: dict[str, Any],
    ) -> None:
        """Apply one theme snapshot to a dialog's native title bar."""
        background = QColor(str(theme_data.get("app_bg", "#2B2B2B")))
        foreground = QColor(str(theme_data.get("text_main", "#E0E0E0")))
        apply_windows_title_bar_style(
            dialog,
            dark_mode=background.lightness() < _COLOR_LIGHTNESS_MIDPOINT,
            title_color=background,
            text_color=foreground,
        )


def install_modal_window_theme_filter(
    app: QApplication,
    theme_manager: ThemeManager,
) -> ModalWindowThemeFilter:
    """Install and return the application-wide modal title-bar handler."""
    theme_filter = ModalWindowThemeFilter(app, theme_manager)
    app.installEventFilter(theme_filter)
    return theme_filter
