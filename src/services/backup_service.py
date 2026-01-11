"""
Backup Service Module.
Handles automated backup operations, restoration, and retention policies.
"""

import hashlib
import json
import logging
import shutil
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List, Optional

try:
    from PySide6.QtCore import QThread, QTimer, Signal

    HAS_QT = True
except ImportError:
    HAS_QT = False

from src.core.backup_config import BackupConfig
from src.core.paths import get_backup_directory

logger = logging.getLogger(__name__)


class BackupType(Enum):
    """Types of backups supported by the system."""

    AUTO_SAVE = "auto"
    DAILY = "daily"
    WEEKLY = "weekly"
    MANUAL = "manual"


@dataclass
class BackupMetadata:
    """
    Metadata information for a backup file.

    Attributes:
        backup_path: Path to the backup file.
        backup_type: Type of backup (auto, daily, weekly, manual).
        timestamp: When the backup was created.
        size: Size of the backup file in bytes.
        checksum: SHA256 checksum of the backup file.
        description: Optional user description for manual backups.
    """

    backup_path: Path
    backup_type: BackupType
    timestamp: datetime
    size: int
    checksum: str
    description: str = ""

    def to_dict(self) -> dict:
        """
        Converts metadata to dictionary for serialization.

        Returns:
            dict: Dictionary representation of the metadata.
        """
        return {
            "backup_path": str(self.backup_path),
            "backup_type": self.backup_type.value,
            "timestamp": self.timestamp.isoformat(),
            "size": self.size,
            "checksum": self.checksum,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "BackupMetadata":
        """
        Creates BackupMetadata from a dictionary.

        Args:
            data: Dictionary containing metadata values.

        Returns:
            BackupMetadata: A new BackupMetadata instance.
        """
        return cls(
            backup_path=Path(data["backup_path"]),
            backup_type=BackupType(data["backup_type"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            size=data["size"],
            checksum=data["checksum"],
            description=data.get("description", ""),
        )


if HAS_QT:

    class BackupWorker(QThread):
        """
        Background worker thread for backup operations.
        Prevents blocking the UI during backup/restore operations.
        """

        backup_completed = Signal(bool, str)  # success, message
        backup_progress = Signal(str)  # progress message

        def __init__(
            self,
            db_path: Path,
            backup_path: Path,
            operation: str = "backup",
        ) -> None:
            """
            Initializes the backup worker.

            Args:
                db_path: Path to the database file.
                backup_path: Path where backup will be saved or restored from.
                operation: Operation type ('backup' or 'restore').
            """
            super().__init__()
            self.db_path = db_path
            self.backup_path = backup_path
            self.operation = operation

        def run(self) -> None:
            """Runs the backup/restore operation in background thread."""
            try:
                if self.operation == "backup":
                    self._perform_backup()
                elif self.operation == "restore":
                    self._perform_restore()
                else:
                    raise ValueError(f"Unknown operation: {self.operation}")
            except Exception as e:
                logger.error(f"Backup operation failed: {e}", exc_info=True)
                self.backup_completed.emit(False, str(e))

        def _perform_backup(self) -> None:
            """Performs the backup operation."""
            self.backup_progress.emit("Creating backup...")

            # Create temporary file
            temp_path = self.backup_path.parent / f".{self.backup_path.name}.tmp"

            try:
                # Copy database file
                shutil.copy2(self.db_path, temp_path)

                # Verify the temp file is a valid SQLite database
                conn = sqlite3.connect(str(temp_path))
                conn.execute("PRAGMA integrity_check")
                conn.close()

                # Atomically rename temp file to final backup
                temp_path.replace(self.backup_path)

                self.backup_progress.emit("Backup created successfully")
                self.backup_completed.emit(True, str(self.backup_path))

            except Exception as e:
                # Clean up temp file on error
                if temp_path.exists():
                    temp_path.unlink()
                raise

        def _perform_restore(self) -> None:
            """Performs the restore operation."""
            self.backup_progress.emit("Restoring from backup...")

            # Verify backup file is valid
            conn = sqlite3.connect(str(self.backup_path))
            conn.execute("PRAGMA integrity_check")
            conn.close()

            # Create temporary file
            temp_path = self.db_path.parent / f".{self.db_path.name}.tmp"

            try:
                # Copy backup to temp location
                shutil.copy2(self.backup_path, temp_path)

                # Atomically replace current database
                temp_path.replace(self.db_path)

                self.backup_progress.emit("Restore completed successfully")
                self.backup_completed.emit(True, "Database restored successfully")

            except Exception as e:
                # Clean up temp file on error
                if temp_path.exists():
                    temp_path.unlink()
                raise

else:
    # Stub class when Qt is not available
    BackupWorker = None


class BackupService:
    """
    Main backup service handling all backup operations.

    Provides automated backup scheduling, manual backups, restoration,
    integrity verification, and retention policy enforcement.
    """

    def __init__(self, config: Optional[BackupConfig] = None) -> None:
        """
        Initializes the backup service.

        Args:
            config: Backup configuration (uses defaults if not provided).
        """
        self.config = config or BackupConfig()
        self._auto_backup_timer: Optional[QTimer] = None
        self._metadata_cache: List[BackupMetadata] = []
        self._current_db_path: Optional[Path] = None

        logger.info("BackupService initialized")

    def set_database_path(self, db_path: str) -> None:
        """
        Sets the current database path for backup operations.

        Args:
            db_path: Path to the database file.
        """
        self._current_db_path = Path(db_path) if db_path != ":memory:" else None
        logger.debug(f"Database path set to: {self._current_db_path}")

    def create_backup(
        self,
        db_path: Optional[Path] = None,
        backup_type: BackupType = BackupType.MANUAL,
        description: str = "",
    ) -> Optional[BackupMetadata]:
        """
        Creates a backup of the database.

        Args:
            db_path: Path to database file (uses current if not specified).
            backup_type: Type of backup to create.
            description: Optional description for manual backups.

        Returns:
            BackupMetadata: Metadata for the created backup, or None on failure.
        """
        if db_path is None:
            db_path = self._current_db_path

        if db_path is None or not db_path.exists():
            logger.error("Cannot create backup: database path not set or doesn't exist")
            return None

        try:
            # Generate backup filename
            backup_path = self._generate_backup_path(db_path, backup_type, description)

            # Ensure backup directory exists
            backup_path.parent.mkdir(parents=True, exist_ok=True)

            # Create temporary file
            temp_path = backup_path.parent / f".{backup_path.name}.tmp"

            # Copy database file
            shutil.copy2(db_path, temp_path)

            # Verify backup integrity
            if self.config.verify_after_backup:
                if not self._verify_backup_file(temp_path):
                    temp_path.unlink()
                    logger.error("Backup verification failed")
                    return None

            # Calculate checksum
            checksum = self._calculate_checksum(temp_path)

            # Atomically rename to final path
            temp_path.replace(backup_path)

            # Create metadata
            metadata = BackupMetadata(
                backup_path=backup_path,
                backup_type=backup_type,
                timestamp=datetime.now(),
                size=backup_path.stat().st_size,
                checksum=checksum,
                description=description,
            )

            # Save metadata
            self._save_metadata(metadata)

            # Enforce retention policy
            self.cleanup_old_backups()

            # Copy to external location if configured
            if self.config.external_backup_path:
                self._copy_to_external(backup_path, backup_type)

            logger.info(f"Backup created: {backup_path}")
            return metadata

        except Exception as e:
            logger.error(f"Failed to create backup: {e}", exc_info=True)
            return None

    def restore_backup(
        self, backup_path: Path, target_path: Optional[Path] = None
    ) -> bool:
        """
        Restores a database from a backup.

        Args:
            backup_path: Path to the backup file to restore.
            target_path: Path to restore to (uses current DB if not specified).

        Returns:
            bool: True if restore was successful, False otherwise.
        """
        if target_path is None:
            target_path = self._current_db_path

        if target_path is None:
            logger.error("Cannot restore: target path not set")
            return False

        if not backup_path.exists():
            logger.error(f"Backup file not found: {backup_path}")
            return False

        try:
            # Verify backup integrity
            if not self._verify_backup_file(backup_path):
                logger.error("Backup verification failed")
                return False

            # Create safety backup of current database
            if target_path.exists():
                safety_backup = target_path.parent / f"pre_restore_{int(time.time())}.kraken"
                shutil.copy2(target_path, safety_backup)
                logger.info(f"Created safety backup: {safety_backup}")

            # Create temporary file
            temp_path = target_path.parent / f".{target_path.name}.tmp"

            # Copy backup to temp location
            shutil.copy2(backup_path, temp_path)

            # Atomically replace current database
            temp_path.replace(target_path)

            logger.info(f"Database restored from: {backup_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to restore backup: {e}", exc_info=True)
            # Clean up temp file if exists
            if temp_path and temp_path.exists():
                temp_path.unlink()
            return False

    def list_backups(
        self, backup_type: Optional[BackupType] = None
    ) -> List[BackupMetadata]:
        """
        Lists available backups, optionally filtered by type.

        Args:
            backup_type: Filter backups by type (None = all types).

        Returns:
            List[BackupMetadata]: List of backup metadata, sorted by timestamp.
        """
        backups = self._load_all_metadata()

        if backup_type is not None:
            backups = [b for b in backups if b.backup_type == backup_type]

        # Sort by timestamp, most recent first
        backups.sort(key=lambda x: x.timestamp, reverse=True)

        return backups

    def verify_backup(self, backup_path: Path) -> bool:
        """
        Verifies the integrity of a backup file.

        Args:
            backup_path: Path to the backup file to verify.

        Returns:
            bool: True if backup is valid, False otherwise.
        """
        return self._verify_backup_file(backup_path)

    def cleanup_old_backups(self) -> None:
        """
        Enforces retention policy by deleting old backups.
        Respects retention counts configured for each backup type.
        """
        for backup_type in BackupType:
            self._cleanup_by_type(backup_type)

    def start_auto_backup(self, interval_minutes: Optional[int] = None) -> None:
        """
        Starts the automated backup timer.

        Args:
            interval_minutes: Backup interval (uses config default if not specified).
        """
        if not HAS_QT:
            logger.warning("Qt not available, auto-backup timer not started")
            return

        if not self.config.enabled:
            logger.info("Auto-backup is disabled in configuration")
            return

        if interval_minutes is None:
            interval_minutes = self.config.auto_save_interval_minutes

        if self._auto_backup_timer is not None:
            self.stop_auto_backup()

        from PySide6.QtCore import QTimer

        self._auto_backup_timer = QTimer()
        self._auto_backup_timer.timeout.connect(self._perform_auto_backup)
        self._auto_backup_timer.start(interval_minutes * 60 * 1000)  # Convert to ms

        logger.info(f"Auto-backup started with {interval_minutes} minute interval")

    def stop_auto_backup(self) -> None:
        """Stops the automated backup timer."""
        if self._auto_backup_timer is not None:
            self._auto_backup_timer.stop()
            self._auto_backup_timer = None
            logger.info("Auto-backup stopped")

    def _perform_auto_backup(self) -> None:
        """Internal method called by timer to perform auto-backup."""
        if self._current_db_path:
            self.create_backup(backup_type=BackupType.AUTO_SAVE)

    def _generate_backup_path(
        self, db_path: Path, backup_type: BackupType, description: str = ""
    ) -> Path:
        """
        Generates a backup file path based on naming convention.

        Args:
            db_path: Path to the database file.
            backup_type: Type of backup.
            description: Optional description for manual backups.

        Returns:
            Path: Path where backup should be saved.
        """
        # Get backup directory
        if self.config.backup_dir:
            backup_dir = self.config.backup_dir
        else:
            backup_dir = get_backup_directory()

        # Create subdirectory for backup type
        type_dir = backup_dir / backup_type.value
        type_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename
        db_name = db_path.stem  # e.g., "world" from "world.kraken"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if backup_type == BackupType.WEEKLY:
            # Use week number for weekly backups
            week = datetime.now().strftime("%Y_W%V")
            filename = f"{db_name}_weekly_{week}.kraken"
        elif backup_type == BackupType.DAILY:
            date = datetime.now().strftime("%Y%m%d")
            filename = f"{db_name}_daily_{date}.kraken"
        elif backup_type == BackupType.MANUAL and description:
            # Sanitize description for filename
            safe_desc = "".join(c for c in description if c.isalnum() or c in "_ -")
            safe_desc = safe_desc[:30]  # Limit length
            filename = f"{db_name}_manual_{timestamp}_{safe_desc}.kraken"
        else:
            filename = f"{db_name}_{backup_type.value}_{timestamp}.kraken"

        return type_dir / filename

    def _verify_backup_file(self, backup_path: Path) -> bool:
        """
        Verifies that a backup file is a valid SQLite database.

        Args:
            backup_path: Path to backup file to verify.

        Returns:
            bool: True if valid, False otherwise.
        """
        try:
            conn = sqlite3.connect(str(backup_path))
            cursor = conn.cursor()
            result = cursor.execute("PRAGMA integrity_check").fetchone()
            conn.close()
            return result[0] == "ok"
        except Exception as e:
            logger.error(f"Backup verification failed: {e}")
            return False

    def _calculate_checksum(self, file_path: Path) -> str:
        """
        Calculates SHA256 checksum of a file.

        Args:
            file_path: Path to file.

        Returns:
            str: Hexadecimal checksum string.
        """
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def _save_metadata(self, metadata: BackupMetadata) -> None:
        """
        Saves backup metadata to index file.

        Args:
            metadata: Backup metadata to save.
        """
        metadata_file = metadata.backup_path.parent / ".backup_index.json"

        # Load existing metadata
        if metadata_file.exists():
            with open(metadata_file, "r") as f:
                data = json.load(f)
        else:
            data = []

        # Add new metadata
        data.append(metadata.to_dict())

        # Save updated metadata
        with open(metadata_file, "w") as f:
            json.dump(data, f, indent=2)

    def _load_all_metadata(self) -> List[BackupMetadata]:
        """
        Loads all backup metadata from index files.

        Returns:
            List[BackupMetadata]: List of all backup metadata.
        """
        backups = []

        # Get backup directory
        if self.config.backup_dir:
            backup_dir = self.config.backup_dir
        else:
            backup_dir = get_backup_directory()

        # Scan all backup type subdirectories
        for backup_type in BackupType:
            type_dir = backup_dir / backup_type.value
            metadata_file = type_dir / ".backup_index.json"

            if metadata_file.exists():
                try:
                    with open(metadata_file, "r") as f:
                        data = json.load(f)
                        for item in data:
                            # Verify the backup file still exists
                            backup_path = Path(item["backup_path"])
                            if backup_path.exists():
                                backups.append(BackupMetadata.from_dict(item))
                except Exception as e:
                    logger.error(f"Failed to load metadata from {metadata_file}: {e}")

        return backups

    def _cleanup_by_type(self, backup_type: BackupType) -> None:
        """
        Cleans up old backups for a specific backup type.

        Args:
            backup_type: Type of backup to clean up.
        """
        # Get retention count for this type
        if backup_type == BackupType.AUTO_SAVE:
            retention_count = self.config.auto_save_retention_count
        elif backup_type == BackupType.DAILY:
            retention_count = self.config.daily_retention_count
        elif backup_type == BackupType.WEEKLY:
            retention_count = self.config.weekly_retention_count
        elif backup_type == BackupType.MANUAL:
            retention_count = self.config.manual_retention_count
        else:
            return

        # Skip if unlimited retention
        if retention_count == -1:
            return

        # Get backups of this type
        backups = self.list_backups(backup_type)

        # Delete old backups beyond retention count
        if len(backups) > retention_count:
            for backup in backups[retention_count:]:
                try:
                    backup.backup_path.unlink()
                    logger.debug(f"Deleted old backup: {backup.backup_path}")
                except Exception as e:
                    logger.error(f"Failed to delete backup {backup.backup_path}: {e}")

    def _copy_to_external(self, backup_path: Path, backup_type: BackupType) -> None:
        """
        Copies a backup to an external location if configured.

        Args:
            backup_path: Path to the backup file.
            backup_type: Type of backup.
        """
        if not self.config.external_backup_path:
            return

        try:
            external_dir = self.config.external_backup_path / backup_type.value
            external_dir.mkdir(parents=True, exist_ok=True)

            external_path = external_dir / backup_path.name
            shutil.copy2(backup_path, external_path)

            logger.info(f"Copied backup to external location: {external_path}")
        except Exception as e:
            logger.error(f"Failed to copy backup to external location: {e}")
