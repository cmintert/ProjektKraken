"""
Application Entry Point.

This module contains the main() function and cleanup logic for the application.
Separated from MainWindow to allow for easier testing and future refactoring.
"""

import os
import sys

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from src.app.constants import WINDOW_SETTINGS_APP, WINDOW_SETTINGS_KEY
from src.app.main import MainWindow
from src.core.logging_config import get_logger, setup_logging, shutdown_logging
from src.core.paths import get_resource_path
from src.core.theme_manager import ThemeManager

# Initialize Logging
setup_logging(debug_mode=True)
logger = get_logger(__name__)


def main() -> None:
    """Application entry point."""
    setup_logging(debug_mode=True)
    from datetime import datetime

    logger.info("=" * 60)
    logger.info(f"Project Kraken Session Started at {datetime.now().isoformat()}")
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
            print("Resetting Application Settings...")
            from PySide6.QtCore import QSettings

            settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
            settings.clear()
            settings.sync()
            print("Settings cleared. Starting in default state.")

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
