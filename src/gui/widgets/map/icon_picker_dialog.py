"""
Icon Picker Dialog Module.

Provides the IconPickerDialog for selecting marker icons.
"""

import logging
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget, QListWidgetItem
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap

logger = logging.getLogger(__name__)

class IconPickerDialog(QDialog):
    """
    Dialog for selecting a marker icon from available SVG icons.

    Displays a grid of icon buttons that the user can click to select.
    """

    def __init__(self, parent=None):
        """
        Initializes the IconPickerDialog.

        Args:
            parent: Parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle("Select Marker Icon")
        self.setMinimumSize(300, 200)
        self.selected_icon: Optional[str] = None

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Sets up the dialog UI."""
        layout = QVBoxLayout(self)

        # Scroll area for icons
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        # Container for icon grid
        container = QWidget()
        grid = QGridLayout(container)
        grid.setSpacing(8)

        # Load available icons
        icons = get_available_icons()
        if not icons:
            label = QLabel("No icons found in assets/icons/markers/")
            layout.addWidget(label)
            return

        # Create icon buttons in a grid
        cols = 4
        for i, icon_name in enumerate(sorted(icons)):
            row = i // cols
            col = i % cols

            btn = QPushButton()
            btn.setFixedSize(48, 48)
            btn.setToolTip(icon_name.replace(".svg", ""))

            # Load icon preview
            icon_path = os.path.join(MARKER_ICONS_PATH, icon_name)
            pixmap = QPixmap(icon_path)
            if not pixmap.isNull():
                btn.setIcon(pixmap.scaled(32, 32, Qt.KeepAspectRatio))
                btn.setIconSize(pixmap.size())

            # Connect click
            btn.clicked.connect(
                lambda checked, name=icon_name: self._on_icon_selected(name)
            )
            grid.addWidget(btn, row, col)

        scroll.setWidget(container)
        layout.addWidget(scroll)

    def _on_icon_selected(self, icon_name: str) -> None:
        """
        Handles icon selection.

        Args:
            icon_name: The selected icon filename.
        """
        self.selected_icon = icon_name
        self.accept()


