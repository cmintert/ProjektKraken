"""
Backup Configuration Module.
Defines configuration settings for the backup system.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class BackupConfig:
    """
    Configuration settings for the backup system.

    Attributes:
        enabled: Whether automated backups are enabled.
        auto_save_interval_minutes: Interval in minutes for auto-save backups.
        auto_save_retention_count: Number of auto-save backups to keep.
        daily_retention_count: Number of daily backups to keep.
        weekly_retention_count: Number of weekly backups to keep.
        manual_retention_count: Number of manual backups to keep (-1 = unlimited).
        backup_dir: Custom backup directory (None = use default).
        external_backup_path: Optional external location for additional copies.
        verify_after_backup: Whether to verify backup integrity after creation.
        vacuum_before_backup: Whether to run VACUUM before creating backup.
    """

    enabled: bool = True
    auto_save_interval_minutes: int = 5
    auto_save_retention_count: int = 12  # 1 hour of history (5 min * 12)
    daily_retention_count: int = 7
    weekly_retention_count: int = 4
    manual_retention_count: int = -1  # Unlimited
    backup_dir: Optional[Path] = None  # Defaults to user_data/backups
    external_backup_path: Optional[Path] = None  # Optional external location
    verify_after_backup: bool = True
    vacuum_before_backup: bool = False  # Can be slow for large DBs

    def to_dict(self) -> dict:
        """
        Converts the config to a dictionary for JSON serialization.

        Returns:
            dict: Dictionary representation of the configuration.
        """
        return {
            "enabled": self.enabled,
            "auto_save_interval_minutes": self.auto_save_interval_minutes,
            "auto_save_retention_count": self.auto_save_retention_count,
            "daily_retention_count": self.daily_retention_count,
            "weekly_retention_count": self.weekly_retention_count,
            "manual_retention_count": self.manual_retention_count,
            "backup_dir": str(self.backup_dir) if self.backup_dir else None,
            "external_backup_path": (
                str(self.external_backup_path) if self.external_backup_path else None
            ),
            "verify_after_backup": self.verify_after_backup,
            "vacuum_before_backup": self.vacuum_before_backup,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "BackupConfig":
        """
        Creates a BackupConfig from a dictionary.

        Args:
            data: Dictionary containing configuration values.

        Returns:
            BackupConfig: A new BackupConfig instance.
        """
        backup_dir = Path(data["backup_dir"]) if data.get("backup_dir") else None
        external_backup_path = (
            Path(data["external_backup_path"])
            if data.get("external_backup_path")
            else None
        )

        return cls(
            enabled=data.get("enabled", True),
            auto_save_interval_minutes=data.get("auto_save_interval_minutes", 5),
            auto_save_retention_count=data.get("auto_save_retention_count", 12),
            daily_retention_count=data.get("daily_retention_count", 7),
            weekly_retention_count=data.get("weekly_retention_count", 4),
            manual_retention_count=data.get("manual_retention_count", -1),
            backup_dir=backup_dir,
            external_backup_path=external_backup_path,
            verify_after_backup=data.get("verify_after_backup", True),
            vacuum_before_backup=data.get("vacuum_before_backup", False),
        )
