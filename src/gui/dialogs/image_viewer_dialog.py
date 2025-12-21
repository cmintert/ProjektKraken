from pathlib import Path
from typing import List

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
)

from src.core.image_attachment import ImageAttachment


class ImageViewerDialog(QDialog):
    """
    Modal dialog for viewing image attachments with navigation.
    """

    def __init__(
        self,
        parent=None,
        attachments: List[ImageAttachment] = None,
        current_index: int = 0,
    ):
        super().__init__(parent)
        self.setWindowTitle("Image Viewer")
        self.resize(1024, 768)

        self.attachments = attachments or []
        self.current_index = current_index

        self.init_ui()
        self.load_current_image()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Image Area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignCenter)
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.scroll_area.setWidget(self.image_label)
        layout.addWidget(self.scroll_area)

        # Caption
        self.caption_label = QLabel()
        self.caption_label.setAlignment(Qt.AlignCenter)
        self.caption_label.setWordWrap(True)
        self.caption_label.setStyleSheet(
            "font-weight: bold; font-size: 14px; margin: 10px;"
        )
        layout.addWidget(self.caption_label)

        # Navigation
        nav_layout = QHBoxLayout()
        self.btn_prev = QPushButton("< Previous")
        self.btn_prev.clicked.connect(self.show_prev)

        self.btn_next = QPushButton("Next >")
        self.btn_next.clicked.connect(self.show_next)

        self.lbl_counter = QLabel()

        nav_layout.addWidget(self.btn_prev)
        nav_layout.addStretch()
        nav_layout.addWidget(self.lbl_counter)
        nav_layout.addStretch()
        nav_layout.addWidget(self.btn_next)

        layout.addLayout(nav_layout)

    def load_current_image(self):
        if not self.attachments:
            return

        # Bounds check
        if self.current_index < 0:
            self.current_index = 0
        if self.current_index >= len(self.attachments):
            self.current_index = len(self.attachments) - 1

        attachment = self.attachments[self.current_index]

        # Resolve Path (Assuming CWD is project root)
        # In a real app we might need a robust way to get project root
        full_path = Path.cwd() / attachment.image_rel_path

        if full_path.exists():
            pixmap = QPixmap(str(full_path))
            if not pixmap.isNull():
                # Scale if too large? Or let scroll area handle it?
                # Let's scale to fit window if huge, but keep aspect ratio
                # Actually scroll area handles it if we set resizeable.
                # But we might want to scale down to fit view initially?
                # Simple approach: set pixmap on label.
                self.image_label.setPixmap(pixmap)
            else:
                self.image_label.setText("Failed to load image.")
        else:
            self.image_label.setText(f"File not found: {attachment.image_rel_path}")

        # Update Caption and Counter
        caption = attachment.caption or "No caption"
        self.caption_label.setText(caption)
        self.lbl_counter.setText(f"{self.current_index + 1} / {len(self.attachments)}")

        # Update buttons
        self.btn_prev.setEnabled(self.current_index > 0)
        self.btn_next.setEnabled(self.current_index < len(self.attachments) - 1)

    def show_prev(self):
        if self.current_index > 0:
            self.current_index -= 1
            self.load_current_image()

    def show_next(self):
        if self.current_index < len(self.attachments) - 1:
            self.current_index += 1
            self.load_current_image()
