"""Backup Settings Dialog.

Provides configuration for backup settings including auto-save intervals, retention
policies, and backup locations.
"""

import logging
import os
import sys
from typing import Optional

from PySide6.QtCore import QSettings, Signal, Slot
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QGroupBox,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.core.paths import get_backup_directory
from src.gui.constants import WINDOW_SETTINGS_APP, WINDOW_SETTINGS_KEY
from src.gui.utils.help_context import declare_inspection
from src.gui.utils.settings_reader import (
    read_bool_setting,
    read_int_setting,
    read_str_setting,
)
from src.gui.utils.style_helper import StyleHelper
from src.gui.widgets.action_flow_layout import ActionFlowLayout as QHBoxLayout
from src.gui.widgets.numeric_inputs import ScrollSafeSpinBox
from src.gui.widgets.responsive_form import ResponsiveFormLayout as QFormLayout
from src.gui.widgets.standard_buttons import StandardButton as QPushButton
from src.gui.widgets.wrapping_choices import WrappingCheckBox as QCheckBox

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
    """Dialog for configuring backup settings.

    Provides controls for:
    - Enabling/disabling automated backups
    - Auto-save interval configuration
    - Retention policy settings for each backup type
    - Custom backup directory configuration
    - External backup path configuration
    """

    settings_changed = Signal()  # Emitted when settings are saved

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the Backup Settings Dialog.

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

        from src.gui.widgets.responsive_form import scrollable_form_page

        body = QWidget()
        body_layout = QVBoxLayout(body)
        StyleHelper.apply_standard_list_spacing(body_layout)
        main_layout.addWidget(scrollable_form_page(body), 1)

        # Create sections
        self._create_general_section(body_layout)
        self._create_retention_section(body_layout)
        self._create_location_section(body_layout)

        # Spacer

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
        self.chk_enabled = declare_inspection(
            QCheckBox("Enable automated backups"),
            "src-gui-dialogs-backup-settings-dialog-backupsettingsdialog-create-general-section-self-chk-enabled|world.backups|help-inspect-src-gui-dialogs-backup-settings-dialog-backupsettingsdialog-create-general-section-self-chk-enabled",
        )
        self.chk_enabled.setToolTip(
            "When enabled, backups are created automatically at regular intervals"
        )
        layout.addRow(self.chk_enabled)

        # Auto-save interval
        self.spin_interval = declare_inspection(
            ScrollSafeSpinBox(),
            "src-gui-dialogs-backup-settings-dialog-backupsettingsdialog-create-general-section-self-spin-interval|world.backups|help-inspect-src-gui-dialogs-backup-settings-dialog-backupsettingsdialog-create-general-section-self-spin-interval",
        )
        self.spin_interval.setRange(1, 60)
        self.spin_interval.setValue(5)
        self.spin_interval.setSuffix(" minutes")
        self.spin_interval.setToolTip("How often to create auto-save backups")
        layout.addRow("Auto-save interval:", self.spin_interval)

        # Verify after backup
        self.chk_verify = declare_inspection(
            QCheckBox("Verify backup integrity after creation"),
            "src-gui-dialogs-backup-settings-dialog-backupsettingsdialog-create-general-section-self-chk-verify|world.backups|help-inspect-src-gui-dialogs-backup-settings-dialog-backupsettingsdialog-create-general-section-self-chk-verify",
        )
        self.chk_verify.setToolTip(
            "Ensures backup files are valid by checking their integrity"
        )
        layout.addRow(self.chk_verify)

        # Vacuum before backup
        self.chk_vacuum = declare_inspection(
            QCheckBox("Optimize database before backup"),
            "src-gui-dialogs-backup-settings-dialog-backupsettingsdialog-create-general-section-self-chk-vacuum|world.backups|help-inspect-src-gui-dialogs-backup-settings-dialog-backupsettingsdialog-create-general-section-self-chk-vacuum",
        )
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
        self.spin_auto_retention = declare_inspection(
            ScrollSafeSpinBox(),
            "src-gui-dialogs-backup-settings-dialog-backupsettingsdialog-create-retention-section-self-spin-auto-retention|world.backups|help-inspect-src-gui-dialogs-backup-settings-dialog-backupsettingsdialog-create-retention-section-self-spin-auto-retention",
        )
        self.spin_auto_retention.setRange(1, 100)
        self.spin_auto_retention.setValue(12)
        self.spin_auto_retention.setToolTip("Number of auto-save backups to keep")
        layout.addRow("Auto-save backups:", self.spin_auto_retention)

        # Daily retention
        self.spin_daily_retention = declare_inspection(
            ScrollSafeSpinBox(),
            "src-gui-dialogs-backup-settings-dialog-backupsettingsdialog-create-retention-section-self-spin-daily-retention|world.backups|help-inspect-src-gui-dialogs-backup-settings-dialog-backupsettingsdialog-create-retention-section-self-spin-daily-retention",
        )
        self.spin_daily_retention.setRange(1, 365)
        self.spin_daily_retention.setValue(7)
        self.spin_daily_retention.setToolTip("Number of daily backups to keep")
        layout.addRow("Daily backups:", self.spin_daily_retention)

        # Weekly retention
        self.spin_weekly_retention = declare_inspection(
            ScrollSafeSpinBox(),
            "src-gui-dialogs-backup-settings-dialog-backupsettingsdialog-create-retention-section-self-spin-weekly-retention|world.backups|help-inspect-src-gui-dialogs-backup-settings-dialog-backupsettingsdialog-create-retention-section-self-spin-weekly-retention",
        )
        self.spin_weekly_retention.setRange(1, 52)
        self.spin_weekly_retention.setValue(4)
        self.spin_weekly_retention.setToolTip("Number of weekly backups to keep")
        layout.addRow("Weekly backups:", self.spin_weekly_retention)

        # Manual retention
        self.spin_manual_retention = declare_inspection(
            ScrollSafeSpinBox(),
            "src-gui-dialogs-backup-settings-dialog-backupsettingsdialog-create-retention-section-self-spin-manual-retention|world.backups|help-inspect-src-gui-dialogs-backup-settings-dialog-backupsettingsdialog-create-retention-section-self-spin-manual-retention",
        )
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
        self.lbl_current_path.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        self.lbl_current_path.setStyleSheet(StyleHelper.get_preview_label_style())
        layout.addWidget(self.lbl_current_path)

        # Open folder button
        btn_open = declare_inspection(
            QPushButton("Open Backup Folder"),
            "src-gui-dialogs-backup-settings-dialog-backupsettingsdialog-create-location-section-btn-open|world.backups|help-inspect-src-gui-dialogs-backup-settings-dialog-backupsettingsdialog-create-location-section-btn-open",
        )
        btn_open.clicked.connect(self._on_open_folder)
        layout.addWidget(btn_open)

        # Separator
        layout.addSpacing(10)

        # Custom directory
        custom_layout = QHBoxLayout()
        custom_layout.addWidget(QLabel("Custom directory:"))
        self.edit_custom_dir = declare_inspection(
            QLineEdit(),
            "src-gui-dialogs-backup-settings-dialog-backupsettingsdialog-create-location-section-self-edit-custom-dir|world.backups|help-inspect-src-gui-dialogs-backup-settings-dialog-backupsettingsdialog-create-location-section-self-edit-custom-dir",
        )
        self.edit_custom_dir.setPlaceholderText("Leave empty to use default")
        custom_layout.addWidget(self.edit_custom_dir, stretch=1)
        btn_browse_custom = declare_inspection(
            QPushButton("Browse..."),
            "src-gui-dialogs-backup-settings-dialog-backupsettingsdialog-create-location-section-btn-browse-custom|world.backups|help-inspect-src-gui-dialogs-backup-settings-dialog-backupsettingsdialog-create-location-section-btn-browse-custom",
        )
        btn_browse_custom.clicked.connect(self._on_browse_custom)
        custom_layout.addWidget(btn_browse_custom)
        layout.addLayout(custom_layout)

        # External backup path
        external_layout = QHBoxLayout()
        external_layout.addWidget(QLabel("External backup:"))
        self.edit_external_path = declare_inspection(
            QLineEdit(),
            "src-gui-dialogs-backup-settings-dialog-backupsettingsdialog-create-location-section-self-edit-external-path|world.backups|help-inspect-src-gui-dialogs-backup-settings-dialog-backupsettingsdialog-create-location-section-self-edit-external-path",
        )
        self.edit_external_path.setPlaceholderText("Optional external backup location")
        self.edit_external_path.setToolTip(
            "Backups will also be copied to this location (e.g., network drive)"
        )
        external_layout.addWidget(self.edit_external_path, stretch=1)
        btn_browse_external = declare_inspection(
            QPushButton("Browse..."),
            "src-gui-dialogs-backup-settings-dialog-backupsettingsdialog-create-location-section-btn-browse-external|world.backups|help-inspect-src-gui-dialogs-backup-settings-dialog-backupsettingsdialog-create-location-section-btn-browse-external",
        )
        btn_browse_external.clicked.connect(self._on_browse_external)
        external_layout.addWidget(btn_browse_external)
        layout.addLayout(external_layout)

        parent_layout.addWidget(group)

    def _create_buttons(self, parent_layout: QVBoxLayout) -> None:
        """Create the dialog buttons."""
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_cancel = declare_inspection(
            QPushButton("Cancel"),
            "src-gui-dialogs-backup-settings-dialog-backupsettingsdialog-create-buttons-btn-cancel|world.backups|help-inspect-src-gui-dialogs-backup-settings-dialog-backupsettingsdialog-create-buttons-btn-cancel",
        )
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        btn_ok = declare_inspection(
            QPushButton("OK"),
            "src-gui-dialogs-backup-settings-dialog-backupsettingsdialog-create-buttons-btn-ok|world.backups|help-inspect-src-gui-dialogs-backup-settings-dialog-backupsettingsdialog-create-buttons-btn-ok",
        )
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

        self.chk_enabled.setChecked(
            read_bool_setting(settings, BACKUP_ENABLED_KEY, True)
        )
        self.spin_interval.setValue(
            read_int_setting(settings, BACKUP_AUTO_SAVE_INTERVAL_KEY, 5)
        )
        self.spin_auto_retention.setValue(
            read_int_setting(settings, BACKUP_AUTO_SAVE_RETENTION_KEY, 12)
        )
        self.spin_daily_retention.setValue(
            read_int_setting(settings, BACKUP_DAILY_RETENTION_KEY, 7)
        )
        self.spin_weekly_retention.setValue(
            read_int_setting(settings, BACKUP_WEEKLY_RETENTION_KEY, 4)
        )
        self.spin_manual_retention.setValue(
            read_int_setting(settings, BACKUP_MANUAL_RETENTION_KEY, -1)
        )
        self.chk_verify.setChecked(
            read_bool_setting(settings, BACKUP_VERIFY_AFTER_KEY, True)
        )
        self.chk_vacuum.setChecked(
            read_bool_setting(settings, BACKUP_VACUUM_BEFORE_KEY, False)
        )
        self.edit_custom_dir.setText(
            read_str_setting(settings, BACKUP_CUSTOM_DIR_KEY, "")
        )
        self.edit_external_path.setText(
            read_str_setting(settings, BACKUP_EXTERNAL_PATH_KEY, "")
        )

        self._update_path_label()
