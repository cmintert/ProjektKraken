import sqlite3
import sys
import os

# Add src to path
sys.path.append(os.getcwd())

from src.core.paths import get_worlds_dir
from PySide6.QtCore import QSettings
from src.app.constants import (
    SETTINGS_ACTIVE_DB_KEY,
    WINDOW_SETTINGS_APP,
    WINDOW_SETTINGS_KEY,
)


def check_tags():
    settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
    active_world = settings.value(SETTINGS_ACTIVE_DB_KEY)

    if not active_world:
        print("No active world found in settings.")
        return

    db_path = get_worlds_dir() / active_world / f"{active_world}.kraken"
    print(f"Checking DB at: {db_path}")

    if not db_path.exists():
        print("DB file not found.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("\n--- Tags Table ---")
    cursor.execute("SELECT * FROM tags")
    tags = cursor.fetchall()
    for row in tags:
        print(row)
    if not tags:
        print("No tags found in 'tags' table.")

    print("\n--- Event Tags Table ---")
    cursor.execute("SELECT * FROM event_tags")
    event_tags = cursor.fetchall()
    for row in event_tags:
        print(row)
    if not event_tags:
        print("No rows in 'event_tags' table.")

    print("\n--- Entity Tags Table ---")
    cursor.execute("SELECT * FROM entity_tags")
    entity_tags = cursor.fetchall()
    for row in entity_tags:
        print(row)
    if not entity_tags:
        print("No rows in 'entity_tags' table.")

    print("\n--- Events with JSON Tags ---")
    cursor.execute("SELECT id, name, attributes FROM events")
    events = cursor.fetchall()
    count = 0
    for eid, name, attrs in events:
        if "_tags" in attrs:
            print(f"Event '{name}' ({eid}) has tags: {attrs}")
            count += 1
    if count == 0:
        print("No events found with '_tags' in attributes.")

    conn.close()


if __name__ == "__main__":
    check_tags()
