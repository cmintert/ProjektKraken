"""
Longform Document Management CLI.

Provides command-line tools for exporting and manipulating the document structure.

Usage:
    python -m src.cli.longform export --database world.kraken
    python -m src.cli.longform move --database world.kraken --table events \
        --id <id> --parent <pid>
"""

import argparse
import logging
import sys
from pathlib import Path

from src.cli.utils import validate_database_path
from src.commands.longform_commands import (
    DemoteLongformEntryCommand,
    MoveLongformEntryCommand,
    PromoteLongformEntryCommand,
    RemoveLongformEntryCommand,
)
from src.services import longform_builder
from src.services.db_service import DatabaseService

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def export_longform(args) -> int:
    """Export longform document."""
    db_service = None
    try:
        db_service = DatabaseService(args.database)
        db_service.connect()

        markdown = longform_builder.export_longform_to_markdown(
            db_service._connection, args.doc_id
        )

        if args.output:
            output_path = Path(args.output)
            output_path.write_text(markdown, encoding="utf-8")
            print(f"✓ Exported to {output_path}")
        else:
            print(markdown)
        return 0

    except Exception as e:
        logger.error(f"Export failed: {e}")
        if args.verbose:
            raise
        return 1
    finally:
        if db_service:
            db_service.close()


def _get_current_meta(db_service, table, row_id, doc_id):
    """Helper to get current longform metadata."""
    # This minimal helper is needed because meta isn't exposed in logic yet.
    # longform_builder has no simple 'get item' returning meta dict.
    # Direct SQL query via db_service connection for now.
    cursor = db_service._connection.cursor()
    cursor.execute(
        "SELECT position, parent_id, depth, title_override FROM longform_structure "
        "WHERE table_name = ? AND row_id = ? AND doc_id = ?",
        (table, row_id, doc_id),
    )
    row = cursor.fetchone()
    if row:
        return {
            "position": row[0],
            "parent_id": row[1],
            "depth": row[2],
            "title_override": row[3],
        }
    return {}


def move_entry(args) -> int:
    """Move a longform entry (or add it if missing)."""
    db_service = None
    try:
        db_service = DatabaseService(args.database)
        db_service.connect()

        # Check if item exists in database at all
        name = db_service.get_name(args.id)
        if not name:
            print(f"✗ Item not found in database: {args.id}")
            return 1

        old_meta = _get_current_meta(db_service, args.table, args.id, args.doc_id)
        # If not in longform, we use empty defaults
        if not old_meta:
            old_meta = {"position": 0, "parent_id": None, "depth": 0}

        new_meta = old_meta.copy()
        if args.parent:
            new_meta["parent_id"] = args.parent if args.parent != "ROOT" else None
        if args.position is not None:
            new_meta["position"] = args.position

        cmd = MoveLongformEntryCommand(
            args.table, args.id, old_meta, new_meta, args.doc_id
        )
        result = cmd.execute(db_service)

        if result.success:
            print(f"✓ Moved/Added entry: {args.id}")
            return 0
        else:
            print(f"✗ Error: {result.message}")
            return 1
    except Exception as e:
        logger.error(f"Failed to move: {e}")
        if args.verbose:
            raise
        return 1
    finally:
        if db_service:
            db_service.close()


def remove_entry(args) -> int:
    """Remove entry from longform."""
    db_service = None
    try:
        db_service = DatabaseService(args.database)
        db_service.connect()

        old_meta = _get_current_meta(db_service, args.table, args.id, args.doc_id)
        if not old_meta:
            print(f"✗ Item not in longform: {args.table}.{args.id}")
            return 1

        cmd = RemoveLongformEntryCommand(args.table, args.id, old_meta, args.doc_id)
        result = cmd.execute(db_service)

        if result.success:
            print(f"✓ Removed entry: {args.id}")
            return 0
        else:
            print(f"✗ Error: {result.message}")
            return 1
    except Exception as e:
        logger.error(f"Failed to remove: {e}")
        return 1
    finally:
        if db_service:
            db_service.close()


def promote_entry(args) -> int:
    """Promote a longform entry (reduce depth)."""
    db_service = None
    try:
        db_service = DatabaseService(args.database)
        db_service.connect()

        old_meta = _get_current_meta(db_service, args.table, args.id, args.doc_id)
        if not old_meta:
            print(f"✗ Item not in longform: {args.table}.{args.id}")
            return 1

        cmd = PromoteLongformEntryCommand(args.table, args.id, old_meta, args.doc_id)
        result = cmd.execute(db_service)

        if result.success:
            print(f"✓ Promoted entry: {args.id}")
            return 0
        else:
            print(f"✗ Error: {result.message}")
            return 1
    except Exception as e:
        logger.error(f"Failed to promote: {e}")
        return 1
    finally:
        if db_service:
            db_service.close()


def demote_entry(args) -> int:
    """Demote a longform entry (increase depth)."""
    db_service = None
    try:
        db_service = DatabaseService(args.database)
        db_service.connect()

        old_meta = _get_current_meta(db_service, args.table, args.id, args.doc_id)
        if not old_meta:
            print(f"✗ Item not in longform: {args.table}.{args.id}")
            return 1

        cmd = DemoteLongformEntryCommand(args.table, args.id, old_meta, args.doc_id)
        result = cmd.execute(db_service)

        if result.success:
            print(f"✓ Demoted entry: {args.id}")
            return 0
        else:
            print(f"✗ Error: {result.message}")
            return 1
    except Exception as e:
        logger.error(f"Failed to demote: {e}")
        return 1
    finally:
        if db_service:
            db_service.close()


def reindex_longform(args) -> int:
    """Reindex all positions in the longform document."""
    db_service = None
    try:
        db_service = DatabaseService(args.database)
        db_service.connect()

        longform_builder.reindex_document_positions(db_service._connection, args.doc_id)
        print("✓ Reindexed longform document positions.")
        return 0
    except Exception as e:
        logger.error(f"Failed to reindex: {e}")
        return 1
    finally:
        if db_service:
            db_service.close()


def main():
    """Main entry point for the longform document CLI tool."""
    parser = argparse.ArgumentParser(
        description="Manage ProjektKraken longform document"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Export
    exp_p = subparsers.add_parser("export", help="Export to Markdown")
    exp_p.add_argument("--database", "-d", required=True)
    exp_p.add_argument("--output", "-o", help="Output file")
    exp_p.add_argument("--doc-id", default="default")
    exp_p.set_defaults(func=export_longform)

    # Move
    mv_p = subparsers.add_parser("move", help="Move an entry")
    mv_p.add_argument("--database", "-d", required=True)
    mv_p.add_argument("--table", required=True, choices=["events", "entities"])
    mv_p.add_argument("--id", required=True)
    mv_p.add_argument("--parent", help="New parent ID (or ROOT)")
    mv_p.add_argument("--position", type=int, help="New position index")
    mv_p.add_argument("--doc-id", default="default")
    mv_p.set_defaults(func=move_entry)

    # Remove
    rm_p = subparsers.add_parser("remove", help="Remove an entry")
    rm_p.add_argument("--database", "-d", required=True)
    rm_p.add_argument("--table", required=True, choices=["events", "entities"])
    rm_p.add_argument("--id", required=True)
    rm_p.add_argument("--doc-id", default="default")
    rm_p.set_defaults(func=remove_entry)

    # Add (Alias for move but ensures item is in longform)
    add_p = subparsers.add_parser("add", help="Add an entry to longform")
    add_p.add_argument("--database", "-d", required=True)
    add_p.add_argument("--table", required=True, choices=["events", "entities"])
    add_p.add_argument("--id", required=True)
    add_p.add_argument("--parent", help="New parent ID (or ROOT)")
    add_p.add_argument("--position", type=int, help="New position index")
    add_p.add_argument("--doc-id", default="default")
    add_p.set_defaults(func=move_entry)

    # Promote
    prom_p = subparsers.add_parser("promote", help="Promote an entry (reduce depth)")
    prom_p.add_argument("--database", "-d", required=True)
    prom_p.add_argument("--table", required=True, choices=["events", "entities"])
    prom_p.add_argument("--id", required=True)
    prom_p.add_argument("--doc-id", default="default")
    prom_p.set_defaults(func=promote_entry)

    # Demote
    dem_p = subparsers.add_parser("demote", help="Demote an entry (increase depth)")
    dem_p.add_argument("--database", "-d", required=True)
    dem_p.add_argument("--table", required=True, choices=["events", "entities"])
    dem_p.add_argument("--id", required=True)
    dem_p.add_argument("--doc-id", default="default")
    dem_p.set_defaults(func=demote_entry)

    # Reindex
    reindex_p = subparsers.add_parser("reindex", help="Reindex all positions")
    reindex_p.add_argument("--database", "-d", required=True)
    reindex_p.add_argument("--doc-id", default="default")
    reindex_p.set_defaults(func=reindex_longform)

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
