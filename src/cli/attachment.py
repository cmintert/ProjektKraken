"""CLI for managing image attachments."""

import argparse
import logging
import sys
from pathlib import Path

from src.cli.utils import validate_database_path
from src.commands.image_commands import (
    AddImagesCommand,
    RemoveImageCommand,
    ReorderImagesCommand,
    UpdateImageCaptionCommand,
)
from src.services.asset_store import AssetStore
from src.services.attachment_service import AttachmentService
from src.services.backup_service import BackupService, BackupType
from src.services.db_service import DatabaseService

logger = logging.getLogger(__name__)

_OWNER_TYPES = {
    "entity": "entity",
    "event": "event",
    "entities": "entity",
    "events": "event",
}


def _open_attachment_database(path: str) -> DatabaseService:
    """Connect the CLI database and its asset-backed attachment service."""
    db_service = DatabaseService(path)
    db_service.connect()
    if db_service.attachment_service is None:
        db_service.attachment_service = AttachmentService(
            db_service.get_attachment_repo(),
            AssetStore(str(Path(path).resolve().parent)),
        )
    return db_service


def repair_legacy_attachments(args: argparse.Namespace) -> int:
    """Preview or explicitly repair plural owner types from older CLI imports."""
    db_service = None
    try:
        db_service = DatabaseService(args.database, read_only=True)
        db_service.connect()
        legacy = [
            item
            for item in db_service.get_attachment_repo().list_all()
            if item.owner_type in {"entities", "events"}
        ]
        world_root = Path(args.database).resolve().parent
        missing: list[str] = []
        for item in legacy:
            for relative in (item.image_rel_path, item.thumb_rel_path):
                if not relative:
                    continue
                relative_path = Path(relative)
                asset = (world_root / relative_path).resolve()
                if (
                    relative_path.is_absolute()
                    or not asset.is_relative_to(world_root)
                    or not asset.is_file()
                ):
                    missing.append(f"{item.id}: {relative}")
        print(f"Legacy attachment records: {len(legacy)}")
        for entry in missing:
            print(f"Missing or unsafe asset: {entry}", file=sys.stderr)
        db_service.close()
        db_service = None
        if not args.apply:
            return 1 if missing else 0
        if missing:
            print("Repair aborted: resolve missing assets first.", file=sys.stderr)
            return 1
        if not legacy:
            return 0
        if not args.force:
            if input("Apply repair after creating a backup? (y/n): ").lower() != "y":
                return 0
        backup_service = BackupService()
        backup_service.set_database_path(args.database)
        backup = backup_service.create_backup(
            backup_type=BackupType.MANUAL,
            description="before legacy attachment owner repair",
        )
        if backup is None:
            print("Repair aborted: backup failed.", file=sys.stderr)
            return 1
        print(f"Recovery backup: {backup.backup_path}", file=sys.stderr)
        db_service = DatabaseService(args.database)
        db_service.connect()
        db_service.get_attachment_repo().normalize_legacy_owner_types(
            [(item.id, item.owner_type) for item in legacy]
        )
        print(f"Repaired {len(legacy)} attachment records")
        return 0
    except Exception as error:
        logger.error("Legacy attachment repair failed: %s", error)
        return 1
    finally:
        if db_service is not None:
            db_service.close()


def add_attachments(args: argparse.Namespace) -> int:
    """Add image attachments to an entity or event."""
    db_service = None
    try:
        db_service = _open_attachment_database(args.database)

        cmd = AddImagesCommand(_OWNER_TYPES[args.type], args.id, args.paths)
        result = cmd.execute(db_service)

        failures: dict[str, str] = {}
        if isinstance(result.data, dict):
            raw_failures = result.data.get("failures")
            if isinstance(raw_failures, dict):
                failures = {
                    str(path): str(error) for path, error in raw_failures.items()
                }
        for path, error in failures.items():
            print(f"Failed to import {path}: {error}", file=sys.stderr)

        if result.success and not failures:
            print(f"OK {result.message}")
            return 0
        else:
            print(f"Import incomplete: {result.message}", file=sys.stderr)
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
        db_service = _open_attachment_database(args.database)

        if not args.force:
            print(f"About to remove attachment: {args.id}")
            if input("Are you sure? (y/n): ").lower() != "y":
                return 0

        cmd = RemoveImageCommand(args.id)
        result = cmd.execute(db_service)

        if result.success:
            print(f"OK Removed attachment: {args.id}")
            return 0
        else:
            print(f"ERROR: {result.message}", file=sys.stderr)
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
        db_service = _open_attachment_database(args.database)

        attachment_service = db_service.attachment_service
        if attachment_service is None:
            print(
                "ERROR AttachmentService not available in DatabaseService",
                file=sys.stderr,
            )
            return 1

        attachments = attachment_service.get_attachments(
            _OWNER_TYPES[args.type], args.id
        )

        if args.json:
            import json

            print(json.dumps([vars(a) for a in attachments], indent=2, default=str))
        else:
            print(
                f"\nFound {len(attachments)} attachment(s) for {args.type} {args.id}:\n"
            )
            for a in attachments:
                print(f"ID: {a.id}")
                print(f"  Filename: {Path(a.image_rel_path).name}")
                if a.caption:
                    print(f"  Caption: {a.caption}")
                print(f"  Position: {a.order_index}")
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
        db_service = _open_attachment_database(args.database)

        cmd = UpdateImageCaptionCommand(args.id, args.caption)
        result = cmd.execute(db_service)

        if result.success:
            print(f"OK Updated caption for: {args.id}")
            return 0
        else:
            print(f"ERROR: {result.message}", file=sys.stderr)
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
        db_service = _open_attachment_database(args.database)

        # args.ids should be a comma-separated list of IDs in desired order
        ids = [i.strip() for i in args.ids.split(",")]

        cmd = ReorderImagesCommand(_OWNER_TYPES[args.type], args.id, ids)
        result = cmd.execute(db_service)

        if result.success:
            print(f"OK Reordered attachments for {args.type} {args.id}")
            return 0
        else:
            print(f"ERROR: {result.message}", file=sys.stderr)
            return 1
    except Exception as e:
        logger.error(f"Failed to reorder attachments: {e}")
        return 1
    finally:
        if db_service:
            db_service.close()


def register_commands(subparsers: argparse._SubParsersAction) -> None:  # type: ignore
    """Register attachment subcommands with a parent subparsers group.

    Args:
        subparsers: The subparsers action group from a parent ArgumentParser.

    """
    # Add
    add_p = subparsers.add_parser("add", help="Add attachments")
    add_p.add_argument("--database", "-d", required=True)
    add_p.add_argument("--type", required=True, choices=list(_OWNER_TYPES))
    add_p.add_argument("--id", required=True, help="Owner ID")
    add_p.add_argument("paths", nargs="+", help="Paths to image files")
    add_p.set_defaults(func=add_attachments)

    # List
    list_p = subparsers.add_parser("list", help="List attachments")
    list_p.add_argument("--database", "-d", required=True)
    list_p.add_argument("--type", required=True, choices=list(_OWNER_TYPES))
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
    ord_p.add_argument("--type", required=True, choices=list(_OWNER_TYPES))
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

    repair_p = subparsers.add_parser(
        "repair-legacy", help="Preview or repair old plural owner types"
    )
    repair_p.add_argument("--database", "-d", required=True)
    repair_p.add_argument("--apply", action="store_true", help="Back up and repair")
    repair_p.add_argument("--force", action="store_true", help="Skip confirmation")
    repair_p.set_defaults(func=repair_legacy_attachments)


def main() -> None:
    """Main entry point for the attachment CLI tool."""
    parser = argparse.ArgumentParser(description="Manage ProjektKraken attachments")
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    subparsers = parser.add_subparsers(dest="command", help="Subcommands")
    register_commands(subparsers)

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)

    if not args.command:
        parser.print_help()
        sys.exit(2)

    if not validate_database_path(args.database):
        sys.exit(1)

    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
