"""
CLI for managing image attachments.
"""

import argparse
import logging
import sys

from src.cli.utils import validate_database_path
from src.commands.image_commands import (
    AddImagesCommand,
    RemoveImageCommand,
    ReorderImagesCommand,
    UpdateImageCaptionCommand,
)
from src.services.db_service import DatabaseService

logger = logging.getLogger(__name__)


def add_attachments(args: argparse.Namespace) -> int:
    """Add image attachments to an entity or event."""
    db_service = None
    try:
        db_service = DatabaseService(args.database)
        db_service.connect()

        cmd = AddImagesCommand(args.type, args.id, args.paths)
        result = cmd.execute(db_service)

        if result.success:
            print(f"✓ {result.message}")
            return 0
        else:
            print(f"✗ Error: {result.message}")
            return 1
    except Exception as e:
        logger.error(f"Failed to add attachments: {e}")
        if args.verbose:
            raise
        return 1
    finally:
        if db_service:
            db_service.close()


def remove_attachment(args: argparse.Namespace) -> int:
    """Remove an image attachment."""
    db_service = None
    try:
        db_service = DatabaseService(args.database)
        db_service.connect()

        if not args.force:
            print(f"About to remove attachment: {args.id}")
            if input("Are you sure? (y/n): ").lower() != "y":
                return 0

        cmd = RemoveImageCommand(args.id)
        result = cmd.execute(db_service)

        if result.success:
            print(f"✓ Removed attachment: {args.id}")
            return 0
        else:
            print(f"✗ Error: {result.message}")
            return 1
    except Exception as e:
        logger.error(f"Failed to remove attachment: {e}")
        return 1
    finally:
        if db_service:
            db_service.close()


def list_attachments(args: argparse.Namespace) -> int:
    """List attachments for an entity or event."""
    db_service = None
    try:
        db_service = DatabaseService(args.database)
        db_service.connect()

        if not hasattr(db_service, "attachment_service"):
            print("✗ AttachmentService not available in DatabaseService")
            return 1

        attachments = db_service.attachment_service.get_attachments(args.type, args.id)

        if args.json:
            import json

            print(json.dumps([vars(a) for a in attachments], indent=2, default=str))
        else:
            print(
                f"\nFound {len(attachments)} attachment(s) for {args.type} {args.id}:\n"
            )
            for a in attachments:
                print(f"ID: {a.id}")
                print(f"  Filename: {a.filename}")
                if a.caption:
                    print(f"  Caption: {a.caption}")
                print(f"  Position: {a.position}")
                print()

        return 0
    except Exception as e:
        logger.error(f"Failed to list attachments: {e}")
        return 1
    finally:
        if db_service:
            db_service.close()


def update_caption(args: argparse.Namespace) -> int:
    """Update the caption of an attachment."""
    db_service = None
    try:
        db_service = DatabaseService(args.database)
        db_service.connect()

        cmd = UpdateImageCaptionCommand(args.id, args.caption)
        result = cmd.execute(db_service)

        if result.success:
            print(f"✓ Updated caption for: {args.id}")
            return 0
        else:
            print(f"✗ Error: {result.message}")
            return 1
    except Exception as e:
        logger.error(f"Failed to update caption: {e}")
        return 1
    finally:
        if db_service:
            db_service.close()


def reorder_attachments(args: argparse.Namespace) -> int:
    """Reorder attachments for an owner."""
    db_service = None
    try:
        db_service = DatabaseService(args.database)
        db_service.connect()

        # args.ids should be a comma-separated list of IDs in desired order
        ids = [i.strip() for i in args.ids.split(",")]

        cmd = ReorderImagesCommand(args.type, args.id, ids)
        result = cmd.execute(db_service)

        if result.success:
            print(f"✓ Reordered attachments for {args.type} {args.id}")
            return 0
        else:
            print(f"✗ Error: {result.message}")
            return 1
    except Exception as e:
        logger.error(f"Failed to reorder attachments: {e}")
        return 1
    finally:
        if db_service:
            db_service.close()


def main() -> None:
    """Main entry point for the attachment CLI tool."""
    parser = argparse.ArgumentParser(description="Manage ProjektKraken attachments")
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    subparsers = parser.add_subparsers(dest="command", help="Subcommands")

    # Add
    add_p = subparsers.add_parser("add", help="Add attachments")
    add_p.add_argument("--database", "-d", required=True)
    add_p.add_argument("--type", required=True, choices=["entities", "events"])
    add_p.add_argument("--id", required=True, help="Owner ID")
    add_p.add_argument("paths", nargs="+", help="Paths to image files")
    add_p.set_defaults(func=add_attachments)

    # List
    list_p = subparsers.add_parser("list", help="List attachments")
    list_p.add_argument("--database", "-d", required=True)
    list_p.add_argument("--type", required=True, choices=["entities", "events"])
    list_p.add_argument("--id", required=True, help="Owner ID")
    list_p.add_argument("--json", action="store_true")
    list_p.set_defaults(func=list_attachments)

    # Update Caption
    cap_p = subparsers.add_parser("caption", help="Update attachment caption")
    cap_p.add_argument("--database", "-d", required=True)
    cap_p.add_argument("--id", required=True, help="Attachment ID")
    cap_p.add_argument("--caption", "-c", required=True)
    cap_p.set_defaults(func=update_caption)

    # Reorder
    ord_p = subparsers.add_parser("reorder", help="Reorder attachments")
    ord_p.add_argument("--database", "-d", required=True)
    ord_p.add_argument("--type", required=True, choices=["entities", "events"])
    ord_p.add_argument("--id", required=True, help="Owner ID")
    ord_p.add_argument(
        "--ids", required=True, help="Comma-separated list of IDs in order"
    )
    ord_p.set_defaults(func=reorder_attachments)

    # Remove
    rem_p = subparsers.add_parser("remove", help="Remove attachment")
    rem_p.add_argument("--database", "-d", required=True)
    rem_p.add_argument("--id", required=True, help="Attachment ID")
    rem_p.add_argument("--force", "-f", action="store_true")
    rem_p.set_defaults(func=remove_attachment)

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
