"""Shared Icon Picker Dialog Module.

Provides a unified IconPickerDialog for selecting marker/node icons from:
  - Default Icons (bundled in default_assets/icons/markers)
  - Project Icons (previously imported into world assets/images)
  - Import from Disk (when a world_root is provided)

Used by both the Lexicon Editor and Map Editor.
"""

import logging
import os
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
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.app.constants import DEFAULT_MARKER_ICONS_PATH
from src.core.paths import get_resource_path

logger = logging.getLogger(__name__)


def _get_default_icons_dir() -> str:
    """Returns the absolute path to the bundled marker icons directory."""
    return get_resource_path(DEFAULT_MARKER_ICONS_PATH)


def get_available_default_icons() -> List[str]:
    """Returns a sorted list of bundled default marker icon filenames.

    Returns:
        List[str]: Sorted list of .svg filenames.

    """
    icons_dir = _get_default_icons_dir()
    if not os.path.exists(icons_dir):
        return []
    return sorted(f for f in os.listdir(icons_dir) if f.endswith(".svg"))


def get_project_icons(world_root: str) -> List[str]:
    """Returns relative paths of previously imported icon files in the world.

    Scans ``<world_root>/assets/images/`` for files whose names start with
    ``icon_`` and have an allowed image extension.

    Args:
        world_root: Absolute path to the world directory.

    Returns:
        List[str]: Sorted list of relative posix paths
                   (e.g. ``assets/images/icon_<uuid>.svg``).

    """
    images_dir = Path(world_root) / "assets" / "images"
    if not images_dir.is_dir():
        return []
    allowed = {".svg", ".png", ".jpg", ".jpeg"}
    icons: List[str] = []
    for f in images_dir.iterdir():
        if f.is_file() and f.name.startswith("icon_") and f.suffix.lower() in allowed:
            rel = f.relative_to(Path(world_root)).as_posix()
            icons.append(rel)
    return sorted(icons)


class IconPickerDialog(QDialog):
    """Dialog for selecting an icon from default, project, or disk sources.

    Displays tabs for default bundled icons, project icons already imported
    into the world, and an import-from-disk action.

    The ``selected_icon`` attribute holds the result after acceptance:
      - For default icons: the filename (e.g. ``castle.svg``)
      - For project icons: the relative path (e.g. ``assets/images/icon_<uuid>.svg``)
      - For imported icons: the newly created relative path
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        world_root: Optional[str] = None,
    ) -> None:
        """Initializes the IconPickerDialog.

        Args:
            parent: Parent widget.
            world_root: Absolute path to the world directory.  When provided,
                the Project Icons tab and Import from Disk button are shown.

        """
        super().__init__(parent)
        self.setWindowTitle("Select Icon")
        self.setMinimumSize(360, 300)
        self.selected_icon: Optional[str] = None
        self._world_root = world_root

        self._setup_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        """Builds the tabbed dialog layout."""
        layout = QVBoxLayout(self)

        tabs = QTabWidget()
        layout.addWidget(tabs, 1)

        # Tab 1: Default Icons
        default_tab = self._build_default_icons_tab()
        tabs.addTab(default_tab, "Default Icons")

        # Tab 2: Project Icons (only when world_root is set)
        if self._world_root is not None:
            project_tab = self._build_project_icons_tab()
            tabs.addTab(project_tab, "Project Icons")

        # Import from Disk button (only when world_root is set)
        if self._world_root is not None:
            btn_layout = QHBoxLayout()
            import_btn = QPushButton("Import from Disk...")
            import_btn.setToolTip(
                "Import an SVG, PNG, or JPG file from your filesystem"
            )
            import_btn.clicked.connect(self._on_import_clicked)
            btn_layout.addWidget(import_btn)
            btn_layout.addStretch()
            layout.addLayout(btn_layout)

    # ------------------------------------------------------------------
    # Default Icons tab
    # ------------------------------------------------------------------

    def _build_default_icons_tab(self) -> QWidget:
        """Builds a scrollable grid of bundled default icons.

        Returns:
            QWidget: The default icons tab widget.

        """
        container = QWidget()
        outer = QVBoxLayout(container)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        inner = QWidget()
        grid = QGridLayout(inner)
        grid.setSpacing(8)

        icons = get_available_default_icons()
        if not icons:
            label = QLabel("No default icons found.")
            grid.addWidget(label, 0, 0)
        else:
            cols = 4
            icons_dir = _get_default_icons_dir()
            for i, icon_name in enumerate(icons):
                row, col = divmod(i, cols)
                btn = self._make_icon_button(
                    os.path.join(icons_dir, icon_name), icon_name
                )
                btn.clicked.connect(
                    lambda checked, name=icon_name: self._on_icon_selected(name)
                )
                grid.addWidget(btn, row, col)

        scroll.setWidget(inner)
        outer.addWidget(scroll)
        return container

    # ------------------------------------------------------------------
    # Project Icons tab
    # ------------------------------------------------------------------

    def _build_project_icons_tab(self) -> QWidget:
        """Builds a scrollable grid of previously imported project icons.

        Returns:
            QWidget: The project icons tab widget.

        """
        container = QWidget()
        outer = QVBoxLayout(container)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        inner = QWidget()
        grid = QGridLayout(inner)
        grid.setSpacing(8)

        icons = get_project_icons(self._world_root) if self._world_root else []
        if not icons:
            label = QLabel("No project icons found.")
            grid.addWidget(label, 0, 0)
        else:
            cols = 4
            for i, rel_path in enumerate(icons):
                row, col = divmod(i, cols)
                abs_path = os.path.join(self._world_root, rel_path)
                btn = self._make_icon_button(abs_path, rel_path)
                btn.clicked.connect(
                    lambda checked, rp=rel_path: self._on_icon_selected(rp)
                )
                grid.addWidget(btn, row, col)

        scroll.setWidget(inner)
        outer.addWidget(scroll)
        return container

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_icon_button(icon_path: str, tooltip: str) -> QPushButton:
        """Creates a 48×48 icon button with a preview pixmap.

        Args:
            icon_path: Absolute path to the icon file.
            tooltip: Tooltip text for the button.

        Returns:
            QPushButton: The configured icon button.

        """
        btn = QPushButton()
        btn.setFixedSize(48, 48)
        btn.setToolTip(tooltip)
        pixmap = QPixmap(icon_path)
        if not pixmap.isNull():
            btn.setIcon(pixmap.scaled(32, 32, Qt.AspectRatioMode.KeepAspectRatio))
            btn.setIconSize(pixmap.size())
        return btn

    def _on_icon_selected(self, icon_identifier: str) -> None:
        """Sets the selected icon and accepts the dialog.

        Args:
            icon_identifier: Filename for default icons, relative path for
                project icons.

        """
        self.selected_icon = icon_identifier
        self.accept()

    def _on_import_clicked(self) -> None:
        """Handles the Import from Disk button.

        Opens a file dialog, imports the file via AssetStore, and returns the
        relative path as the selected icon.
        """
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Icon",
            "",
            "Image Files (*.svg *.png *.jpg *.jpeg);;All Files (*)",
        )
        if not file_path or self._world_root is None:
            return

        try:
            from src.services.asset_store import AssetStore

            store = AssetStore(self._world_root)
            relative_path = store.import_icon(file_path)
            self.selected_icon = relative_path
            self.accept()
        except Exception as exc:
            logger.error(f"Failed to import icon: {exc}")
