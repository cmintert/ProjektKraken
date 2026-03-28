#!/usr/bin/env python3
"""Database Info/Stats CLI.

Provides command-line tools for inspecting a ProjektKraken database.

Usage:
    python -m src.cli.info show --database world.kraken
    python -m src.cli.info show --database world.kraken --json
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from src.cli.utils import validate_database_path
from src.services.db_service import DatabaseService

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def gather_stats(db_service: DatabaseService) -> dict:
    """Gather database statistics.

    Args:
        db_service: Connected DatabaseService instance.

    Returns:
        Dictionary containing all statistics.

    """
    stats = {
        "objects": {
            "entities": 0,
            "events": 0,
            "relations": 0,
            "maps": 0,
            "markers": 0,
        },
        "attachments": {
            "count": 0,
            "total_size_mb": 0.0,
        },
        "calendars": {
            "active": None,
            "total": 0,
        },
        "tags": 0,
        "timeline_grouping": False,
    }

    try:
        entities = db_service.get_all_entities()
        events = db_service.get_all_events()
        stats["objects"]["entities"] = len(entities)
        stats["objects"]["events"] = len(events)

        conn = db_service.get_connection()
        if conn:
            row = conn.execute("SELECT COUNT(*) FROM relations").fetchone()
            stats["objects"]["relations"] = row[0] if row else 0

        maps = db_service.get_all_maps()
        stats["objects"]["maps"] = len(maps)
        stats["objects"]["markers"] = sum(
            len(db_service.get_markers_for_map(m.id)) for m in maps
        )

        attachment_repo = db_service.get_attachment_repo()
        all_attachments = attachment_repo.list_all()
        attachment_count = len(all_attachments)
        total_size = 0
        for att in all_attachments:
            if att.file_path:
                try:
                    total_size += Path(att.file_path).stat().st_size
                except (OSError, TypeError):
                    pass

        stats["attachments"]["count"] = attachment_count
        stats["attachments"]["total_size_mb"] = round(total_size / (1024 * 1024), 2)

        calendars = db_service.get_all_calendar_configs()
        stats["calendars"]["total"] = len(calendars)
        for cal in calendars:
            if cal.is_active:
                stats["calendars"]["active"] = cal.name
                break

        stats["tags"] = len(db_service.get_all_tags())
        stats["timeline_grouping"] = db_service.get_timeline_grouping_config() is not None

    except Exception as e:
        logger.error(f"Error gathering stats: {e}")
        if logger.isEnabledFor(logging.DEBUG):
            raise

    return stats


def show_info(args: argparse.Namespace) -> int:
    """Show database info.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code (0 for success, 1 for failure).

    """
    db_service = None
    try:
        db_service = DatabaseService(args.database)
        db_service.connect()

        stats = gather_stats(db_service)

        if args.json:
            # JSON output
            output = {
                "database": Path(args.database).name,
                **stats,
            }
            print(json.dumps(output, indent=2))
        else:
            # Human-readable output
            db_name = Path(args.database).name
            print(f"\nDatabase: {db_name}")
            print("-" * 45)
            print("\nObjects:")
            print(f"  Entities:   {stats['objects']['entities']:>5}")
            print(f"  Events:     {stats['objects']['events']:>5}")
            print(f"  Relations:  {stats['objects']['relations']:>5}")
            print(f"  Maps:       {stats['objects']['maps']:>5}")
            print(f"  Markers:    {stats['objects']['markers']:>5}")

            print("\nAttachments:")
            print(f"  Count:      {stats['attachments']['count']:>5}")
            print(f"  Total Size: {stats['attachments']['total_size_mb']:>6.2f} MB")

            print("\nCalendars:")
            if stats["calendars"]["active"]:
                print(f"  Active:     {stats['calendars']['active']}")
            else:
                print("  Active:     (none)")
            print(f"  Total:      {stats['calendars']['total']:>5}")

            print(f"\nTags:       {stats['tags']:>5} unique")

            grouping_status = "Yes" if stats["timeline_grouping"] else "No"
            print(f"Timeline Grouping: {grouping_status}")
            print()

        return 0

    except Exception as e:
        logger.error(f"Failed to show info: {e}")
        if args.verbose:
            raise
        return 1
    finally:
        if db_service:
            db_service.close()


def register_commands(subparsers: argparse._SubParsersAction) -> None:  # type: ignore
    """Register info subcommands with a parent subparsers group.

    Args:
        subparsers: The subparsers action group from a parent ArgumentParser.

    """
    # Show
    show_p = subparsers.add_parser("show", help="Show database info")
    show_p.add_argument("--database", "-d", required=True)
    show_p.add_argument(
        "--json", action="store_true", help="Output as JSON"
    )
    show_p.set_defaults(func=show_info)


def main() -> None:
    """Main CLI entry point for info tools."""
    parser = argparse.ArgumentParser(description="Inspect ProjektKraken databases")
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    register_commands(subparsers)

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if hasattr(args, "database"):
        if not validate_database_path(args.database, allow_create=False):
            sys.exit(1)

    if hasattr(args, "func"):
        sys.exit(args.func(args))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
