"""Database Manager Dialog Module.

Provides a dialog for managing portable world folders and explicitly approved
external database links.
"""

import logging
import os
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QSettings, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
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

from src.core.paths import ensure_worlds_directory
from src.core.world import EXTERNAL_DATABASE_STORAGE, World, WorldManager
from src.gui.constants import SETTINGS_ACTIVE_DB_KEY
from src.gui.dialogs.external_database_warning import external_database_warning
from src.services.world_storage_settings import WorldStorageSettings

logger = logging.getLogger(__name__)


class DatabaseManagerDialog(QDialog):
    """Dialog to manage portable world folders and external database approvals.

    New worlds use the default worlds directory. Existing complete world folders may
    be registered from other locations.
    """

    # Signal to indicate a restart is requested
    restart_required = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the database manager dialog.

        Args:
            parent: Parent widget.

        """
        super().__init__(parent)
        self.setWindowTitle("World Manager")
        self.resize(720, 440)
        main_layout = QVBoxLayout(self)

        self.storage_settings = WorldStorageSettings()

        # Initialize worlds directory
        self.worlds_dir: Path | None
        self.world_manager: WorldManager | None
        try:
            self.worlds_dir = ensure_worlds_directory()
            self.world_manager = self._build_world_manager()
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
        self.btn_add_folder = QPushButton("Add World Folder")
        self.btn_open_folder = QPushButton("Open Folder")
        self.btn_link_external = QPushButton("Link External DB")
        self.btn_revoke_external = QPushButton("Revoke External DB")
        self.btn_delete = QPushButton("Delete")
        self.btn_select = QPushButton("Select && Restart")  # && escapes to &
        self.btn_close = QPushButton("Cancel")

        btn_layout.addWidget(self.btn_create)
        btn_layout.addWidget(self.btn_add_folder)
        btn_layout.addWidget(self.btn_open_folder)
        btn_layout.addWidget(self.btn_link_external)
        btn_layout.addWidget(self.btn_revoke_external)
        btn_layout.addWidget(self.btn_delete)
        btn_layout.addWidget(self.btn_select)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_close)

        main_layout.addLayout(btn_layout)

        # Connections
        self.btn_create.clicked.connect(self._create_world)
        self.btn_add_folder.clicked.connect(self._add_world_folder)
        self.btn_open_folder.clicked.connect(self._open_folder)
        self.btn_link_external.clicked.connect(self._link_external_database)
        self.btn_revoke_external.clicked.connect(self._revoke_external_database)
        self.btn_delete.clicked.connect(self._delete_world)
        self.btn_select.clicked.connect(self._select_world)
        self.btn_close.clicked.connect(self.reject)

        # Disable buttons if world manager couldn't be initialized
        if not self.world_manager:
            self.btn_create.setEnabled(False)
            self.btn_add_folder.setEnabled(False)
            self.btn_open_folder.setEnabled(False)
            self.btn_link_external.setEnabled(False)
            self.btn_revoke_external.setEnabled(False)
            self.btn_delete.setEnabled(False)
            self.btn_select.setEnabled(False)

        # Initial Refresh
        self._refresh_list()

    def _build_world_manager(self) -> WorldManager:
        """Build a manager using locally registered folders and approvals."""
        if self.worlds_dir is None:
            raise OSError("Worlds directory is unavailable")
        return WorldManager(
            self.worlds_dir,
            additional_world_paths=self.storage_settings.registered_world_paths(),
            approved_external_paths=self.storage_settings.external_approvals(),
        )

    def _selected_world(self) -> World | None:
        """Return the inspected world represented by the selected row."""
        item = self.db_list.currentItem()
        if item is None:
            return None
        raw_path = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(raw_path, str):
            return None
        return World.inspect(Path(raw_path))

    def _refresh_list(self) -> None:
        """Refresh the list of worlds from the worlds directory."""
        self.db_list.clear()

        if not self.world_manager:
            return

        settings = QSettings()
        active_world_name = settings.value(SETTINGS_ACTIVE_DB_KEY, None)
        active_world_path = self.storage_settings.active_world_path()

        worlds = self.world_manager.inspect_worlds()

        for world in worlds:
            label = world.name
            if world.is_external_database:
                if not world.db_path.is_file():
                    label += " [External database missing]"
                elif not self.storage_settings.is_external_path_approved(world):
                    label += " [External approval required]"
                else:
                    label += " [External]"

            is_active = (
                active_world_path is not None and world.path == active_world_path
            ) or (active_world_path is None and world.name == active_world_name)
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, str(world.path))
            if is_active:
                item.setText(f"{label} (Active)")
                font = item.font()
                font.setBold(True)
                item.setFont(font)
                item.setForeground(Qt.GlobalColor.green)
                # Pre-select active
                self.db_list.setCurrentItem(item)
            self.db_list.addItem(item)

    @Slot()
    def _open_folder(self) -> None:
        """Open the selected world folder or the default worlds directory."""
        import subprocess
        import sys

        selected_world = self._selected_world()
        folder = selected_world.path if selected_world else self.worlds_dir
        if not folder:
            return

        try:
            if sys.platform == "win32":
                # Use os.startfile on Windows - more reliable than subprocess
                os.startfile(str(folder))
            elif sys.platform == "darwin":
                subprocess.run(["open", str(folder)], check=False)
            else:  # Linux
                subprocess.run(["xdg-open", str(folder)], check=False)
        except Exception as e:
            logger.error(f"Failed to open worlds directory: {e}")
            QMessageBox.information(
                self, "World Location", f"World directory:\n{folder}"
            )

    @Slot()
    def _add_world_folder(self) -> None:
        """Register a complete world folder from any supported location."""
        selected = QFileDialog.getExistingDirectory(
            self,
            "Select Complete World Folder",
            str(self.worlds_dir or Path.home()),
        )
        if not selected:
            return

        world = World.inspect(Path(selected))
        if world is None:
            QMessageBox.warning(
                self,
                "Invalid World Folder",
                "The selected folder does not contain a valid world.json and "
                ".kraken database configuration.",
            )
            return
        if not world.db_path.is_file():
            QMessageBox.warning(
                self,
                "Database Missing",
                f"The configured database does not exist:\n\n{world.db_path}",
            )
            return
        if not self._approve_external_world_if_needed(world):
            return

        self.storage_settings.register_world_path(world.path)
        self.world_manager = self._build_world_manager()
        self._refresh_list()

    def _approve_external_world_if_needed(self, world: World) -> bool:
        """Request and persist approval for an external database when needed."""
        if not world.is_external_database:
            return True
        if self.storage_settings.is_external_path_approved(world):
            return True
        response = QMessageBox.question(
            self,
            "Approve External World Database?",
            external_database_warning(world.db_path),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if response != QMessageBox.StandardButton.Yes:
            return False
        self.storage_settings.approve_external_path(world)
        return True

    @Slot()
    def _link_external_database(self) -> None:
        """Configure the selected world to use an explicitly chosen database."""
        world = self._selected_world()
        if world is None:
            QMessageBox.information(
                self,
                "Select a World",
                "Select the world whose database you want to link.",
            )
            return

        selected, _ = QFileDialog.getOpenFileName(
            self,
            "Select External Projekt Kraken Database",
            str(world.path),
            "Projekt Kraken databases (*.kraken)",
        )
        if not selected:
            return
        database_path = Path(selected).resolve(strict=False)
        if database_path.suffix.lower() != ".kraken" or not database_path.is_file():
            QMessageBox.warning(
                self,
                "Invalid External Database",
                "Select an existing database with the .kraken extension.",
            )
            return

        response = QMessageBox.question(
            self,
            "Link External World Database?",
            external_database_warning(database_path),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if response != QMessageBox.StandardButton.Yes:
            return

        world.manifest.storage_mode = EXTERNAL_DATABASE_STORAGE
        world.manifest.db_filename = str(database_path)
        world.save_manifest()
        self.storage_settings.approve_external_path(world)
        self.storage_settings.register_world_path(world.path)
        self.world_manager = self._build_world_manager()
        self._refresh_list()

        QMessageBox.information(
            self,
            "External Database Linked",
            "The external database is approved on this installation. Select "
            "the world and restart to open it.",
        )

    @Slot()
    def _revoke_external_database(self) -> None:
        """Revoke the selected world's locally stored external-path approval."""
        world = self._selected_world()
        if world is None or not world.is_external_database:
            QMessageBox.information(
                self,
                "No External Database",
                "Select a world configured with an external database.",
            )
            return

        self.storage_settings.revoke_external_path(world)
        if self.storage_settings.active_world_path() == world.path:
            self.storage_settings.clear_active_world_path()
            QSettings().remove(SETTINGS_ACTIVE_DB_KEY)
        self.world_manager = self._build_world_manager()
        self._refresh_list()
        QMessageBox.information(
            self,
            "External Approval Revoked",
            "Projekt Kraken will not open this external database again until "
            "you explicitly approve its resolved path. The current session "
            "continues until you restart the application.",
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

        world = self._selected_world()
        if world is None:
            QMessageBox.information(self, "Info", "Please select a world to delete.")
            return

        # Check if active
        settings = QSettings()
        active_world_name = settings.value(SETTINGS_ACTIVE_DB_KEY, None)
        active_world_path = self.storage_settings.active_world_path()

        if active_world_path == world.path or (
            active_world_path is None and world.name == active_world_name
        ):
            QMessageBox.warning(
                self,
                "Warning",
                "Cannot delete the currently active world.\n"
                "Please switch to another world first.",
            )
            return

        database_line = (
            "- The external database approval (the external database file "
            "will not be deleted)\n"
            if world.is_external_database
            else "- The world database\n"
        )
        confirm = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete '{world.name}'?\n\n"
            "This will permanently delete:\n"
            + database_line
            + "- All assets (images, maps)\n"
            "- The world manifest\n\n"
            "This action cannot be undone!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if confirm == QMessageBox.StandardButton.Yes:
            try:
                self.storage_settings.revoke_external_path(world)
                self.storage_settings.unregister_world_path(world.path)
                self.world_manager.delete_world(world)
                logger.info(f"Deleted world: {world.name}")
                self.world_manager = self._build_world_manager()
                self._refresh_list()
            except Exception as e:
                logger.error(f"Failed to delete world: {e}")
                QMessageBox.critical(self, "Error", f"Failed to delete world:\n{e}")

    @Slot()
    def _select_world(self) -> None:
        """Handle selection of a world to make active (requires restart)."""
        if not self.world_manager:
            return

        world = self._selected_world()
        if world is None:
            return

        settings = QSettings()
        active_world_name = settings.value(SETTINGS_ACTIVE_DB_KEY, None)
        active_world_path = self.storage_settings.active_world_path()

        if active_world_path == world.path or (
            active_world_path is None and world.name == active_world_name
        ):
            QMessageBox.information(self, "Info", "This world is already active.")
            return

        if not world.db_path.is_file():
            QMessageBox.warning(
                self,
                "Database Missing",
                "The configured database is unavailable and will not be "
                f"recreated:\n\n{world.db_path}",
            )
            return
        if not self._approve_external_world_if_needed(world):
            return

        self.storage_settings.register_world_path(world.path)
        self.storage_settings.set_active_world_path(world.path)
        settings.setValue(SETTINGS_ACTIVE_DB_KEY, world.name)
        logger.info(f"Switched active world to: {world.name}")

        QMessageBox.information(
            self,
            "Restart Required",
            f"Successfully switched to '{world.name}'.\n\n"
            "Please restart the application to load the new world.",
        )
        self.accept()
