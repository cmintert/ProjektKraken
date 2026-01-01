"""
Database Manager Dialog Module.

Provides a dialog for managing multiple database files (worlds),
including creating, deleting, and switching between databases.
"""

import logging
import os
from typing import Optional

from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from src.app.constants import DEFAULT_DB_NAME, SETTINGS_ACTIVE_DB_KEY
from src.core.paths import get_user_data_path

logger = logging.getLogger(__name__)


class DatabaseManagerDialog(QDialog):
    """
    Dialog to manage database files (CRUD) and select the active one.
    """

    # Signal to indicate a restart is requested (optional, handled by dialog msg)
    restart_required = Signal()

    def __init__(self, parent: Optional[QDialog] = None) -> None:
        """
        Initialize the database manager dialog.

        Args:
            parent: Parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle("Database Manager")
        self.resize(500, 400)
        self.layout = QVBoxLayout(self)

        self.data_dir = get_user_data_path()

        # Header
        header = QLabel("Manage Your Worlds")
        header.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        self.layout.addWidget(header)

        # Info
        info = QLabel(f"Database Location:\n{self.data_dir}")
        info.setWordWrap(True)
        info.setStyleSheet("color: gray; margin-bottom: 10px;")
        self.layout.addWidget(info)

        # List
        self.db_list = QListWidget()
        self.db_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.layout.addWidget(self.db_list)

        # Buttons
        btn_layout = QHBoxLayout()
        self.btn_create = QPushButton("Create New")
        self.btn_delete = QPushButton("Delete")
        self.btn_select = QPushButton("Select && Restart")  # && escapes to &
        self.btn_close = QPushButton("Cancel")

        btn_layout.addWidget(self.btn_create)
        btn_layout.addWidget(self.btn_delete)
        btn_layout.addWidget(self.btn_select)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_close)

        self.layout.addLayout(btn_layout)

        # Connections
        self.btn_create.clicked.connect(self._create_db)
        self.btn_delete.clicked.connect(self._delete_db)
        self.btn_select.clicked.connect(self._select_db)
        self.btn_close.clicked.connect(self.reject)

        # Initial Refresh
        self._refresh_list()

    def _refresh_list(self) -> None:
        """Refresh the list of database files from the data directory."""
        self.db_list.clear()
        settings = QSettings()
        active_db = settings.value(SETTINGS_ACTIVE_DB_KEY, DEFAULT_DB_NAME)

        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir, exist_ok=True)

        files = [f for f in os.listdir(self.data_dir) if f.endswith(".kraken")]
        files.sort()

        for f in files:
            item = QListWidgetItem(f)
            if f == active_db:
                item.setText(f"{f} (Active)")
                font = item.font()
                font.setBold(True)
                item.setFont(font)
                item.setForeground(Qt.GlobalColor.green)  # Or theme color
                # Pre-select active
                self.db_list.setCurrentItem(item)
            self.db_list.addItem(item)

    def _create_db(self) -> None:
        """Handle creation of a new database file."""
        name, ok = QInputDialog.getText(
            self, "Create New World", "Database Name (e.g. 'MyCampaign'):"
        )
        if ok and name:
            name = name.strip()
            if not name:
                return

            filename = f"{name}.kraken" if not name.endswith(".kraken") else name
            path = os.path.join(self.data_dir, filename)

            if os.path.exists(path):
                QMessageBox.warning(
                    self, "Error", "A database with this name already exists!"
                )
                return

            try:
                # Create empty file
                open(path, "w").close()
                logger.info(f"Created new database file: {path}")
                self._refresh_list()

                # Highlight the new item
                items = self.db_list.findItems(filename, Qt.MatchExactly)
                if items:
                    self.db_list.setCurrentItem(items[0])

            except Exception as e:
                logger.error(f"Failed to create database: {e}")
                QMessageBox.critical(self, "Error", f"Failed to create database:\n{e}")

    def _delete_db(self) -> None:
        """Handle deletion of a database file."""
        item = self.db_list.currentItem()
        if not item:
            QMessageBox.information(self, "Info", "Please select a database to delete.")
            return

        filename = item.text().replace(" (Active)", "")

        # Check if active
        settings = QSettings()
        active_db = settings.value(SETTINGS_ACTIVE_DB_KEY, DEFAULT_DB_NAME)

        if filename == active_db:
            QMessageBox.warning(
                self,
                "Warning",
                "Cannot delete the currently active database.\nPlease switch to another database first.",
            )
            return

        confirm = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete '{filename}'?\n\nThis action cannot be undone and all data in this world will be lost.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if confirm == QMessageBox.StandardButton.Yes:
            try:
                os.remove(os.path.join(self.data_dir, filename))
                logger.info(f"Deleted database file: {filename}")
                self._refresh_list()
            except Exception as e:
                logger.error(f"Failed to delete database: {e}")
                QMessageBox.critical(self, "Error", f"Failed to delete database:\n{e}")

    def _select_db(self) -> None:
        """Handle selection of a database to make active (requires restart)."""
        item = self.db_list.currentItem()
        if not item:
            return

        filename = item.text().replace(" (Active)", "")
        settings = QSettings()
        active_db = settings.value(SETTINGS_ACTIVE_DB_KEY, DEFAULT_DB_NAME)

        if filename == active_db:
            QMessageBox.information(self, "Info", "This database is already active.")
            return

        settings.setValue(SETTINGS_ACTIVE_DB_KEY, filename)
        logger.info(f"Switched active database to: {filename}")

        QMessageBox.information(
            self,
            "Restart Required",
            f"Successfully switched to '{filename}'.\n\nPlease restart application to load the new world.",
        )
        self.accept()
