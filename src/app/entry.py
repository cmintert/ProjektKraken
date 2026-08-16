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

    if sys.stderr is not None:
        faulthandler.enable()

    # Defer MainWindow import to ensure AA_ShareOpenGLContexts is already set
    from src.app.main_window import MainWindow
    from src.app.package_smoke import (
        PackageSmokeController,
        parse_package_smoke_options,
    )

    package_smoke_options = parse_package_smoke_options(sys.argv)

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

        qt_argv = [sys.argv[0]] if package_smoke_options is not None else sys.argv
        app = QApplication(qt_argv)
        if package_smoke_options is not None:
            app.setQuitOnLastWindowClosed(False)
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

        splash = None
        if package_smoke_options is None:
            from src.gui.splash_screen import SplashScreen

            splash = SplashScreen()
            splash.show()
            app.processEvents()

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
        if splash is not None:
            splash.set_status("Loading world data…")
            window.startup_completed.connect(
                lambda _success: splash.dismiss(window)
            )
            # Retain the splash until the asynchronous startup signal arrives.
            setattr(app, "_startup_splash", splash)
        window.show()

        if package_smoke_options is not None:
            package_smoke_controller = PackageSmokeController(
                window,
                package_smoke_options,
            )
            # Keep the smoke controller alive for the QApplication lifetime.
            setattr(app, "_package_smoke_controller", package_smoke_controller)
            package_smoke_controller.start()

        logger.info("Entering Event Loop...")
        exit_code = app.exec()
        cleanup_app()
        sys.exit(exit_code)
    except Exception as exc:
        logger.exception("CRITICAL: Unhandled exception in main application loop")
        from src.app.startup_check import report_unhandled_startup_exception

        report_unhandled_startup_exception(exc)
        sys.exit(1)


def cleanup_app() -> None:
    """Performs global cleanup operations before exit."""
    logger.info("Shimmying down the drain pipe...Shutting down logging.")
    shutdown_logging()
