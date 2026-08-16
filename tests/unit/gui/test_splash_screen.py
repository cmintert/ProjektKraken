"""Tests for the ProjektKraken startup splash screen."""

from PySide6.QtCore import Qt

from src.core.version import AUTHOR, RELEASE_DATE, VERSION
from src.gui.splash_screen import SplashScreen


def test_splash_displays_release_identity(qtbot) -> None:
    """The splash exposes the canonical version, date, and author."""
    splash = SplashScreen()
    qtbot.addWidget(splash)

    assert VERSION in splash.version_value.text()
    assert splash.release_value.text() == RELEASE_DATE
    assert AUTHOR in splash.author_value.text()


def test_splash_loads_full_brand_mark(qtbot) -> None:
    """The splash uses the full Kraken artwork rather than the tiny app icon."""
    splash = SplashScreen()
    qtbot.addWidget(splash)

    pixmap = splash.logo_label.pixmap()
    assert not pixmap.isNull()
    assert pixmap.width() >= 300
    assert pixmap.height() > 250


def test_splash_status_can_be_updated(qtbot) -> None:
    """Startup phases can report their current activity."""
    splash = SplashScreen()
    qtbot.addWidget(splash)

    splash.set_status("Loading world data…")

    assert splash.status_label.text() == "Loading world data…"


def test_splash_stays_above_other_windows(qtbot) -> None:
    """The window manager keeps the splash above application windows."""
    splash = SplashScreen()
    qtbot.addWidget(splash)

    assert splash.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
