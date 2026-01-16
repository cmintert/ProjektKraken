"""
Tests for the BackupConfig dataclass.
"""
from pathlib import Path

import pytest

from src.core.backup_config import BackupConfig


def test_backup_config_defaults():
    """Test BackupConfig with default values."""
    config = BackupConfig()
    
    assert config.enabled is True
    assert config.auto_save_interval_minutes == 5
    assert config.auto_save_retention_count == 12
    assert config.daily_retention_count == 7
    assert config.weekly_retention_count == 4
    assert config.manual_retention_count == -1
    assert config.backup_dir is None
    assert config.external_backup_path is None
    assert config.verify_after_backup is True
    assert config.vacuum_before_backup is False


def test_backup_config_custom_values():
    """Test BackupConfig with custom values."""
    backup_dir = Path("/custom/backup/dir")
    external_path = Path("/external/backup")
    
    config = BackupConfig(
        enabled=False,
        auto_save_interval_minutes=10,
        auto_save_retention_count=6,
        daily_retention_count=14,
        weekly_retention_count=8,
        manual_retention_count=10,
        backup_dir=backup_dir,
        external_backup_path=external_path,
        verify_after_backup=False,
        vacuum_before_backup=True,
    )
    
    assert config.enabled is False
    assert config.auto_save_interval_minutes == 10
    assert config.auto_save_retention_count == 6
    assert config.daily_retention_count == 14
    assert config.weekly_retention_count == 8
    assert config.manual_retention_count == 10
    assert config.backup_dir == backup_dir
    assert config.external_backup_path == external_path
    assert config.verify_after_backup is False
    assert config.vacuum_before_backup is True


def test_backup_config_to_dict():
    """Test converting BackupConfig to dictionary."""
    backup_dir = Path("/test/backup")
    external_path = Path("/external")
    
    config = BackupConfig(
        enabled=False,
        auto_save_interval_minutes=10,
        backup_dir=backup_dir,
        external_backup_path=external_path,
    )
    
    result = config.to_dict()
    
    assert result["enabled"] is False
    assert result["auto_save_interval_minutes"] == 10
    assert result["auto_save_retention_count"] == 12
    assert result["daily_retention_count"] == 7
    assert result["weekly_retention_count"] == 4
    assert result["manual_retention_count"] == -1
    assert result["backup_dir"] == "/test/backup"
    assert result["external_backup_path"] == "/external"
    assert result["verify_after_backup"] is True
    assert result["vacuum_before_backup"] is False


def test_backup_config_to_dict_with_none_paths():
    """Test converting BackupConfig to dict when paths are None."""
    config = BackupConfig()
    
    result = config.to_dict()
    
    assert result["backup_dir"] is None
    assert result["external_backup_path"] is None


def test_backup_config_from_dict():
    """Test creating BackupConfig from dictionary."""
    data = {
        "enabled": False,
        "auto_save_interval_minutes": 15,
        "auto_save_retention_count": 8,
        "daily_retention_count": 10,
        "weekly_retention_count": 5,
        "manual_retention_count": 20,
        "backup_dir": "/test/backup",
        "external_backup_path": "/external/path",
        "verify_after_backup": False,
        "vacuum_before_backup": True,
    }
    
    config = BackupConfig.from_dict(data)
    
    assert config.enabled is False
    assert config.auto_save_interval_minutes == 15
    assert config.auto_save_retention_count == 8
    assert config.daily_retention_count == 10
    assert config.weekly_retention_count == 5
    assert config.manual_retention_count == 20
    assert config.backup_dir == Path("/test/backup")
    assert config.external_backup_path == Path("/external/path")
    assert config.verify_after_backup is False
    assert config.vacuum_before_backup is True


def test_backup_config_from_dict_with_defaults():
    """Test creating BackupConfig from dict with missing values."""
    data = {}
    
    config = BackupConfig.from_dict(data)
    
    assert config.enabled is True
    assert config.auto_save_interval_minutes == 5
    assert config.auto_save_retention_count == 12
    assert config.daily_retention_count == 7
    assert config.weekly_retention_count == 4
    assert config.manual_retention_count == -1
    assert config.backup_dir is None
    assert config.external_backup_path is None
    assert config.verify_after_backup is True
    assert config.vacuum_before_backup is False


def test_backup_config_from_dict_with_none_paths():
    """Test creating BackupConfig from dict with None paths."""
    data = {
        "backup_dir": None,
        "external_backup_path": None,
    }
    
    config = BackupConfig.from_dict(data)
    
    assert config.backup_dir is None
    assert config.external_backup_path is None


def test_backup_config_roundtrip():
    """Test that to_dict and from_dict are inverse operations."""
    original = BackupConfig(
        enabled=False,
        auto_save_interval_minutes=20,
        auto_save_retention_count=10,
        daily_retention_count=5,
        weekly_retention_count=3,
        manual_retention_count=15,
        backup_dir=Path("/test/backup"),
        external_backup_path=Path("/external"),
        verify_after_backup=False,
        vacuum_before_backup=True,
    )
    
    data = original.to_dict()
    restored = BackupConfig.from_dict(data)
    
    assert restored.enabled == original.enabled
    assert restored.auto_save_interval_minutes == original.auto_save_interval_minutes
    assert restored.auto_save_retention_count == original.auto_save_retention_count
    assert restored.daily_retention_count == original.daily_retention_count
    assert restored.weekly_retention_count == original.weekly_retention_count
    assert restored.manual_retention_count == original.manual_retention_count
    assert restored.backup_dir == original.backup_dir
    assert restored.external_backup_path == original.external_backup_path
    assert restored.verify_after_backup == original.verify_after_backup
    assert restored.vacuum_before_backup == original.vacuum_before_backup


def test_backup_config_unlimited_manual_retention():
    """Test that manual_retention_count can be -1 for unlimited."""
    config = BackupConfig(manual_retention_count=-1)
    
    assert config.manual_retention_count == -1


def test_backup_config_retention_logic():
    """Test the retention count logic makes sense."""
    config = BackupConfig()
    
    # Default config should provide 1 hour of auto-save history
    # (5 minutes * 12 = 60 minutes)
    total_auto_save_minutes = (
        config.auto_save_interval_minutes * config.auto_save_retention_count
    )
    assert total_auto_save_minutes == 60
    
    # Should have a week of daily backups
    assert config.daily_retention_count == 7
    
    # Should have roughly a month of weekly backups
    assert config.weekly_retention_count == 4
