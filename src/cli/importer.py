"""CLI Import Module.

Handles command-line triggering of the import process.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List, cast

from PySide6.QtCore import QSettings

from src.app.constants import (
    SETTINGS_ACTIVE_DB_KEY,
    WINDOW_SETTINGS_APP,
    WINDOW_SETTINGS_KEY,
)
from src.core.command import CommandProtocol
from src.core.logging_config import get_logger
from src.core.paths import get_worlds_dir
from src.core.world import World, WorldManager
from src.services.db_service import DatabaseService
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


def _arguments(args: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import reviewed Lore JSON into Kraken."
    )
    parser.add_argument("--file", "-f", help="Path to the JSON source.")
    parser.add_argument("--database", "-d", help="Existing database in a world folder")
    parser.add_argument("--mode", choices=("skip", "update", "overwrite"))
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview without writes."
    )
    parser.add_argument("--review-out", help="Write a review artifact and stop.")
    parser.add_argument(
        "--apply-review", help="Reconstruct a saved review from sources."
    )
    parser.add_argument(
        "--confirm-timing", help="Confirm the reviewed timing fingerprint."
    )
    parser.add_argument(
        "--calendar-map", action="append", default=[], metavar="SOURCE=TARGET"
    )
    parser.add_argument("--accept-unresolved-calendar", action="append", default=[])
    parser.add_argument("--accept-unresolved-event", action="append", default=[])
    parsed = parser.parse_args(args)
    if not parsed.file and not parsed.apply_review:
        parser.error("--file or --apply-review is required")
    return parsed


def _execute_import(db: DatabaseService, world: World, args: argparse.Namespace) -> int:
    from src.cli.import_review import (
        REVIEW_REQUIRED,
        prepare_review,
        review_artifact,
        reviewed_command,
        verify_artifact,
    )
    from src.services.history_service import HistoryService

    artifact = None
    if args.apply_review:
        artifact = json.loads(Path(args.apply_review).read_text(encoding="utf-8"))
        source = str(Path(artifact["source"]).resolve())
        if args.file and str(Path(args.file).resolve()) != source:
            raise ValueError("The source differs from the saved review.")
        options = artifact["options"]
    else:
        source = str(Path(args.file).resolve())
        options = {
            "mode": args.mode or "update",
            "calendar_mappings": dict(item.split("=", 1) for item in args.calendar_map),
            "unresolved_calendars": args.accept_unresolved_calendar,
            "unresolved_events": args.accept_unresolved_event,
        }
    preview, plan = prepare_review(db, source, options)
    report = {
        key: preview.get(key)
        for key in (
            "errors",
            "warnings",
            "actions",
            "calendar_decisions",
            "timing_review",
        )
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if preview["errors"]:
        return 1
    fresh = review_artifact(source, preview)
    if artifact is not None:
        verify_artifact(artifact, fresh)
    if args.review_out:
        Path(args.review_out).write_text(
            json.dumps(fresh, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    needs_review = bool((preview.get("timing_review") or {}).get("needs_review"))
    if args.dry_run or args.review_out:
        return REVIEW_REQUIRED if needs_review else 0
    if needs_review and (
        artifact is None or plan is None or args.confirm_timing != plan.fingerprint
    ):
        print(
            "Timing review required. Save a review and confirm its fingerprint.",
            file=sys.stderr,
        )
        return REVIEW_REQUIRED
    command = reviewed_command(db, preview, plan)
    with db.transaction():
        result = command.execute(db)
        if not result.success:
            raise ValueError(result.message)
        HistoryService(db, world.id).save_command(cast(CommandProtocol, command))
    print("Import Successful! Reviewed changes applied; Undo is available.")
    return 0


def run_import_cli(args: List[str]) -> int:
    """Import into an approved existing world; return 3 when review is required."""
    try:
        parsed = _arguments(args)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2
    db_service = None
    try:
        world = _resolve_import_world(parsed.database)
        if world is None:
            raise ValueError("Import target is not a valid, approved existing world.")
        print(f"Import target: {world.name} ({world.db_path})", file=sys.stderr)
        db_service = DatabaseService(str(world.db_path))
        db_service.connect()
        return _execute_import(db_service, world, parsed)
    except (ValueError, OSError, TypeError, KeyError) as exc:
        logger.error("Import failed: %s", exc)
        print(f"Import Failed: {exc}", file=sys.stderr)
        return 1
    finally:
        if db_service is not None:
            db_service.close()
