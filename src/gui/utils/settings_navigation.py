"""GUI intent bus for contextual Settings Center navigation."""

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication


class SettingsNavigation(QObject):
    """Carry navigation intents without importing application coordinators."""

    requested = Signal(str, str)
    contextual_changed = Signal(str, object)


def settings_navigation() -> SettingsNavigation:
    """Return the application-owned navigation bus."""
    app = QApplication.instance()
    if app is None:
        raise RuntimeError("Settings navigation requires QApplication")
    bus = getattr(app, "_kraken_settings_navigation", None)
    if bus is None:
        bus = SettingsNavigation(app)
        setattr(app, "_kraken_settings_navigation", bus)
    return bus


def request_settings(setting_id: str = "", scope: str = "kraken") -> None:
    """Ask the single Center to reveal a setting."""
    settings_navigation().requested.emit(setting_id, scope)
