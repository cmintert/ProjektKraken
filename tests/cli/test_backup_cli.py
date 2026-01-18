import argparse
from pathlib import Path
from unittest.mock import patch

import pytest

from src.cli.backup import create_backup, list_backups, restore_backup
from src.services.backup_service import BackupType


@pytest.fixture
def mock_backup_service():
    with patch("src.cli.backup.BackupService") as mock:
        yield mock


@pytest.fixture
def mock_db_path(tmp_path):
    return tmp_path / "world.kraken"


def test_create_backup_success(mock_backup_service, mock_db_path):
    """Test successful backup creation."""
    args = argparse.Namespace(
        database=str(mock_db_path), description="Test Backup", verbose=False
    )

    service_instance = mock_backup_service.return_value
    service_instance.create_backup.return_value = Path("backup.kraken")

    assert create_backup(args) == 0

    service_instance.set_database_path.assert_called_with(str(mock_db_path))
    service_instance.create_backup.assert_called_with(
        backup_type=BackupType.MANUAL, description="Test Backup"
    )


def test_create_backup_failure(mock_backup_service, mock_db_path):
    """Test failed backup creation."""
    args = argparse.Namespace(
        database=str(mock_db_path), description="Test Backup", verbose=False
    )

    service_instance = mock_backup_service.return_value
    service_instance.create_backup.return_value = None

    assert create_backup(args) == 1


def test_list_backups_empty(mock_backup_service, mock_db_path):
    """Test listing backups when none exist."""
    args = argparse.Namespace(database=str(mock_db_path), verbose=False)

    service_instance = mock_backup_service.return_value
    service_instance.backup_root = Path("/tmp/backups")

    # Mock glob to return nothing
    with patch("pathlib.Path.glob", return_value=[]):
        assert list_backups(args) == 0


def test_restore_backup_success(mock_backup_service, mock_db_path):
    """Test successful backup restoration."""
    backup_file = mock_db_path.parent / "backup.kraken"
    backup_file.touch()

    args = argparse.Namespace(
        database=str(mock_db_path), file=str(backup_file), force=True, verbose=False
    )

    service_instance = mock_backup_service.return_value
    service_instance.restore_backup.return_value = True

    assert restore_backup(args) == 0
    service_instance.restore_backup.assert_called_with(backup_file, mock_db_path)


def test_restore_backup_file_not_found(mock_backup_service, mock_db_path):
    """Test restore with missing backup file."""
    args = argparse.Namespace(
        database=str(mock_db_path), file="nonexistent.kraken", force=True, verbose=False
    )

    assert restore_backup(args) == 1
    mock_backup_service.return_value.restore_backup.assert_not_called()
