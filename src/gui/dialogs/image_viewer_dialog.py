"""
Image Viewer Dialog Module.

Provides a full-screen image viewer with navigation controls
for browsing through image attachments.
"""

import logging
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QResizeEvent, QShowEvent
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.core.image_attachment import ImageAttachment

logger = logging.getLogger(__name__)


class ImageViewerDialog(QDialog):
    """
    Modal dialog for viewing image attachments with navigation.
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        attachments: List[ImageAttachment] = None,
        current_index: int = 0,
    ) -> None:
        """
        Initialize the image viewer dialog.

        Args:
            parent: Parent widget.
            attachments: List of ImageAttachment objects to display.
            current_index: Index of the image to display first.
        """
        super().__init__(parent)
        self.setWindowTitle("Image Viewer")
        # Self resize removed to allow adjustSize() to work optimally

        self.attachments = attachments or []
        self.current_index = current_index

        self.init_ui()
        self.load_current_image()

    def init_ui(self) -> None:
        """Initialize the user interface components."""
        self.setStyleSheet("background-color: #2b2b2b; color: #e0e0e0;")
        # Main layout with zero margins to let image touch edges if desired
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Image Area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.scroll_area.setFrameShape(QScrollArea.NoFrame)

        # Style the scroll area background to match
        self.scroll_area.setStyleSheet("background-color: #2b2b2b;")

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setWidget(self.image_label)
        layout.addWidget(self.scroll_area)

        # Controls Container (Caption + Buttons)
        # We wrap this in a widget to apply margins/spacing nicely separate from image
        controls_widget = QWidget()
        controls_layout = QVBoxLayout(controls_widget)
        controls_layout.setContentsMargins(10, 10, 10, 10)
        controls_layout.setSpacing(10)

        # Caption
        self.caption_label = QLabel()
        self.caption_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.caption_label.setWordWrap(True)
        self.caption_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        controls_layout.addWidget(self.caption_label)

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

        controls_layout.addLayout(nav_layout)

        layout.addWidget(controls_widget)

    def load_current_image(self) -> None:
        """Load and display the current image from the attachments list."""
        if not self.attachments:
            return

        # Bounds check
        if self.current_index < 0:
            self.current_index = 0
        if self.current_index >= len(self.attachments):
            self.current_index = len(self.attachments) - 1

        attachment = self.attachments[self.current_index]
        full_path = Path.cwd() / attachment.image_rel_path

        if full_path.exists():
            original = QPixmap(str(full_path))
            if not original.isNull():
                # 1. Scale down largest dimension to 1024 if needed
                if original.width() > 1024 or original.height() > 1024:
                    self._base_pixmap = original.scaled(
                        1024,
                        1024,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                else:
                    self._base_pixmap = original

                # 2. Update Label
                self.image_label.setPixmap(self._base_pixmap)

                # 2. Update Label
                self.image_label.setPixmap(self._base_pixmap)

                # 3. Request Resize
                # If we are already visible, we can resize now.
                # If not, showEvent will handle it.
                if self.isVisible():
                    self._resize_to_fit()
            else:
                self.image_label.setText("Failed to load image.")
                self._base_pixmap = None
        else:
            self.image_label.setText(f"File not found: {attachment.image_rel_path}")
            self._base_pixmap = None

        # Update Caption and Counter
        caption = attachment.caption or "No caption"
        self.caption_label.setText(caption)
        self.lbl_counter.setText(f"{self.current_index + 1} / {len(self.attachments)}")

    def showEvent(self, event: QShowEvent) -> None:
        """Ensure we resize to fit image when first shown."""
        super().showEvent(event)
        if hasattr(self, "_base_pixmap") and self._base_pixmap:
            self._resize_to_fit()

    def _resize_to_fit(self) -> None:
        """Calculates optimal window size and applies it."""
        if not self._base_pixmap:
            return

        img_w = self._base_pixmap.width()
        img_h = self._base_pixmap.height()

        # Minimum width for controls (buttons etc)
        min_controls_w = 300
        target_w = max(img_w, min_controls_w)

        # Estimate controls height via sizeHint of controls_widget
        controls_widget = self.layout().itemAt(1).widget()
        if controls_widget:
            # Force layout update to get accurate hint if needed
            controls_widget.adjustSize()
            controls_h = controls_widget.sizeHint().height()
        else:
            controls_h = 100  # Fallback

        target_h = img_h + controls_h

        # Ensure we don't go larger than available screen geometry (optional safety)
        # For now, just trust the calcs as per user request (1024 max)

        logger.info(f"ImageViewer: Resizing window to {target_w}x{target_h}")
        self.resize(target_w, target_h)

        # Update buttons
        self.btn_prev.setEnabled(self.current_index > 0)
        self.btn_next.setEnabled(self.current_index < len(self.attachments) - 1)

    def _update_image(self) -> None:
        """
        Updates the displayed image based on scroll area size.
        - Downscales if viewport < base image.
        - Centers base image if viewport > base image (No Upscale).
        """
        if not hasattr(self, "_base_pixmap") or not self._base_pixmap:
            return

        viewport_size = self.scroll_area.viewport().size()
        if viewport_size.isEmpty():
            return

        base_size = self._base_pixmap.size()

        logger.debug(
            f"ImageViewer: Resize Event. Viewport: {viewport_size}, Image: {base_size}"
        )

        if (
            base_size.width() > viewport_size.width()
            or base_size.height() > viewport_size.height()
        ):
            scaled = self._base_pixmap.scaled(
                viewport_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.image_label.setPixmap(scaled)
        else:
            # Viewport area is larger or equal (in containing rect), use base (no upscale)
            self.image_label.setPixmap(self._base_pixmap)

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Handle resize to update image scaling."""
        super().resizeEvent(event)
        self._update_image()

    def show_prev(self) -> None:
        """Show the previous image in the list."""
        if self.current_index > 0:
            self.current_index -= 1
            self.load_current_image()

    def show_next(self) -> None:
        """Show the next image in the list."""
        if self.current_index < len(self.attachments) - 1:
            self.current_index += 1
            self.load_current_image()
