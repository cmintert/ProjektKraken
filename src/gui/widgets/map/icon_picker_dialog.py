"""Icon Picker Dialog Module.

Provides the IconPickerDialog for selecting marker icons and importing
SVG/PNG/JPG assets from the operating system into the project sandbox.
"""

import logging
import os
import shutil
import uuid
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

# Define locally to avoid circular import
MARKER_ICONS_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "..",
    "..",
    "default_assets",
    "icons",
    "markers",
)


def get_available_icons() -> List[str]:
    """Returns a list of available marker icon filenames."""
    if not os.path.exists(MARKER_ICONS_PATH):
        return []
    return [f for f in os.listdir(MARKER_ICONS_PATH) if f.endswith(".svg")]


logger = logging.getLogger(__name__)

# Allowed image file extensions for secure asset importing
ALLOWED_IMAGE_EXTENSIONS = {".svg", ".png", ".jpg", ".jpeg"}


def import_asset_file(source_path: str, assets_dir: Path) -> Optional[str]:
    """Imports an image file into the project's local asset store.

    Validates the file extension, generates a collision-free filename using
    UUID, and copies the file into the assets/images/ directory.

    Args:
        source_path: Absolute path to the source file on the OS.
        assets_dir: Path to the world's assets directory (World.assets_path).

    Returns:
        Relative path string (e.g., 'assets/images/icon_<uuid>.svg')
        for database storage, or None if the import failed.

    """
    source = Path(source_path)

    # Validate file exists
    if not source.is_file():
        logger.warning(f"Import source not found: {source_path}")
        return None

    # Validate extension (security: prevent importing executables)
    ext = source.suffix.lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        logger.warning(
            f"Blocked import of disallowed file type: {ext} ({source_path})"
        )
        return None

    # Ensure target directory exists
    images_dir = assets_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    # Generate collision-free filename
    safe_name = f"icon_{uuid.uuid4().hex}{ext}"
    target_path = images_dir / safe_name

    try:
        shutil.copy2(str(source), str(target_path))
        relative_path = f"assets/images/{safe_name}"
        logger.info(f"Imported asset: {source_path} -> {relative_path}")
        return relative_path
    except OSError as e:
        logger.error(f"Failed to import asset: {e}")
        return None


class IconPickerDialog(QDialog):
    """Dialog for selecting a marker icon from available SVG icons.

    Displays a grid of icon buttons that the user can click to select.
    Optionally supports importing icons from the OS filesystem when an
    assets_dir is provided.
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        assets_dir: Optional[Path] = None,
    ) -> None:
        """Initializes the IconPickerDialog.

        Args:
            parent: Parent widget.
            assets_dir: Path to the world's assets directory. When provided,
                an "Import from Disk" button is shown to allow importing
                SVG/PNG/JPG files into the project sandbox.

        """
        super().__init__(parent)
        self.setWindowTitle("Select Marker Icon")
        self.setMinimumSize(300, 200)
        self.selected_icon: Optional[str] = None
        self._assets_dir = assets_dir

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Sets up the dialog UI."""
        layout = QVBoxLayout(self)

        # Import from Disk button (only when assets_dir is available)
        if self._assets_dir is not None:
            btn_layout = QHBoxLayout()
            import_btn = QPushButton("Import from Disk...")
            import_btn.setToolTip(
                "Import an SVG, PNG, or JPG file from your filesystem"
            )
            import_btn.clicked.connect(self._on_import_clicked)
            btn_layout.addWidget(import_btn)
            btn_layout.addStretch()
            layout.addLayout(btn_layout)

        # Scroll area for icons
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        # Container for icon grid
        container = QWidget()
        grid = QGridLayout(container)
        grid.setSpacing(8)

        # Load available icons
        icons = get_available_icons()
        if not icons:
            label = QLabel("No icons found in default_assets/icons/markers/")
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
                btn.setIcon(pixmap.scaled(32, 32, Qt.AspectRatioMode.KeepAspectRatio))
                btn.setIconSize(pixmap.size())

            # Connect click
            btn.clicked.connect(
                lambda checked, name=icon_name: self._on_icon_selected(name)
            )
            grid.addWidget(btn, row, col)

        scroll.setWidget(container)
        layout.addWidget(scroll)

    def _on_icon_selected(self, icon_name: str) -> None:
        """Handles icon selection.

        Args:
            icon_name: The selected icon filename.

        """
        self.selected_icon = icon_name
        self.accept()

    def _on_import_clicked(self) -> None:
        """Handles the Import from Disk button click.

        Opens a file dialog filtered to allowed image types, imports the
        selected file into the project's asset store, and returns the
        relative path as the selection result.
        """
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Image Asset",
            "",
            "Image Files (*.svg *.png *.jpg *.jpeg);;All Files (*)",
        )
        if not file_path or self._assets_dir is None:
            return

        relative_path = import_asset_file(file_path, self._assets_dir)
        if relative_path:
            self.selected_icon = relative_path
            self.accept()
