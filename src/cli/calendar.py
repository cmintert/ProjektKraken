"""
CLI for managing calendar configurations.
"""

import argparse
import logging
import sys
import uuid
from typing import List

from src.cli.utils import validate_database_path
from src.core.calendar import (
    CalendarConfig,
    MonthDefinition,
    WeekDefinition,
)
from src.commands.calendar_commands import (
    CreateCalendarConfigCommand,
    DeleteCalendarConfigCommand,
    SetActiveCalendarCommand,
)
from src.services.db_service import DatabaseService

logger = logging.getLogger(__name__)


def create_calendar(args) -> int:
    """Create a new calendar configuration."""
    db_service = None
    try:
        db_service = DatabaseService(args.database)
        db_service.connect()

        # Parse months: "Name:Days,Name:Days"
        months: List[MonthDefinition] = []
        if args.months:
            for m_str in args.months.split(","):
                if ":" not in m_str:
                    print(f"✗ Invalid month format: {m_str}. Use Name:Days")
                    return 1
                name, days = m_str.split(":", 1)
                months.append(
                    MonthDefinition(
                        name=name.strip(),
                        abbreviation=name[:3].strip(),
                        days=int(days.strip()),
                    )
                )
        else:
            # Default structure if not provided
            months = [
                MonthDefinition(name=f"Month {i+1}", abbreviation=f"M{i+1}", days=30)
                for i in range(12)
            ]

        # Parse week: "Day,Day,Day"
        if args.week:
            day_names = [d.strip() for d in args.week.split(",")]
            week = WeekDefinition(
                day_names=day_names,
                day_abbreviations=[d[:3] for d in day_names],
            )
        else:
            week = WeekDefinition(
                day_names=[
                    "Day 1",
                    "Day 2",
                    "Day 3",
                    "Day 4",
                    "Day 5",
                    "Day 6",
                    "Day 7",
                ],
                day_abbreviations=["D1", "D2", "D3", "D4", "D5", "D6", "D7"],
            )

        config = CalendarConfig(
            id=str(uuid.uuid4()),
            name=args.name,
            months=months,
            week=week,
            year_variants=[],
            epoch_name=args.epoch or "Year",
        )

        errors = config.validate()
        if errors:
            for err in errors:
                print(f"✗ Validation error: {err}")
            return 1

        cmd = CreateCalendarConfigCommand(config)
        result = cmd.execute(db_service)

        if result.success:
            print(f"✓ Created calendar: {config.id}")
            print(f"  Name: {config.name}")
            return 0
        else:
            print(f"✗ Error: {result.message}")
            return 1

    except Exception as e:
        logger.error(f"Failed to create calendar: {e}")
        if args.verbose:
            raise
        return 1
    finally:
        if db_service:
            db_service.close()


def list_calendars(args) -> int:
    """List all calendar configurations."""
    db_service = None
    try:
        db_service = DatabaseService(args.database)
        db_service.connect()

        configs = db_service.get_all_calendar_configs()

        if args.json:
            import json

            print(json.dumps([c.to_dict() for c in configs], indent=2))
        else:
            print(f"\nFound {len(configs)} calendar(s):\n")
            for c in configs:
                active_str = " (ACTIVE)" if c.is_active else ""
                print(f"ID: {c.id}{active_str}")
                print(f"  Name: {c.name}")
                print(f"  Epoch: {c.epoch_name}")
                print(f"  Months: {len(c.months)}")
                print()

        return 0
    except Exception as e:
        logger.error(f"Failed to list calendars: {e}")
        return 1
    finally:
        if db_service:
            db_service.close()


def show_calendar(args) -> int:
    """Show details of a calendar configuration."""
    db_service = None
    try:
        db_service = DatabaseService(args.database)
        db_service.connect()

        config = db_service.get_calendar_config(args.id)
        if not config:
            print(f"✗ Calendar not found: {args.id}")
            return 1

        if args.json:
            import json

            print(json.dumps(config.to_dict(), indent=2))
        else:
            print(f"\nCalendar: {config.name} ({config.id})")
            if config.is_active:
                print("*** ACTIVE CALENDAR ***")
            print(f"Epoch: {config.epoch_name}")
            print("\nMonths:")
            for i, m in enumerate(config.months):
                print(f"  {i+1}. {m.name} ({m.days} days)")
            print("\nWeek Days:")
            print(f"  {', '.join(config.week.day_names)}")

        return 0
    except Exception as e:
        logger.error(f"Failed to show calendar: {e}")
        return 1
    finally:
        if db_service:
            db_service.close()


def set_active_calendar(args) -> int:
    """Set a calendar configuration as active."""
    db_service = None
    try:
        db_service = DatabaseService(args.database)
        db_service.connect()

        cmd = SetActiveCalendarCommand(args.id)
        result = cmd.execute(db_service)

        if result.success:
            print(f"✓ Calendar {args.id} is now active.")
            return 0
        else:
            print(f"✗ Error: {result.message}")
            return 1
    except Exception as e:
        logger.error(f"Failed to set active calendar: {e}")
        return 1
    finally:
        if db_service:
            db_service.close()


def delete_calendar(args) -> int:
    """Delete a calendar configuration."""
    db_service = None
    try:
        db_service = DatabaseService(args.database)
        db_service.connect()

        if not args.force:
            c = db_service.get_calendar_config(args.id)
            if not c:
                print(f"✗ Calendar not found: {args.id}")
                return 1
            print(f"About to delete calendar: {c.name} ({args.id})")
            if input("Are you sure? (y/n): ").lower() != "y":
                return 0

        cmd = DeleteCalendarConfigCommand(args.id)
        result = cmd.execute(db_service)

        if result.success:
            print(f"✓ Deleted calendar: {args.id}")
            return 0
        else:
            print(f"✗ Error: {result.message}")
            return 1
    except Exception as e:
        logger.error(f"Failed to delete calendar: {e}")
        return 1
    finally:
        if db_service:
            db_service.close()


def main():
    parser = argparse.ArgumentParser(description="Manage ProjektKraken calendars")
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    subparsers = parser.add_subparsers(dest="command", help="Subcommands")

    # Create
    create_p = subparsers.add_parser("create", help="Create a new calendar")
    create_p.add_argument("--database", "-d", required=True)
    create_p.add_argument("--name", "-n", required=True)
    create_p.add_argument("--months", help="Month definitions (Name:Days,Name:Days)")
    create_p.add_argument("--week", help="Week day names (Day1,Day2,...)")
    create_p.add_argument("--epoch", help="Epoch name (e.g. DR, AD)")
    create_p.set_defaults(func=create_calendar)

    # List
    list_p = subparsers.add_parser("list", help="List all calendars")
    list_p.add_argument("--database", "-d", required=True)
    list_p.add_argument("--json", action="store_true")
    list_p.set_defaults(func=list_calendars)

    # Show
    show_p = subparsers.add_parser("show", help="Show calendar details")
    show_p.add_argument("--database", "-d", required=True)
    show_p.add_argument("--id", required=True)
    show_p.add_argument("--json", action="store_true")
    show_p.set_defaults(func=show_calendar)

    # Set Active
    active_p = subparsers.add_parser("set-active", help="Set calendar as active")
    active_p.add_argument("--database", "-d", required=True)
    active_p.add_argument("--id", required=True)
    active_p.set_defaults(func=set_active_calendar)

    # Delete
    del_p = subparsers.add_parser("delete", help="Delete a calendar")
    del_p.add_argument("--database", "-d", required=True)
    del_p.add_argument("--id", required=True)
    del_p.add_argument("--force", "-f", action="store_true")
    del_p.set_defaults(func=delete_calendar)

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if not validate_database_path(args.database):
        sys.exit(1)

    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
