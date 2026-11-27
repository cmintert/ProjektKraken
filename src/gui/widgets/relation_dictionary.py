"""Focused world dictionary view, backed by detached review snapshots."""

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.core.relation_vocabulary import ENDPOINTS, FLAGS, OPTIONAL_TEXT, REQUIRED_TEXT
from src.gui.utils.help_context import declare_inspection
from src.gui.utils.style_helper import StyleHelper
from src.gui.utils.theme_connections import connect_theme
from src.gui.utils.theme_presentation import register_theme_scope
from src.gui.widgets.action_flow_layout import ActionFlowLayout
from src.gui.widgets.relation_preset_review import RelationPresetReview
from src.gui.widgets.responsive_form import ResponsiveFormLayout, scrollable_form_page
from src.gui.widgets.standard_buttons import PrimaryButton, StandardButton

_NARROW_DICTIONARY_WIDTH = 480


class RelationDictionaryDialog(QDialog):
    """Render a list, the current definition, and its review without persistence."""

    selected = Signal(str, str)
    draft_changed = Signal()
    review_requested = Signal()
    edit_requested = Signal()
    save_requested = Signal()
    back_requested = Signal()
    close_requested = Signal()
    export_requested = Signal()
    import_requested = Signal()

    def __init__(self, world: str, parent: QWidget) -> None:
        """Create a scrollable editor with an always reachable action row."""
        super().__init__(parent)
        self.setWindowTitle("Relation Dictionary")
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.resize(620, 640)
        layout = QVBoxLayout(self)
        StyleHelper.apply_standard_list_spacing(layout)
        layout.addWidget(self._text(f"This World — {world}"))
        self.pages = QStackedWidget()
        layout.addWidget(self.pages, 1)
        self.message = self._text()
        self.message.hide()
        layout.addWidget(self.message)
        self._build_list()
        self._build_editor()
        self._build_review()
        self.preset_review = RelationPresetReview()
        self.pages.addWidget(self.preset_review)
        connect_theme(self, self._apply_theme)
        register_theme_scope(self, priority=True)
        self._apply_theme()

    @staticmethod
    def _text(text: str = "") -> QLabel:
        label = QLabel(text)
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setWordWrap(True)
        return label

    def _build_list(self) -> None:
        self.list_page = QWidget()
        layout = QVBoxLayout(self.list_page)
        self.entries = declare_inspection(
            QListWidget(),
            "settings.dictionary.list|settings.relation-dictionary|help-inspect-relation-dictionary-list",
        )
        self.entries.setAccessibleName("Relation definitions and Kraken defaults")
        self.entries.setWordWrap(True)
        self.entries.setTextElideMode(Qt.TextElideMode.ElideNone)
        layout.addWidget(self.entries, 1)
        actions = ActionFlowLayout()
        self.open_button = PrimaryButton("Open definition")
        self.add_button = StandardButton("Add definition")
        self.export_preset = declare_inspection(
            StandardButton("Export preset…"),
            "settings.dictionary.export-preset|settings.relation-dictionary|help-inspect-relation-preset-export",
        )
        self.import_preset = declare_inspection(
            StandardButton("Import preset…"),
            "settings.dictionary.import-preset|settings.relation-dictionary|help-inspect-relation-preset-import",
        )
        close = StandardButton("Close")
        for button in (
            self.open_button,
            self.add_button,
            self.export_preset,
            self.import_preset,
            close,
        ):
            button.setAutoDefault(False)
            actions.addWidget(button)
        layout.addLayout(actions)
        close.clicked.connect(self.close_requested.emit)
        self.open_button.clicked.connect(self._open_selected)
        self.entries.itemActivated.connect(self._open_selected)
        self.add_button.clicked.connect(lambda: self.selected.emit("new", ""))
        self.export_preset.clicked.connect(self.export_requested.emit)
        self.import_preset.clicked.connect(self.import_requested.emit)
        self.pages.addWidget(self.list_page)

    def _build_editor(self) -> None:
        self.edit_page = QWidget()
        layout = QVBoxLayout(self.edit_page)
        self.form = QWidget()
        form_layout = self.form_layout = ResponsiveFormLayout(self.form)
        self.fields: dict[str, QLineEdit] = {}
        for key, label in (
            ("key", "Stable key"),
            ("forward_label", "Forward label"),
            ("reverse_label", "Reverse label"),
            ("description", "Description"),
            ("category", "Category (optional)"),
        ):
            self._add_field(form_layout, key, label)
        self.kinds: dict[str, QComboBox] = {}
        for key, label in zip(
            ENDPOINTS, ("Preferred source", "Preferred target"), strict=True
        ):
            field = declare_inspection(
                QComboBox(),
                "settings.dictionary.endpoints|settings.relation-dictionary|help-inspect-relation-dictionary-endpoints",
            )
            field.setAccessibleName(label)
            for caption, value in (
                ("Any kind", ""),
                ("Entity", "entity"),
                ("Event", "event"),
            ):
                field.addItem(caption, value)
            field.currentIndexChanged.connect(lambda _index: self.draft_changed.emit())
            form_layout.addRow(label, field)
            self.kinds[key] = field
        self.flags: dict[str, QCheckBox] = {}
        for key, label in zip(
            FLAGS, ("Definition enabled", "Symmetric meaning"), strict=True
        ):
            checkbox = declare_inspection(
                QCheckBox(label),
                "settings.dictionary.flags|settings.relation-dictionary|help-inspect-relation-dictionary-flags",
            )
            checkbox.toggled.connect(lambda _checked: self.draft_changed.emit())
            form_layout.addRow(checkbox)
            self.flags[key] = checkbox
        self.advanced = StandardButton("Advanced")
        self.advanced.setCheckable(True)
        self.advanced.setAutoDefault(False)
        form_layout.addRow(self.advanced)
        advanced = QWidget()
        advanced_form = self.advanced_layout = ResponsiveFormLayout(advanced)
        advanced_form.addRow(self._text("Templates may use {source} and {target}."))
        self._add_field(
            advanced_form, "forward_template", "Forward sentence (optional)"
        )
        self._add_field(
            advanced_form, "reverse_template", "Reverse sentence (optional)"
        )
        self.migration = StandardButton("Migrate identifier…")
        self.migration.setEnabled(False)
        advanced_form.addRow(self.migration)
        self.migration_note = self._text()
        advanced_form.addRow(self.migration_note)
        advanced.hide()
        self.advanced.toggled.connect(advanced.setVisible)
        form_layout.addRow(advanced)
        self.preview = self._text()
        self.preview.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        form_layout.addRow(self.preview)
        self.form_scroll = scrollable_form_page(self.form)
        layout.addWidget(self.form_scroll, 1)
        actions = ActionFlowLayout()
        self.back = StandardButton("Back")
        self.review = declare_inspection(
            PrimaryButton("Review impact"),
            "settings.dictionary.review|settings.relation-dictionary|help-inspect-relation-dictionary-review",
        )
        for button in (self.back, self.review):
            button.setAutoDefault(False)
            actions.addWidget(button)
        layout.addLayout(actions)
        self.back.clicked.connect(self.back_requested.emit)
        self.review.clicked.connect(self.review_requested.emit)
        self.pages.addWidget(self.edit_page)

    def _build_review(self) -> None:
        self.review_page = QWidget()
        layout = QVBoxLayout(self.review_page)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        self.review_text = self._text()
        self.review_text.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        content_layout.addWidget(self.review_text)
        content_layout.addStretch()
        self.review_scroll = scrollable_form_page(content)
        layout.addWidget(self.review_scroll, 1)
        actions = ActionFlowLayout()
        self.edit = StandardButton("Edit definition")
        self.save = declare_inspection(
            PrimaryButton("Save definition"),
            "settings.dictionary.save|settings.relation-dictionary|help-inspect-relation-dictionary-save",
        )
        for button in (self.edit, self.save):
            button.setAutoDefault(False)
            actions.addWidget(button)
        layout.addLayout(actions)
        self.edit.clicked.connect(self.edit_requested.emit)
        self.save.clicked.connect(self.save_requested.emit)
        self.pages.addWidget(self.review_page)

    def _add_field(self, form: ResponsiveFormLayout, key: str, label: str) -> None:
        field = declare_inspection(
            QLineEdit(),
            "settings.dictionary.wording|settings.relation-dictionary|help-inspect-relation-dictionary-wording",
        )
        field.setAccessibleName(label)
        field.textEdited.connect(lambda _text: self.draft_changed.emit())
        self.fields[key] = field
        caption = self._text(label)
        caption.setBuddy(field)
        form.addRow(caption, field)

    def _open_selected(self) -> None:
        item = self.entries.currentItem()
        if item is not None:
            source, key = item.data(Qt.ItemDataRole.UserRole)
            self.selected.emit(source, key)

    def show_entries(
        self,
        rows: list[tuple[str, str, str]],
        writable: bool,
        selected_key: str,
        *,
        exportable: bool = False,
    ) -> None:
        """List world entries and explicitly labelled catalog suggestions."""
        self.entries.clear()
        for source, key, caption in rows:
            item = QListWidgetItem(caption)
            item.setData(Qt.ItemDataRole.UserRole, (source, key))
            self.entries.addItem(item)
            if key == selected_key and self.entries.currentItem() is None:
                self.entries.setCurrentItem(item)
        if self.entries.currentItem() is None and rows:
            self.entries.setCurrentRow(0)
        self.open_button.setEnabled(bool(rows))
        self.add_button.setEnabled(writable)
        self.import_preset.setEnabled(writable)
        self.export_preset.setEnabled(exportable)
        self.pages.setCurrentWidget(self.list_page)
        self.entries.setFocus()

    def show_definition(
        self, definition: dict[str, Any], locked: bool, writable: bool
    ) -> None:
        """Hydrate one draft and expose its immutable identity where applicable."""
        for key, field in self.fields.items():
            field.setText(str(definition.get(key, "")))
            field.setReadOnly(not writable or (key == "key" and locked))
        for key, combo in self.kinds.items():
            combo.setCurrentIndex(max(0, combo.findData(definition.get(key, ""))))
            combo.setEnabled(writable)
        for key, checkbox in self.flags.items():
            checkbox.setChecked(definition.get(key, key == "enabled") is True)
            checkbox.setEnabled(writable)
        self.migration_note.setText(
            "Identifier migration is unavailable in this version."
            if locked
            else "The key becomes read-only after saving."
        )
        self.migration.setVisible(locked)
        self.advanced.setChecked(False)
        self.pages.setCurrentWidget(self.edit_page)
        self.form_scroll.verticalScrollBar().setValue(0)
        self.fields["forward_label" if locked else "key"].setFocus()

    def definition(self) -> dict[str, Any]:
        """Collect the current definition without altering an existing key."""
        key = self.fields["key"]
        result: dict[str, Any] = {
            "key": key.text() if key.isReadOnly() else key.text().strip(),
            **{name: self.fields[name].text().strip() for name in REQUIRED_TEXT},
        }
        result.update(
            (name, self.fields[name].text())
            for name in OPTIONAL_TEXT
            if self.fields[name].text().strip()
        )
        result.update(
            (name, field.currentData())
            for name, field in self.kinds.items()
            if field.currentData()
        )
        result.update((name, field.isChecked()) for name, field in self.flags.items())
        return result

    def show_message(self, message: str = "", *, error: bool = False) -> None:
        """Show feedback in text as well as semantic color."""
        self.message.setProperty("dictionary_error", error)
        self.message.setText(message)
        self.message.setVisible(bool(message))
        self._style_message()

    def show_review(self, text: str) -> None:
        """Present the scope of the change on a dedicated review page."""
        self.review_text.setText(text)
        self.pages.setCurrentWidget(self.review_page)
        self.review_scroll.verticalScrollBar().setValue(0)
        self.save.setFocus()

    def return_to_edit(self) -> None:
        """Return to the unchanged form for revisions or another review."""
        self.pages.setCurrentWidget(self.edit_page)
        self.review.setFocus()

    def _style_message(self) -> None:
        self.message.setStyleSheet(
            StyleHelper.get_error_label_style()
            if self.message.property("dictionary_error")
            else ""
        )

    def _apply_theme(self) -> None:
        self.setStyleSheet(StyleHelper.get_dialog_base_style())
        self._style_message()

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        """Stack labels above fields where the combined row would overflow."""
        policy = (
            QFormLayout.RowWrapPolicy.WrapAllRows
            if event.size().width() < _NARROW_DICTIONARY_WIDTH
            else QFormLayout.RowWrapPolicy.WrapLongRows
        )
        self.form_layout.setRowWrapPolicy(policy)
        self.advanced_layout.setRowWrapPolicy(policy)
        super().resizeEvent(event)

    def reject(self) -> None:
        """Route Escape and window closing through the draft guard."""
        self.close_requested.emit()
