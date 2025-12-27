#!/usr/bin/env python3
"""
Timeline Grouping CLI.

Provides command-line tools for managing timeline grouping configurations
and tag colors.

Usage:
    python -m src.cli.timeline group --database world.kraken \
        --tags "Type,Faction" --mode DUPLICATE
    python -m src.cli.timeline clear --database world.kraken
    python -m src.cli.timeline tag-color --database world.kraken \
        --tag "Faction" --color "#FF0000"
"""

import argparse
import logging
import sys

from src.cli.utils import validate_database_path
from src.commands.timeline_grouping_commands import (
    ClearTimelineGroupingCommand,
    SetTimelineGroupingCommand,
    UpdateTagColorCommand,
)
from src.services.db_service import DatabaseService

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def set_grouping(args: argparse.Namespace) -> int:
    """Set timeline grouping configuration."""
    db_service = None
    try:
        db_service = DatabaseService(args.database)
        db_service.connect()

        # Parse tags
        tags = [t.strip() for t in args.tags.split(",") if t.strip()]
        if not tags:
            print("✗ No tags specified.")
            return 1

        cmd = SetTimelineGroupingCommand(tags, mode=args.mode)
        result = cmd.execute(db_service)

        if result.success:
            print("✓ Set timeline grouping:")
            print(f"  Tags: {', '.join(tags)}")
            print(f"  Mode: {args.mode}")
            return 0
        else:
            print(f"✗ Error: {result.message}")
            return 1

    except Exception as e:
        logger.error(f"Failed to set grouping: {e}")
        if args.verbose:
            raise
        return 1
    finally:
        if db_service:
            db_service.close()


def clear_grouping(args: argparse.Namespace) -> int:
    """Clear timeline grouping configuration."""
    db_service = None
    try:
        db_service = DatabaseService(args.database)
        db_service.connect()

        cmd = ClearTimelineGroupingCommand()
        result = cmd.execute(db_service)

        if result.success:
            print("✓ Timeline grouping cleared.")
            return 0
        else:
            print(f"✗ Error: {result.message}")
            return 1

    except Exception as e:
        logger.error(f"Failed to clear grouping: {e}")
        if args.verbose:
            raise
        return 1
    finally:
        if db_service:
            db_service.close()


def update_tag_color(args: argparse.Namespace) -> int:
    """Update color for a tag."""
    db_service = None
    try:
        db_service = DatabaseService(args.database)
        db_service.connect()

        cmd = UpdateTagColorCommand(args.tag, args.color)
        result = cmd.execute(db_service)

        if result.success:
            print(f"✓ Updated color for tag '{args.tag}' to {args.color}")
            return 0
        else:
            print(f"✗ Error: {result.message}")
            return 1

    except Exception as e:
        logger.error(f"Failed to update tag color: {e}")
        if args.verbose:
            raise
        return 1
    finally:
        if db_service:
            db_service.close()


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Manage ProjektKraken timeline grouping",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Group command
    group_parser = subparsers.add_parser("group", help="Set timeline grouping")
    group_parser.add_argument(
        "--database", "-d", required=True, help="Path to .kraken database file"
    )
    group_parser.add_argument(
        "--tags", required=True, help="Comma-separated list of tags"
    )
    group_parser.add_argument(
        "--mode",
        choices=["DUPLICATE", "FIRST_MATCH"],
        default="DUPLICATE",
        help="Grouping mode (default: DUPLICATE)",
    )
    group_parser.set_defaults(func=set_grouping)

    # Clear command
    clear_parser = subparsers.add_parser("clear", help="Clear timeline grouping")
    clear_parser.add_argument(
        "--database", "-d", required=True, help="Path to .kraken database file"
    )
    clear_parser.set_defaults(func=clear_grouping)

    # Tag Color command
    color_parser = subparsers.add_parser("tag-color", help="Set tag color")
    color_parser.add_argument(
        "--database", "-d", required=True, help="Path to .kraken database file"
    )
    color_parser.add_argument("--tag", required=True, help="Tag name")
    color_parser.add_argument("--color", required=True, help="Hex color code")
    color_parser.set_defaults(func=update_tag_color)

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Validate database path
    if hasattr(args, "database"):
        if not validate_database_path(args.database, allow_create=False):
            sys.exit(1)

    # Execute command
    if hasattr(args, "func"):
        sys.exit(args.func(args))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
