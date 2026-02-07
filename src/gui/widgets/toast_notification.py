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
        self._variant = "success"  # Default variant
        self._setup_ui(message, show_undo)
        self._apply_theme()
        self._connect_theme_signals()
        self._setup_timer()

    def _setup_ui(self, message: str, show_undo: bool) -> None:
        """Configure the toast UI layout and styling."""
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)

        # Success icon (will be updated in _apply_theme if needed,
        # but text is static here)
        # We might want to change icon based on variant too, but for now stick to "✓"
        # for success and maybe others for error? Current code hardcodes "✓".
        # Let's keep the label creation here, but style it in _apply_theme.
        self.icon_label = QLabel("✓")
        self.icon_label.setObjectName("icon_label")
        layout.addWidget(self.icon_label)

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

    def _connect_theme_signals(self) -> None:
        """Connect to theme change signals."""
        try:
            from src.core.theme_manager import ThemeManager

            ThemeManager().theme_changed.connect(self._on_theme_changed)
        except Exception:
            pass

    def _on_theme_changed(self, theme_data: dict) -> None:
        """Handle theme change."""
        self._apply_theme()

    def _apply_theme(self) -> None:
        """Apply current theme colors to the widget."""
        try:
            from src.core.theme_manager import ThemeManager

            theme = ThemeManager().get_theme()

            # Determine colors based on variant
            bg_color = "#4CAF50"  # Default success
            text_color = "#FFFFFF"

            if self._variant == "error":
                bg_color = theme.get("error", "#E74C3C")
                self.icon_label.setText("⚠")
            elif self._variant == "warning":
                bg_color = theme.get("primary", "#FFB84D")  # Fallback for warning
                # Check if we have a specific warning key in recent themes
                if "warning" in theme:
                    bg_color = theme["warning"]
                self.icon_label.setText("!")
                text_color = (
                    "#333333"  # Warning usually needs dark text on yellow/orange
                )
            else:
                self.icon_label.setText("✓")
                # Success green - not standard in theme yet,
                # keep hardcoded or add to theme
                bg_color = "#4CAF50"

            font_size = "10pt"  # Default
            if "font_size_body" in theme:
                font_size = theme["font_size_body"]

            # Construct stylesheet
            style = f"""
            QFrame {{
                background-color: {bg_color};
                border-radius: 6px;
                padding: 12px 16px;
                border: 1px solid {theme.get("border", "transparent")};
            }}
            QLabel {{
                color: {text_color};
                font-size: {font_size};
                font-weight: normal;
                background: transparent;
            }}
            QLabel#icon_label {{
                font-weight: bold;
                font-size: 14pt;
            }}
            QPushButton {{
                background: transparent;
                color: {text_color};
                border: none;
                text-decoration: underline;
                font-size: {font_size};
                padding: 0px 8px;
            }}
            QPushButton:hover {{
                background: rgba(255, 255, 255, 0.1);
            }}
            """

            if self._variant == "warning":
                style += """
                 QPushButton:hover {
                    background: rgba(0, 0, 0, 0.1);
                 }
                 """

            self.setStyleSheet(style)

        except Exception as e:
            logger.error(f"Failed to apply theme to toast: {e}")
            # Fallback to simple green if theme fails
            self.setStyleSheet(
                "QFrame { background-color: #4CAF50; border-radius: 6px; } "
                "QLabel { color: white; }"
            )

    def _setup_timer(self) -> None:
        """Setup auto-dismiss timer."""
        self.dismiss_timer = QTimer(self)
        self.dismiss_timer.setSingleShot(True)
        self.dismiss_timer.timeout.connect(self.dismiss)

    def show_centered(self) -> None:
        """Show toast centered in the parent window."""
        self.adjustSize()
        parent = self.parent()
        if parent:
            # Calculate center relative to parent's geometry
            # Since Toast is a Tool window, we need global coordinates.
            # parent.geometry() is usually global for top-level windows.
            parent_geo = parent.geometry()
            center_point = parent_geo.center()

            x = center_point.x() - (self.width() // 2)
            y = center_point.y() - (self.height() // 2)

            self.move(x, y)
        else:
            self.show_at_bottom_right()
            return

        self.show()
        self.raise_()
        self.dismiss_timer.start(self.duration_ms)

        current_geo = self.geometry()
        logger.debug(f"Toast shown centered at ({current_geo.x()}, {current_geo.y()})")

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
        self._variant = "error"
        self._apply_theme()

    def set_warning_style(self) -> None:
        """Change toast style to warning (orange background)."""
        self._variant = "warning"
        self._apply_theme()
