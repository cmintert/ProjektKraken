"""Shared icon selection and custom library intent UI."""

from __future__ import annotations

from functools import partial
from typing import Any

from PySide6.QtCore import QPoint, QSize, Qt, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.core.marker_icon import MarkerIconDefinition, MarkerIconSource
from src.gui.dialogs.icon_metadata_dialog import IconMetadataDialog
from src.gui.utils.style_helper import StyleHelper
from src.services.marker_icon_catalog import MarkerIconCatalog


class ProjectIconCard(QWidget):
    """Named artwork preview with selection and context-menu intent."""

    selected = Signal()
    edit_requested = Signal()
    delete_requested = Signal()

    def __init__(
        self, icon_path: str, display_name: str, parent: QWidget | None = None
    ) -> None:
        """Render a named card without library mutations."""
        super().__init__(parent)
        self.setFixedWidth(104)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        self._icon_btn = IconPickerDialog._make_icon_button(icon_path, display_name)
        self._icon_btn.clicked.connect(self.selected.emit)
        self._icon_btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._icon_btn.customContextMenuRequested.connect(self._show_context_menu)
        label = QLabel(display_name)
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        label.setToolTip(display_name)
        layout.addWidget(self._icon_btn, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(label)

    def _show_context_menu(self, position: QPoint) -> None:
        menu = QMenu(self)
        menu.setToolTipsVisible(True)
        edit = menu.addAction("Edit Icon…")
        edit.setToolTip("Edit the name, category, size and anchor")
        edit.triggered.connect(self.edit_requested.emit)
        delete = menu.addAction("Delete Icon…")
        delete.setToolTip("Remove an unused icon; restore it with Undo")
        delete.triggered.connect(self.delete_requested.emit)
        menu.exec(self._icon_btn.mapToGlobal(position))


class IconPickerDialog(QDialog):
    """Select icons and emit library operations for a feature coordinator."""

    library_requested = Signal(dict)

    def __init__(
        self,
        parent: QWidget | None = None,
        world_root: str | None = None,
        catalog: MarkerIconCatalog | None = None,
        *,
        manage_only: bool = False,
    ) -> None:
        """Initialize selection using an immutable catalog snapshot."""
        super().__init__(parent)
        self._manage_only = manage_only
        self.setWindowTitle("Icon Library" if manage_only else "Select Icon")
        self.setMinimumSize(580, 460)
        self.resize(640, 540)
        self.setStyleSheet(StyleHelper.get_dialog_base_style())
        self.selected_definition: MarkerIconDefinition | None = None
        self._world_root = world_root
        self._catalog = catalog or MarkerIconCatalog.load(world_root)
        self._metadata: dict[str, Any] = {}
        self._pending = False
        self._delete_candidate: MarkerIconDefinition | None = None
        self._setup_ui()
        if manage_only and world_root is not None:
            self._tabs.setCurrentIndex(1)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        StyleHelper.apply_form_spacing(layout)
        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_default_icons_tab(), "Default Icons")
        layout.addWidget(self._tabs, 1)
        if self._world_root is not None:
            project = QWidget()
            project_layout = QVBoxLayout(project)
            filters = QHBoxLayout()
            self._search = QLineEdit()
            self._search.setPlaceholderText("Search project icons…")
            self._search.setClearButtonEnabled(True)
            self._category = QComboBox()
            self._category.addItem("All categories", "")
            filters.addWidget(self._search, 1)
            filters.addWidget(self._category)
            project_layout.addLayout(filters)
            self._project_tab_container = QWidget()
            self._project_tab_layout = QVBoxLayout(self._project_tab_container)
            StyleHelper.apply_no_margins(self._project_tab_layout)
            project_layout.addWidget(self._project_tab_container, 1)
            self._tabs.addTab(project, "Project Icons")
            self._search.textChanged.connect(self._rebuild_project_icons_tab)
            self._category.currentIndexChanged.connect(self._rebuild_project_icons_tab)
            self._rebuild_project_icons_tab()
            self._import_btn = QPushButton("Import Icons…")
            self._import_btn.setToolTip(
                "Add one or several SVG, PNG, JPEG or WebP icons"
            )
            self._import_btn.setStyleSheet(StyleHelper.get_tool_button_style())
            self._import_btn.clicked.connect(self._on_import_clicked)
            layout.addWidget(self._import_btn, 0, Qt.AlignmentFlag.AlignLeft)
        self._status = QTextEdit()
        self._status.setReadOnly(True)
        self._status.setMaximumHeight(110)
        self._status.hide()
        layout.addWidget(self._status)
        close = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Close
            if self._manage_only
            else QDialogButtonBox.StandardButton.Cancel
        )
        if self._manage_only:
            hint = QLabel(
                "Import project icons, or click an icon to edit its details. "
                "Right-click an icon to delete it."
            )
            hint.setWordWrap(True)
            layout.addWidget(hint)
        close.rejected.connect(self.reject)
        layout.addWidget(close)

    @staticmethod
    def _make_icon_button(icon_path: str, tooltip: str) -> QPushButton:
        """Render a theme-aware artwork preview button."""
        button = QPushButton()
        button.setFixedSize(64, 64)
        button.setToolTip(tooltip)
        button.setAccessibleName(tooltip)
        button.setStyleSheet(StyleHelper.get_tool_button_style())
        button.setIcon(QIcon(QPixmap(icon_path)))
        button.setIconSize(QSize(48, 48))
        return button

    def _build_default_icons_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(StyleHelper.get_scroll_area_style())
        inner = QWidget()
        grid = QGridLayout(inner)
        grouped: dict[str, list[MarkerIconDefinition]] = {}
        for definition in self._catalog.defaults():
            grouped.setdefault(definition.category or "Other", []).append(definition)
        row = 0
        for category, definitions in grouped.items():
            heading = QLabel(category)
            heading.setStyleSheet(StyleHelper.get_section_header_style())
            grid.addWidget(heading, row, 0, 1, 5)
            row += 1
            for index, definition in enumerate(definitions):
                card = ProjectIconCard(
                    str(self._catalog.asset_file(definition)), definition.name
                )
                card._icon_btn.setContextMenuPolicy(
                    Qt.ContextMenuPolicy.DefaultContextMenu
                )
                card.selected.connect(partial(self._on_definition_selected, definition))
                grid.addWidget(card, row + index // 5, index % 5)
            row += (len(definitions) + 4) // 5
        scroll.setWidget(inner)
        return scroll

    def _rebuild_project_icons_tab(self) -> None:
        while self._project_tab_layout.count():
            item = self._project_tab_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(StyleHelper.get_scroll_area_style())
        inner = QWidget()
        grid = QGridLayout(inner)
        query = self._search.text().strip().casefold()
        category = self._category.currentData()
        definitions = [
            d
            for d in self._catalog.custom()
            if (
                (not category or d.category == category)
                and query
                in " ".join(
                    (
                        d.name,
                        d.category or "",
                        str(self._metadata.get(d.id, {}).get("source_filename", "")),
                    )
                ).casefold()
            )
        ]
        for index, definition in enumerate(definitions):
            card = ProjectIconCard(
                str(self._catalog.asset_file(definition)), definition.name
            )
            card.selected.connect(partial(self._on_definition_selected, definition))
            card.edit_requested.connect(partial(self._on_edit_project_icon, definition))
            card.delete_requested.connect(
                partial(self._on_remove_project_icon, definition)
            )
            grid.addWidget(card, index // 5, index % 5)
        if not definitions:
            grid.addWidget(QLabel("No matching project icons."), 0, 0)
        grid.setRowStretch((len(definitions) + 4) // 5, 1)
        scroll.setWidget(inner)
        self._project_tab_layout.addWidget(scroll)

    def set_library_snapshot(self, snapshot: dict[str, Any]) -> None:
        """Render worker-provided metadata without database access."""
        self._metadata = snapshot.get("metadata", {})
        self._catalog = MarkerIconCatalog.load(self._world_root, self._metadata)
        if self._world_root is None:
            return
        current = self._category.currentData()
        self._category.blockSignals(True)
        self._category.clear()
        self._category.addItem("All categories", "")
        for category in sorted(
            {d.category for d in self._catalog.custom() if d.category}
        ):
            self._category.addItem(category, category)
        self._category.setCurrentIndex(max(0, self._category.findData(current)))
        self._category.blockSignals(False)
        self._rebuild_project_icons_tab()

    def set_request_pending(self, pending: bool) -> None:
        """Disable conflicting operations while a worker request is running."""
        self._pending = pending
        self._tabs.setEnabled(not pending)
        if self._world_root is not None:
            self._import_btn.setEnabled(not pending)

    def _request(self, intent: dict[str, Any]) -> None:
        if self._pending:
            return
        self.set_request_pending(True)
        self._set_status("Updating icon library…")
        self.library_requested.emit(intent)

    def _set_status(self, text: str) -> None:
        """Keep complete request details in a bounded, scrollable report."""
        self._status.setPlainText(text)
        self._status.setVisible(bool(text))

    def finish_library_request(
        self, success: bool, message: str, data: dict[str, Any]
    ) -> None:
        """Present batch outcomes or a reference-aware delete confirmation."""
        self.set_request_pending(False)
        if not success:
            self._set_status(message)
            self._delete_candidate = None
            return
        report = data.get("report", {})
        operation = data.get("operation")
        if operation == "import":
            lines = [
                f"Added {len(report.get('added', []))}, already imported "
                f"{len(report.get('reused', []))}, failed {len(report.get('failed', []))}."
            ]
            lines.extend(f"{f['file']}: {f['error']}" for f in report.get("failed", []))
            self._set_status("\n".join(lines))
            self._tabs.setCurrentIndex(1)
        elif operation == "usage" and self._delete_candidate is not None:
            definition = self._delete_candidate
            self._delete_candidate = None
            uses = report.get("usage", [])
            if uses:
                self._set_status("Icon is in use:\n" + "\n".join(uses))
            elif (
                QMessageBox.question(
                    self,
                    "Delete Icon",
                    f"Delete '{definition.name}'? You can restore it with Undo.",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                == QMessageBox.StandardButton.Yes
            ):
                self._request({"operation": "delete", "icon_id": definition.id})
        else:
            self._set_status("" if operation == "load" else message)

    def icon_references(self) -> dict[str, list[str]]:
        """Expose a pending selection to the application coordinator."""
        if self.selected_definition is None:
            return {}
        return {self.selected_definition.id: ["Open icon selection"]}

    def _on_definition_selected(self, definition: MarkerIconDefinition) -> None:
        if not self._pending:
            if self._manage_only:
                if definition.source is MarkerIconSource.CUSTOM:
                    self._on_edit_project_icon(definition)
                return
            self.selected_definition = definition
            self.accept()

    def _on_import_clicked(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self, "Import Icons", "", "Image Files (*.svg *.png *.jpg *.jpeg *.webp)"
        )
        if files:
            self._request({"operation": "import", "source_paths": files})

    def _on_edit_project_icon(self, definition: MarkerIconDefinition) -> None:
        dialog = IconMetadataDialog(
            definition, str(self._catalog.asset_file(definition)), self
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._request(
                {
                    "operation": "edit",
                    "icon_id": definition.id,
                    "changes": dialog.changes(),
                }
            )

    def _on_remove_project_icon(self, definition: MarkerIconDefinition) -> None:
        self._delete_candidate = definition
        self._request({"operation": "usage", "icon_id": definition.id})
