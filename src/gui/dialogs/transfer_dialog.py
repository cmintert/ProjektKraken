"""Unified transfer chooser, review and persistent results (presentation only)."""

from __future__ import annotations

import json
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QTextBrowser,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.transfer import (
    FORMAT_BY_KEY,
    FORMATS,
    LORE_JSON_EXAMPLE_TEXT,
    LORE_KINDS,
    REFERENCE_TAB,
)
from src.gui.constants import SUPPORTED_IMAGE_FORMATS
from src.gui.utils.style_helper import StyleHelper


class TransferDialog(QDialog):
    """Render transfer choices and snapshots; emit user intent to the coordinator."""

    files_requested = Signal()
    folder_requested = Signal()
    review_requested = Signal(dict)
    apply_requested = Signal(dict)
    cancel_requested = Signal()
    template_requested = Signal(str, str)
    specialist_requested = Signal(str)
    destination_requested = Signal(str)
    package_requested = Signal()
    report_requested = Signal()
    open_requested = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the shared chooser, review and persistent results pages."""
        super().__init__(parent)
        self.setWindowTitle("Import / Export")
        self.resize(1000, 760)
        self.setMinimumSize(780, 560)
        self.setStyleSheet(StyleHelper.get_dialog_base_style())
        self.busy = False
        self.sources: list[dict[str, Any]] = []
        self.data: dict[str, Any] = {}
        self._review_kind = ""
        self._row_controls: dict[str, tuple[QTreeWidgetItem, QComboBox, QComboBox]] = {}
        self._selected_token = ""
        self._drafts: dict[str, str] = {}
        layout = QVBoxLayout(self)
        self.context = QLabel()
        self.context.setWordWrap(True)
        layout.addWidget(self.context)
        self.steps = QLabel("Choose → Configure → Review → Transfer → Results")
        layout.addWidget(self.steps)
        self.pages = QStackedWidget()
        layout.addWidget(self.pages, 1)
        self.tabs = QTabWidget()
        self.pages.addWidget(self.tabs)
        self._build_import()
        self._build_export()
        self._build_world()
        self._build_reference()
        self._build_review()
        self._build_results()
        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        buttons = QHBoxLayout()
        self.back = QPushButton("Back")
        self.back.clicked.connect(self._back)
        buttons.addWidget(self.back)
        buttons.addStretch()
        self.cancel = QPushButton("Close")
        self.cancel.clicked.connect(self._cancel_clicked)
        buttons.addWidget(self.cancel)
        self.next = QPushButton("Review…")
        self.next.clicked.connect(self._next)
        buttons.addWidget(self.next)
        layout.addLayout(buttons)
        self.tabs.currentChanged.connect(lambda _: self._update_choice())
        self._update_choice()

    def _build_import(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        label = QLabel(
            "Add lore to the current world: JSON, Markdown / Obsidian notes, "
            "or CSV/TSV.\nAll selected files are reviewed together. Existing "
            "matches are skipped by default."
        )
        label.setWordWrap(True)
        layout.addWidget(label)
        self.source_list = QListWidget()
        layout.addWidget(self.source_list, 1)
        row = QHBoxLayout()
        for title, callback in (
            ("Add files…", self.files_requested.emit),
            ("Add folder…", self.folder_requested.emit),
            ("Remove selected", self._remove_sources),
        ):
            button = QPushButton(title)
            button.clicked.connect(callback)
            row.addWidget(button)
        layout.addLayout(row)
        paste_header = QHBoxLayout()
        paste_header.addWidget(QLabel("Or paste lore JSON:"))
        paste_header.addStretch()
        self.pasted_example = QPushButton("Insert complete example")
        self.pasted_example.setToolTip(
            "Load a complete, valid entity/event/relation example for editing."
        )
        self.pasted_example.clicked.connect(self._insert_json_example)
        paste_header.addWidget(self.pasted_example)
        layout.addLayout(paste_header)
        self.pasted = QPlainTextEdit()
        self.pasted.setStyleSheet(StyleHelper.get_input_field_style())
        self.pasted.setPlaceholderText("Paste a lore JSON object here.")
        self.pasted.textChanged.connect(self._update_example_button)
        self.pasted.setMaximumHeight(110)
        layout.addWidget(self.pasted)
        row = QHBoxLayout()
        row.addWidget(QLabel("When an existing record matches:"))
        self.mode = QComboBox()
        for title, key in (
            ("Skip existing records", "skip"),
            ("Merge fields", "update"),
            ("Replace record fields", "overwrite"),
        ):
            self.mode.addItem(title, key)
        row.addWidget(self.mode)
        layout.addLayout(row)
        self.mode_help = QLabel(
            "Merge combines imported fields with existing data. Replace resets "
            "record fields.\n"
            "The review shows changes before anything is written. Import can be undone."
        )
        self.mode_help.setWordWrap(True)
        layout.addWidget(self.mode_help)
        self.tabs.addTab(page, "Import")

    def _build_export(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        form = QFormLayout()
        self.export_format = QComboBox()
        for item in FORMATS:
            if item.exports and item.key != "world":
                self.export_format.addItem(item.title, item.key)
        form.addRow("Format:", self.export_format)
        self.format_help = QLabel()
        self.format_help.setWordWrap(True)
        form.addRow(self.format_help)
        self.scope = QComboBox()
        self.scope.addItem("All lore", "all")
        self.scope.addItem("Explorer selection", "selected")
        form.addRow("Include:", self.scope)
        self.endpoints = QCheckBox("Include missing relationship endpoints")
        form.addRow(self.endpoints)
        self.title_edit = QLineEdit("Longform document")
        form.addRow("Document title:", self.title_edit)
        self.page_size = QComboBox()
        self.page_size.addItems(["A4", "Letter"])
        form.addRow("Page size:", self.page_size)
        self.contents = QCheckBox("Include contents list")
        self.images = QCheckBox("Include referenced images")
        self.images.setChecked(True)
        form.addRow(self.contents)
        form.addRow(self.images)
        layout.addLayout(form)
        row = QHBoxLayout()
        self.destination = QLineEdit()
        self.destination.setReadOnly(True)
        self.destination.setPlaceholderText("Choose where the output will be saved")
        row.addWidget(self.destination, 1)
        choose = QPushButton("Choose destination…")
        choose.clicked.connect(
            lambda: self.destination_requested.emit(self.export_format.currentData())
        )
        row.addWidget(choose)
        layout.addLayout(row)
        layout.addStretch()
        self.export_format.currentIndexChanged.connect(self._format_changed)
        self.tabs.addTab(page, "Export")
        self._format_changed()

    def _build_world(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.world_mode = QComboBox()
        self.world_mode.addItem(
            "Import a portable world as a new world", "import_world"
        )
        self.world_mode.addItem("Export the current world with assets", "export_world")
        layout.addWidget(self.world_mode)
        label = QLabel(
            "Portable world (.krakenworld): manifest, database, maps, calendars "
            "and assets.\nImport creates a separate world. Local preferences and "
            "backups are excluded."
        )
        label.setWordWrap(True)
        layout.addWidget(label)
        row = QHBoxLayout()
        self.package_path = QLineEdit()
        self.package_path.setReadOnly(True)
        row.addWidget(self.package_path, 1)
        self.package_button = QPushButton("Choose package…")
        self.package_button.clicked.connect(self.package_requested.emit)
        row.addWidget(self.package_button)
        layout.addLayout(row)
        self.world_name = QLineEdit()
        self.world_name.setPlaceholderText(
            "New world folder name (required for import)"
        )
        layout.addWidget(self.world_name)
        layout.addStretch()
        label = QLabel(
            "Backup recovery is separate: a .kraken backup restores the database "
            "and replaces\n"
            "the active world state. It does not include the world's asset files."
        )
        label.setWordWrap(True)
        layout.addWidget(label)
        row = QHBoxLayout()
        for title, key in (
            ("Create backup…", "backup"),
            ("Restore backup…", "restore"),
            ("Manage worlds…", "worlds"),
        ):
            button = QPushButton(title)
            button.clicked.connect(
                lambda _=False, k=key: self.specialist_requested.emit(k)
            )
            row.addWidget(button)
        layout.addLayout(row)
        self.world_mode.currentIndexChanged.connect(self._world_mode_changed)
        self.tabs.addTab(page, "World Transfer && Backups")

    def _build_reference(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        browser = QTextBrowser()
        browser.setStyleSheet(StyleHelper.get_input_field_style())
        rows = []
        for item in FORMATS:
            direction = (
                "Import and export" if item.imports and item.exports else "Export only"
            )
            rows.append(
                f"<h3>{item.title} ({', '.join(item.extensions)})</h3>"
                f"<p>{direction}. {item.description}<br>{item.limitation}</p>"
            )
        rows.append(
            "<h3>Specialist transfers</h3><p>Map backgrounds and gallery images: "
            + ", ".join(ext.upper() for ext in SUPPORTED_IMAGE_FORMATS)
            + ". "
            "Raster layers: PNG, TIFF, JPEG. Palette JSON: import and export in "
            "the raster palette editor. "
            "Analysis reports: JSON and Markdown export from the Analysis panel. "
            "Calendars travel inside complete-world packages; standalone "
            "calendar exchange is unavailable.</p>"
        )
        browser.setHtml("".join(rows))
        layout.addWidget(browser, 1)
        row = QHBoxLayout()
        self.template_kind = QComboBox()
        self.template_kind.addItems(list(LORE_KINDS))
        row.addWidget(self.template_kind)
        for title, key in (
            ("Save CSV template…", "csv"),
            ("Save JSON example…", "json"),
        ):
            button = QPushButton(title)
            button.clicked.connect(
                lambda _=False, k=key: self.template_requested.emit(
                    self.template_kind.currentText(), k
                )
            )
            row.addWidget(button)
        layout.addLayout(row)
        row = QHBoxLayout()
        for title, key in (
            ("Import map image…", "map"),
            ("Raster tools…", "raster"),
            ("Gallery…", "gallery"),
            ("Analysis reports…", "analysis"),
        ):
            button = QPushButton(title)
            button.clicked.connect(
                lambda _=False, k=key: self.specialist_requested.emit(k)
            )
            row.addWidget(button)
        layout.addLayout(row)
        self.tabs.addTab(page, "Supported formats")

    def _build_review(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.review_summary = QLabel()
        self.review_summary.setWordWrap(True)
        layout.addWidget(self.review_summary)
        splitter = QSplitter()
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Use / type", "Name", "Source", "Action", "Match"])
        splitter.addWidget(self.tree)
        self.details = QPlainTextEdit()
        self.details.setStyleSheet(StyleHelper.get_input_field_style())
        self.details.setPlaceholderText(
            "Select a record to inspect or correct its JSON fields."
        )
        splitter.addWidget(self.details)
        layout.addWidget(splitter, 1)
        self.document_preview = QTextBrowser()
        self.document_preview.setStyleSheet(StyleHelper.get_input_field_style())
        layout.addWidget(self.document_preview, 1)
        self.diagnostics = QPlainTextEdit()
        self.diagnostics.setStyleSheet(StyleHelper.get_input_field_style())
        self.diagnostics.setReadOnly(True)
        self.diagnostics.setMaximumHeight(150)
        layout.addWidget(self.diagnostics)
        self.recheck = QPushButton("Apply edits and recheck")
        self.recheck.clicked.connect(self._recheck)
        layout.addWidget(self.recheck)
        self.tree.currentItemChanged.connect(self._select_record)
        self.tree.itemChanged.connect(self._invalidate)
        self.details.textChanged.connect(self._invalidate)
        self.pages.addWidget(page)

    def _build_results(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.results = QPlainTextEdit()
        self.results.setStyleSheet(StyleHelper.get_input_field_style())
        self.results.setReadOnly(True)
        layout.addWidget(self.results, 1)
        row = QHBoxLayout()
        self.open_file = QPushButton("Open file")
        self.open_folder = QPushButton("Open folder")
        self.open_file.clicked.connect(lambda: self.open_requested.emit(False))
        self.open_folder.clicked.connect(lambda: self.open_requested.emit(True))
        row.addWidget(self.open_file)
        row.addWidget(self.open_folder)
        save = QPushButton("Save report…")
        save.clicked.connect(self.report_requested.emit)
        row.addWidget(save)
        layout.addLayout(row)
        self.pages.addWidget(page)

    def _format_changed(self) -> None:
        item = FORMAT_BY_KEY[self.export_format.currentData()]
        self.format_help.setText(item.description + "\n" + item.limitation)
        document = item.key in {"markdown", "pdf", "docx"}
        for widget in (self.title_edit, self.page_size, self.contents, self.images):
            widget.setEnabled(document)
        self.scope.setEnabled(not document)
        self.endpoints.setEnabled(not document)
        self.destination.clear()

    def _world_mode_changed(self) -> None:
        importing = self.world_mode.currentData() == "import_world"
        self.package_button.setText(
            "Choose package…" if importing else "Choose destination…"
        )
        self.world_name.setEnabled(importing)
        self.package_path.clear()

    def _update_choice(self) -> None:
        self.back.setEnabled(self.pages.currentIndex() != 0)
        self.next.setVisible(self.tabs.currentIndex() != REFERENCE_TAB)
        self.next.setText("Review…")

    def _remove_sources(self) -> None:
        index = self.source_list.currentRow()
        if index >= 0:
            self.sources.pop(index)
            self.source_list.takeItem(index)

    def _insert_json_example(self) -> None:
        self.pasted.setPlainText(LORE_JSON_EXAMPLE_TEXT)
        self.pasted.setFocus()
        self.pasted.moveCursor(QTextCursor.MoveOperation.Start)

    def _update_example_button(self) -> None:
        self.pasted_example.setEnabled(not self.pasted.toPlainText().strip())

    def set_sources(self, sources: list[dict[str, Any]]) -> None:
        """Render the coordinator's source list and CSV mapping summaries."""
        self.sources = sources
        self.source_list.clear()
        self.source_list.addItems(
            [
                row["path"] + (f" — {row['kind']}" if "kind" in row else "")
                for row in sources
            ]
        )

    def request(self) -> dict[str, Any]:
        """Return serializable user choices."""
        return {
            "tab": self.tabs.currentIndex(),
            "sources": self.sources,
            "pasted": self.pasted.toPlainText(),
            "mode": self.mode.currentData(),
            "format": self.export_format.currentData(),
            "scope": self.scope.currentData(),
            "include_endpoints": self.endpoints.isChecked(),
            "destination": self.destination.text(),
            "world_mode": self.world_mode.currentData(),
            "package_path": self.package_path.text(),
            "world_name": self.world_name.text(),
            "options": {
                "title": self.title_edit.text(),
                "contents": self.contents.isChecked(),
                "images": self.images.isChecked(),
                "page_size": self.page_size.currentText(),
            },
        }

    def _next(self) -> None:
        if self.pages.currentIndex() == 0:
            self.review_requested.emit(self.request())
        elif self.pages.currentIndex() == 1:
            self.apply_requested.emit(self.request())
        else:
            self._back()

    def _back(self) -> None:
        self.pages.setCurrentIndex(0)
        self.status.clear()
        self._update_choice()

    def _cancel_clicked(self) -> None:
        if self.busy:
            self.cancel_requested.emit()
        else:
            self.reject()

    def set_busy(self, busy: bool, message: str = "") -> None:
        """Keep cancellation available while a worker operation is running."""
        self.busy = busy
        self.pages.setEnabled(not busy)
        self.next.setEnabled(not busy)
        self.back.setEnabled(not busy and self.pages.currentIndex() != 0)
        self.cancel.setText("Cancel operation" if busy else "Close")
        self.status.setText(message)

    def show_import_review(self, data: dict[str, Any], preview: dict[str, Any]) -> None:
        """Show records and the actual database changes computed by the worker."""
        self.data = data
        self._drafts.clear()
        self._review_kind = "import"
        self._selected_token = ""
        self.tree.clear()
        self._row_controls.clear()
        for kind in LORE_KINDS:
            for index, record in enumerate(data.get(kind, [])):
                token = f"{kind}:{index}"
                row = QTreeWidgetItem(
                    [
                        kind,
                        record.get("name", record.get("rel_type", "")),
                        record.get("_transfer_source", "Input"),
                    ]
                )
                row.setData(0, Qt.ItemDataRole.UserRole, token)
                options = preview.get("options", {})
                state = (
                    Qt.CheckState.Unchecked
                    if token in options.get("excluded", [])
                    else Qt.CheckState.Checked
                )
                row.setCheckState(0, state)
                self.tree.addTopLevelItem(row)
                action = QComboBox()
                for label, key in (
                    ("Default", ""),
                    ("Skip", "skip"),
                    ("Merge", "update"),
                    ("Replace", "overwrite"),
                ):
                    action.addItem(label, key)
                action.setCurrentIndex(
                    max(0, action.findData(options.get("actions", {}).get(token, "")))
                )
                self.tree.setItemWidget(row, 3, action)
                match = QComboBox()
                match.addItem("Automatic", "")
                for ambiguity in preview.get("ambiguous", []):
                    if (
                        ambiguity["name"] == record.get("name")
                        and ambiguity["type"] == kind[:-1]
                    ):
                        for candidate in ambiguity["candidates"]:
                            match.addItem(
                                f"{candidate['name']} ({candidate['id'][:8]})",
                                candidate["id"],
                            )
                self.tree.setItemWidget(row, 4, match)
                chosen_match = options.get("matches", {}).get(token, "")
                if chosen_match and match.findData(chosen_match) < 0:
                    match.addItem(chosen_match, chosen_match)
                match.setCurrentIndex(max(0, match.findData(chosen_match)))
                for outcome in preview.get("actions", []):
                    if (
                        outcome.get("name") == record.get("name")
                        and outcome.get("type") == kind[:-1]
                    ):
                        row.setToolTip(1, f"{outcome['action']}: {outcome['reason']}")
                self._row_controls[token] = row, action, match
        self.tree.setVisible(True)
        self.details.setVisible(True)
        self.document_preview.setVisible(False)
        self.recheck.setVisible(True)
        self.details.setReadOnly(False)
        self.details.clear()
        counts: dict[str, int] = {}
        for change in preview.get("delta", []):
            if change["table"] in LORE_KINDS:
                key = "create" if change["before"] is None else "change"
                counts[key] = counts.get(key, 0) + 1
        diagnostics = list(preview.get("errors", [])) + list(
            preview.get("warnings", [])
        )
        self.diagnostics.setPlainText(
            "\n".join(diagnostics) or "No blocking issues found."
        )
        self.review_summary.setText(
            f"Review import: {counts.get('create', 0)} new records, "
            f"{counts.get('change', 0)} changed records.\n"
            "Uncheck to exclude, choose how matches are handled, or edit a "
            "record and recheck."
        )
        self._preview = preview
        self.pages.setCurrentIndex(1)
        self.next.setText("Import reviewed changes")
        self.next.setEnabled(not preview.get("errors") and bool(preview.get("delta")))
        self.back.setEnabled(True)
        for row, action, match in self._row_controls.values():
            action.currentIndexChanged.connect(self._invalidate)
            match.currentIndexChanged.connect(self._invalidate)

    def _invalidate(self, *_: Any) -> None:
        if self._review_kind == "import":
            self.next.setEnabled(False)

    def _select_record(
        self, current: QTreeWidgetItem | None, previous: QTreeWidgetItem | None
    ) -> None:
        if not current or self._review_kind != "import":
            return
        token = current.data(0, Qt.ItemDataRole.UserRole)
        if not token:
            return
        if self._selected_token:
            self._drafts[self._selected_token] = self.details.toPlainText()
        self._selected_token = token
        kind, index = token.split(":")
        self.details.blockSignals(True)
        self.details.setPlainText(
            self._drafts.get(
                token,
                json.dumps(self.data[kind][int(index)], indent=2, ensure_ascii=False),
            )
        )
        self.details.blockSignals(False)
        record = self.data[kind][int(index)]
        delta = [
            item
            for item in self._preview.get("delta", [])
            if item["table"] == kind
            and (item["after"] or item["before"]).get("name") == record.get("name")
        ]
        issues = self._preview.get("errors", []) + self._preview.get("warnings", [])
        detail = (
            json.dumps(delta, indent=2, ensure_ascii=False)
            if delta
            else "No stored fields change for this record."
        )
        self.diagnostics.setPlainText("\n".join(issues) + "\n" + detail)

    def _recheck(self) -> None:
        if self._selected_token:
            self._drafts[self._selected_token] = self.details.toPlainText()
        edits = dict(self._drafts)
        options: dict[str, Any] = {
            "mode": self.mode.currentData(),
            "actions": {},
            "matches": {},
            "excluded": [],
        }
        for token, (row, action, match) in self._row_controls.items():
            if row.checkState(0) != Qt.CheckState.Checked:
                options["excluded"].append(token)
            if action.currentData():
                options["actions"][token] = action.currentData()
            if match.currentData():
                options["matches"][token] = match.currentData()
        self.review_requested.emit(
            {
                **self.request(),
                "recheck": True,
                "edits": edits,
                "import_options": options,
            }
        )

    def show_export_review(
        self, summary: str, details: str, document_html: str = ""
    ) -> None:
        """Display content, limitations and destination before creating output."""
        self._review_kind = "export"
        self.review_summary.setText(summary)
        self.tree.setVisible(False)
        self.details.setVisible(False)
        self.recheck.setVisible(False)
        self.document_preview.setVisible(bool(document_html))
        self.document_preview.setHtml(document_html)
        self.diagnostics.setPlainText(details)
        self.pages.setCurrentIndex(1)
        self.next.setText(
            "Create output" if self.tabs.currentIndex() == 1 else "Transfer world"
        )
        self.next.setEnabled(True)
        self.back.setEnabled(True)

    def show_result(self, text: str, has_path: bool, is_directory: bool) -> None:
        """Keep the full report and output actions available until dismissed."""
        self.results.setPlainText(text)
        self.pages.setCurrentIndex(2)
        self.open_file.setEnabled(has_path and not is_directory)
        self.open_folder.setEnabled(has_path)
        self.next.setVisible(True)
        self.next.setText("Another transfer")
        self.next.setEnabled(True)
        self.back.setEnabled(True)

    def reject(self) -> None:
        """Cancel preparation cooperatively; committed imports cannot be interrupted."""
        if self.busy:
            self.cancel_requested.emit()
        else:
            super().reject()
