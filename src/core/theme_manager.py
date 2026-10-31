"""Theme Manager Module.

Manages loading and applying UI themes (Dark/Light) for the application. Implements a
singleton pattern to ensure consistent theming across the app.

This is the Qt-specific implementation that extends BaseThemeManager.
"""

import logging
from collections.abc import Callable
from typing import Any, Dict, Optional, cast

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from src.core.base_theme_manager import BaseThemeManager

logger = logging.getLogger(__name__)


class ThemeManager(QObject, BaseThemeManager):
    """Qt-specific theme manager that extends BaseThemeManager.

    Manages loading and applying UI themes (Dark/Light) with Qt signal support. Reads
    'themes.json' and applies values to a QSS template. Implements Singleton pattern.
    """

    theme_changed = Signal(dict)  # Emits new theme data

    def __new__(cls, *args: Any, **kwargs: Any) -> "ThemeManager":
        """Create or return the singleton instance of ThemeManager.

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
            # Use super() for proper MRO with multiple inheritance
            cls._instance = cast("ThemeManager", super().__new__(cls))
            # Initialize QObject only once
            if cls._instance:
                QObject.__init__(cls._instance)
        return cast("ThemeManager", cls._instance)

    def __init__(self, theme_file: str = "themes.json") -> None:
        """Initializes the ThemeManager.

        Args:
            theme_file: Path to the themes JSON file.

        """
        if not hasattr(self, "_presentation_handler"):
            self._presentation_handler: (
                Callable[[QApplication, str, dict], None] | None
            ) = None
        if hasattr(self, "_initialized"):
            return

        # Initialize BaseThemeManager (will set _initialized)
        BaseThemeManager.__init__(self, theme_file)

        # Restore saved theme preference from Qt settings
        from PySide6.QtCore import QSettings

        settings = QSettings("ProjektKraken", "ThemeSettings")
        saved_theme = str(settings.value("current_theme", "dark_mode"))
        if saved_theme in self.themes:
            self.current_theme_name = saved_theme

    def _notify_theme_changed(self, theme_data: Dict[str, Any]) -> None:
        """Override to emit Qt signal in addition to calling callbacks.

        Args:
            theme_data: The new theme data dictionary.

        """
        # Call base class method for callbacks
        super()._notify_theme_changed(theme_data)

        # Emit Qt signal
        self.theme_changed.emit(theme_data)

    @property
    def has_scoped_presentation(self) -> bool:
        """Whether application composition installed visibility-aware rendering."""
        return self._presentation_handler is not None

    @property
    def defers_theme_delivery(self) -> bool:
        """Whether a scoped presentation transaction is collecting GUI work."""
        return bool(getattr(self, "_collecting_presentation", False))

    def set_presentation_handler(
        self, handler: Callable[[QApplication, str, dict], None] | None
    ) -> None:
        """Install GUI presentation through a narrow callback; core never imports GUI."""
        self._presentation_handler = handler

    def set_theme(
        self,
        theme_name: str,
        app: Optional[QApplication] = None,
        *,
        persist: bool = True,
    ) -> None:
        """Switches the current theme and updates the application.

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
            app = cast(QApplication, QApplication.instance())

        if self.has_scoped_presentation:
            # Collect local presentation work for coherent per-panel frames.
            # GUI composition controls visible-first delivery without event pumping.
            self._collecting_presentation = True
            try:
                self._notify_theme_changed(theme_data)
            finally:
                self._collecting_presentation = False
            if app and self._qss_template:
                self.apply_theme(app, self._qss_template)
        else:
            if app and self._qss_template:
                self.apply_theme(app, self._qss_template)
            self._notify_theme_changed(theme_data)

        # Persist selection
        from PySide6.QtCore import QSettings

        if persist:
            settings = QSettings("ProjektKraken", "ThemeSettings")
            settings.setValue("current_theme", theme_name)

        logger.info(f"Theme switched to: {theme_name}")

    def apply_theme(
        self, app: QApplication, qss_template: Optional[str] = None
    ) -> None:
        """Formats the QSS template with current theme values and applies it to the
        QApplication.

        Args:
            app: QApplication instance.
            qss_template: Optional QSS template string.

        """
        if qss_template:
            self._qss_template = qss_template

        if not self._qss_template:
            return

        if self._presentation_handler is not None:
            self._apply_native_palette(app)
            self._presentation_handler(app, self._qss_template, self.get_theme())
            return

        stylesheet = self.format_stylesheet()
        if stylesheet:
            self._apply_native_palette(app)
            app.setStyleSheet(stylesheet)

    def _apply_native_palette(self, app: QApplication) -> None:
        """Keep unstyled panel/viewport backgrounds within the active theme.

        QSS continues to own specific control states. Native auto-filled widgets
        use these same existing tokens rather than the Windows light palette.
        """
        theme = self.get_theme()
        palette = QPalette(app.palette())
        roles = {
            QPalette.ColorRole.Window: "app_bg",
            QPalette.ColorRole.WindowText: "text_main",
            QPalette.ColorRole.Base: "surface",
            QPalette.ColorRole.AlternateBase: "app_bg",
            QPalette.ColorRole.Text: "text_main",
            QPalette.ColorRole.Button: "surface",
            QPalette.ColorRole.ButtonText: "text_main",
            QPalette.ColorRole.Highlight: "selection_bg",
            QPalette.ColorRole.HighlightedText: "selection_text",
        }
        for role, token in roles.items():
            palette.setColor(role, QColor(theme[token]))
        for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text):
            palette.setColor(
                QPalette.ColorGroup.Disabled, role, QColor(theme["text_dim"])
            )
        palette.setColor(
            QPalette.ColorGroup.Disabled,
            QPalette.ColorRole.ButtonText,
            QColor(theme["action_secondary_disabled_text"]),
        )
        app.setPalette(palette)
