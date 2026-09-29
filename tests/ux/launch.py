"""Launch Kraken with task-local Windows QSettings and the normal preflight."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from PySide6.QtCore import QCoreApplication, QSettings

from src.app.constants import (
    SETTINGS_ACTIVE_DB_KEY,
    WINDOW_SETTINGS_APP,
    WINDOW_SETTINGS_KEY,
)
from src.services.world_storage_settings import WorldStorageSettings


def configure_task_settings(world_path: Path, settings_path: Path) -> None:
    """Select one imported world without reading the user's registry settings."""
    world_path = world_path.resolve(strict=True)
    settings_path.mkdir(parents=True, exist_ok=True)
    QCoreApplication.setOrganizationName(WINDOW_SETTINGS_KEY)
    QCoreApplication.setApplicationName(WINDOW_SETTINGS_APP)
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(
        QSettings.Format.IniFormat,
        QSettings.Scope.UserScope,
        str(settings_path),
    )
    settings = QSettings()
    settings.clear()
    settings.setValue(SETTINGS_ACTIVE_DB_KEY, world_path.name)
    storage = WorldStorageSettings(settings)
    storage.set_active_world_path(world_path)
    storage.register_world_path(world_path)
    settings.sync()
    if settings.status() != QSettings.Status.NoError:
        raise OSError("Could not isolate UX benchmark settings")


def main(argv: Sequence[str] | None = None) -> int:
    """Run the ordinary source launcher after installing isolated settings."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--world", type=Path, required=True)
    parser.add_argument("--settings", type=Path, required=True)
    options = parser.parse_args(argv)
    configure_task_settings(options.world, options.settings)
    sys.argv = [sys.argv[0]]
    from launcher import run

    return run()


if __name__ == "__main__":
    raise SystemExit(main())
