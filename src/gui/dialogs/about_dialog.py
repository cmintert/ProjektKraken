"""About Dialog.

A themed dialog displaying application information.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.app.constants import VERSION
from src.gui.utils.style_helper import StyleHelper


class AboutDialog(QDialog):
    """Themed about dialog."""

    def __init__(self, parent: QWidget = None) -> None:
        """Initialize the about dialog.

        Args:
            parent: Parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle("About ProjektKraken")
        self.setMinimumWidth(400)
        self.setStyleSheet(StyleHelper.get_dialog_base_style())

        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)

        # Title
        title = QLabel("ProjektKraken")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(StyleHelper.get_content_header_style())
        layout.addWidget(title)

        # Version
        version = QLabel(f"Version {VERSION}")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Reuse preview label style for subtitle feel, or standard text
        # Let's just use standard text but centered
        layout.addWidget(version)

        # Description
        desc = QLabel(
            "A desktop worldbuilding environment\nwith timeline-first workflow."
        )
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Footer / Copyright
        footer = QLabel("© 2026 Christian Mintert")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setStyleSheet(StyleHelper.get_preview_label_style())
        layout.addWidget(footer)

        layout.addStretch()

        # Close button
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.setMinimumWidth(100)
        close_btn.setStyleSheet(StyleHelper.get_primary_button_style())
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        button_layout.addStretch()  # Center the button

        layout.addLayout(button_layout)
