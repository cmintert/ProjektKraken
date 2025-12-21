import logging
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import QSize, Qt, Slot
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.app.constants import IMAGE_FILE_FILTER
from src.commands.image_commands import (
    AddImagesCommand,
    RemoveImageCommand,
    UpdateImageCaptionCommand,
)
from src.core.image_attachment import ImageAttachment
from src.gui.dialogs.image_viewer_dialog import ImageViewerDialog

logger = logging.getLogger(__name__)


class GalleryWidget(QWidget):
    """
    Widget for managing and displaying image attachments.
    """

    # Needs access to main_window to emit commands

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.owner_type: Optional[str] = None
        self.owner_id: Optional[str] = None

        self.attachments: List[ImageAttachment] = []

        self.init_ui()
        self.connect_signals()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header / Toolbar
        toolbar = QHBoxLayout()
        self.lbl_title = QLabel("Images")
        self.lbl_title.setStyleSheet("font-weight: bold;")

        self.btn_add = QPushButton("Add...")
        self.btn_add.setToolTip("Add images")
        self.btn_add.clicked.connect(self.on_add_clicked)
        self.btn_add.setEnabled(False)  # Disabled until owner set

        toolbar.addWidget(self.lbl_title)
        toolbar.addStretch()
        toolbar.addWidget(self.btn_add)

        layout.addLayout(toolbar)

        # File List (Icon Mode)
        self.list_widget = QListWidget()
        self.list_widget.setViewMode(QListWidget.IconMode)
        self.list_widget.setIconSize(QSize(128, 128))
        self.list_widget.setResizeMode(QListWidget.Adjust)
        self.list_widget.setSpacing(10)
        self.list_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list_widget.itemDoubleClicked.connect(self.on_item_double_clicked)

        # Context Menu
        self.list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self.show_context_menu)

        layout.addWidget(self.list_widget)

    def connect_signals(self):
        if hasattr(self.main_window, "worker"):
            self.main_window.worker.attachments_loaded.connect(
                self.on_attachments_loaded
            )
            self.main_window.worker.command_finished.connect(self.on_command_finished)

    def set_owner(self, owner_type: str, owner_id: str):
        """Sets the current owner and refreshes the view."""
        logger.debug(
            f"GalleryWidget: set_owner called with type={owner_type}, id={owner_id}"
        )
        self.owner_type = owner_type
        self.owner_id = owner_id
        self.btn_add.setEnabled(True)
        self.clear()

        # Request data
        # We need to invoke method on worker via QMetaObject usually,
        # or expose a slot on main_window that calls worker.
        # But connecting signal directly is easier but we are in UI thread,
        # invoking slot on worker (in bg thread) is safe via queues.
        from PySide6.QtCore import Q_ARG, QMetaObject

        QMetaObject.invokeMethod(
            self.main_window.worker,
            "load_attachments",
            Qt.QueuedConnection,
            Q_ARG(str, self.owner_type),
            Q_ARG(str, self.owner_id),
        )

    def clear(self):
        self.list_widget.clear()
        self.attachments = []

    @Slot(str, str, list)
    def on_attachments_loaded(self, owner_type, owner_id, attachments):
        """Callback when data is loaded from worker."""
        if owner_type != self.owner_type or owner_id != self.owner_id:
            logger.debug(
                f"GalleryWidget: Stale data {owner_type}/{owner_id} "
                f"vs {self.owner_type}/{self.owner_id}"
            )
            return  # Stale data

        logger.info(f"GalleryWidget: Data loaded. Count={len(attachments)}")
        self.attachments = attachments
        self.list_widget.clear()

        for att in attachments:
            item = QListWidgetItem()
            item.setText(att.caption if att.caption else "")
            item.setData(Qt.UserRole, att.id)

            # Load thumbnail
            # Try thumb path, else full path
            rel_path = att.thumb_rel_path if att.thumb_rel_path else att.image_rel_path
            full_path = Path.cwd() / rel_path

            if full_path.exists():
                icon = QIcon(str(full_path))
                item.setIcon(icon)
            else:
                logger.warning(f"GalleryWidget: Image not found at {full_path}")
                item.setText(f"(Missing)\n{item.text()}")

            self.list_widget.addItem(item)

        self.list_widget.sortItems()

    @Slot(object)
    def on_command_finished(self, result):
        """
        Handles command completion signals to auto-refresh the gallery.
        """
        if not result.success:
            return

        should_refresh = False

        # 1. Check Owner Match (Add, Reorder)
        if "owner_id" in result.data and "owner_type" in result.data:
            if (
                result.data["owner_id"] == self.owner_id
                and result.data["owner_type"] == self.owner_type
            ):
                should_refresh = True

        # 2. Check Attachment Match (Remove, UpdateCaption)
        if not should_refresh and "attachment_id" in result.data:
            att_id = result.data["attachment_id"]
            # Check if this attachment is currently displayed
            if any(a.id == att_id for a in self.attachments):
                should_refresh = True

        if should_refresh:
            logger.info(
                f"GalleryWidget: Refreshing due to command {result.command_name}"
            )
            # Re-fetch data
            self.set_owner(self.owner_type, self.owner_id)

    def on_add_clicked(self):
        if not self.owner_id:
            return

        files, _ = QFileDialog.getOpenFileNames(
            self, "Select Images", "", IMAGE_FILE_FILTER
        )
        if files:
            logger.info(f"GalleryWidget: Adding images: {files}")
            cmd = AddImagesCommand(self.owner_type, self.owner_id, files)
            self.main_window.command_requested.emit(cmd)
            # Auto-refresh handled by listing to command_finished signal.
            # MainWindow doesn't auto-trigger 'load_attachments' on command finish.

    def on_item_double_clicked(self, item):
        idx = self.list_widget.row(item)
        if idx >= 0:
            logger.debug(f"GalleryWidget: Opening viewer at index {idx}")
            # We pass the list of attachments to viewer
            viewer = ImageViewerDialog(self, self.attachments, idx)
            viewer.exec()

    def show_context_menu(self, pos):
        item = self.list_widget.itemAt(pos)
        if not item:
            return

        menu = QMenu()
        view_action = menu.addAction("View")
        edit_caption_action = menu.addAction("Edit Caption")
        menu.addSeparator()
        remove_action = menu.addAction("Remove")

        action = menu.exec(self.list_widget.mapToGlobal(pos))

        if action == view_action:
            self.on_item_double_clicked(item)
        elif action == edit_caption_action:
            self.edit_caption(item)
        elif action == remove_action:
            self.remove_item(item)

    def edit_caption(self, item):
        att_id = item.data(Qt.UserRole)
        # Find current caption
        att = next((a for a in self.attachments if a.id == att_id), None)
        current = att.caption if att else ""

        text, ok = QInputDialog.getText(self, "Edit Caption", "Caption:", text=current)
        if ok:
            logger.info(f"GalleryWidget: Updating caption for {att_id} to '{text}'")
            cmd = UpdateImageCaptionCommand(att_id, text)
            self.main_window.command_requested.emit(cmd)

    def remove_item(self, item):
        att_id = item.data(Qt.UserRole)
        confirm = QMessageBox.question(
            self,
            "Remove Image",
            "Are you sure you want to remove this image?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm == QMessageBox.Yes:
            logger.info(f"GalleryWidget: Requesting removal of {att_id}")
            cmd = RemoveImageCommand(att_id)
            self.main_window.command_requested.emit(cmd)
