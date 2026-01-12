"""
Unit tests for BackupSettingsDialog.
"""

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QSettings

from src.gui.dialogs.backup_settings_dialog import (
    BACKUP_AUTO_SAVE_INTERVAL_KEY,
    BACKUP_AUTO_SAVE_RETENTION_KEY,
    BACKUP_CUSTOM_DIR_KEY,
    BACKUP_DAILY_RETENTION_KEY,
    BACKUP_ENABLED_KEY,
    BACKUP_VERIFY_AFTER_KEY,
    BackupSettingsDialog,
)


@pytest.fixture(scope="session")
def qapp():
    """Create or get QApplication instance."""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def dialog(qapp):
    """Create a BackupSettingsDialog instance."""
    # Don't mock QSettings - let it use defaults
    dlg = BackupSettingsDialog()
    yield dlg
    dlg.close()


@pytest.mark.unit
class TestBackupSettingsDialogInit:
    """Tests for dialog initialization."""

    def test_dialog_opens_without_error(self, dialog):
        """Dialog should open without errors."""
        assert dialog is not None
        assert dialog.windowTitle() == "Backup Settings"

    def test_dialog_has_all_controls(self, dialog):
        """Dialog should have all required controls."""
        # General section
        assert dialog.chk_enabled is not None
        assert dialog.spin_interval is not None
        assert dialog.chk_verify is not None
        assert dialog.chk_vacuum is not None

        # Retention section
        assert dialog.spin_auto_retention is not None
        assert dialog.spin_daily_retention is not None
        assert dialog.spin_weekly_retention is not None
        assert dialog.spin_manual_retention is not None

        # Location section
        assert dialog.lbl_current_path is not None
        assert dialog.edit_custom_dir is not None
        assert dialog.edit_external_path is not None


@pytest.mark.unit
class TestBackupSettingsDialogDefaults:
    """Tests for default values."""

    def test_default_enabled(self, dialog):
        """Backup should be enabled by default."""
        assert dialog.chk_enabled.isChecked() is True

    def test_default_interval(self, dialog):
        """Default interval should be 5 minutes."""
        assert dialog.spin_interval.value() == 5

    def test_default_auto_retention(self, dialog):
        """Default auto-save retention should be 12."""
        assert dialog.spin_auto_retention.value() == 12

    def test_default_daily_retention(self, dialog):
        """Default daily retention should be 7."""
        assert dialog.spin_daily_retention.value() == 7

    def test_default_weekly_retention(self, dialog):
        """Default weekly retention should be 4."""
        assert dialog.spin_weekly_retention.value() == 4

    def test_default_manual_retention(self, dialog):
        """Default manual retention should be -1 (unlimited)."""
        assert dialog.spin_manual_retention.value() == -1

    def test_default_verify(self, dialog):
        """Verify after backup should be enabled by default."""
        assert dialog.chk_verify.isChecked() is True

    def test_default_vacuum(self, dialog):
        """Vacuum before backup should be disabled by default."""
        assert dialog.chk_vacuum.isChecked() is False


@pytest.mark.unit
class TestBackupSettingsDialogSaveLoad:
    """Tests for save/load functionality."""

    def test_save_settings(self, dialog):
        """Settings should be saved correctly."""
        dialog.chk_enabled.setChecked(False)
        dialog.spin_interval.setValue(10)
        dialog.spin_auto_retention.setValue(24)
        dialog.chk_verify.setChecked(False)
        dialog.edit_custom_dir.setText("/custom/path")

        with patch.object(QSettings, "setValue") as mock_set:
            dialog.save_settings()

            # Verify key settings were saved
            calls = {call[0][0]: call[0][1] for call in mock_set.call_args_list}
            assert calls[BACKUP_ENABLED_KEY] is False
            assert calls[BACKUP_AUTO_SAVE_INTERVAL_KEY] == 10
            assert calls[BACKUP_AUTO_SAVE_RETENTION_KEY] == 24
            assert calls[BACKUP_VERIFY_AFTER_KEY] is False
            assert calls[BACKUP_CUSTOM_DIR_KEY] == "/custom/path"

    def test_load_settings(self, qapp):
        """Settings should be loaded correctly."""
        mock_values = {
            BACKUP_ENABLED_KEY: False,
            BACKUP_AUTO_SAVE_INTERVAL_KEY: 15,
            BACKUP_DAILY_RETENTION_KEY: 14,
            BACKUP_CUSTOM_DIR_KEY: "/test/path",
        }

        def mock_value(key, default=None, type=None):
            if key in mock_values:
                return mock_values[key]
            if type is bool:
                return default if default is not None else True
            return default if default is not None else 0

        with patch.object(QSettings, "value", side_effect=mock_value):
            dlg = BackupSettingsDialog()

            assert dlg.chk_enabled.isChecked() is False
            assert dlg.spin_interval.value() == 15
            assert dlg.spin_daily_retention.value() == 14
            assert dlg.edit_custom_dir.text() == "/test/path"

            dlg.close()


@pytest.mark.unit
class TestBackupSettingsDialogSignals:
    """Tests for signal emissions."""

    def test_settings_changed_signal_on_ok(self, dialog):
        """settings_changed signal should be emitted on OK."""
        handler = MagicMock()
        dialog.settings_changed.connect(handler)

        with patch.object(QSettings, "setValue"):
            dialog._on_ok_clicked()

        handler.assert_called_once()
