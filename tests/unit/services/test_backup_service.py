"""
Unit tests for the BackupService.
Tests backup creation, restoration, verification, and retention policies.
"""

import json
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from src.core.backup_config import BackupConfig
from src.services.backup_service import BackupMetadata, BackupService, BackupType
from src.services.db_service import DatabaseService


@pytest.fixture
def temp_db(tmp_path):
    """Creates a temporary test database."""
    db_path = tmp_path / "test.kraken"
    service = DatabaseService(str(db_path))
    service.connect()

    # Add some test data
    from src.core.events import Event

    event = Event(name="Test Event", lore_date=100.0)
    service.insert_event(event)

    service.close()
    return db_path


@pytest.fixture
def backup_service(tmp_path):
    """Creates a backup service with temporary backup directory."""
    config = BackupConfig(
        backup_dir=tmp_path / "backups",
        auto_save_retention_count=3,
        daily_retention_count=2,
        weekly_retention_count=2,
        verify_after_backup=True,
    )
    service = BackupService(config)
    return service


@pytest.mark.unit
def test_backup_config_to_dict():
    """Test BackupConfig serialization."""
    config = BackupConfig(
        enabled=True,
        auto_save_interval_minutes=10,
        auto_save_retention_count=5,
    )

    data = config.to_dict()

    assert data["enabled"] is True
    assert data["auto_save_interval_minutes"] == 10
    assert data["auto_save_retention_count"] == 5


@pytest.mark.unit
def test_backup_config_from_dict():
    """Test BackupConfig deserialization."""
    data = {
        "enabled": False,
        "auto_save_interval_minutes": 15,
        "daily_retention_count": 10,
    }

    config = BackupConfig.from_dict(data)

    assert config.enabled is False
    assert config.auto_save_interval_minutes == 15
    assert config.daily_retention_count == 10


@pytest.mark.unit
def test_create_manual_backup(backup_service, temp_db):
    """Test creating a manual backup."""
    metadata = backup_service.create_backup(
        db_path=temp_db, backup_type=BackupType.MANUAL, description="test backup"
    )

    assert metadata is not None
    assert metadata.backup_type == BackupType.MANUAL
    assert metadata.backup_path.exists()
    assert metadata.size > 0
    assert len(metadata.checksum) == 64  # SHA256 hash length
    assert "test backup" in metadata.description


@pytest.mark.unit
def test_create_auto_save_backup(backup_service, temp_db):
    """Test creating an auto-save backup."""
    metadata = backup_service.create_backup(
        db_path=temp_db, backup_type=BackupType.AUTO_SAVE
    )

    assert metadata is not None
    assert metadata.backup_type == BackupType.AUTO_SAVE
    assert metadata.backup_path.exists()
    assert "auto" in str(metadata.backup_path)


@pytest.mark.unit
def test_create_daily_backup(backup_service, temp_db):
    """Test creating a daily backup."""
    metadata = backup_service.create_backup(
        db_path=temp_db, backup_type=BackupType.DAILY
    )

    assert metadata is not None
    assert metadata.backup_type == BackupType.DAILY
    assert "daily" in str(metadata.backup_path)


@pytest.mark.unit
def test_create_weekly_backup(backup_service, temp_db):
    """Test creating a weekly backup."""
    metadata = backup_service.create_backup(
        db_path=temp_db, backup_type=BackupType.WEEKLY
    )

    assert metadata is not None
    assert metadata.backup_type == BackupType.WEEKLY
    assert "weekly" in str(metadata.backup_path)


@pytest.mark.unit
def test_backup_verification(backup_service, temp_db):
    """Test backup integrity verification."""
    metadata = backup_service.create_backup(db_path=temp_db)

    # Verify the backup
    is_valid = backup_service.verify_backup(metadata.backup_path)
    assert is_valid is True


@pytest.mark.unit
def test_backup_verification_corrupted(backup_service, temp_db, tmp_path):
    """Test that corrupted backups are detected."""
    # Create a backup
    metadata = backup_service.create_backup(db_path=temp_db)

    # Corrupt the backup
    with open(metadata.backup_path, "ab") as f:
        f.write(b"CORRUPTED_DATA")

    # Verify should fail
    is_valid = backup_service.verify_backup(metadata.backup_path)
    assert is_valid is False


@pytest.mark.unit
def test_restore_backup(backup_service, temp_db, tmp_path):
    """Test restoring from a backup."""
    # Create a backup
    metadata = backup_service.create_backup(db_path=temp_db)

    # Create a new database file
    restored_db = tmp_path / "restored.kraken"

    # Restore the backup
    success = backup_service.restore_backup(metadata.backup_path, restored_db)

    assert success is True
    assert restored_db.exists()

    # Verify restored database has the data
    service = DatabaseService(str(restored_db))
    service.connect()
    events = service.get_all_events()
    assert len(events) == 1
    assert events[0].name == "Test Event"
    service.close()


@pytest.mark.unit
def test_list_backups(backup_service, temp_db):
    """Test listing backups."""
    # Create several backups
    backup_service.create_backup(db_path=temp_db, backup_type=BackupType.MANUAL)
    backup_service.create_backup(db_path=temp_db, backup_type=BackupType.DAILY)
    backup_service.create_backup(db_path=temp_db, backup_type=BackupType.AUTO_SAVE)

    # List all backups
    all_backups = backup_service.list_backups()
    assert len(all_backups) == 3

    # List manual backups only
    manual_backups = backup_service.list_backups(BackupType.MANUAL)
    assert len(manual_backups) == 1
    assert manual_backups[0].backup_type == BackupType.MANUAL


@pytest.mark.unit
def test_auto_save_retention_policy(backup_service, temp_db):
    """Test that auto-save retention policy is enforced."""
    # Config has auto_save_retention_count=3

    # Create 5 auto-save backups
    for i in range(5):
        backup_service.create_backup(db_path=temp_db, backup_type=BackupType.AUTO_SAVE)
        time.sleep(0.1)  # Small delay to ensure different timestamps

    # Should only have 3 backups (retention count)
    backups = backup_service.list_backups(BackupType.AUTO_SAVE)
    assert len(backups) <= 3


@pytest.mark.unit
def test_daily_retention_policy(backup_service, temp_db):
    """Test that daily retention policy is enforced."""
    # Config has daily_retention_count=2

    # Create 4 daily backups
    for i in range(4):
        backup_service.create_backup(db_path=temp_db, backup_type=BackupType.DAILY)
        time.sleep(0.1)

    # Should only have 2 backups (retention count)
    backups = backup_service.list_backups(BackupType.DAILY)
    assert len(backups) <= 2


@pytest.mark.unit
def test_manual_backup_unlimited_retention(backup_service, temp_db):
    """Test that manual backups have unlimited retention by default."""
    # Create 10 manual backups
    for i in range(10):
        backup_service.create_backup(
            db_path=temp_db, backup_type=BackupType.MANUAL, description=f"backup_{i}"
        )
        time.sleep(0.1)

    # All 10 should still exist (unlimited retention)
    backups = backup_service.list_backups(BackupType.MANUAL)
    assert len(backups) == 10


@pytest.mark.unit
def test_backup_metadata_persistence(backup_service, temp_db):
    """Test that backup metadata is persisted and can be loaded."""
    # Create a backup
    original_metadata = backup_service.create_backup(db_path=temp_db)

    # Create a new service instance
    new_service = BackupService(backup_service.config)

    # Load backups
    loaded_backups = new_service.list_backups()

    assert len(loaded_backups) >= 1
    # Find our backup in the loaded list
    found = any(b.checksum == original_metadata.checksum for b in loaded_backups)
    assert found is True


@pytest.mark.unit
def test_backup_with_nonexistent_db(backup_service, tmp_path):
    """Test that backup fails gracefully with non-existent database."""
    nonexistent_db = tmp_path / "nonexistent.kraken"

    metadata = backup_service.create_backup(db_path=nonexistent_db)

    assert metadata is None


@pytest.mark.unit
def test_restore_with_nonexistent_backup(backup_service, tmp_path):
    """Test that restore fails gracefully with non-existent backup."""
    nonexistent_backup = tmp_path / "nonexistent_backup.kraken"
    target_db = tmp_path / "target.kraken"

    success = backup_service.restore_backup(nonexistent_backup, target_db)

    assert success is False


@pytest.mark.unit
def test_backup_metadata_serialization():
    """Test BackupMetadata serialization and deserialization."""
    original = BackupMetadata(
        backup_path=Path("/tmp/backup.kraken"),
        backup_type=BackupType.DAILY,
        timestamp=datetime.now(),
        size=1024,
        checksum="abc123",
        description="Test backup",
    )

    # Serialize to dict
    data = original.to_dict()

    # Deserialize from dict
    restored = BackupMetadata.from_dict(data)

    assert restored.backup_path == original.backup_path
    assert restored.backup_type == original.backup_type
    assert restored.size == original.size
    assert restored.checksum == original.checksum
    assert restored.description == original.description


@pytest.mark.unit
def test_set_database_path(backup_service, temp_db):
    """Test setting the database path for automatic operations."""
    backup_service.set_database_path(str(temp_db))

    # Should be able to create backup without specifying path
    metadata = backup_service.create_backup()

    assert metadata is not None
    assert metadata.backup_path.exists()


@pytest.mark.unit
def test_backup_naming_convention(backup_service, temp_db):
    """Test that backup files follow the naming convention."""
    # Auto-save backup
    auto_backup = backup_service.create_backup(
        db_path=temp_db, backup_type=BackupType.AUTO_SAVE
    )
    assert "auto" in str(auto_backup.backup_path)
    # Should contain autosave or auto in the filename
    filename = auto_backup.backup_path.name.lower()
    assert "autosave" in filename or "_auto_" in filename

    # Daily backup
    daily_backup = backup_service.create_backup(
        db_path=temp_db, backup_type=BackupType.DAILY
    )
    assert "daily" in str(daily_backup.backup_path)

    # Weekly backup
    weekly_backup = backup_service.create_backup(
        db_path=temp_db, backup_type=BackupType.WEEKLY
    )
    assert "weekly" in str(weekly_backup.backup_path)

    # Manual backup with description
    manual_backup = backup_service.create_backup(
        db_path=temp_db, backup_type=BackupType.MANUAL, description="my backup"
    )
    assert "manual" in str(manual_backup.backup_path)


@pytest.mark.unit
def test_backup_creates_subdirectories(backup_service, temp_db, tmp_path):
    """Test that backup creates proper subdirectories for each type."""
    config = BackupConfig(backup_dir=tmp_path / "backups")
    service = BackupService(config)

    service.create_backup(db_path=temp_db, backup_type=BackupType.AUTO_SAVE)
    service.create_backup(db_path=temp_db, backup_type=BackupType.DAILY)
    service.create_backup(db_path=temp_db, backup_type=BackupType.WEEKLY)
    service.create_backup(db_path=temp_db, backup_type=BackupType.MANUAL)

    # Check that subdirectories were created
    assert (tmp_path / "backups" / "auto").exists()
    assert (tmp_path / "backups" / "daily").exists()
    assert (tmp_path / "backups" / "weekly").exists()
    assert (tmp_path / "backups" / "manual").exists()


@pytest.mark.unit
def test_external_backup_location(tmp_path, temp_db):
    """Test copying backups to external location."""
    external_path = tmp_path / "external_backups"
    config = BackupConfig(
        backup_dir=tmp_path / "backups", external_backup_path=external_path
    )
    service = BackupService(config)

    metadata = service.create_backup(db_path=temp_db, backup_type=BackupType.DAILY)

    # Check that backup was also copied to external location
    external_daily_dir = external_path / "daily"
    assert external_daily_dir.exists()

    # Check that a file exists in external location
    external_files = list(external_daily_dir.glob("*.kraken"))
    assert len(external_files) > 0


@pytest.mark.unit
def test_checksum_calculation(backup_service, temp_db):
    """Test that checksums are calculated correctly."""
    metadata1 = backup_service.create_backup(db_path=temp_db)
    metadata2 = backup_service.create_backup(db_path=temp_db)

    # Same database should produce same checksum
    assert metadata1.checksum == metadata2.checksum
    assert len(metadata1.checksum) == 64  # SHA256 length


@pytest.mark.unit
def test_restore_creates_safety_backup(backup_service, temp_db, tmp_path):
    """Test that restore creates a safety backup of current database."""
    # Create original backup
    metadata = backup_service.create_backup(db_path=temp_db)

    # Modify the database
    service = DatabaseService(str(temp_db))
    service.connect()
    from src.core.events import Event

    event = Event(name="New Event", lore_date=200.0)
    service.insert_event(event)
    service.close()

    # Restore from backup (should create safety backup first)
    success = backup_service.restore_backup(metadata.backup_path, temp_db)

    assert success is True

    # Check that a pre_restore backup was created
    safety_backups = list(temp_db.parent.glob("pre_restore_*.kraken"))
    assert len(safety_backups) > 0


@pytest.mark.unit
def test_backup_config_defaults():
    """Test that BackupConfig has sensible defaults."""
    config = BackupConfig()

    assert config.enabled is True
    assert config.auto_save_interval_minutes == 5
    assert config.auto_save_retention_count == 12
    assert config.daily_retention_count == 7
    assert config.weekly_retention_count == 4
    assert config.manual_retention_count == -1  # Unlimited
    assert config.verify_after_backup is True
    assert config.vacuum_before_backup is False
