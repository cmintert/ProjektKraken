"""CLI Import Module.

Handles command-line triggering of the import process.
"""

import argparse
import sys
from pathlib import Path
from typing import List, cast

from PySide6.QtCore import QSettings

from src.app.constants import (
    SETTINGS_ACTIVE_DB_KEY,
    WINDOW_SETTINGS_APP,
    WINDOW_SETTINGS_KEY,
)
from src.core.logging_config import get_logger
from src.core.paths import get_worlds_dir
from src.core.world import World, WorldManager
from src.services.db_service import DatabaseService
from src.services.import_service import ImportService
from src.services.world_storage_settings import WorldStorageSettings

logger = get_logger(__name__)


def _resolve_import_world(database: str | None) -> World | None:
    """Choose an existing, trusted world using the desktop application's settings."""
    settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
    storage = WorldStorageSettings(settings)
    manager = WorldManager(
        get_worlds_dir(),
        additional_world_paths=storage.registered_world_paths(),
        approved_external_paths=storage.external_approvals(),
    )
    if database:
        target = Path(database).resolve(strict=False)
        return next(
            (
                world
                for world in manager.discover_worlds()
                if world.db_path.resolve(strict=False) == target
            ),
            None,
        )
    active_path = storage.active_world_path()
    if active_path is not None:
        inspected = World.inspect(active_path)
        approval = storage.approved_external_path(inspected) if inspected else None
        return World.load(active_path, [approval] if approval else [])
    active_name = cast(str | None, settings.value(SETTINGS_ACTIVE_DB_KEY, None))
    return manager.get_world(active_name) if active_name else None


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
    parser.add_argument(
        "--database", "-d", help="Existing database in a complete world folder"
    )

    try:
        parsed_args = parser.parse_args(args)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2

    file_path = Path(parsed_args.file).resolve()  # Security: Resolve path

    if not file_path.exists():
        logger.error(f"File not found: {file_path}")
        print(f"Error: File '{file_path}' does not exist.", file=sys.stderr)
        return 1

    if not file_path.is_file():
        logger.error(f"Not a file: {file_path}")
        print(f"Error: '{file_path}' is not a file.", file=sys.stderr)
        return 1

    world = _resolve_import_world(parsed_args.database)
    if world is None:
        print(
            "Error: Import target is not a valid, approved existing world.",
            file=sys.stderr,
        )
        return 1
    db_path = str(world.db_path)
    print(f"Import target: {world.name} ({world.db_path})", file=sys.stderr)

    try:
        db_service = DatabaseService(db_path)
        db_service.connect()
        import_service = ImportService(db_service)

        # 2. Read File
        print(f"Reading {file_path}...")
        # Modified file reading to include JSON parsing error handling
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                json_content = f.read()
        except FileNotFoundError:  # Should be caught by file_path.exists() earlier
            logger.error(f"File not found: {file_path}")
            print(f"Error: File not found: '{file_path}'.", file=sys.stderr)
            return 1
        except Exception as e:  # Catch other potential file reading errors
            logger.error(f"Error reading file '{file_path}': {e}")
            print(f"Error reading file '{file_path}': {e}", file=sys.stderr)
            return 1

        # 3. Parse and Validate
        try:
            parsed_data = import_service.parse_only(json_content)
        except ValueError as e:
            msg = f"Validation Error: {e}"
            logger.error(msg)
            print(msg, file=sys.stderr)
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
            print("\nImport Failed!", file=sys.stderr)
            for error in result.errors:
                print(f"  - {error}", file=sys.stderr)
            return 1

    except Exception as e:
        logger.exception("Unexpected CLI import error")
        print(f"Critical Error: {e}", file=sys.stderr)
        return 1
    finally:
        if "db_service" in locals() and db_service:
            db_service.close()
