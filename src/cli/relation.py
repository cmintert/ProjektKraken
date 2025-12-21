#!/usr/bin/env python3
"""
Relation Management CLI.

Provides command-line tools for creating, listing, and deleting relations
between events and entities.

Usage:
    python -m src.cli.relation add --database world.kraken
        --source <id> --target <id> --type "caused"
    python -m src.cli.relation list --database world.kraken
        --source <id>
    python -m src.cli.relation delete --database world.kraken
        --id <relation-id>
"""

import argparse
import logging
import sys

from src.cli.utils import validate_database_path
from src.commands.relation_commands import (
    AddRelationCommand,
    RemoveRelationCommand,
    UpdateRelationCommand,
)
from src.services.db_service import DatabaseService

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def add_relation(args) -> int:
    """Add a relation between two entities/events."""
    db_service = None
    try:
        db_service = DatabaseService(args.database)
        db_service.connect()

        # Verify source exists
        source_name = db_service.get_name(args.source)
        if not source_name:
            print(f"✗ Source not found: {args.source}")
            return 1

        # Verify target exists
        target_name = db_service.get_name(args.target)
        if not target_name:
            print(f"✗ Target not found: {args.target}")
            return 1

        cmd = AddRelationCommand(
            args.source, args.target, args.type, bidirectional=args.bidirectional
        )
        result = cmd.execute(db_service)

        if result:
            source_short = args.source[:8]
            target_short = args.target[:8]
            print("✓ Added relation:")
            print(f"  Source: {source_name} ({source_short}...)")
            print(f"  Target: {target_name} ({target_short}...)")
            print(f"  Type: {args.type}")
            if args.bidirectional:
                print("  (bidirectional)")
            return 0
        else:
            print("✗ Failed to add relation")
            return 1

    except Exception as e:
        logger.error(f"Failed to add relation: {e}")
        if args.verbose:
            raise
        return 1
    finally:
        if db_service:
            db_service.close()


def list_relations(args) -> int:
    """List relations for an entity/event."""
    db_service = None
    try:
        db_service = DatabaseService(args.database)
        db_service.connect()

        # Verify source exists
        source_name = db_service.get_name(args.source)
        if not source_name:
            print(f"✗ Source not found: {args.source}")
            return 1

        # Get relations
        outgoing = db_service.get_relations(args.source)
        incoming = db_service.get_incoming_relations(args.source)

        if args.json:
            import json

            print(json.dumps({"outgoing": outgoing, "incoming": incoming}, indent=2))
        else:
            print(f"\nRelations for: {source_name} ({args.source[:8]}...)\n")

            if outgoing:
                print(f"Outgoing ({len(outgoing)}):")
                for rel in outgoing:
                    target_name = db_service.get_name(rel["target_id"])
                    print(f"  → {target_name}")
                    print(f"    Type: {rel['rel_type']}")
                    print(f"    Target ID: {rel['target_id']}")
                    print(f"    Relation ID: {rel['id']}")
                    print()

            if incoming:
                print(f"Incoming ({len(incoming)}):")
                for rel in incoming:
                    source_rel_name = db_service.get_name(rel["source_id"])
                    print(f"  ← {source_rel_name}")
                    print(f"    Type: {rel['rel_type']}")
                    print(f"    Source ID: {rel['source_id']}")
                    print(f"    Relation ID: {rel['id']}")
                    print()

            if not outgoing and not incoming:
                print("  No relations found.")

        return 0

    except Exception as e:
        logger.error(f"Failed to list relations: {e}")
        if args.verbose:
            raise
        return 1
    finally:
        if db_service:
            db_service.close()


def delete_relation(args) -> int:
    """Delete a relation."""
    db_service = None
    try:
        db_service = DatabaseService(args.database)
        db_service.connect()

        # Get relation details for confirmation
        relation = db_service.get_relation(args.id)
        if not relation:
            print(f"✗ Relation not found: {args.id}")
            return 1

        # Confirm deletion unless --force
        if not args.force:
            source_name = db_service.get_name(relation["source_id"])
            target_name = db_service.get_name(relation["target_id"])
            rel_type = relation["rel_type"]
            print(
                f"About to delete relation: {source_name} → {target_name} "
                f"({rel_type})"
            )
            response = input("Are you sure? (yes/no): ")
            if response.lower() not in ["yes", "y"]:
                print("Deletion cancelled.")
                return 0

        cmd = RemoveRelationCommand(args.id)
        result = cmd.execute(db_service)

        if result:
            print(f"✓ Deleted relation: {args.id}")
            return 0
        else:
            print("✗ Failed to delete relation")
            return 1

    except Exception as e:
        logger.error(f"Failed to delete relation: {e}")
        if args.verbose:
            raise
        return 1
    finally:
        if db_service:
            db_service.close()


def update_relation(args) -> int:
    """Update an existing relation."""
    db_service = None
    try:
        db_service = DatabaseService(args.database)
        db_service.connect()

        # Check if relation exists
        relation = db_service.get_relation(args.id)
        if not relation:
            print(f"✗ Relation not found: {args.id}")
            return 1

        target_id = args.target if args.target else relation["target_id"]
        rel_type = args.type if args.type else relation["rel_type"]

        # Attributes
        attributes = relation.get("attributes", {}).copy()
        if args.attr:
            for kv in args.attr:
                if "=" in kv:
                    k, v = kv.split("=", 1)
                    attributes[k] = v

        cmd = UpdateRelationCommand(args.id, target_id, rel_type, attributes)
        result = cmd.execute(db_service)

        if result:
            print(f"✓ Updated relation: {args.id}")
            return 0
        else:
            print("✗ Failed to update relation")
            return 1

    except Exception as e:
        logger.error(f"Failed to update relation: {e}")
        if args.verbose:
            raise
        return 1
    finally:
        if db_service:
            db_service.close()


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Manage ProjektKraken relations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Add command
    add_parser = subparsers.add_parser("add", help="Add a new relation")
    add_parser.add_argument(
        "--database", "-d", required=True, help="Path to .kraken database file"
    )
    add_parser.add_argument(
        "--source", "-s", required=True, help="Source entity/event ID"
    )
    add_parser.add_argument(
        "--target", "-t", required=True, help="Target entity/event ID"
    )
    add_parser.add_argument(
        "--type", required=True, help="Relation type (e.g., 'caused', 'located_in')"
    )
    add_parser.add_argument(
        "--bidirectional",
        "-b",
        action="store_true",
        help="Create bidirectional relation",
    )
    add_parser.set_defaults(func=add_relation)

    # List command
    list_parser = subparsers.add_parser(
        "list", help="List relations for an entity/event"
    )
    list_parser.add_argument(
        "--database", "-d", required=True, help="Path to .kraken database file"
    )
    list_parser.add_argument(
        "--source", "-s", required=True, help="Source entity/event ID"
    )
    list_parser.add_argument("--json", action="store_true", help="Output as JSON")
    list_parser.set_defaults(func=list_relations)

    # Update command
    update_parser = subparsers.add_parser("update", help="Update a relation")
    update_parser.add_argument(
        "--database", "-d", required=True, help="Path to .kraken database file"
    )
    update_parser.add_argument("--id", required=True, help="Relation ID")
    update_parser.add_argument("--target", "-t", help="New target ID")
    update_parser.add_argument("--type", help="New relation type")
    update_parser.add_argument(
        "--attr", nargs="*", help="Update attributes (key=value)"
    )
    update_parser.set_defaults(func=update_relation)

    # Delete command
    delete_parser = subparsers.add_parser("delete", help="Delete a relation")
    delete_parser.add_argument(
        "--database", "-d", required=True, help="Path to .kraken database file"
    )
    delete_parser.add_argument("--id", required=True, help="Relation ID")
    delete_parser.add_argument(
        "--force", "-f", action="store_true", help="Skip confirmation"
    )
    delete_parser.set_defaults(func=delete_relation)

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Validate database path (relations always require existing database)
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
