"""
Base Theme Manager Module (Headless).

Provides core theme management functionality without Qt dependencies.
This allows the theme system to work in headless environments.
"""

import json
import logging
import os
from typing import Dict, List, Callable

logger = logging.getLogger(__name__)


class BaseThemeManager:
    """
    Base theme manager without Qt dependencies.
    
    Manages loading and applying UI themes (Dark/Light) in a framework-agnostic way.
    Implements a singleton pattern to ensure consistent theming across the app.
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        """
        Create or return the singleton instance of BaseThemeManager.

        Implements the singleton pattern to ensure only one ThemeManager
        instance exists throughout the application lifecycle. This is
        critical for maintaining consistent theming across all UI components.

        Args:
            *args: Variable length argument list (unused).
            **kwargs: Arbitrary keyword arguments (unused).

        Returns:
            BaseThemeManager: The singleton instance.
        """
        if not cls._instance:
            cls._instance = super(BaseThemeManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, theme_file: str = "themes.json"):
        """
        Initializes the BaseThemeManager.
        
        Args:
            theme_file: Path to the themes JSON file.
        """
        if hasattr(self, "_initialized"):
            return

        self.theme_file = theme_file
        self.themes: Dict[str, Dict[str, str]] = {}
        self.current_theme_name: str = "dark_mode"
        self._theme_changed_callbacks: List[Callable[[Dict], None]] = []
        self._qss_template: str = ""

        self._load_themes()
        self._initialized = True

    def _load_themes(self):
        """Loads the JSON theme definition."""
        logger.debug(f"Attempting to load themes from: {self.theme_file}")
        logger.debug(f"File exists: {os.path.exists(self.theme_file)}")
        logger.debug(f"Current working directory: {os.getcwd()}")

        if not os.path.exists(self.theme_file):
            logger.warning(
                f"Theme file not found at '{self.theme_file}', using fallback themes"
            )
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
                    "scrollbar_bg": "#2B2B2B",
                    "scrollbar_handle": "#555555",
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
                    "scrollbar_bg": "#F0F0F0",
                    "scrollbar_handle": "#C0C0C0",
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
            logger.debug(f"Successfully loaded themes: {list(self.themes.keys())}")
            # Log font size keys for verification
            for theme_name, theme_data in self.themes.items():
                font_keys = [k for k in theme_data.keys() if "font" in k]
                logger.debug(f"Theme '{theme_name}' font settings: {font_keys}")
        except Exception as e:
            logger.error(f"Error loading themes: {e}")

    def load_stylesheet(self, path: str):
        """
        Loads and caches the stylesheet template.
        
        Args:
            path: Path to the stylesheet file.
        """
        try:
            with open(path, "r") as f:
                self._qss_template = f.read()
        except FileNotFoundError:
            logger.error(f"Style template not found: {path}")

    def get_available_themes(self) -> List[str]:
        """
        Returns a list of available theme names.
        
        Returns:
            List of theme names.
        """
        return list(self.themes.keys())

    def get_theme(self) -> Dict[str, str]:
        """
        Returns the current theme dictionary.
        
        Returns:
            Dictionary containing theme colors and settings.
        """
        return self.themes.get(
            self.current_theme_name, self.themes.get("dark_mode", {})
        )

    def set_theme(self, theme_name: str):
        """
        Switches the current theme.

        Args:
            theme_name: The key of the theme to switch to.
        """
        if theme_name not in self.themes:
            logger.warning(f"Theme '{theme_name}' not found.")
            return

        self.current_theme_name = theme_name
        theme_data = self.get_theme()

        # Notify callbacks
        self._notify_theme_changed(theme_data)

        logger.info(f"Theme switched to: {theme_name}")

    def on_theme_changed(self, callback: Callable[[Dict], None]):
        """
        Register a callback to be called when the theme changes.
        
        Args:
            callback: Function to call with theme data when theme changes.
        """
        self._theme_changed_callbacks.append(callback)

    def _notify_theme_changed(self, theme_data: Dict):
        """
        Notify all registered callbacks of theme change.
        
        Args:
            theme_data: The new theme data dictionary.
        """
        for callback in self._theme_changed_callbacks:
            try:
                callback(theme_data)
            except Exception as e:
                logger.error(f"Error in theme changed callback: {e}")

    def format_stylesheet(self, template: str = None) -> str:
        """
        Formats a stylesheet template with current theme values.
        
        Args:
            template: Optional stylesheet template. If None, uses cached template.
            
        Returns:
            Formatted stylesheet string.
        """
        if template:
            self._qss_template = template

        if not self._qss_template:
            return ""

        theme_data = self.get_theme()
        try:
            return self._qss_template.format(**theme_data)
        except KeyError as e:
            logger.error(f"Theme Error: Missing key {e} in theme definition.")
            return ""
        except ValueError as e:
            logger.error(f"Theme Error: Format string error (check braces): {e}")
            return ""
