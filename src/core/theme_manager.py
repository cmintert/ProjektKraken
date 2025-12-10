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


class ThemeManager:
    """
    Manages loading and applying UI themes (Dark/Light).
    Reads 'themes.json' and applies values to a QSS template.
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        """
        Ensures only one instance of ThemeManager exists (Singleton pattern).

        Returns:
            ThemeManager: The singleton instance.
        """
        if not cls._instance:
            cls._instance = super(ThemeManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, theme_file: str = "themes.json"):
        """
        Initializes the ThemeManager.

        Args:
            theme_file (str, optional): Path to the themes JSON file. Defaults to "themes.json".
        """
        if hasattr(self, "_initialized"):
            return

        self.theme_file = theme_file
        self.themes: Dict[str, Dict[str, str]] = {}
        self.current_theme: str = "dark_mode"  # Default
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
                    "accent_secondary": "#0078D4",
                    "text_main": "#E0E0E0",
                    "text_dim": "#9E9E9E",
                    "error": "#CF6679",
                }
            }
            return

        try:
            with open(self.theme_file, "r") as f:
                self.themes = json.load(f)
        except Exception as e:
            logger.error(f"Error loading themes: {e}")

    def get_theme(self) -> Dict[str, str]:
        """Returns the current theme dictionary."""
        return self.themes.get(self.current_theme, self.themes.get("dark_mode", {}))

    def apply_theme(self, app, qss_template: str):
        """
        Formats the QSS template with current theme values
        and applies it to the QApplication.
        """
        theme_data = self.get_theme()
        try:
            # Safe formatting to ignore keys not in theme but in QSS?
            # Ideally strict to ensure all tokens are present.
            stylesheet = qss_template.format(**theme_data)
            app.setStyleSheet(stylesheet)
        except KeyError as e:
            logger.error(f"Theme Error: Missing key {e} in theme definition.")
