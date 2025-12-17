#!/usr/bin/env python3
"""
Entity Management CLI.

Provides command-line tools for creating, listing, updating, and deleting
entities.

Usage:
    python -m src.cli.entity create --database world.kraken
        --name "Entity Name" --type character
    python -m src.cli.entity list --database world.kraken
    python -m src.cli.entity show --database world.kraken
        --id <entity-id>
    python -m src.cli.entity update --database world.kraken
        --id <entity-id> --name "New Name"
    python -m src.cli.entity delete --database world.kraken
        --id <entity-id>
"""

import sys
import argparse
import logging
from src.services.db_service import DatabaseService
from src.commands.entity_commands import (
    CreateEntityCommand,
    UpdateEntityCommand,
    DeleteEntityCommand,
)
from src.cli.utils import validate_database_path

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def create_entity(args) -> int:
    """Create a new entity."""
    db_service = None
    try:
        db_service = DatabaseService(args.database)
        db_service.connect()

        entity_data = {
            "name": args.name,
            "type": args.type,
        }

        if args.description:
            entity_data["description"] = args.description

        cmd = CreateEntityCommand(entity_data)
        result = cmd.execute(db_service)

        if result.success:
            print(f"✓ Created entity: {result.data['id']}")
            print(f"  Name: {args.name}")
            print(f"  Type: {args.type}")
            return 0
        else:
            print(f"✗ Error: {result.message}")
            return 1

    except Exception as e:
        logger.error(f"Failed to create entity: {e}")
        if args.verbose:
            raise
        return 1
    finally:
        if db_service:
            db_service.close()


def list_entities(args) -> int:
    """List all entities."""
    db_service = None
    try:
        db_service = DatabaseService(args.database)
        db_service.connect()

        entities = db_service.get_all_entities()

        if not entities:
            print("No entities found.")
            return 0

        # Apply filters
        if args.type:
            entities = [e for e in entities if e.type == args.type]

        # Sort by name
        entities.sort(key=lambda e: e.name.lower())

        # Output format
        if args.json:
            import json

            print(json.dumps([e.to_dict() for e in entities], indent=2))
        else:
            print(f"\nFound {len(entities)} {'entity' if len(entities) == 1 else 'entities'}:\n")
            for entity in entities:
                print(f"ID: {entity.id}")
                print(f"  Name: {entity.name}")
                print(f"  Type: {entity.type}")
                if entity.description:
                    desc_preview = (
                        entity.description[:50] + "..."
                        if len(entity.description) > 50
                        else entity.description
                    )
                    print(f"  Description: {desc_preview}")
                print()

        return 0

    except Exception as e:
        logger.error(f"Failed to list entities: {e}")
        if args.verbose:
            raise
        return 1
    finally:
        if db_service:
            db_service.close()


def show_entity(args) -> int:
    """Show detailed information about a specific entity."""
    db_service = None
    try:
        db_service = DatabaseService(args.database)
        db_service.connect()

        entity = db_service.get_entity(args.id)

        if not entity:
            print(f"✗ Entity not found: {args.id}")
            return 1

        # Output format
        if args.json:
            import json

            print(json.dumps(entity.to_dict(), indent=2))
        else:
            print("\nEntity Details:\n")
            print(f"ID: {entity.id}")
            print(f"Name: {entity.name}")
            print(f"Type: {entity.type}")
            print("\nDescription:")
            print(entity.description if entity.description else "(none)")
            print("\nAttributes:")
            if entity.attributes:
                import json

                print(json.dumps(entity.attributes, indent=2))
            else:
                print("(none)")
            print(f"\nCreated: {entity.created_at}")
            print(f"Modified: {entity.modified_at}")

            # Show relations if requested
            if args.relations:
                print("\n--- Relations ---")
                outgoing = db_service.get_relations(args.id)
                incoming = db_service.get_incoming_relations(args.id)

                if outgoing:
                    print(f"\nOutgoing ({len(outgoing)}):")
                    for rel in outgoing:
                        target_name = db_service.get_name(rel["target_id"])
                        target_id_short = rel['target_id'][:8]
                        print(
                            f"  → {target_name} ({rel['rel_type']}) "
                            f"[{target_id_short}...]"
                        )

                if incoming:
                    print(f"\nIncoming ({len(incoming)}):")
                    for rel in incoming:
                        source_name = db_service.get_name(rel["source_id"])
                        source_id_short = rel['source_id'][:8]
                        print(
                            f"  ← {source_name} ({rel['rel_type']}) "
                            f"[{source_id_short}...]"
                        )

                if not outgoing and not incoming:
                    print("  (no relations)")

        return 0

    except Exception as e:
        logger.error(f"Failed to show entity: {e}")
        if args.verbose:
            raise
        return 1
    finally:
        if db_service:
            db_service.close()


def update_entity(args) -> int:
    """Update an existing entity."""
    db_service = None
    try:
        db_service = DatabaseService(args.database)
        db_service.connect()

        # Check if entity exists
        entity = db_service.get_entity(args.id)
        if not entity:
            print(f"✗ Entity not found: {args.id}")
            return 1

        # Build update data
        update_data = {}
        if args.name:
            update_data["name"] = args.name
        if args.type:
            update_data["type"] = args.type
        if args.description is not None:
            update_data["description"] = args.description

        if not update_data:
            print("✗ No updates specified. Use --name, --type, --description")
            return 1

        cmd = UpdateEntityCommand(args.id, update_data)
        result = cmd.execute(db_service)

        if result.success:
            print(f"✓ Updated entity: {args.id}")
            for key, value in update_data.items():
                print(f"  {key}: {value}")
            return 0
        else:
            print(f"✗ Error: {result.message}")
            return 1

    except Exception as e:
        logger.error(f"Failed to update entity: {e}")
        if args.verbose:
            raise
        return 1
    finally:
        if db_service:
            db_service.close()


def delete_entity(args) -> int:
    """Delete an entity."""
    db_service = None
    try:
        db_service = DatabaseService(args.database)
        db_service.connect()

        # Check if entity exists
        entity = db_service.get_entity(args.id)
        if not entity:
            print(f"✗ Entity not found: {args.id}")
            return 1

        # Confirm deletion unless --force
        if not args.force:
            print(f"About to delete entity: {entity.name} ({args.id})")
            response = input("Are you sure? (yes/no): ")
            if response.lower() not in ["yes", "y"]:
                print("Deletion cancelled.")
                return 0

        cmd = DeleteEntityCommand(args.id)
        result = cmd.execute(db_service)

        if result.success:
            print(f"✓ Deleted entity: {args.id}")
            return 0
        else:
            print(f"✗ Error: {result.message}")
            return 1

    except Exception as e:
        logger.error(f"Failed to delete entity: {e}")
        if args.verbose:
            raise
        return 1
    finally:
        if db_service:
            db_service.close()


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Manage ProjektKraken entities",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Create command
    create_parser = subparsers.add_parser("create", help="Create a new entity")
    create_parser.add_argument(
        "--database", "-d", required=True, help="Path to .kraken database file"
    )
    create_parser.add_argument("--name", "-n", required=True, help="Entity name")
    create_parser.add_argument(
        "--type",
        "-t",
        required=True,
        help="Entity type (e.g., character, location, faction)",
    )
    create_parser.add_argument("--description", help="Entity description")
    create_parser.set_defaults(func=create_entity)

    # List command
    list_parser = subparsers.add_parser("list", help="List all entities")
    list_parser.add_argument(
        "--database", "-d", required=True, help="Path to .kraken database file"
    )
    list_parser.add_argument("--type", "-t", help="Filter by entity type")
    list_parser.add_argument("--json", action="store_true", help="Output as JSON")
    list_parser.set_defaults(func=list_entities)

    # Show command
    show_parser = subparsers.add_parser("show", help="Show entity details")
    show_parser.add_argument(
        "--database", "-d", required=True, help="Path to .kraken database file"
    )
    show_parser.add_argument("--id", required=True, help="Entity ID")
    show_parser.add_argument("--json", action="store_true", help="Output as JSON")
    show_parser.add_argument(
        "--relations", "-r", action="store_true", help="Show relations"
    )
    show_parser.set_defaults(func=show_entity)

    # Update command
    update_parser = subparsers.add_parser("update", help="Update an entity")
    update_parser.add_argument(
        "--database", "-d", required=True, help="Path to .kraken database file"
    )
    update_parser.add_argument("--id", required=True, help="Entity ID")
    update_parser.add_argument("--name", "-n", help="New entity name")
    update_parser.add_argument("--type", "-t", help="New entity type")
    update_parser.add_argument("--description", help="New description")
    update_parser.set_defaults(func=update_entity)

    # Delete command
    delete_parser = subparsers.add_parser("delete", help="Delete an entity")
    delete_parser.add_argument(
        "--database", "-d", required=True, help="Path to .kraken database file"
    )
    delete_parser.add_argument("--id", required=True, help="Entity ID")
    delete_parser.add_argument(
        "--force", "-f", action="store_true", help="Skip confirmation"
    )
    delete_parser.set_defaults(func=delete_entity)

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Validate database path
    if hasattr(args, "database"):
        # Note: Create operations can work with non-existent databases
        # as DatabaseService will create them automatically
        allow_create = args.command == "create"
        if not validate_database_path(args.database, allow_create=allow_create):
            sys.exit(1)

    # Execute command
    if hasattr(args, "func"):
        sys.exit(args.func(args))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
