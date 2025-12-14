#!/usr/bin/env python3
"""
Event Management CLI.

Provides command-line tools for creating, listing, updating, and deleting events.

Usage:
    python -m src.cli.event create --database world.kraken --name "Event Name" --date 100.5
    python -m src.cli.event list --database world.kraken
    python -m src.cli.event show --database world.kraken --id <event-id>
    python -m src.cli.event update --database world.kraken --id <event-id> --name "New Name"
    python -m src.cli.event delete --database world.kraken --id <event-id>
"""

import sys
import argparse
import logging
from pathlib import Path
from typing import Optional
from src.services.db_service import DatabaseService
from src.commands.event_commands import (
    CreateEventCommand,
    UpdateEventCommand,
    DeleteEventCommand,
)
from src.cli.utils import validate_database_path

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def create_event(args) -> int:
    """Create a new event."""
    db_service = None
    try:
        db_service = DatabaseService(args.database)
        db_service.connect()

        event_data = {
            "name": args.name,
            "lore_date": args.date,
        }

        if args.type:
            event_data["type"] = args.type
        if args.description:
            event_data["description"] = args.description
        if args.duration:
            event_data["lore_duration"] = args.duration

        cmd = CreateEventCommand(event_data)
        result = cmd.execute(db_service)

        if result.success:
            print(f"✓ Created event: {result.data['id']}")
            print(f"  Name: {args.name}")
            print(f"  Date: {args.date}")
            return 0
        else:
            print(f"✗ Error: {result.message}")
            return 1

    except Exception as e:
        logger.error(f"Failed to create event: {e}")
        if args.verbose:
            raise
        return 1
    finally:
        if db_service:
            db_service.close()


def list_events(args) -> int:
    """List all events."""
    db_service = None
    try:
        db_service = DatabaseService(args.database)
        db_service.connect()

        events = db_service.get_all_events()

        if not events:
            print("No events found.")
            return 0

        # Apply filters
        if args.type:
            events = [e for e in events if e.type == args.type]

        # Sort
        events.sort(key=lambda e: e.lore_date)

        # Output format
        if args.json:
            import json

            print(json.dumps([e.to_dict() for e in events], indent=2))
        else:
            print(f"\nFound {len(events)} event(s):\n")
            for event in events:
                print(f"ID: {event.id}")
                print(f"  Name: {event.name}")
                print(f"  Date: {event.lore_date}")
                print(f"  Type: {event.type}")
                if event.description:
                    desc_preview = (
                        event.description[:50] + "..."
                        if len(event.description) > 50
                        else event.description
                    )
                    print(f"  Description: {desc_preview}")
                print()

        return 0

    except Exception as e:
        logger.error(f"Failed to list events: {e}")
        if args.verbose:
            raise
        return 1
    finally:
        if db_service:
            db_service.close()


def show_event(args) -> int:
    """Show detailed information about a specific event."""
    db_service = None
    try:
        db_service = DatabaseService(args.database)
        db_service.connect()

        event = db_service.get_event(args.id)

        if not event:
            print(f"✗ Event not found: {args.id}")
            return 1

        # Output format
        if args.json:
            import json

            print(json.dumps(event.to_dict(), indent=2))
        else:
            print(f"\nEvent Details:\n")
            print(f"ID: {event.id}")
            print(f"Name: {event.name}")
            print(f"Type: {event.type}")
            print(f"Date: {event.lore_date}")
            print(f"Duration: {event.lore_duration}")
            print(f"\nDescription:")
            print(event.description if event.description else "(none)")
            print(f"\nAttributes:")
            if event.attributes:
                import json

                print(json.dumps(event.attributes, indent=2))
            else:
                print("(none)")
            print(f"\nCreated: {event.created_at}")
            print(f"Modified: {event.modified_at}")

        return 0

    except Exception as e:
        logger.error(f"Failed to show event: {e}")
        if args.verbose:
            raise
        return 1
    finally:
        if db_service:
            db_service.close()


def update_event(args) -> int:
    """Update an existing event."""
    db_service = None
    try:
        db_service = DatabaseService(args.database)
        db_service.connect()

        # Check if event exists
        event = db_service.get_event(args.id)
        if not event:
            print(f"✗ Event not found: {args.id}")
            return 1

        # Build update data
        update_data = {}
        if args.name:
            update_data["name"] = args.name
        if args.date is not None:
            update_data["lore_date"] = args.date
        if args.type:
            update_data["type"] = args.type
        if args.description is not None:
            update_data["description"] = args.description
        if args.duration is not None:
            update_data["lore_duration"] = args.duration

        if not update_data:
            print("✗ No updates specified. Use --name, --date, --type, etc.")
            return 1

        cmd = UpdateEventCommand(args.id, update_data)
        result = cmd.execute(db_service)

        if result.success:
            print(f"✓ Updated event: {args.id}")
            for key, value in update_data.items():
                print(f"  {key}: {value}")
            return 0
        else:
            print(f"✗ Error: {result.message}")
            return 1

    except Exception as e:
        logger.error(f"Failed to update event: {e}")
        if args.verbose:
            raise
        return 1
    finally:
        if db_service:
            db_service.close()


def delete_event(args) -> int:
    """Delete an event."""
    db_service = None
    try:
        db_service = DatabaseService(args.database)
        db_service.connect()

        # Check if event exists
        event = db_service.get_event(args.id)
        if not event:
            print(f"✗ Event not found: {args.id}")
            return 1

        # Confirm deletion unless --force
        if not args.force:
            print(f"About to delete event: {event.name} ({args.id})")
            response = input("Are you sure? (yes/no): ")
            if response.lower() not in ["yes", "y"]:
                print("Deletion cancelled.")
                return 0

        cmd = DeleteEventCommand(args.id)
        result = cmd.execute(db_service)

        if result.success:
            print(f"✓ Deleted event: {args.id}")
            return 0
        else:
            print(f"✗ Error: {result.message}")
            return 1

    except Exception as e:
        logger.error(f"Failed to delete event: {e}")
        if args.verbose:
            raise
        return 1
    finally:
        if db_service:
            db_service.close()


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Manage ProjektKraken events",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Create command
    create_parser = subparsers.add_parser("create", help="Create a new event")
    create_parser.add_argument(
        "--database", "-d", required=True, help="Path to .kraken database file"
    )
    create_parser.add_argument("--name", "-n", required=True, help="Event name")
    create_parser.add_argument(
        "--date", type=float, required=True, help="Lore date (float)"
    )
    create_parser.add_argument("--type", "-t", help="Event type (e.g., historical)")
    create_parser.add_argument("--description", help="Event description")
    create_parser.add_argument(
        "--duration", type=float, help="Event duration (float)"
    )
    create_parser.set_defaults(func=create_event)

    # List command
    list_parser = subparsers.add_parser("list", help="List all events")
    list_parser.add_argument(
        "--database", "-d", required=True, help="Path to .kraken database file"
    )
    list_parser.add_argument("--type", "-t", help="Filter by event type")
    list_parser.add_argument("--json", action="store_true", help="Output as JSON")
    list_parser.set_defaults(func=list_events)

    # Show command
    show_parser = subparsers.add_parser("show", help="Show event details")
    show_parser.add_argument(
        "--database", "-d", required=True, help="Path to .kraken database file"
    )
    show_parser.add_argument("--id", required=True, help="Event ID")
    show_parser.add_argument("--json", action="store_true", help="Output as JSON")
    show_parser.set_defaults(func=show_event)

    # Update command
    update_parser = subparsers.add_parser("update", help="Update an event")
    update_parser.add_argument(
        "--database", "-d", required=True, help="Path to .kraken database file"
    )
    update_parser.add_argument("--id", required=True, help="Event ID")
    update_parser.add_argument("--name", "-n", help="New event name")
    update_parser.add_argument("--date", type=float, help="New lore date")
    update_parser.add_argument("--type", "-t", help="New event type")
    update_parser.add_argument("--description", help="New description")
    update_parser.add_argument("--duration", type=float, help="New duration")
    update_parser.set_defaults(func=update_event)

    # Delete command
    delete_parser = subparsers.add_parser("delete", help="Delete an event")
    delete_parser.add_argument(
        "--database", "-d", required=True, help="Path to .kraken database file"
    )
    delete_parser.add_argument("--id", required=True, help="Event ID")
    delete_parser.add_argument(
        "--force", "-f", action="store_true", help="Skip confirmation"
    )
    delete_parser.set_defaults(func=delete_event)

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
