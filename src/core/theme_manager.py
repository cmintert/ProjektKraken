"""
Theme Manager Module.

Manages loading and applying UI themes (Dark/Light) for the application.
Implements a singleton pattern to ensure consistent theming across the app.

This is the Qt-specific implementation that extends BaseThemeManager.
"""

import logging
from typing import Dict

from PySide6.QtCore import QObject, Signal
from src.core.base_theme_manager import BaseThemeManager

logger = logging.getLogger(__name__)


class ThemeManager(QObject, BaseThemeManager):
    """
    Qt-specific theme manager that extends BaseThemeManager.
    
    Manages loading and applying UI themes (Dark/Light) with Qt signal support.
    Reads 'themes.json' and applies values to a QSS template.
    Implements Singleton pattern.
    """

    _instance = None
    theme_changed = Signal(dict)  # Emits new theme data

    def __new__(cls, *args, **kwargs):
        """
        Create or return the singleton instance of ThemeManager.

        Implements the singleton pattern to ensure only one ThemeManager
        instance exists throughout the application lifecycle. This is
        critical for maintaining consistent theming across all UI components.

        Args:
            *args: Variable length argument list (unused).
            **kwargs: Arbitrary keyword arguments (unused).

        Returns:
            ThemeManager: The singleton instance.
        """
        if not cls._instance:
            cls._instance = object.__new__(cls)
            # Initialize QObject only once
            QObject.__init__(cls._instance)
        return cls._instance

    def __init__(self, theme_file: str = "themes.json"):
        """
        Initializes the ThemeManager.
        
        Args:
            theme_file: Path to the themes JSON file.
        """
        if hasattr(self, "_initialized"):
            return

        # Initialize BaseThemeManager (will set _initialized)
        BaseThemeManager.__init__(self, theme_file)

        # Restore saved theme preference from Qt settings
        from PySide6.QtCore import QSettings

        settings = QSettings("ProjektKraken", "ThemeSettings")
        saved_theme = settings.value("current_theme", "dark_mode")
        if saved_theme in self.themes:
            self.current_theme_name = saved_theme

    def _notify_theme_changed(self, theme_data: Dict):
        """
        Override to emit Qt signal in addition to calling callbacks.
        
        Args:
            theme_data: The new theme data dictionary.
        """
        # Call base class method for callbacks
        super()._notify_theme_changed(theme_data)
        
        # Emit Qt signal
        self.theme_changed.emit(theme_data)

    def set_theme(self, theme_name: str, app=None):
        """
        Switches the current theme and updates the application.

        Args:
            theme_name: The key of the theme to switch to.
            app: The QApplication instance to apply the stylesheet to (optional).
        """
        if theme_name not in self.themes:
            logger.warning(f"Theme '{theme_name}' not found.")
            return

        self.current_theme_name = theme_name
        theme_data = self.get_theme()

        # Apply to app if provided (re-applies stylesheet)
        if not app:
            from PySide6.QtWidgets import QApplication

            app = QApplication.instance()

        if app and self._qss_template:
            self.apply_theme(app, self._qss_template)

        # Notify callbacks and emit signal
        self._notify_theme_changed(theme_data)

        # Persist selection
        from PySide6.QtCore import QSettings

        settings = QSettings("ProjektKraken", "ThemeSettings")
        settings.setValue("current_theme", theme_name)

        logger.info(f"Theme switched to: {theme_name}")

    def apply_theme(self, app, qss_template: str = None):
        """
        Formats the QSS template with current theme values
        and applies it to the QApplication.
        
        Args:
            app: QApplication instance.
            qss_template: Optional QSS template string.
        """
        if qss_template:
            self._qss_template = qss_template

        if not self._qss_template:
            return

        stylesheet = self.format_stylesheet()
        if stylesheet:
            app.setStyleSheet(stylesheet)

