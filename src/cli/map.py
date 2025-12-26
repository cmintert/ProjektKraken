#!/usr/bin/env python3
"""
Map Management CLI.

Provides command-line tools for creating, listing, updating, and deleting
maps and markers.

Usage:
    python -m src.cli.map create --database world.kraken --name "World Map"
    python -m src.cli.map list --database world.kraken
    python -m src.cli.map marker-add --database world.kraken --map-id <id> ...
"""

import argparse
import logging
import sys

from src.cli.utils import validate_database_path
from src.commands.map_commands import (
    CreateMapCommand,
    CreateMarkerCommand,
    DeleteMapCommand,
    DeleteMarkerCommand,
    UpdateMapCommand,
    UpdateMarkerCommand,
)
from src.services.db_service import DatabaseService

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def create_map(args) -> int:
    """Create a new map."""
    db_service = None
    try:
        db_service = DatabaseService(args.database)
        db_service.connect()

        map_data = {"name": args.name}
        if args.image:
            map_data["image_path"] = args.image

        cmd = CreateMapCommand(map_data)
        result = cmd.execute(db_service)

        if result.success:
            print(f"✓ Created map: {result.data['id']}")
            print(f"  Name: {args.name}")
            return 0
        else:
            print(f"✗ Error: {result.message}")
            return 1

    except Exception as e:
        logger.error(f"Failed to create map: {e}")
        if args.verbose:
            raise
        return 1
    finally:
        if db_service:
            db_service.close()


def list_maps(args) -> int:
    """List all maps."""
    db_service = None
    try:
        db_service = DatabaseService(args.database)
        db_service.connect()

        maps = db_service.get_all_maps()

        if args.json:
            import json

            print(json.dumps([m.to_dict() for m in maps], indent=2))
        else:
            print(f"\nFound {len(maps)} map(s):\n")
            for m in maps:
                print(f"ID: {m.id}")
                print(f"  Name: {m.name}")
                print(f"  Image: {m.image_path}")
                print()

        return 0

    except Exception as e:
        logger.error(f"Failed to list maps: {e}")
        if args.verbose:
            raise
        return 1
    finally:
        if db_service:
            db_service.close()


def delete_map(args) -> int:
    """Delete a map."""
    db_service = None
    try:
        db_service = DatabaseService(args.database)
        db_service.connect()

        if not args.force:
            m = db_service.get_map(args.id)
            if not m:
                print(f"Map not found: {args.id}")
                return 1
            print(f"About to delete map: {m.name} ({args.id})")
            if input("Are you sure? (y/n): ").lower() != "y":
                return 0

        cmd = DeleteMapCommand(args.id)
        result = cmd.execute(db_service)

        if result.success:
            print(f"✓ Deleted map: {args.id}")
            return 0
        else:
            print(f"✗ Error: {result.message}")
            return 1

    except Exception as e:
        logger.error(f"Failed to delete map: {e}")
        if args.verbose:
            raise
        return 1
    finally:
        if db_service:
            db_service.close()


def add_marker(args) -> int:
    """Add a marker to a map."""
    db_service = None
    try:
        db_service = DatabaseService(args.database)
        db_service.connect()

        marker_data = {
            "map_id": args.map_id,
            "object_id": args.object_id,
            "object_type": args.object_type,
            "x": args.x,
            "y": args.y,
        }

        if args.label:
            marker_data["label"] = args.label

        # Extended attributes
        attributes = {}
        if args.color:
            attributes["color"] = args.color
        if args.icon:
            attributes["icon"] = args.icon

        if attributes:
            marker_data["attributes"] = attributes

        cmd = CreateMarkerCommand(marker_data)
        result = cmd.execute(db_service)

        if result.success:
            print(f"✓ Added marker: {result.data['id']}")
            return 0
        else:
            print(f"✗ Error: {result.message}")
            return 1

    except Exception as e:
        logger.error(f"Failed to add marker: {e}")
        if args.verbose:
            raise
        return 1
    finally:
        if db_service:
            db_service.close()


def update_map(args) -> int:
    """Update an existing map."""
    db_service = None
    try:
        db_service = DatabaseService(args.database)
        db_service.connect()

        update_data = {}
        if args.name:
            update_data["name"] = args.name
        if args.image is not None:
            update_data["image_path"] = args.image

        if not update_data:
            print("✗ No updates specified. Use --name or --image.")
            return 1

        cmd = UpdateMapCommand(args.id, update_data)
        result = cmd.execute(db_service)

        if result.success:
            print(f"✓ Updated map: {args.id}")
            return 0
        else:
            print(f"✗ Error: {result.message}")
            return 1

    except Exception as e:
        logger.error(f"Failed to update map: {e}")
        if args.verbose:
            raise
        return 1
    finally:
        if db_service:
            db_service.close()


def marker_update(args) -> int:
    """Update an existing marker."""
    db_service = None
    try:
        db_service = DatabaseService(args.database)
        db_service.connect()

        update_data = {}
        if args.x is not None:
            update_data["x"] = args.x
        if args.y is not None:
            update_data["y"] = args.y
        if args.label is not None:
            update_data["label"] = args.label

        # Attributes
        attributes = {}
        if args.color is not None:
            attributes["color"] = args.color
        if args.icon is not None:
            attributes["icon"] = args.icon

        if attributes:
            update_data["attributes"] = attributes

        if not update_data:
            print("✗ No updates specified.")
            return 1

        cmd = UpdateMarkerCommand(args.id, update_data)
        result = cmd.execute(db_service)

        if result.success:
            print(f"✓ Updated marker: {args.id}")
            return 0
        else:
            print(f"✗ Error: {result.message}")
            return 1

    except Exception as e:
        logger.error(f"Failed to update marker: {e}")
        if args.verbose:
            raise
        return 1
    finally:
        if db_service:
            db_service.close()


def marker_delete(args) -> int:
    """Delete a marker."""
    db_service = None
    try:
        db_service = DatabaseService(args.database)
        db_service.connect()

        if not args.force:
            m = db_service.get_marker(args.id)
            if not m:
                print(f"Marker not found: {args.id}")
                return 1
            print(f"About to delete marker: {m.label or m.id} ({args.id})")
            if input("Are you sure? (y/n): ").lower() != "y":
                return 0

        cmd = DeleteMarkerCommand(args.id)
        result = cmd.execute(db_service)

        if result.success:
            print(f"✓ Deleted marker: {args.id}")
            return 0
        else:
            print(f"✗ Error: {result.message}")
            return 1

    except Exception as e:
        logger.error(f"Failed to delete marker: {e}")
        if args.verbose:
            raise
        return 1
    finally:
        if db_service:
            db_service.close()


def marker_list(args) -> int:
    """List markers for a map."""
    db_service = None
    try:
        db_service = DatabaseService(args.database)
        db_service.connect()

        markers = db_service.get_markers_for_map(args.map_id)

        if args.json:
            import json

            print(json.dumps([m.to_dict() for m in markers], indent=2))
        else:
            print(f"\nFound {len(markers)} marker(s) for map {args.map_id}:\n")
            for m in markers:
                print(f"ID: {m.id}")
                print(f"  Object: {m.object_type} {m.object_id}")
                print(f"  Pos: ({m.x}, {m.y})")
                if m.label:
                    print(f"  Label: {m.label}")
                if m.attributes:
                    print(f"  Attributes: {m.attributes}")
                print()

        return 0

    except Exception as e:
        logger.error(f"Failed to list markers: {e}")
        if args.verbose:
            raise
        return 1
    finally:
        if db_service:
            db_service.close()


def main():
    """Main entry point for the map CLI tool."""
    parser = argparse.ArgumentParser(description="Manage ProjektKraken maps")
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Map Create
    create_p = subparsers.add_parser("create", help="Create a new map")
    create_p.add_argument("--database", "-d", required=True)
    create_p.add_argument("--name", "-n", required=True)
    create_p.add_argument("--image", "-i", help="Path to image file")
    create_p.set_defaults(func=create_map)

    # Map List
    list_p = subparsers.add_parser("list", help="List all maps")
    list_p.add_argument("--database", "-d", required=True)
    list_p.add_argument("--json", action="store_true")
    list_p.set_defaults(func=list_maps)

    # Map Update
    update_p = subparsers.add_parser("update", help="Update a map")
    update_p.add_argument("--database", "-d", required=True)
    update_p.add_argument("--id", required=True)
    update_p.add_argument("--name", "-n")
    update_p.add_argument("--image", "-i", help="Path to image file")
    update_p.set_defaults(func=update_map)

    # Map Delete
    del_p = subparsers.add_parser("delete", help="Delete a map")
    del_p.add_argument("--database", "-d", required=True)
    del_p.add_argument("--id", required=True)
    del_p.add_argument("--force", "-f", action="store_true")
    del_p.set_defaults(func=delete_map)

    # Marker Add
    marker_add_p = subparsers.add_parser("marker-add", help="Add marker to map")
    marker_add_p.add_argument("--database", "-d", required=True)
    marker_add_p.add_argument("--map-id", required=True)
    marker_add_p.add_argument("--object-id", required=True)
    marker_add_p.add_argument(
        "--object-type", required=True, choices=["entity", "event"]
    )
    marker_add_p.add_argument("--x", type=float, required=True)
    marker_add_p.add_argument("--y", type=float, required=True)
    marker_add_p.add_argument("--label")
    marker_add_p.add_argument("--color")
    marker_add_p.add_argument("--icon")
    marker_add_p.set_defaults(func=add_marker)

    # Marker Update
    marker_upd_p = subparsers.add_parser("marker-update", help="Update marker")
    marker_upd_p.add_argument("--database", "-d", required=True)
    marker_upd_p.add_argument("--id", required=True)
    marker_upd_p.add_argument("--x", type=float)
    marker_upd_p.add_argument("--y", type=float)
    marker_upd_p.add_argument("--label")
    marker_upd_p.add_argument("--color")
    marker_upd_p.add_argument("--icon")
    marker_upd_p.set_defaults(func=marker_update)

    # Marker Delete
    marker_del_p = subparsers.add_parser("marker-delete", help="Delete marker")
    marker_del_p.add_argument("--database", "-d", required=True)
    marker_del_p.add_argument("--id", required=True)
    marker_del_p.add_argument("--force", "-f", action="store_true")
    marker_del_p.set_defaults(func=marker_delete)

    # Marker List
    marker_list_p = subparsers.add_parser("marker-list", help="List markers for map")
    marker_list_p.add_argument("--database", "-d", required=True)
    marker_list_p.add_argument("--map-id", required=True)
    marker_list_p.add_argument("--json", action="store_true")
    marker_list_p.set_defaults(func=marker_list)

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if hasattr(args, "database"):
        if not validate_database_path(
            args.database, allow_create=(args.command == "create")
        ):
            sys.exit(1)

    if hasattr(args, "func"):
        sys.exit(args.func(args))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
