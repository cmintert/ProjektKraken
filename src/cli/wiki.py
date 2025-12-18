#!/usr/bin/env python3
"""
Wiki Management CLI.

Provides command-line tools for wiki operations, such as scanning content for links.

Usage:
    python -m src.cli.wiki scan --database world.kraken --source <id> --field description
"""

import sys
import argparse
import logging
from src.services.db_service import DatabaseService
from src.commands.wiki_commands import ProcessWikiLinksCommand
from src.cli.utils import validate_database_path

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def scan_links(args) -> int:
    """Scan a source object for wiki links."""
    db_service = None
    try:
        db_service = DatabaseService(args.database)
        db_service.connect()

        # Fetch source object to get text
        text_content = ""

        # Try finding as entity
        obj = db_service.get_entity(args.source)
        if not obj:
            # Try finding as event
            obj = db_service.get_event(args.source)

        if not obj:
            print(f"✗ Source object not found: {args.source}")
            return 1

        # Get content from field
        if hasattr(obj, args.field):
            text_content = getattr(obj, args.field)
        elif hasattr(obj, "attributes") and args.field in obj.attributes:
            text_content = obj.attributes[args.field]
        else:
            print(f"✗ Field '{args.field}' not found on object.")
            return 1

        if not text_content:
            print("No content to scan.")
            return 0

        cmd = ProcessWikiLinksCommand(args.source, text_content, args.field)
        result = cmd.execute(db_service)

        if result.success:
            print(f"✓ {result.message}")
            return 0
        else:
            print(f"✗ Error: {result.message}")
            return 1

    except Exception as e:
        logger.error(f"Failed to scan links: {e}")
        if args.verbose:
            raise
        return 1
    finally:
        if db_service:
            db_service.close()


def main():
    parser = argparse.ArgumentParser(description="Manage ProjektKraken wiki content")
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Scan command
    scan_p = subparsers.add_parser("scan", help="Scan text for wiki links")
    scan_p.add_argument("--database", "-d", required=True)
    scan_p.add_argument(
        "--source", "-s", required=True, help="ID of entity or event to scan"
    )
    scan_p.add_argument(
        "--field",
        "-f",
        default="description",
        help="Field to scan (default: description)",
    )
    scan_p.set_defaults(func=scan_links)

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
