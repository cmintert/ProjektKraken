#!/usr/bin/env python3
"""
Longform Document Export CLI.

Exports a longform document to Markdown format.
Can output to stdout or write to a file.

Usage:
    python -m src.cli.export_longform <database_path> [output_file]
    python -m src.cli.export_longform world.kraken
    python -m src.cli.export_longform world.kraken longform_export.md
"""

import sys
import argparse
import logging
from pathlib import Path
from src.services.db_service import DatabaseService
from src.services import longform_builder

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Export ProjektKraken longform document to Markdown",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Export to stdout
  python -m src.cli.export_longform world.kraken

  # Export to file
  python -m src.cli.export_longform world.kraken output.md

  # Export specific document ID
  python -m src.cli.export_longform world.kraken --doc-id custom
        """,
    )
    parser.add_argument("database", help="Path to the .kraken database file")
    parser.add_argument(
        "output",
        nargs="?",
        help="Output file path (defaults to stdout if not provided)",
    )
    parser.add_argument(
        "--doc-id",
        default=longform_builder.DOC_ID_DEFAULT,
        help=f"Document ID to export (default: {longform_builder.DOC_ID_DEFAULT})",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Validate database path
    db_path = Path(args.database)
    if not db_path.exists():
        logger.error(f"Database file not found: {db_path}")
        sys.exit(1)

    # Connect to database and export
    db_service = None
    try:
        logger.info(f"Opening database: {db_path}")
        db_service = DatabaseService(str(db_path))
        db_service.connect()

        logger.info(f"Exporting document: {args.doc_id}")
        markdown = longform_builder.export_longform_to_markdown(
            db_service._connection, args.doc_id
        )

        # Output to file or stdout
        if args.output:
            output_path = Path(args.output)
            logger.info(f"Writing to file: {output_path}")
            output_path.write_text(markdown, encoding="utf-8")
            logger.info(f"Export complete: {output_path}")
        else:
            # Output to stdout
            print(markdown)

    except Exception as e:
        logger.error(f"Export failed: {e}")
        if args.verbose:
            raise
        sys.exit(1)
    finally:
        # Ensure database connection is always closed
        if db_service:
            db_service.close()


if __name__ == "__main__":
    main()
