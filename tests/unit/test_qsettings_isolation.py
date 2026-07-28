"""Regression tests for the shared QSettings isolation fixture."""

from pathlib import Path

from PySide6.QtCore import QSettings


def test_qsettings_uses_private_ini_store() -> None:
    """Settings are written beneath the test-only temporary directory."""
    settings = QSettings("ProjektKrakenTests", "Isolation")
    settings.setValue("example", "value")
    settings.sync()

    settings_path = Path(settings.fileName())
    assert settings.format() == QSettings.Format.IniFormat
    assert "projektkraken-tests-" in str(settings_path)
    assert "case-" in str(settings_path)


def test_qsettings_group_round_trip() -> None:
    """The native test store supports the grouped API used by the app."""
    settings = QSettings()
    settings.beginGroup("SpellCheck")
    settings.setValue("enabled", True)
    settings.endGroup()
    settings.sync()

    reread = QSettings()
    reread.beginGroup("SpellCheck")
    assert reread.value("enabled", False, type=bool) is True
    reread.endGroup()
