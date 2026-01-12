"""
Backup Settings Dialog.

Provides configuration for backup settings including auto-save intervals,
retention policies, and backup locations.
"""

import logging
import os
import sys
from typing import Optional

from PySide6.QtCore import QSettings, Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.app.constants import WINDOW_SETTINGS_APP, WINDOW_SETTINGS_KEY
from src.core.paths import get_backup_directory
from src.gui.utils.style_helper import StyleHelper

logger = logging.getLogger(__name__)

# Settings keys for backup configuration
BACKUP_ENABLED_KEY = "backup_enabled"
BACKUP_AUTO_SAVE_INTERVAL_KEY = "backup_auto_save_interval"
BACKUP_AUTO_SAVE_RETENTION_KEY = "backup_auto_save_retention"
BACKUP_DAILY_RETENTION_KEY = "backup_daily_retention"
BACKUP_WEEKLY_RETENTION_KEY = "backup_weekly_retention"
BACKUP_MANUAL_RETENTION_KEY = "backup_manual_retention"
BACKUP_VERIFY_AFTER_KEY = "backup_verify_after"
BACKUP_VACUUM_BEFORE_KEY = "backup_vacuum_before"
BACKUP_CUSTOM_DIR_KEY = "backup_custom_dir"
BACKUP_EXTERNAL_PATH_KEY = "backup_external_path"


class BackupSettingsDialog(QDialog):
    """
    Dialog for configuring backup settings.

    Provides controls for:
    - Enabling/disabling automated backups
    - Auto-save interval configuration
    - Retention policy settings for each backup type
    - Custom backup directory configuration
    - External backup path configuration
    """

    settings_changed = Signal()  # Emitted when settings are saved

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Initialize the Backup Settings Dialog.

        Args:
            parent: Parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle("Backup Settings")
        self.setMinimumWidth(450)
        self.setMinimumHeight(500)

        logger.info("Initializing Backup Settings Dialog")

        # Main layout
        main_layout = QVBoxLayout(self)
        StyleHelper.apply_standard_list_spacing(main_layout)

        # Create sections
        self._create_general_section(main_layout)
        self._create_retention_section(main_layout)
        self._create_location_section(main_layout)

        # Spacer
        main_layout.addStretch()

        # Button box
        self._create_buttons(main_layout)

        # Load current settings
        self.load_settings()

    def _create_general_section(self, parent_layout: QVBoxLayout) -> None:
        """Create the general settings section."""
        group = QGroupBox("General Settings")
        layout = QFormLayout(group)
        StyleHelper.apply_standard_list_spacing(layout)

        # Enable backups checkbox
        self.chk_enabled = QCheckBox("Enable automated backups")
        self.chk_enabled.setToolTip(
            "When enabled, backups are created automatically at regular intervals"
        )
        layout.addRow(self.chk_enabled)

        # Auto-save interval
        self.spin_interval = QSpinBox()
        self.spin_interval.setRange(1, 60)
        self.spin_interval.setValue(5)
        self.spin_interval.setSuffix(" minutes")
        self.spin_interval.setToolTip("How often to create auto-save backups")
        layout.addRow("Auto-save interval:", self.spin_interval)

        # Verify after backup
        self.chk_verify = QCheckBox("Verify backup integrity after creation")
        self.chk_verify.setToolTip(
            "Ensures backup files are valid by checking their integrity"
        )
        layout.addRow(self.chk_verify)

        # Vacuum before backup
        self.chk_vacuum = QCheckBox("Optimize database before backup")
        self.chk_vacuum.setToolTip(
            "Runs VACUUM to reclaim space before backup (may be slow for large DBs)"
        )
        layout.addRow(self.chk_vacuum)

        parent_layout.addWidget(group)

    def _create_retention_section(self, parent_layout: QVBoxLayout) -> None:
        """Create the retention policy section."""
        group = QGroupBox("Retention Policy")
        layout = QFormLayout(group)
        StyleHelper.apply_standard_list_spacing(layout)

        # Auto-save retention
        self.spin_auto_retention = QSpinBox()
        self.spin_auto_retention.setRange(1, 100)
        self.spin_auto_retention.setValue(12)
        self.spin_auto_retention.setToolTip("Number of auto-save backups to keep")
        layout.addRow("Auto-save backups:", self.spin_auto_retention)

        # Daily retention
        self.spin_daily_retention = QSpinBox()
        self.spin_daily_retention.setRange(1, 365)
        self.spin_daily_retention.setValue(7)
        self.spin_daily_retention.setToolTip("Number of daily backups to keep")
        layout.addRow("Daily backups:", self.spin_daily_retention)

        # Weekly retention
        self.spin_weekly_retention = QSpinBox()
        self.spin_weekly_retention.setRange(1, 52)
        self.spin_weekly_retention.setValue(4)
        self.spin_weekly_retention.setToolTip("Number of weekly backups to keep")
        layout.addRow("Weekly backups:", self.spin_weekly_retention)

        # Manual retention
        self.spin_manual_retention = QSpinBox()
        self.spin_manual_retention.setRange(-1, 1000)
        self.spin_manual_retention.setValue(-1)
        self.spin_manual_retention.setSpecialValueText("Unlimited")
        self.spin_manual_retention.setToolTip(
            "Number of manual backups to keep (-1 = unlimited)"
        )
        layout.addRow("Manual backups:", self.spin_manual_retention)

        parent_layout.addWidget(group)

    def _create_location_section(self, parent_layout: QVBoxLayout) -> None:
        """Create the backup location section."""
        group = QGroupBox("Backup Location")
        layout = QVBoxLayout(group)
        StyleHelper.apply_standard_list_spacing(layout)

        # Current backup path display
        self.lbl_current_path = QLabel()
        self.lbl_current_path.setWordWrap(True)
        self.lbl_current_path.setStyleSheet("color: #888;")
        layout.addWidget(self.lbl_current_path)

        # Open folder button
        btn_open = QPushButton("Open Backup Folder")
        btn_open.clicked.connect(self._on_open_folder)
        layout.addWidget(btn_open)

        # Separator
        layout.addSpacing(10)

        # Custom directory
        custom_layout = QHBoxLayout()
        custom_layout.addWidget(QLabel("Custom directory:"))
        self.edit_custom_dir = QLineEdit()
        self.edit_custom_dir.setPlaceholderText("Leave empty to use default")
        custom_layout.addWidget(self.edit_custom_dir, stretch=1)
        btn_browse_custom = QPushButton("Browse...")
        btn_browse_custom.clicked.connect(self._on_browse_custom)
        custom_layout.addWidget(btn_browse_custom)
        layout.addLayout(custom_layout)

        # External backup path
        external_layout = QHBoxLayout()
        external_layout.addWidget(QLabel("External backup:"))
        self.edit_external_path = QLineEdit()
        self.edit_external_path.setPlaceholderText("Optional external backup location")
        self.edit_external_path.setToolTip(
            "Backups will also be copied to this location (e.g., network drive)"
        )
        external_layout.addWidget(self.edit_external_path, stretch=1)
        btn_browse_external = QPushButton("Browse...")
        btn_browse_external.clicked.connect(self._on_browse_external)
        external_layout.addWidget(btn_browse_external)
        layout.addLayout(external_layout)

        parent_layout.addWidget(group)

    def _create_buttons(self, parent_layout: QVBoxLayout) -> None:
        """Create the dialog buttons."""
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        btn_ok = QPushButton("OK")
        btn_ok.setStyleSheet(StyleHelper.get_primary_button_style())
        btn_ok.clicked.connect(self._on_ok_clicked)
        btn_layout.addWidget(btn_ok)

        parent_layout.addLayout(btn_layout)

    def _update_path_label(self) -> None:
        """Update the current backup path label."""
        custom_dir = self.edit_custom_dir.text().strip()
        if custom_dir:
            path = custom_dir
        else:
            path = str(get_backup_directory())
        self.lbl_current_path.setText(f"Current path: {path}")

    @Slot()
    def _on_ok_clicked(self) -> None:
        """Handle OK button click."""
        self.save_settings()
        self.settings_changed.emit()
        self.accept()

    @Slot()
    def _on_open_folder(self) -> None:
        """Open the backup folder in file explorer."""
        custom_dir = self.edit_custom_dir.text().strip()
        if custom_dir and os.path.isdir(custom_dir):
            path = custom_dir
        else:
            path = str(get_backup_directory())

        try:
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                import subprocess

                subprocess.run(["open", path], check=False)
            else:
                import subprocess

                subprocess.run(["xdg-open", path], check=False)
        except Exception as e:
            logger.error(f"Failed to open backup folder: {e}")

    @Slot()
    def _on_browse_custom(self) -> None:
        """Browse for custom backup directory."""
        current = self.edit_custom_dir.text().strip()
        if not current:
            current = str(get_backup_directory())

        path = QFileDialog.getExistingDirectory(
            self, "Select Backup Directory", current
        )
        if path:
            self.edit_custom_dir.setText(path)
            self._update_path_label()

    @Slot()
    def _on_browse_external(self) -> None:
        """Browse for external backup path."""
        current = self.edit_external_path.text().strip()
        path = QFileDialog.getExistingDirectory(
            self, "Select External Backup Location", current
        )
        if path:
            self.edit_external_path.setText(path)

    def save_settings(self) -> None:
        """Save settings to QSettings."""
        settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)

        settings.setValue(BACKUP_ENABLED_KEY, self.chk_enabled.isChecked())
        settings.setValue(BACKUP_AUTO_SAVE_INTERVAL_KEY, self.spin_interval.value())
        settings.setValue(
            BACKUP_AUTO_SAVE_RETENTION_KEY, self.spin_auto_retention.value()
        )
        settings.setValue(BACKUP_DAILY_RETENTION_KEY, self.spin_daily_retention.value())
        settings.setValue(
            BACKUP_WEEKLY_RETENTION_KEY, self.spin_weekly_retention.value()
        )
        settings.setValue(
            BACKUP_MANUAL_RETENTION_KEY, self.spin_manual_retention.value()
        )
        settings.setValue(BACKUP_VERIFY_AFTER_KEY, self.chk_verify.isChecked())
        settings.setValue(BACKUP_VACUUM_BEFORE_KEY, self.chk_vacuum.isChecked())
        settings.setValue(BACKUP_CUSTOM_DIR_KEY, self.edit_custom_dir.text().strip())
        settings.setValue(
            BACKUP_EXTERNAL_PATH_KEY, self.edit_external_path.text().strip()
        )

        logger.info(
            f"Backup settings saved. Enabled: {self.chk_enabled.isChecked()}, "
            f"Interval: {self.spin_interval.value()} min"
        )

    def load_settings(self) -> None:
        """Load settings from QSettings."""
        settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)

        self.chk_enabled.setChecked(settings.value(BACKUP_ENABLED_KEY, True, type=bool))
        self.spin_interval.setValue(
            int(settings.value(BACKUP_AUTO_SAVE_INTERVAL_KEY, 5))
        )
        self.spin_auto_retention.setValue(
            int(settings.value(BACKUP_AUTO_SAVE_RETENTION_KEY, 12))
        )
        self.spin_daily_retention.setValue(
            int(settings.value(BACKUP_DAILY_RETENTION_KEY, 7))
        )
        self.spin_weekly_retention.setValue(
            int(settings.value(BACKUP_WEEKLY_RETENTION_KEY, 4))
        )
        self.spin_manual_retention.setValue(
            int(settings.value(BACKUP_MANUAL_RETENTION_KEY, -1))
        )
        self.chk_verify.setChecked(
            settings.value(BACKUP_VERIFY_AFTER_KEY, True, type=bool)
        )
        self.chk_vacuum.setChecked(
            settings.value(BACKUP_VACUUM_BEFORE_KEY, False, type=bool)
        )
        self.edit_custom_dir.setText(settings.value(BACKUP_CUSTOM_DIR_KEY, ""))
        self.edit_external_path.setText(settings.value(BACKUP_EXTERNAL_PATH_KEY, ""))

        self._update_path_label()
