"""
Gallery Widget Module.

Provides a visual gallery interface for managing image attachments
associated with events and entities.
"""

import logging
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import QPoint, QSize, Qt, Slot
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QIcon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
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
from src.core.paths import get_user_data_path
from src.gui.dialogs.image_viewer_dialog import ImageViewerDialog
from src.gui.widgets.standard_buttons import StandardButton

logger = logging.getLogger(__name__)


class GalleryWidget(QWidget):
    """
    Widget for managing and displaying image attachments.
    Supports drag-and-drop, thumbnails, and captions.
    """

    # Needs access to main_window to emit commands

    def __init__(self, main_window) -> None:
        """
        Initialize the gallery widget.

        Args:
            main_window: Reference to MainWindow for command emission.
        """
        super().__init__()
        self.main_window = main_window
        self.owner_type: Optional[str] = None
        self.owner_id: Optional[str] = None

        self.attachments: List[ImageAttachment] = []

        self.init_ui()
        self.connect_signals()

    def init_ui(self):
        """Initialize the user interface components."""
        self.setAcceptDrops(True)
        layout = QVBoxLayout(self)
        from src.gui.utils.style_helper import StyleHelper

        StyleHelper.apply_compact_spacing(layout)

        # Toolbar / Action buttons
        toolbar = QHBoxLayout()
        self.btn_add = StandardButton("Add Image")
        self.btn_add.setToolTip("Add images to this item")
        self.btn_add.clicked.connect(self.on_add_clicked)
        self.btn_add.setEnabled(False)  # Disabled until owner set

        self.btn_edit = StandardButton("Edit Caption")
        self.btn_edit.setToolTip("Edit caption for selected image")
        self.btn_edit.clicked.connect(self._on_edit_caption_clicked)
        self.btn_edit.setEnabled(False)

        self.btn_remove = StandardButton("Remove")
        self.btn_remove.setToolTip("Remove selected image")
        self.btn_remove.setStyleSheet(StyleHelper.get_destructive_button_style())
        self.btn_remove.clicked.connect(self._on_remove_clicked)
        self.btn_remove.setEnabled(False)

        toolbar.addWidget(self.btn_add)
        toolbar.addWidget(self.btn_edit)
        toolbar.addWidget(self.btn_remove)
        toolbar.addStretch()

        layout.addLayout(toolbar)

        # File List (Icon Mode)
        self.list_widget = QListWidget()
        self.list_widget.setViewMode(QListWidget.IconMode)
        self.list_widget.setIconSize(QSize(128, 128))
        self.list_widget.setResizeMode(QListWidget.Adjust)
        self.list_widget.setSpacing(10)
        self.list_widget.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.list_widget.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.list_widget.itemSelectionChanged.connect(self._update_button_states)

        # Context Menu
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self.show_context_menu)

        layout.addWidget(self.list_widget)

    def connect_signals(self):
        """Connect widget signals to main window slots."""
        if hasattr(self.main_window, "worker"):
            self.main_window.worker.attachments_loaded.connect(
                self.on_attachments_loaded
            )
            self.main_window.worker.command_finished.connect(self.on_command_finished)

    def _update_button_states(self):
        """Updates enabled states for Edit and Remove buttons based on selection."""
        items = self.list_widget.selectedItems()
        count = len(items)
        self.btn_edit.setEnabled(count == 1)
        self.btn_remove.setEnabled(count > 0)

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
            Qt.ConnectionType.QueuedConnection,
            Q_ARG(str, self.owner_type),
            Q_ARG(str, self.owner_id),
        )

    def clear(self):
        """Clear all displayed attachments from the gallery."""
        self.list_widget.clear()
        self.attachments = []
        self._update_button_states()

    @Slot(str, str, list)
    def on_attachments_loaded(
        self, owner_type: str, owner_id: str, attachments: List[ImageAttachment]
    ) -> None:
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
            item.setData(Qt.ItemDataRole.UserRole, att.id)

            # Load thumbnail
            # Try thumb path, else full path
            rel_path = att.thumb_rel_path if att.thumb_rel_path else att.image_rel_path
            full_path = Path(get_user_data_path(rel_path))

            if full_path.exists():
                icon = QIcon(str(full_path))
                item.setIcon(icon)
            else:
                logger.warning(f"GalleryWidget: Image not found at {full_path}")
                item.setText(f"(Missing)\n{item.text()}")

            self.list_widget.addItem(item)

        self.list_widget.sortItems()
        self._update_button_states()

    @Slot(object)
    def on_command_finished(self, result: object) -> None:
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

    def on_add_clicked(self) -> None:
        """Handle add image button click - open file dialog and create command."""
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

    def on_item_double_clicked(self, item: QListWidgetItem) -> None:
        """
        Handle double-click on gallery item - open image viewer.

        Args:
            item: The clicked QListWidgetItem.
        """
        att_id = item.data(Qt.ItemDataRole.UserRole)
        # Find index in self.attachments
        try:
            target_index = next(
                i for i, att in enumerate(self.attachments) if att.id == att_id
            )
            logger.debug(
                f"GalleryWidget: Opening viewer for {att_id} at index {target_index}"
            )
            viewer = ImageViewerDialog(self, self.attachments, target_index)
            viewer.exec()
        except StopIteration:
            logger.error(f"GalleryWidget: Attachment {att_id} not found in data list")

    def show_context_menu(self, pos: "QPoint") -> None:
        """
        Show context menu for gallery items.

        Args:
            pos: The position where the menu was requested.
        """
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

    def _on_edit_caption_clicked(self) -> None:
        """Handles toolbar button click for editing caption."""
        item = self.list_widget.currentItem()
        if item:
            self.edit_caption(item)

    def _on_remove_clicked(self) -> None:
        """Handles toolbar button click for removal."""
        item = self.list_widget.currentItem()
        if item:
            self.remove_item(item)

    def edit_caption(self, item: QListWidgetItem) -> None:
        """
        Edit the caption for a gallery item.

        Args:
            item: The QListWidgetItem representing the attachment.
        """
        att_id = item.data(Qt.ItemDataRole.UserRole)
        # Find current caption
        att = next((a for a in self.attachments if a.id == att_id), None)
        current = att.caption if att else ""

        text, ok = QInputDialog.getText(self, "Edit Caption", "Caption:", text=current)
        if ok:
            logger.info(f"GalleryWidget: Updating caption for {att_id} to '{text}'")
            cmd = UpdateImageCaptionCommand(att_id, text)
            self.main_window.command_requested.emit(cmd)

    def remove_item(self, item: QListWidgetItem) -> None:
        """
        Remove an attachment from the gallery.

        Args:
            item: The QListWidgetItem representing the attachment.
        """
        att_id = item.data(Qt.ItemDataRole.UserRole)
        confirm = QMessageBox.question(
            self,
            "Remove Image",
            "Are you sure you want to remove this image?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            logger.info(f"GalleryWidget: Requesting removal of {att_id}")
            cmd = RemoveImageCommand(att_id)
            self.main_window.command_requested.emit(cmd)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """Handle drag enter event for files."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        """Handle drop event for files."""
        if not self.owner_id:
            return

        urls = event.mimeData().urls()
        if not urls:
            return

        files = []
        for url in urls:
            if url.isLocalFile():
                files.append(url.toLocalFile())

        if files:
            logger.info(f"GalleryWidget: Dropped files: {files}")
            # Filter for images roughly
            valid_files = [
                f
                for f in files
                if f.lower().endswith(
                    (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp")
                )
            ]
            if valid_files:
                cmd = AddImagesCommand(self.owner_type, self.owner_id, valid_files)
                self.main_window.command_requested.emit(cmd)
                event.acceptProposedAction()

    def minimumSizeHint(self) -> QSize:
        """
        Override to prevent dock collapse.

        Returns:
            QSize: Minimum size for usable gallery.
        """
        from PySide6.QtCore import QSize

        return QSize(250, 150)

    def sizeHint(self) -> QSize:
        """
        Preferred size for the gallery.

        Returns:
            QSize: Comfortable working size.
        """
        from PySide6.QtCore import QSize

        return QSize(350, 300)
