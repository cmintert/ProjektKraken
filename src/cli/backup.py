#!/usr/bin/env python3
"""
Backup Management CLI.

Provides command-line tools for creating, listing, and restoring backups.

Usage:
    python -m src.cli.backup create --database world.kraken --description "Pre-update"
    python -m src.cli.backup list --database world.kraken
    python -m src.cli.backup restore --database world.kraken --file "path/to/backup.kraken"
"""

import argparse
import logging
import sys
from pathlib import Path

from src.cli.utils import validate_database_path
from src.services.backup_service import BackupService, BackupType

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def create_backup(args: argparse.Namespace) -> int:
    """Create a new backup."""
    try:
        service = BackupService()
        service.set_database_path(args.database)

        desc = args.description or "Manual backup via CLI"
        backup_path = service.create_backup(
            backup_type=BackupType.MANUAL, description=desc
        )

        if backup_path:
            print(f"✓ Backup created successfully: {backup_path}")
            return 0
        else:
            print("✗ Backup creation failed.")
            return 1

    except Exception as e:
        logger.error(f"Failed to create backup: {e}")
        if args.verbose:
            raise
        return 1


def list_backups(args: argparse.Namespace) -> int:
    """List available backups."""
    try:
        service = BackupService()
        service.set_database_path(args.database)

        # Build list of all backups
        backups = []
        for backup_type in [
            BackupType.MANUAL,
            BackupType.AUTO_SAVE,
            BackupType.DAILY,
            BackupType.WEEKLY,
        ]:
            type_dir = service.backup_root / backup_type.value
            if type_dir.exists():
                for f in type_dir.glob("*.kraken"):
                    backups.append(
                        {
                            "type": backup_type.value,
                            "path": f,
                            "time": f.stat().st_mtime,
                            "size": f.stat().st_size,
                        }
                    )

        backups.sort(key=lambda x: x["time"], reverse=True)

        if not backups:
            print("No backups found.")
            return 0

        print(f"\nFound {len(backups)} backup(s):\n")
        print(f"{'Type':<10} {'Date':<20} {'Size':<10} {'Filename'}")
        print("-" * 60)

        import datetime

        for b in backups:
            dt = datetime.datetime.fromtimestamp(b["time"]).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            size_mb = b["size"] / (1024 * 1024)
            print(f"{b['type']:<10} {dt:<20} {size_mb:>6.2f} MB  {b['path'].name}")
        print()
        return 0

    except Exception as e:
        logger.error(f"Failed to list backups: {e}")
        if args.verbose:
            raise
        return 1


def restore_backup(args: argparse.Namespace) -> int:
    """Restore from a backup."""
    try:
        service = BackupService()
        # We don't set db path here needed for restore target,
        # but the service restore_backup method takes target_path.

        backup_file = Path(args.file)
        if not backup_file.exists():
            print(f"✗ Backup file not found: {backup_file}")
            return 1

        target_path = Path(args.database)

        if not args.force:
            print(f"WARNING: This will overwrite the database at: {target_path}")
            if input("Are you sure? (y/n): ").lower() != "y":
                return 0

        success = service.restore_backup(backup_file, target_path)

        if success:
            print(f"✓ Database restored successfully to: {target_path}")
            return 0
        else:
            print("✗ Restore failed.")
            return 1

    except Exception as e:
        logger.error(f"Failed to restore backup: {e}")
        if args.verbose:
            raise
        return 1


def main() -> None:
    """Main CLI entry point for backup tools."""
    parser = argparse.ArgumentParser(description="Manage ProjektKraken backups")
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Create
    create_p = subparsers.add_parser("create", help="Create a manual backup")
    create_p.add_argument("--database", "-d", required=True)
    create_p.add_argument("--description", "-m", help="Backup description")
    create_p.set_defaults(func=create_backup)

    # List
    list_p = subparsers.add_parser("list", help="List available backups")
    list_p.add_argument("--database", "-d", required=True)
    list_p.set_defaults(func=list_backups)

    # Restore
    restore_p = subparsers.add_parser("restore", help="Restore from backup")
    restore_p.add_argument(
        "--database", "-d", required=True, help="Target database path"
    )
    restore_p.add_argument("--file", "-f", required=True, help="Path to backup file")
    restore_p.add_argument("--force", action="store_true", help="Skip confirmation")
    restore_p.set_defaults(func=restore_backup)

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if hasattr(args, "database"):
        # For restore we might be restoring to a new path, so allow_create=True
        # effectively just checks validity of path structure
        if not validate_database_path(args.database, allow_create=True):
            sys.exit(1)

    if hasattr(args, "func"):
        sys.exit(args.func(args))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
