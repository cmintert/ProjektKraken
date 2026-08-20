"""Print a concise inspection of the active world's database contents."""

import sys
from pathlib import Path

from PySide6.QtCore import QSettings

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.app.constants import (  # noqa: E402
    SETTINGS_ACTIVE_DB_KEY,
    WINDOW_SETTINGS_APP,
    WINDOW_SETTINGS_KEY,
)
from src.core.paths import get_worlds_dir  # noqa: E402
from src.services.db_service import DatabaseService  # noqa: E402


def verify_db() -> None:
    """Load the active world database and print its entities and events."""
    settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
    active_world = settings.value(SETTINGS_ACTIVE_DB_KEY, "Default World")

    world_dir = get_worlds_dir() / active_world
    db_path = world_dir / "kraken.db"

    print(f"Checking DB at: {db_path}")

    if not db_path.exists():
        print("DB file not found!")
        return

    db = DatabaseService(str(db_path))
    db.connect()

    entities = db.get_entities()
    events = db.get_events()

    print(f"\n--- Entities ({len(entities)}) ---")
    for e in entities:
        print(f"- [{e.type}] {e.name} (ID: {e.id})")

    print(f"\n--- Events ({len(events)}) ---")
    for ev in events:
        print(f"- [{ev.type}] {ev.name} (Date: {ev.lore_date})")

    db.close()


if __name__ == "__main__":
    verify_db()
