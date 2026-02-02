"""Security tests for checking Path Traversal vulnerabilities."""

import pytest
from pathlib import Path
import os
from src.services.backup_service import BackupService, BackupType, BackupConfig
from src.services.obsidian_exporter import ObsidianExporter
from src.services.prompt_loader import PromptLoader, PromptTemplate
from src.core.base_theme_manager import BaseThemeManager
from src.core.fast_inject import FastInjectManager, FastInjectTemplate
from unittest.mock import MagicMock, patch


@pytest.fixture
def temp_backup_dir(tmp_path):
    """Create a temporary backup directory."""
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    return backup_dir


@pytest.fixture
def mock_db_service():
    """Mock database service for dependencies."""
    mock = MagicMock()
    mock.get_all_entities.return_value = []
    mock.get_all_events.return_value = []
    return mock


class TestBackupServiceSecurity:
    """Tests for BackupService path traversal."""

    def test_restore_backup_traversal(self, temp_backup_dir, tmp_path):
        """Test accessing a file outside backup directory raises error."""
        config = BackupConfig(enabled=True, backup_dir=temp_backup_dir)
        service = BackupService(config)

        # Create a valid SQLite file outside backup dir to simulate a backup
        import sqlite3

        sensitive_file = tmp_path / "sensitive.kraken"
        conn = sqlite3.connect(sensitive_file)
        conn.execute("CREATE TABLE test (id INTEGER)")
        conn.commit()
        conn.close()

        # Create a target database
        target_db = temp_backup_dir / "target.kraken"
        conn = sqlite3.connect(target_db)
        conn.execute("CREATE TABLE test (id INTEGER)")
        conn.commit()
        conn.close()

        # Attempt traversal path
        traversal_path = temp_backup_dir / ".." / "sensitive.kraken"

        # Expect security error (ValueError) when we implement the fix
        # The security check should run BEFORE file validation
        with pytest.raises(ValueError, match="Security Violation"):
            service.restore_backup(traversal_path, target_db)

    def test_restore_backup_absolute_path_traversal(self, temp_backup_dir, tmp_path):
        """Test accessing an absolute path outside backup directory raises error."""
        config = BackupConfig(enabled=True, backup_dir=temp_backup_dir)
        service = BackupService(config)

        # Create a valid SQLite file outside backup dir
        import sqlite3

        sensitive_file = tmp_path / "sensitive.kraken"
        conn = sqlite3.connect(sensitive_file)
        conn.execute("CREATE TABLE test (id INTEGER)")
        conn.commit()
        conn.close()

        # Create a target database
        target_db = temp_backup_dir / "target.kraken"
        conn = sqlite3.connect(target_db)
        conn.execute("CREATE TABLE test (id INTEGER)")
        conn.commit()
        conn.close()

        with pytest.raises(ValueError, match="Security Violation"):
            service.restore_backup(sensitive_file, target_db)


class TestObsidianExporterSecurity:
    """Tests for ObsidianExporter path traversal."""

    def test_export_traversal(self, tmp_path, mock_db_service):
        """Test exporting to a traversal path raises error."""
        exporter = ObsidianExporter(mock_db_service)

        # This one is tricky because export_to_folder TAKES an output_dir.
        # The vulnerability is likely if the output_dir ITSELF is allowed to be anywhere?
        # Or maybe if filenames within it can traverse?
        # The report said: filepath.write_text(content)
        # We need to ensure that the constructed filepath stays within output_dir

        output_dir = tmp_path / "exports"
        output_dir.mkdir()

        # Mock an entity with a malicious name that might cause traversal if used in filename
        malicious_entity = MagicMock()
        malicious_entity.name = "../../../etc/passwd"
        malicious_entity.id = "1"
        malicious_entity.type = "person"
        malicious_entity.tags = []
        malicious_entity.created_at = 0
        malicious_entity.modified_at = 0

        mock_db_service.get_all_entities.return_value = [malicious_entity]

        # The exporter uses _get_unique_filename which calls _sanitize_filename.
        # We need to verify _sanitize_filename actually strips traversal chars adequately
        # OR that we explicitly check the final path.

        # If the fix works, this should NOT write outside output_dir
        exporter.export_to_folder(output_dir)

        # Verify no file exists successfully outside
        assert not (tmp_path / "passwd.md").exists()
        assert not (tmp_path / "etc/passwd.md").exists()


class TestPromptLoaderSecurity:
    """Tests for PromptLoader path traversal."""

    def test_load_template_traversal(self, tmp_path):
        """Test loading a template with traversal sequence in ID."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()

        # Create a "sensitive" file outside
        secret_file = tmp_path / "secret.txt"
        secret_file.write_text("---`\nkey: value\n---\nSECRET CONTENT")

        loader = PromptLoader(str(templates_dir))

        # Attempt to load the secret file via traversal in template_id
        # Assuming filename construction is f"{template_id}_v{version}.txt"
        traversal_id = "../secret"

        # Should raise security violation
        with pytest.raises(ValueError, match="Security Violation"):
            # Version None tries to find latest, which involves globbing.
            # If we provide specific version, it constructs the path directly.
            # filename = "../secret_v1.0.txt" -- might not hit secret.txt exactly unless we control version too
            # If we pass version="", filename is "../secret_v.txt"

            # Let's try to access a file we named specifically to match the pattern if possible
            # But the fix should block ".." regardless.
            loader.load_template(traversal_id, version="1.0")


class TestThemeManagerSecurity:
    """Tests for BaseThemeManager path traversal."""

    def test_load_stylesheet_traversal(self, tmp_path):
        """Test loading stylesheet from outside authorized paths."""
        # Theme manager doesn't strictly have a "base dir" for stylesheets in the signature,
        # but we should probably restrict it or at least check it doesn't leave the app structure?
        # The report was `with open(path, "r")`.
        # If we enforce it must be within resource path, we can test that.
        pass
