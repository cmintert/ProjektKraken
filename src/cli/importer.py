"""CLI Import Module.

Handles command-line triggering of the import process.
"""

import argparse
from pathlib import Path
from typing import List

from PySide6.QtCore import QSettings

from src.app.constants import (
    SETTINGS_ACTIVE_DB_KEY,
    WINDOW_SETTINGS_APP,
    WINDOW_SETTINGS_KEY,
)
from src.core.logging_config import get_logger
from src.core.paths import get_worlds_dir
from src.services.db_service import DatabaseService
from src.services.import_service import ImportService

logger = get_logger(__name__)


def run_import_cli(args: List[str]) -> int:
    """Entry point for CLI import command.

    Args:
        args: Command line arguments (excluding script name and 'import' command).

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    parser = argparse.ArgumentParser(description="Import JSON data into ProjektKraken.")
    parser.add_argument(
        "--file", "-f", required=True, help="Path to the JSON file to import."
    )
    # Future flags could be added here (e.g., --world, --verbose)

    try:
        parsed_args = parser.parse_args(args)
    except SystemExit:
        return 1

    file_path = Path(parsed_args.file)
    if not file_path.exists():
        logger.error(f"File not found: {file_path}")
        print(f"Error: File '{file_path}' does not exist.")
        return 1

    # 1. Setup Database Connection
    # We need to know which world to use. For now, use the active one from settings.
    settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
    active_world = settings.value(SETTINGS_ACTIVE_DB_KEY, "Default World")

    # Check if world exists
    world_dir = get_worlds_dir() / active_world
    if not world_dir.exists():
        logger.error(f"Active world directory not found: {world_dir}")
        print(f"Error: Active world '{active_world}' not found.")
        return 1

    db_path = str(world_dir / "kraken.db")
    logger.info(f"Using database: {db_path}")

    try:
        db_service = DatabaseService(db_path)
        db_service.connect()
        import_service = ImportService(db_service)

        # 2. Read File
        print(f"Reading {file_path}...")
        with open(file_path, "r", encoding="utf-8") as f:
            json_content = f.read()

        # 3. Parse and Validate
        try:
            parsed_data = import_service.parse_only(json_content)
        except ValueError as e:
            msg = f"Validation Error: {e}"
            logger.error(msg)
            print(msg)
            return 1

        # 4. Import
        print(
            f"Importing {len(parsed_data.get('entities', []))} entities, "
            f"{len(parsed_data.get('events', []))} events..."
        )
        result = import_service.import_batch(parsed_data)

        if result.success:
            print("Import Successful!")
            print(f"  Entities Created: {len(result.created_entities)}")
            print(f"  Events Created:   {len(result.created_events)}")
            print(f"  Relations Created:{len(result.created_relations)}")
            if result.warnings:
                print("\nWarnings:")
                for w in result.warnings:
                    print(f"  - {w}")
            return 0
        else:
            print("\nImport Failed!")
            for e in result.errors:
                print(f"  - {e}")
            return 1

    except Exception as e:
        logger.exception("Unexpected CLI import error")
        print(f"Critical Error: {e}")
        return 1
    finally:
        if "db_service" in locals() and db_service:
            db_service.close()
