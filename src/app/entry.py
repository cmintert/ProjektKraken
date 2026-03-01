"""Application Entry Point.

This module contains the main() function and cleanup logic for the application.
Separated from MainWindow to allow for easier testing and future refactoring.
"""

import os
import sys

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Imports after load_dotenv() to allow modules to access environment variables
# CRITICAL: Set OpenGL context sharing BEFORE any other Qt imports.
# This is required for QWebEngineView + QQuickWidget compatibility.
from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QIcon  # noqa: E402
from PySide6.QtQuick import QQuickWindow, QSGRendererInterface  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

# Force QQuickWidget to use OpenGL to match QWebEngineView
QQuickWindow.setGraphicsApi(QSGRendererInterface.GraphicsApi.OpenGLRhi)
QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)

# Now safe to import other modules that may use Qt widgets
# Now safe to import other modules that may use Qt widgets
from src.app.constants import (  # noqa: E402
    VERSION,
    WINDOW_SETTINGS_APP,
    WINDOW_SETTINGS_KEY,
)
from src.core.logging_config import (  # noqa: E402
    get_logger,
    setup_logging,
    shutdown_logging,
)
from src.core.paths import get_resource_path  # noqa: E402
from src.core.theme_manager import ThemeManager  # noqa: E402

# Initialize Logging
# setup_logging(debug_mode=True)  # Removed module-level side-effect
logger = get_logger(__name__)


def main() -> None:
    """Application entry point."""
    import faulthandler

    faulthandler.enable()

    # Defer MainWindow import to ensure AA_ShareOpenGLContexts is already set
    from src.app.main_window import MainWindow

    setup_logging(debug_mode=True)
    from datetime import datetime

    # CLI Command Routing
    if len(sys.argv) > 1 and sys.argv[1] == "import":
        from src.cli.importer import run_import_cli

        # Pass arguments after 'import'
        exit_code = run_import_cli(sys.argv[2:])
        shutdown_logging()
        sys.exit(exit_code)

    logger.info("=" * 60)
    logger.info(
        f"Project Kraken v{VERSION} Session Started at {datetime.now().isoformat()}"
    )
    logger.info("=" * 60)

    try:
        logger.info("Starting Application...")

        # 1. High DPI Scaling
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )

        app = QApplication(sys.argv)
        app.setOrganizationName(WINDOW_SETTINGS_KEY)
        app.setApplicationName(WINDOW_SETTINGS_APP)

        # 1.5 Custom Tooltip Timing
        from src.gui.utils.style_helper import TooltipEventFilter, TooltipProxyStyle

        app.setStyle(TooltipProxyStyle())
        tooltip_filter = TooltipEventFilter(app)
        app.installEventFilter(tooltip_filter)

        # Set App Icon
        icon_path = get_resource_path(
            os.path.join(
                "default_assets", "icons", "app_icons", "Projekt_Kraken_Icon_32x32.png"
            )
        )
        if os.path.exists(icon_path):
            app.setWindowIcon(QIcon(icon_path))
        else:
            logger.warning(f"App icon not found at: {icon_path}")

        # 2. Apply Theme
        tm = ThemeManager()
        try:
            qss_path = get_resource_path(os.path.join("src", "resources", "main.qss"))
            with open(qss_path, "r") as f:
                qss_template = f.read()
                tm.apply_theme(app, qss_template)
        except FileNotFoundError:
            logger.warning("main.qss not found, skipping styling.")

        # CLI Argument Parsing for Layout Capture
        capture_layout = "--set-default-layout" in sys.argv
        if capture_layout:
            logger.info(
                "Layout Capture Mode Active: Default layout will be updated on exit."
            )

        # Check for reset settings flag
        if "--reset-settings" in sys.argv:
            logger.info("Resetting Application Settings...")
            from PySide6.QtCore import QSettings

            settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
            settings.clear()
            settings.sync()
            logger.info("Settings cleared. Starting in default state.")

        window = MainWindow(capture_layout_on_exit=capture_layout)
        window.show()

        logger.info("Entering Event Loop...")
        exit_code = app.exec()
        cleanup_app()
        sys.exit(exit_code)
    except Exception:
        logger.exception("CRITICAL: Unhandled exception in main application loop")
        sys.exit(1)


def cleanup_app() -> None:
    """Performs global cleanup operations before exit."""
    logger.info("Shimmying down the drain pipe...Shutting down logging.")
    shutdown_logging()
