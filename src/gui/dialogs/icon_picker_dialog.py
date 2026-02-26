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
from typing import Callable, List, Optional

from PySide6.QtCore import QPoint, QSize, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.app.constants import DEFAULT_MARKER_ICONS_PATH
from src.core.paths import get_resource_path
from src.gui.utils.style_helper import StyleHelper

logger = logging.getLogger(__name__)

# Neutral background colour for icon preview buttons so icons are
# clearly visible regardless of theme.
_ICON_PREVIEW_BG = "#D9D9D9"


class ProjectIconCard(QWidget):
    """A custom widget for displaying project icons with a context menu.

    Provides a clean card interface with right-click context menu for deletion.
    """

    def __init__(
        self,
        icon_path: str,
        relative_path: str,
        on_select_callback: Callable[[], None],
        on_delete_callback: Callable[[], None],
        parent: Optional[QWidget] = None,
    ) -> None:
        """Initializes the ProjectIconCard.

        Args:
            icon_path: Absolute path to the icon file.
            relative_path: Relative path for identification.
            on_select_callback: Callback when icon is clicked.
            on_delete_callback: Callback when delete is selected from menu.
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self._icon_path = icon_path
        self._relative_path = relative_path
        self._on_select = on_select_callback
        self._on_delete = on_delete_callback
        self.setFixedSize(64, 64)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        # Create the icon button (main clickable area)
        self._icon_btn = QPushButton(self)
        self._icon_btn.setFixedSize(64, 64)
        self._icon_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._icon_btn.setToolTip(relative_path)
        self._icon_btn.clicked.connect(self._on_select)

        # Load and set icon
        pixmap = QPixmap(icon_path)
        if not pixmap.isNull():
            self._icon_btn.setIcon(
                pixmap.scaled(
                    48,
                    48,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
            self._icon_btn.setIconSize(QSize(48, 48))

        self._update_style()

    def _update_style(self) -> None:
        """Updates the widget styling."""
        from src.core.theme_manager import ThemeManager

        theme = ThemeManager().get_theme()

        card_style = (
            f"QWidget {{ background-color: {theme['surface']}; "
            f"border: 1px solid {theme['border']}; "
            f"border-radius: 4px; }}"
        )
        icon_btn_style = (
            f"QPushButton {{ background-color: {_ICON_PREVIEW_BG}; "
            f"border: none; border-radius: 4px; }}"
            f"QPushButton:hover {{ border: 2px solid {theme['primary']}; }}"
        )

        self.setStyleSheet(card_style)
        self._icon_btn.setStyleSheet(icon_btn_style)

    def _show_context_menu(self, position: QPoint) -> None:
        """Shows the context menu for this icon card.

        Args:
            position: The position where the menu should appear.
        """
        from PySide6.QtWidgets import QMenu

        menu = QMenu(self)

        delete_action = menu.addAction("Delete Icon")
        delete_action.triggered.connect(self._on_delete)

        # Show menu at the cursor position
        menu.exec(self.mapToGlobal(position))


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


def remove_project_icon(world_root: str, rel_path: str) -> bool:
    """Deletes a previously imported project icon from disk.

    Args:
        world_root: Absolute path to the world directory.
        rel_path: Relative posix path of the icon (e.g.
                  ``assets/images/icon_<uuid>.svg``).

    Returns:
        True if the file was removed, False otherwise.

    """
    abs_path = Path(world_root) / rel_path
    if abs_path.is_file():
        try:
            abs_path.unlink()
            logger.info(f"Removed project icon: {rel_path}")
            return True
        except OSError as exc:
            logger.error(f"Failed to remove icon {rel_path}: {exc}")
    return False


class IconPickerDialog(QDialog):
    """Dialog for selecting an icon from default, project, or disk sources.

    Displays tabs for default bundled icons, project icons already imported
    into the world, and an import-from-disk action.  Adheres to the
    application's theme via :class:`StyleHelper`.

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
        self.setMinimumSize(420, 380)
        self.setStyleSheet(StyleHelper.get_dialog_base_style())
        self.selected_icon: Optional[str] = None
        self._world_root = world_root

        self._setup_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        """Builds the tabbed dialog layout."""
        layout = QVBoxLayout(self)
        StyleHelper.apply_form_spacing(layout)

        tabs = QTabWidget()
        layout.addWidget(tabs, 1)

        # Tab 1: Default Icons
        default_tab = self._build_default_icons_tab()
        tabs.addTab(default_tab, "Default Icons")

        # Tab 2: Project Icons (only when world_root is set)
        if self._world_root is not None:
            self._project_tab_container = QWidget()
            self._project_tab_layout = QVBoxLayout(self._project_tab_container)
            StyleHelper.apply_no_margins(self._project_tab_layout)
            self._rebuild_project_icons_tab()
            tabs.addTab(self._project_tab_container, "Project Icons")

        # Import from Disk button (only when world_root is set)
        if self._world_root is not None:
            btn_layout = QHBoxLayout()
            import_btn = QPushButton("Import from Disk…")
            import_btn.setStyleSheet(StyleHelper.get_tool_button_style())
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
        StyleHelper.apply_no_margins(outer)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(StyleHelper.get_scroll_area_style())

        inner = QWidget()
        grid = QGridLayout(inner)
        grid.setSpacing(8)
        grid.setContentsMargins(8, 8, 8, 8)

        icons = get_available_default_icons()
        if not icons:
            label = QLabel("No default icons found.")
            label.setStyleSheet(StyleHelper.get_empty_state_style())
            grid.addWidget(label, 0, 0)
        else:
            cols = 5
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

    def _rebuild_project_icons_tab(self) -> None:
        """(Re)builds the project icons grid inside the existing container.

        Called on initial construction and after a project icon is removed.
        """
        # Clear previous contents
        for i in reversed(range(self._project_tab_layout.count())):
            widget = self._project_tab_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(StyleHelper.get_scroll_area_style())

        inner = QWidget()
        grid = QGridLayout(inner)
        grid.setSpacing(8)
        grid.setContentsMargins(8, 8, 8, 8)

        icons = get_project_icons(self._world_root) if self._world_root else []
        if not icons:
            label = QLabel("No project icons found.")
            label.setStyleSheet(StyleHelper.get_empty_state_style())
            grid.addWidget(label, 0, 0)
        else:
            cols = 5
            for i, rel_path in enumerate(icons):
                grid_row, col = divmod(i, cols)
                abs_path = os.path.join(self._world_root, rel_path)

                # Create ProjectIconCard with callbacks
                card = ProjectIconCard(
                    icon_path=abs_path,
                    relative_path=rel_path,
                    on_select_callback=lambda checked=False, rp=rel_path: (
                        self._on_icon_selected(rp)
                    ),
                    on_delete_callback=lambda checked=False, rp=rel_path: (
                        self._on_remove_project_icon(rp)
                    ),
                )
                grid.addWidget(card, grid_row, col)

        scroll.setWidget(inner)
        self._project_tab_layout.addWidget(scroll)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_icon_button(icon_path: str, tooltip: str) -> QPushButton:
        """Creates a 48×48 icon button with a preview pixmap.

        The button uses a neutral light background so that icons are
        clearly visible regardless of the current theme.

        Args:
            icon_path: Absolute path to the icon file.
            tooltip: Tooltip text for the button.

        Returns:
            QPushButton: The configured icon button.

        """
        btn = QPushButton()
        btn.setFixedSize(48, 48)
        btn.setToolTip(tooltip)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(
            f"QPushButton {{ background-color: {_ICON_PREVIEW_BG}; "
            f"border: 1px solid #888; border-radius: 4px; }}"
            f"QPushButton:hover {{ border: 2px solid #555; }}"
        )
        pixmap = QPixmap(icon_path)
        if not pixmap.isNull():
            btn.setIcon(
                pixmap.scaled(
                    32,
                    32,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
            btn.setIconSize(QSize(32, 32))
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

    def _on_remove_project_icon(self, rel_path: str) -> None:
        """Asks for confirmation and removes a project icon.

        After removal the Project Icons tab is rebuilt.

        Args:
            rel_path: Relative posix path of the project icon.
        """
        reply = QMessageBox.question(
            self,
            "Remove Icon",
            f"Remove icon '{Path(rel_path).name}' from the project?\n\n"
            "This will delete the file from disk.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        if remove_project_icon(self._world_root, rel_path):
            self._rebuild_project_icons_tab()
