"""
Database Manager Dialog Module.

Provides a dialog for managing multiple worlds in portable-only mode.
Each world is a self-contained folder with its own .kraken database,
world.json manifest, and assets/ directory.

Worlds are stored in the worlds/ directory next to the executable.
"""

import logging
import os
from typing import Optional

from PySide6.QtCore import QSettings, Qt, Signal, Slot
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
    QWidget,
)

from src.app.constants import SETTINGS_ACTIVE_DB_KEY
from src.core.paths import ensure_worlds_directory
from src.core.world import WorldManager

logger = logging.getLogger(__name__)


class DatabaseManagerDialog(QDialog):
    """
    Dialog to manage worlds in portable-only mode.

    Manages worlds stored in worlds/ directory next to the executable.
    Each world is a self-contained folder with database, manifest, and assets.
    """

    # Signal to indicate a restart is requested
    restart_required = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Initialize the database manager dialog.

        Args:
            parent: Parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle("World Manager")
        self.resize(500, 400)
        main_layout = QVBoxLayout(self)

        # Initialize worlds directory
        try:
            self.worlds_dir = ensure_worlds_directory()
            self.world_manager = WorldManager(self.worlds_dir)
        except OSError as e:
            logger.critical(f"Cannot access worlds directory: {e}")
            QMessageBox.critical(
                self,
                "Critical Error",
                f"Cannot access worlds directory:\n{e}\n\n"
                "Please ensure the application has write permissions.",
            )
            self.worlds_dir = None
            self.world_manager = None

        # Header
        header = QLabel("Manage Your Worlds")
        header.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        main_layout.addWidget(header)

        # Info
        info_text = (
            f"Worlds Location:\n{self.worlds_dir}"
            if self.worlds_dir
            else "Error: Cannot access worlds directory"
        )
        info = QLabel(info_text)
        info.setWordWrap(True)
        info.setStyleSheet("color: gray; margin-bottom: 10px;")
        main_layout.addWidget(info)

        # List
        self.db_list = QListWidget()
        self.db_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        main_layout.addWidget(self.db_list)

        # Buttons
        btn_layout = QHBoxLayout()
        self.btn_create = QPushButton("Create New")
        self.btn_open_folder = QPushButton("Open Folder")
        self.btn_delete = QPushButton("Delete")
        self.btn_select = QPushButton("Select && Restart")  # && escapes to &
        self.btn_close = QPushButton("Cancel")

        btn_layout.addWidget(self.btn_create)
        btn_layout.addWidget(self.btn_open_folder)
        btn_layout.addWidget(self.btn_delete)
        btn_layout.addWidget(self.btn_select)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_close)

        main_layout.addLayout(btn_layout)

        # Connections
        self.btn_create.clicked.connect(self._create_world)
        self.btn_open_folder.clicked.connect(self._open_folder)
        self.btn_delete.clicked.connect(self._delete_world)
        self.btn_select.clicked.connect(self._select_world)
        self.btn_close.clicked.connect(self.reject)

        # Disable buttons if world manager couldn't be initialized
        if not self.world_manager:
            self.btn_create.setEnabled(False)
            self.btn_delete.setEnabled(False)
            self.btn_select.setEnabled(False)

        # Initial Refresh
        self._refresh_list()

    def _refresh_list(self) -> None:
        """Refresh the list of worlds from the worlds directory."""
        self.db_list.clear()

        if not self.world_manager:
            return

        settings = QSettings()
        active_world_name = settings.value(SETTINGS_ACTIVE_DB_KEY, None)

        worlds = self.world_manager.discover_worlds()

        for world in worlds:
            item = QListWidgetItem(world.name)
            if world.name == active_world_name:
                item.setText(f"{world.name} (Active)")
                font = item.font()
                font.setBold(True)
                item.setFont(font)
                item.setForeground(Qt.GlobalColor.green)
                # Pre-select active
                self.db_list.setCurrentItem(item)
            self.db_list.addItem(item)

    @Slot()
    def _open_folder(self) -> None:
        """Open the worlds directory in the system file explorer."""
        import subprocess
        import sys

        if not self.worlds_dir:
            return

        try:
            if sys.platform == "win32":
                # Use os.startfile on Windows - more reliable than subprocess
                os.startfile(str(self.worlds_dir))
            elif sys.platform == "darwin":
                subprocess.run(["open", str(self.worlds_dir)], check=False)
            else:  # Linux
                subprocess.run(["xdg-open", str(self.worlds_dir)], check=False)
        except Exception as e:
            logger.error(f"Failed to open worlds directory: {e}")
            QMessageBox.information(
                self, "Worlds Location", f"Worlds directory:\n{self.worlds_dir}"
            )

    @Slot()
    def _create_world(self) -> None:
        """Handle creation of a new world."""
        if not self.world_manager:
            return

        # Get world name from user
        name, ok = QInputDialog.getText(
            self, "Create New World", "World Name (e.g. 'My Fantasy Campaign'):"
        )
        if not ok or not name:
            return

        name = name.strip()
        if not name:
            return

        # Get optional description
        description, ok = QInputDialog.getText(
            self, "World Description", "Optional Description:", text=""
        )
        if not ok:
            description = ""

        try:
            # Create the world
            world = self.world_manager.create_world(name, description.strip())
            logger.info(f"Created new world: {world.name} at {world.path}")

            self._refresh_list()

            # Highlight the new item
            items = self.db_list.findItems(world.name, Qt.MatchFlag.MatchExactly)
            if items:
                self.db_list.setCurrentItem(items[0])

        except ValueError as e:
            QMessageBox.warning(self, "Error", str(e))
        except Exception as e:
            logger.error(f"Failed to create world: {e}")
            QMessageBox.critical(self, "Error", f"Failed to create world:\n{e}")

    @Slot()
    def _delete_world(self) -> None:
        """Handle deletion of a world."""
        if not self.world_manager:
            return

        item = self.db_list.currentItem()
        if not item:
            QMessageBox.information(self, "Info", "Please select a world to delete.")
            return

        world_name = item.text().replace(" (Active)", "")

        # Check if active
        settings = QSettings()
        active_world_name = settings.value(SETTINGS_ACTIVE_DB_KEY, None)

        if world_name == active_world_name:
            QMessageBox.warning(
                self,
                "Warning",
                "Cannot delete the currently active world.\n"
                "Please switch to another world first.",
            )
            return

        confirm = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete '{world_name}'?\n\n"
            "This will permanently delete:\n"
            "- The world database\n"
            "- All assets (images, maps)\n"
            "- The world manifest\n\n"
            "This action cannot be undone!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if confirm == QMessageBox.StandardButton.Yes:
            try:
                world = self.world_manager.get_world(world_name)
                if world:
                    self.world_manager.delete_world(world)
                    logger.info(f"Deleted world: {world_name}")
                    self._refresh_list()
                else:
                    QMessageBox.warning(
                        self, "Error", f"World '{world_name}' not found."
                    )
            except Exception as e:
                logger.error(f"Failed to delete world: {e}")
                QMessageBox.critical(self, "Error", f"Failed to delete world:\n{e}")

    @Slot()
    def _select_world(self) -> None:
        """Handle selection of a world to make active (requires restart)."""
        if not self.world_manager:
            return

        item = self.db_list.currentItem()
        if not item:
            return

        world_name = item.text().replace(" (Active)", "")
        settings = QSettings()
        active_world_name = settings.value(SETTINGS_ACTIVE_DB_KEY, None)

        if world_name == active_world_name:
            QMessageBox.information(self, "Info", "This world is already active.")
            return

        settings.setValue(SETTINGS_ACTIVE_DB_KEY, world_name)
        logger.info(f"Switched active world to: {world_name}")

        QMessageBox.information(
            self,
            "Restart Required",
            f"Successfully switched to '{world_name}'.\n\n"
            "Please restart the application to load the new world.",
        )
        self.accept()
