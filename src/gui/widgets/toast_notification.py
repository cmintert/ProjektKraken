"""Toast Notification Widget.

Displays temporary notification messages with optional action buttons.
Used for drag-drop relation creation feedback with Undo functionality.
"""

import logging
from typing import Optional

from PySide6.QtCore import QPoint, QPropertyAnimation, QRect, Qt, QTimer, Signal
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QPushButton

logger = logging.getLogger(__name__)


class ToastNotification(QFrame):
    """Temporary notification widget that appears at bottom-right of screen.

    Shows success/error messages with optional action button (e.g., Undo).
    Auto-dismisses after a timeout period.

    Signals:
        undo_clicked: Emitted when user clicks the Undo button.
        dismissed: Emitted when toast is dismissed (auto or manual).
    """

    undo_clicked = Signal()
    dismissed = Signal()

    def __init__(
        self,
        message: str,
        duration_ms: int = 3000,
        show_undo: bool = False,
        parent: Optional["QWidget"] = None,
    ) -> None:
        """Initialize toast notification.

        Args:
            message: Text to display in the toast.
            duration_ms: Time in milliseconds before auto-dismiss (default 3000).
            show_undo: Whether to show an Undo button (default False).
            parent: Parent widget (usually MainWindow).
        """
        super().__init__(parent)
        self.duration_ms = duration_ms
        self._setup_ui(message, show_undo)
        self._setup_timer()

    def _setup_ui(self, message: str, show_undo: bool) -> None:
        """Configure the toast UI layout and styling."""
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet(
            """
            QFrame {
                background-color: #4CAF50;
                border-radius: 6px;
                padding: 12px 16px;
            }
            QLabel {
                color: white;
                font-size: 12px;
                font-weight: normal;
            }
            QPushButton {
                background: transparent;
                color: white;
                border: none;
                text-decoration: underline;
                font-size: 12px;
                padding: 0px 8px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.1);
            }
            """
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)

        # Success icon
        icon_label = QLabel("✓")
        icon_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(icon_label)

        # Message text
        self.message_label = QLabel(message)
        layout.addWidget(self.message_label)

        # Undo button (optional)
        if show_undo:
            self.undo_button = QPushButton("Undo")
            self.undo_button.clicked.connect(self._on_undo_clicked)
            self.undo_button.setCursor(Qt.CursorShape.PointingHandCursor)
            layout.addWidget(self.undo_button)
        else:
            self.undo_button = None

        # Set fixed width and auto-adjust height
        self.setFixedWidth(280)
        self.adjustSize()

    def _setup_timer(self) -> None:
        """Setup auto-dismiss timer."""
        self.dismiss_timer = QTimer(self)
        self.dismiss_timer.setSingleShot(True)
        self.dismiss_timer.timeout.connect(self.dismiss)

    def show_at_bottom_right(self, offset: QPoint = QPoint(20, 20)) -> None:
        """Show toast at bottom-right corner of screen.

        Args:
            offset: Offset from bottom-right corner (default 20, 20).
        """
        # Get screen geometry
        screen = QApplication.primaryScreen()
        if not screen:
            logger.error("No primary screen found for toast positioning")
            return

        screen_geometry = screen.availableGeometry()

        # Calculate position (bottom-right with offset)
        toast_width = self.width()
        toast_height = self.height()
        x = screen_geometry.right() - toast_width - offset.x()
        y = screen_geometry.bottom() - toast_height - offset.y()

        self.move(x, y)
        self.show()
        self.raise_()

        # Start auto-dismiss timer
        self.dismiss_timer.start(self.duration_ms)

        logger.debug(
            f"Toast shown at ({x}, {y}) with message: {self.message_label.text()}"
        )

    def dismiss(self) -> None:
        """Dismiss the toast notification."""
        self.dismiss_timer.stop()
        self.hide()
        self.dismissed.emit()
        logger.debug("Toast dismissed")

    def _on_undo_clicked(self) -> None:
        """Handle undo button click."""
        logger.info("Toast undo button clicked")
        self.undo_clicked.emit()
        self.dismiss()

    def set_error_style(self) -> None:
        """Change toast style to error (red background)."""
        self.setStyleSheet(
            """
            QFrame {
                background-color: #E74C3C;
                border-radius: 6px;
                padding: 12px 16px;
            }
            QLabel {
                color: white;
                font-size: 12px;
                font-weight: normal;
            }
            QPushButton {
                background: transparent;
                color: white;
                border: none;
                text-decoration: underline;
                font-size: 12px;
                padding: 0px 8px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.1);
            }
            """
        )

    def set_warning_style(self) -> None:
        """Change toast style to warning (orange background)."""
        self.setStyleSheet(
            """
            QFrame {
                background-color: #FFB84D;
                border-radius: 6px;
                padding: 12px 16px;
            }
            QLabel {
                color: #333;
                font-size: 12px;
                font-weight: normal;
            }
            QPushButton {
                background: transparent;
                color: #333;
                border: none;
                text-decoration: underline;
                font-size: 12px;
                padding: 0px 8px;
            }
            QPushButton:hover {
                background: rgba(0, 0, 0, 0.1);
            }
            """
        )
