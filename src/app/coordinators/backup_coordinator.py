import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from PySide6.QtCore import QSettings, QTimer, Slot
from PySide6.QtWidgets import (
    QFileDialog,
    QInputDialog,
    QMessageBox,
)

from src.app.constants import WINDOW_SETTINGS_APP, WINDOW_SETTINGS_KEY
from src.app.coordinators.base_coordinator import BaseCoordinator
from src.core.paths import get_backup_directory
from src.services.backup_service import BackupType

if TYPE_CHECKING:
    from src.app.main_window import MainWindow

logger = logging.getLogger(__name__)


class BackupCoordinator(BaseCoordinator):
    """Coordinator for Backup operations and UI.

    Handles:
    - Manual Backups
    - Backup Restoration
    - Backup Settings UI
    - Backup Location access
    """

    def __init__(self, main_window: "MainWindow") -> None:
        super().__init__(main_window)

    @property
    def backup_service(self) -> Any:
        """Access backup service from main window."""
        return self.main_window.backup_service

    @Slot()
    def create_manual_backup(self) -> None:
        """Creates a manual backup with optional description."""
        if self.backup_service is None:
            QMessageBox.warning(
                self.main_window,
                "Backup Unavailable",
                "Backup service is not initialized.",
            )
            return

        # Ask user for optional description
        description, ok = QInputDialog.getText(
            self.main_window, "Create Backup", "Backup description (optional):"
        )
        if not ok:
            return  # User cancelled

        # Create backup - use QTimer to allow UI to update first
        self.main_window.status_bar.showMessage("Creating backup...")

        # Defer backup execution to allow status bar message to display
        QTimer.singleShot(0, lambda: self._execute_backup(description))

    def _execute_backup(self, description: str) -> None:
        """Execute the backup operation.

        Args:
            description: Optional description for the backup.

        Note:
            This method is called via QTimer.singleShot to avoid blocking
            the UI during status bar updates.
        """
        metadata = self.backup_service.create_backup(
            backup_type=BackupType.MANUAL, description=description
        )

        if metadata:
            self.main_window.status_bar.showMessage(
                f"Backup created: {metadata.backup_path.name}", 5000
            )
            QMessageBox.information(
                self.main_window,
                "Backup Created",
                f"Backup created successfully!\n\n"
                f"Location: {metadata.backup_path}\n"
                f"Size: {metadata.size / 1024:.1f} KB",
            )
        else:
            self.main_window.status_bar.showMessage("Backup failed", 5000)
            QMessageBox.critical(
                self.main_window,
                "Backup Failed",
                "Failed to create backup. Your data is safe, but the backup "
                "could not be saved.\n\n"
                "Possible causes:\n"
                "• Insufficient disk space\n"
                "• Write permissions denied in backup directory\n"
                "• Database file is locked by another process\n\n"
                "Recovery steps:\n"
                "1. Check available disk space\n"
                "2. Try again in a few moments\n"
                "3. Check application logs for detailed error information\n"
                "4. Consider changing backup location in Settings",
            )

    @Slot()
    def restore_from_backup(self) -> None:
        """Restores database from a backup file."""
        if self.backup_service is None:
            QMessageBox.warning(
                self.main_window,
                "Backup Unavailable",
                "Backup service is not initialized.",
            )
            return

        # Get backup file from user
        backup_file, _ = QFileDialog.getOpenFileName(
            self.main_window,
            "Select Backup File",
            str(self.backup_service.config.backup_dir or ""),
            "Kraken Database (*.kraken)",
        )

        if not backup_file:
            return  # User cancelled

        # Warn user about restoration
        reply = QMessageBox.question(
            self.main_window,
            "Restore Backup",
            "Restoring will replace the current database.\n"
            "A safety backup will be created first.\n\n"
            "Do you want to continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # Restore backup - use QTimer to allow UI to update first
        self.main_window.status_bar.showMessage("Restoring from backup...")

        # Defer restore execution to allow status bar message to display
        QTimer.singleShot(0, lambda: self._execute_restore(backup_file))

    def _execute_restore(self, backup_file: str) -> None:
        """Execute the restore operation.

        Args:
            backup_file: Path to the backup file to restore from.

        Note:
            This method is called via QTimer.singleShot to avoid blocking
            the UI during status bar updates.
        """
        success = self.backup_service.restore_backup(
            Path(backup_file), Path(self.main_window.db_path)
        )

        if success:
            self.main_window.status_bar.showMessage("Restore completed", 5000)
            QMessageBox.information(
                self.main_window,
                "Restore Complete",
                "Database restored successfully!\n\n"
                "The application will now close. Please restart to use the "
                "restored database.",
            )
            # Close application so user can restart
            self.main_window.close()
        else:
            self.main_window.status_bar.showMessage("Restore failed", 5000)
            QMessageBox.critical(
                self.main_window,
                "Restore Failed",
                "Failed to restore backup. Your current database is unchanged "
                "and a safety backup was created before the attempt.\n\n"
                "Possible causes:\n"
                "• Backup file is corrupted\n"
                "• Backup file is from an incompatible version\n"
                "• Insufficient permissions to modify database\n\n"
                "Recovery steps:\n"
                "1. Verify the backup file is not corrupted\n"
                "2. Try a different backup file\n"
                "3. Check application logs for detailed error information\n"
                "4. If backup is from an older version, use migration tools",
            )

    @Slot()
    def show_backup_location(self) -> None:
        """Opens the backup directory in the system file explorer."""
        if self.backup_service is None:
            QMessageBox.warning(
                self.main_window,
                "Backup Unavailable",
                "Backup service is not initialized.",
            )
            return

        # Use configured backup directory if set, otherwise use default
        if self.backup_service.config.backup_dir:
            backup_dir = Path(self.backup_service.config.backup_dir)
        else:
            backup_dir = get_backup_directory()

        backup_dir_str = str(backup_dir)
        logger.debug(f"show_backup_location: backup_dir = {backup_dir_str}")

        # Ensure directory exists - use os.makedirs for explicit creation
        try:
            os.makedirs(backup_dir_str, exist_ok=True)
            logger.debug("show_backup_location: os.makedirs completed")
        except OSError as e:
            logger.error(f"Failed to create backup directory: {e}")
            QMessageBox.warning(
                self.main_window,
                "Backup Location Error",
                f"Could not create backup directory:\n{backup_dir_str}\n\nError: {e}",
            )
            return

        # Verify directory actually exists before opening
        exists = os.path.isdir(backup_dir_str)
        logger.debug(f"show_backup_location: exists check = {exists}")
        if not exists:
            logger.error(f"Backup directory does not exist: {backup_dir_str}")
            QMessageBox.warning(
                self.main_window,
                "Backup Location Error",
                f"Backup directory could not be created:\n{backup_dir_str}",
            )
            return

        logger.info(f"Opening backup location: {backup_dir_str}")

        # Open directory in file explorer
        try:
            if sys.platform == "win32":
                # Use os.startfile on Windows - more reliable than subprocess
                os.startfile(backup_dir_str)
            elif sys.platform == "darwin":
                subprocess.run(["open", backup_dir_str], check=False)
            else:  # Linux
                subprocess.run(["xdg-open", backup_dir_str], check=False)
        except Exception as e:
            logger.error(f"Failed to open backup directory: {e}")
            QMessageBox.information(
                self.main_window,
                "Backup Location",
                f"Backup directory:\n{backup_dir_str}",
            )

    @Slot()
    def show_backup_settings(self) -> None:
        """Opens the backup settings dialog and applies changes to BackupService."""
        from src.core.backup_config import BackupConfig
        from src.gui.dialogs.backup_settings_dialog import (
            BACKUP_AUTO_SAVE_INTERVAL_KEY,
            BACKUP_AUTO_SAVE_RETENTION_KEY,
            BACKUP_CUSTOM_DIR_KEY,
            BACKUP_DAILY_RETENTION_KEY,
            BACKUP_ENABLED_KEY,
            BACKUP_EXTERNAL_PATH_KEY,
            BACKUP_MANUAL_RETENTION_KEY,
            BACKUP_VACUUM_BEFORE_KEY,
            BACKUP_VERIFY_AFTER_KEY,
            BACKUP_WEEKLY_RETENTION_KEY,
            BackupSettingsDialog,
        )

        dialog = BackupSettingsDialog(self.main_window)

        def apply_settings() -> None:
            """Apply dialog settings to BackupService."""
            if self.backup_service is None:
                return

            settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)

            # Build config from QSettings
            custom_dir = cast(str, settings.value(BACKUP_CUSTOM_DIR_KEY, ""))
            external_path = cast(
                str, settings.value(BACKUP_EXTERNAL_PATH_KEY, "")
            )

            config = BackupConfig(
                enabled=cast(
                    bool,
                    settings.value(BACKUP_ENABLED_KEY, True, type=bool),
                ),
                auto_save_interval_minutes=int(
                    cast(
                        int | str,
                        settings.value(BACKUP_AUTO_SAVE_INTERVAL_KEY, 5),
                    )
                ),
                auto_save_retention_count=int(
                    cast(
                        int | str,
                        settings.value(BACKUP_AUTO_SAVE_RETENTION_KEY, 12),
                    )
                ),
                daily_retention_count=int(
                    cast(
                        int | str,
                        settings.value(BACKUP_DAILY_RETENTION_KEY, 7),
                    )
                ),
                weekly_retention_count=int(
                    cast(
                        int | str,
                        settings.value(BACKUP_WEEKLY_RETENTION_KEY, 4),
                    )
                ),
                manual_retention_count=int(
                    cast(
                        int | str,
                        settings.value(BACKUP_MANUAL_RETENTION_KEY, -1),
                    )
                ),
                verify_after_backup=cast(
                    bool,
                    settings.value(BACKUP_VERIFY_AFTER_KEY, True, type=bool),
                ),
                vacuum_before_backup=cast(
                    bool,
                    settings.value(BACKUP_VACUUM_BEFORE_KEY, False, type=bool),
                ),
                backup_dir=Path(custom_dir) if custom_dir else None,
                external_backup_path=Path(external_path) if external_path else None,
            )

            self.backup_service.update_config(config)
            logger.info("Backup settings applied to service")

        dialog.settings_changed.connect(apply_settings)
        dialog.exec()
