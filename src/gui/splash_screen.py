"""Branded splash screen shown while ProjektKraken initializes."""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt
from PySide6.QtGui import QColor, QPainter, QPixmap, QShowEvent
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from src.core.paths import get_resource_path
from src.core.theme_manager import ThemeManager
from src.core.version import AUTHOR, RELEASE_DATE, VERSION

_SPLASH_WIDTH = 800
_SPLASH_HEIGHT = 400
_LOGO_WIDTH = 300
_LOGO_HEIGHT = 300
_DISMISS_DURATION_MS = 180


class SplashScreen(QWidget):
    """Frameless, theme-aware application startup screen."""

    def __init__(self) -> None:
        """Create the splash screen and populate release metadata."""
        super().__init__(
            None,
            Qt.WindowType.SplashScreen
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint,
        )
        self.setObjectName("splashWindow")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(_SPLASH_WIDTH, _SPLASH_HEIGHT)
        self.setAccessibleName("Projekt Kraken startup screen")

        theme = ThemeManager().get_theme()
        self._dismiss_target: QWidget | None = None
        self._fade_animation: QPropertyAnimation | None = None
        self._build_ui(theme)
        self.setStyleSheet(self._stylesheet(theme))

    def _build_ui(self, theme: dict[str, str]) -> None:
        """Assemble the branded card and its release information."""
        window_layout = QVBoxLayout(self)
        window_layout.setContentsMargins(18, 16, 18, 22)

        card = QFrame()
        card.setObjectName("splashCard")
        shadow = QGraphicsDropShadowEffect(card)
        shadow_color = QColor(theme["app_bg"])
        shadow_color.setAlpha(95)
        shadow.setColor(shadow_color)
        shadow.setBlurRadius(22)
        shadow.setOffset(0, 5)
        card.setGraphicsEffect(shadow)
        window_layout.addWidget(card)

        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        brand_panel = QFrame()
        brand_panel.setObjectName("brandPanel")
        brand_panel.setFixedWidth(390)
        brand_layout = QVBoxLayout(brand_panel)
        brand_layout.setContentsMargins(28, 20, 28, 20)
        brand_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.logo_label = QLabel()
        self.logo_label.setObjectName("splashLogo")
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo_label.setAccessibleName("Projekt Kraken logo")
        self._load_logo()
        brand_layout.addWidget(self.logo_label, alignment=Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(brand_panel)

        details_panel = QFrame()
        details_panel.setObjectName("detailsPanel")
        details_layout = QVBoxLayout(details_panel)
        details_layout.setContentsMargins(30, 28, 30, 26)
        details_layout.setSpacing(0)

        eyebrow = QLabel("TIMELINE-FIRST WORLDBUILDING")
        eyebrow.setObjectName("eyebrow")
        details_layout.addWidget(eyebrow)

        title = QLabel("Loading your world")
        title.setObjectName("splashTitle")
        title.setWordWrap(True)
        details_layout.addSpacing(8)
        details_layout.addWidget(title)

        rule = QFrame()
        rule.setObjectName("accentRule")
        rule.setFixedHeight(3)
        rule.setFixedWidth(84)
        details_layout.addSpacing(15)
        details_layout.addWidget(rule, alignment=Qt.AlignmentFlag.AlignLeft)
        details_layout.addSpacing(20)

        metadata_card = QFrame()
        metadata_card.setObjectName("metadataCard")
        metadata = QGridLayout(metadata_card)
        metadata.setContentsMargins(16, 14, 16, 14)
        metadata.setHorizontalSpacing(18)
        metadata.setVerticalSpacing(11)
        self.version_value = self._add_metadata_row(
            metadata, 0, "VERSION", f"{VERSION}  BETA"
        )
        self.release_value = self._add_metadata_row(
            metadata, 1, "RELEASED", RELEASE_DATE
        )
        details_layout.addWidget(metadata_card)
        details_layout.addSpacing(26)

        self.status_label = QLabel("Opening workspace…")
        self.status_label.setObjectName("statusLabel")
        details_layout.addWidget(self.status_label)
        details_layout.addSpacing(9)

        progress = QProgressBar()
        progress.setObjectName("startupProgress")
        progress.setRange(0, 0)
        progress.setTextVisible(False)
        progress.setFixedHeight(4)
        details_layout.addWidget(progress)
        details_layout.addStretch()

        self.author_value = QLabel(f"{AUTHOR}  ·  GPL-3.0")
        self.author_value.setObjectName("copyrightLabel")
        details_layout.addWidget(self.author_value)
        card_layout.addWidget(details_panel, 1)

    @staticmethod
    def _add_metadata_row(
        layout: QGridLayout, row: int, label: str, value: str
    ) -> QLabel:
        """Add one labelled metadata value to the details grid."""
        key_label = QLabel(label)
        key_label.setObjectName("metadataKey")
        value_label = QLabel(value)
        value_label.setObjectName("metadataValue")
        layout.addWidget(key_label, row, 0)
        layout.addWidget(value_label, row, 1)
        return value_label

    def _load_logo(self) -> None:
        """Load the full-resolution bundled ProjektKraken brand mark."""
        pixmap = QPixmap(get_resource_path("Kraken.webp"))
        if pixmap.isNull():
            self.logo_label.setText("PROJEKT\nKRAKEN")
            return
        logo_color = QColor(ThemeManager().get_theme()["text_main"])
        logo_color.setAlpha(210)
        painter = QPainter(pixmap)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), logo_color)
        painter.end()
        self.logo_label.setPixmap(
            pixmap.scaled(
                _LOGO_WIDTH,
                _LOGO_HEIGHT,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    @staticmethod
    def _stylesheet(theme: dict[str, str]) -> str:
        """Return splash-specific QSS using the active application palette."""
        return f"""
            QWidget#splashWindow {{
                background: transparent;
                font-family: "Segoe UI";
            }}
            QFrame#splashCard {{
                background-color: {theme["surface"]};
                border: 1px solid {theme["border"]};
                border-radius: 14px;
            }}
            QFrame#brandPanel {{
                background-color: {theme["app_bg"]};
                border: none;
                border-right: 1px solid {theme["border"]};
                border-top-left-radius: 14px;
                border-bottom-left-radius: 14px;
            }}
            QFrame#detailsPanel {{ background: transparent; border: none; }}
            QFrame#metadataCard {{
                background-color: {theme["app_bg"]};
                border: 1px solid {theme["border"]};
                border-radius: 8px;
            }}
            QLabel {{
                background: transparent;
                color: {theme["text_main"]};
                border: none;
            }}
            QLabel#splashLogo {{
                color: {theme["text_main"]};
                font-size: 31px;
                font-weight: 700;
                letter-spacing: 2px;
            }}
            QLabel#eyebrow {{
                color: {theme["primary"]};
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 2px;
            }}
            QLabel#splashTitle {{
                color: {theme["text_main"]};
                font-size: 27px;
                font-weight: 300;
            }}
            QFrame#accentRule {{
                background-color: {theme["primary"]};
                border: none;
                border-radius: 1px;
            }}
            QLabel#metadataKey {{
                color: {theme["text_dim"]};
                font-size: 9px;
                font-weight: 700;
                letter-spacing: 1px;
            }}
            QLabel#metadataValue {{
                color: {theme["text_main"]};
                font-size: 11px;
                font-weight: 500;
            }}
            QLabel#statusLabel {{
                color: {theme["text_dim"]};
                font-size: 10px;
            }}
            QLabel#copyrightLabel {{
                color: {theme["text_dim"]};
                font-size: 9px;
            }}
            QProgressBar#startupProgress {{
                background-color: {theme["border"]};
                border: none;
                border-radius: 2px;
            }}
            QProgressBar#startupProgress::chunk {{
                background-color: {theme["primary"]};
                border-radius: 2px;
                width: 72px;
            }}
        """

    def set_status(self, message: str) -> None:
        """Update the short startup activity message."""
        self.status_label.setText(message)

    def dismiss(self, main_window: QWidget) -> None:
        """Fade out, then transfer focus to the initialized window."""
        self._dismiss_target = main_window
        self._fade_animation = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade_animation.setDuration(_DISMISS_DURATION_MS)
        self._fade_animation.setStartValue(self.windowOpacity())
        self._fade_animation.setEndValue(0.0)
        self._fade_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade_animation.finished.connect(self._finish_dismissal)
        self._fade_animation.start()

    def _finish_dismissal(self) -> None:
        """Close after the fade and activate the main application window."""
        self.close()
        if self._dismiss_target is not None:
            self._dismiss_target.raise_()
            self._dismiss_target.activateWindow()
        self._dismiss_target = None

    def showEvent(self, event: QShowEvent) -> None:
        """Center the splash on the screen where it is shown."""
        super().showEvent(event)
        screen = self.screen()
        if screen is None:
            return
        available = screen.availableGeometry()
        self.move(available.center() - self.rect().center())
