"""Thumbnail Loader Module.

Provides asynchronous thumbnail loading for the gallery widget.
"""

import logging
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Qt, Signal
from PySide6.QtGui import QIcon, QPixmap, QPixmapCache

logger = logging.getLogger(__name__)


class ThumbnailLoaderSignals(QObject):
    """Signals for the ThumbnailLoader.

    Qt signals must be defined in a QObject subclass.
    """

    loaded = Signal(str, QIcon)  # (attachment_id, icon)
    error = Signal(str, str)  # (attachment_id, error_message)


class ThumbnailLoader(QRunnable):
    """A worker for loading image thumbnails asynchronously.

    Loads images in a background thread and caches them using QPixmapCache
    to prevent redundant I/O operations.
    """

    def __init__(self, attachment_id: str, image_path: Path) -> None:
        """Initialize the thumbnail loader.

        Args:
            attachment_id: Unique ID of the attachment.
            image_path: Absolute path to the image file.
        """
        super().__init__()
        self.attachment_id = attachment_id
        self.image_path = image_path
        self.signals = ThumbnailLoaderSignals()
        self.setAutoDelete(True)

    def run(self) -> None:
        """Load the thumbnail image.

        This runs in a background thread. Results are emitted via signals.
        """
        try:
            # Check if already in cache
            cache_key = f"thumb_{self.attachment_id}"
            cached_pixmap = QPixmap()

            if QPixmapCache.find(cache_key, cached_pixmap):
                # Use cached version
                icon = QIcon(cached_pixmap)
                self.signals.loaded.emit(self.attachment_id, icon)
                return

            # Load from disk
            if not self.image_path.exists():
                self.signals.error.emit(
                    self.attachment_id, f"Image not found: {self.image_path}"
                )
                return

            # Load pixmap
            pixmap = QPixmap(str(self.image_path))

            if pixmap.isNull():
                self.signals.error.emit(
                    self.attachment_id, f"Failed to load image: {self.image_path}"
                )
                return

            # Scale to thumbnail size if needed (max 128x128)
            if pixmap.width() > 128 or pixmap.height() > 128:
                pixmap = pixmap.scaled(
                    128,
                    128,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )

            # Cache the pixmap
            QPixmapCache.insert(cache_key, pixmap)

            # Create icon and emit
            icon = QIcon(pixmap)
            self.signals.loaded.emit(self.attachment_id, icon)

        except Exception as e:
            logger.error(
                f"Thumbnail loader error for {self.attachment_id}: {e}", exc_info=True
            )
            self.signals.error.emit(self.attachment_id, str(e))
