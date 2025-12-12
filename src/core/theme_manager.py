"""
Theme Manager Module.

Manages loading and applying UI themes (Dark/Light) for the application.
Implements a singleton pattern to ensure consistent theming across the app.
"""

import json
import logging
import os
from typing import Dict

logger = logging.getLogger(__name__)


from PySide6.QtCore import QObject, Signal


class ThemeManager(QObject):
    """
    Manages loading and applying UI themes (Dark/Light).
    Reads 'themes.json' and applies values to a QSS template.
    Implements Singleton pattern.
    """

    _instance = None
    theme_changed = Signal(dict)  # Emits new theme data

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(ThemeManager, cls).__new__(cls)
            # Initialize QObject only once
            super(ThemeManager, cls._instance).__init__()
        return cls._instance

    def __init__(self, theme_file: str = "themes.json"):
        """
        Initializes the ThemeManager.
        """
        if hasattr(self, "_initialized"):
            return

        self.theme_file = theme_file
        self.themes: Dict[str, Dict[str, str]] = {}
        self.current_theme_name: str = "dark_mode"
        self._qss_template: str = ""

        self._load_themes()
        self._initialized = True

    def _load_themes(self):
        """Loads the JSON theme definition."""
        if not os.path.exists(self.theme_file):
            # Fallback hardcoded if missing
            self.themes = {
                "dark_mode": {
                    "app_bg": "#2B2B2B",
                    "surface": "#323232",
                    "border": "#454545",
                    "primary": "#FF9900",
                    "accent_secondary": "#4DA6FF",
                    "text_main": "#E0E0E0",
                    "text_dim": "#9E9E9E",
                    "error": "#CF6679",
                    "font_size_h1": "18pt",
                    "font_size_h2": "16pt",
                    "font_size_h3": "14pt",
                    "font_size_body": "10pt",
                },
                "light_mode": {
                    "app_bg": "#F5F5F5",
                    "surface": "#FFFFFF",
                    "border": "#E0E0E0",
                    "primary": "#E68A00",
                    "accent_secondary": "#005A9E",
                    "text_main": "#212121",
                    "text_dim": "#757575",
                    "error": "#B00020",
                    "font_size_h1": "18pt",
                    "font_size_h2": "16pt",
                    "font_size_h3": "14pt",
                    "font_size_body": "10pt",
                },
            }
            return

        try:
            with open(self.theme_file, "r") as f:
                self.themes = json.load(f)
        except Exception as e:
            logger.error(f"Error loading themes: {e}")

    def load_stylesheet(self, path: str):
        """Loads and caches the QSS template."""
        try:
            with open(path, "r") as f:
                self._qss_template = f.read()
        except FileNotFoundError:
            logger.error(f"Style template not found: {path}")

    def get_available_themes(self) -> list[str]:
        """Returns a list of available theme names."""
        return list(self.themes.keys())

    def get_theme(self) -> Dict[str, str]:
        """Returns the current theme dictionary."""
        return self.themes.get(
            self.current_theme_name, self.themes.get("dark_mode", {})
        )

    def set_theme(self, theme_name: str, app=None):
        """
        Switches the current theme and updates the application.

        Args:
            theme_name (str): The key of the theme to switch to.
            app (QApplication, optional): The app instance to apply the stylesheet to.
        """
        if theme_name not in self.themes:
            logger.warning(f"Theme '{theme_name}' not found.")
            return

        self.current_theme_name = theme_name
        theme_data = self.get_theme()

        # apply to app if provided (re-applies stylesheet)
        if not app:
            from PySide6.QtWidgets import QApplication

            app = QApplication.instance()

        if app and self._qss_template:
            self.apply_theme(app, self._qss_template)

        # Emit signal for custom widgets
        self.theme_changed.emit(theme_data)
        logger.info(f"Theme switched to: {theme_name}")

    def apply_theme(self, app, qss_template: str = None):
        """
        Formats the QSS template with current theme values
        and applies it to the QApplication.
        """
        if qss_template:
            self._qss_template = qss_template

        if not self._qss_template:
            return

        theme_data = self.get_theme()
        try:
            stylesheet = self._qss_template.format(**theme_data)
            app.setStyleSheet(stylesheet)
        except KeyError as e:
            logger.error(f"Theme Error: Missing key {e} in theme definition.")
        except ValueError as e:
            logger.error(f"Theme Error: Format string error (check braces): {e}")
