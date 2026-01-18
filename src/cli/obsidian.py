#!/usr/bin/env python3
"""
Obsidian Export CLI.

Provides command-line tools for exporting the database to an Obsidian vault.

Usage:
    python -m src.cli.obsidian export --database world.kraken --out-dir ./obsidian_export
"""

import argparse
import logging
import sys
from pathlib import Path

from src.cli.utils import validate_database_path
from src.services.db_service import DatabaseService
from src.services.obsidian_exporter import ObsidianExporter

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def export_obsidian(args: argparse.Namespace) -> int:
    """Export database to Obsidian vault."""
    db_service = None
    try:
        db_service = DatabaseService(args.database)
        db_service.connect()

        exporter = ObsidianExporter(db_service)
        output_dir = Path(args.out_dir)

        print(f"Exporting to: {output_dir}")
        result = exporter.export_to_folder(
            output_dir, include_relations=not args.no_relations
        )

        if result.success:
            print(f"✓ Export successful!")
            print(f"  Files created: {result.files_created}")
            print(f"  Location: {result.output_dir}")

            if result.errors:
                print(f"\n⚠️ Completed with {len(result.errors)} warnings:")
                for err in result.errors:
                    print(f"  - {err}")
            return 0
        else:
            print("✗ Export failed.")
            for err in result.errors:
                print(f"  - {err}")
            return 1

    except Exception as e:
        logger.error(f"Failed to export: {e}")
        if args.verbose:
            raise
        return 1
    finally:
        if db_service:
            db_service.close()


def main() -> None:
    """Main CLI entry point for obsidian tools."""
    parser = argparse.ArgumentParser(description="Export ProjektKraken to Obsidian")
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Export
    export_p = subparsers.add_parser("export", help="Export to Obsidian vault")
    export_p.add_argument("--database", "-d", required=True)
    export_p.add_argument("--out-dir", "-o", required=True, help="Output directory")
    export_p.add_argument(
        "--no-relations", action="store_true", help="Skip 'Related' section"
    )
    export_p.set_defaults(func=export_obsidian)

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
