"""Compact presentation of one checked-selection metadata operation."""

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from src.gui.dialogs.help_aware_dialog import HelpAwareDialog
from src.gui.utils.help_context import declare_inspection
from src.gui.utils.style_helper import StyleHelper
from src.gui.widgets.action_flow_layout import ActionFlowLayout
from src.gui.widgets.choice_inputs import ScrollSafeComboBox
from src.gui.widgets.responsive_form import scrollable_form_page
from src.gui.widgets.standard_buttons import PrimaryButton, StandardButton
from src.gui.widgets.tag_editor import TagEditorWidget
from src.gui.widgets.wrapping_combo_box import WrappingComboBox


class BatchMetadataDialog(HelpAwareDialog):
    """Render intent and preview counts; emit requests without database access."""

    preview_requested = Signal(dict)
    apply_requested = Signal()
    intent_changed = Signal()

    def __init__(self, count: int, tags: list[str], parent: Any = None) -> None:
        """Build a single-operation form with explicit preview and Apply."""
        super().__init__(parent)
        self.setWindowTitle("Batch Edit")
        self.setModal(True)
        self._ready = False
        self._busy = False
        self._applying = False
        outer = QVBoxLayout(self)
        StyleHelper.apply_panel_spacing(outer)
        page = QWidget()
        layout = QVBoxLayout(page)
        StyleHelper.apply_panel_spacing(layout)
        outer.addWidget(scrollable_form_page(page))
        context = QLabel(
            f"{count} checked objects. Edits apply to saved metadata.\n"
            "Entity attributes change the baseline; dated overrides stay in place."
        )
        context.setWordWrap(True)
        layout.addWidget(context)
        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self.action = declare_inspection(
            WrappingComboBox(),
            "batch-metadata-operation|explorer.batch-edit|help-batch-metadata-operation",
        )
        for label, action in (
            ("Add tags", "add_tags"),
            ("Remove tags", "remove_tags"),
            ("Set attribute", "set"),
            ("Set attribute only if missing", "set_missing"),
            ("Remove attribute", "remove"),
        ):
            self.action.addItem(label, action)
        form.addRow("Operation", self.action)
        self.tags = TagEditorWidget()
        self.tags.update_suggestions(tags)
        form.addRow("Tags", self.tags)
        self.key = declare_inspection(
            QLineEdit(),
            "batch-metadata-key|explorer.batch-edit|help-batch-metadata-key",
        )
        self.key.setPlaceholderText("Custom attribute name")
        form.addRow("Attribute", self.key)
        self.value_type = declare_inspection(
            ScrollSafeComboBox(),
            "batch-metadata-type|explorer.batch-edit|help-batch-metadata-type",
        )
        self.value_type.addItems(["String", "Number", "Boolean"])
        form.addRow("Type", self.value_type)
        self.value = declare_inspection(
            QLineEdit(),
            "batch-metadata-value|explorer.batch-edit|help-batch-metadata-value",
        )
        form.addRow("Value", self.value)
        self.boolean = declare_inspection(
            QCheckBox("True"),
            "batch-metadata-boolean|explorer.batch-edit|help-batch-metadata-boolean",
        )
        form.addRow("Boolean value", self.boolean)
        self.form = form
        layout.addLayout(form)
        self.status = QLabel("Choose an operation, then preview its changes.")
        self.status.setWordWrap(True)
        self.status.setAccessibleName("Batch preview and status")
        layout.addWidget(self.status)
        buttons = ActionFlowLayout()
        self.preview_button = declare_inspection(
            StandardButton("Preview"),
            "batch-metadata-preview|explorer.batch-edit|help-batch-metadata-preview",
        )
        self.apply_button = declare_inspection(
            PrimaryButton("Apply"),
            "batch-metadata-apply|explorer.batch-edit|help-batch-metadata-apply",
        )
        self.cancel_button = declare_inspection(
            StandardButton("Cancel"),
            "batch-metadata-cancel|explorer.batch-edit|help-batch-metadata-cancel",
        )
        for button in (self.preview_button, self.apply_button, self.cancel_button):
            button.setAutoDefault(False)
            buttons.addWidget(button)
        outer.addLayout(buttons)
        self.preview_button.clicked.connect(self._preview)
        self.apply_button.clicked.connect(self.apply_requested.emit)
        self.cancel_button.clicked.connect(self.reject)
        self.action.currentIndexChanged.connect(self._changed)
        self.value_type.currentIndexChanged.connect(self._changed)
        self.key.textChanged.connect(self._changed)
        self.value.textChanged.connect(self._changed)
        self.boolean.toggled.connect(self._changed)
        self.tags.tags_changed.connect(self._changed)
        self.tags.tag_input.textChanged.connect(self._changed)
        self._changed()

    def _changed(self, *_args: Any) -> None:
        self._ready = False
        self.apply_button.setEnabled(False)
        action = self.action.currentData()
        tag_action = action in ("add_tags", "remove_tags")
        setting = action in ("set", "set_missing")
        self.form.setRowVisible(self.tags, tag_action)
        self.form.setRowVisible(self.key, not tag_action)
        self.form.setRowVisible(self.value_type, setting)
        self.form.setRowVisible(
            self.value, setting and self.value_type.currentText() != "Boolean"
        )
        self.form.setRowVisible(
            self.boolean, setting and self.value_type.currentText() == "Boolean"
        )
        self.status.setText("Preview required before applying.")
        self.intent_changed.emit()

    def operation(self) -> dict:
        """Return form intent, retaining a pending tag typed before Preview."""
        value: Any = self.value.text()
        if self.action.currentData() in ("set", "set_missing"):
            if self.value_type.currentText() == "Number":
                try:
                    value = float(value)
                except ValueError as exc:
                    raise ValueError("Enter a valid number.") from exc
            elif self.value_type.currentText() == "Boolean":
                value = self.boolean.isChecked()
        tags = self.tags.get_tags()
        if pending := self.tags.tag_input.text().strip():
            tags.append(pending)
        return {
            "action": self.action.currentData(),
            "key": self.key.text(),
            "value_type": self.value_type.currentText(),
            "value": value,
            "tags": tags,
        }

    def _preview(self) -> None:
        try:
            self.preview_requested.emit(self.operation())
        except ValueError as exc:
            self.show_error(str(exc))

    def set_busy(
        self, busy: bool, message: str = "", *, applying: bool = False
    ) -> None:
        """Prevent input races and duplicate submission during an async request."""
        self._busy = busy
        self._applying = busy and applying
        for widget in (
            self.action,
            self.tags,
            self.key,
            self.value_type,
            self.value,
            self.boolean,
            self.preview_button,
        ):
            widget.setEnabled(not busy)
        self.cancel_button.setEnabled(not self._applying)
        self.apply_button.setEnabled(not busy and self._ready)
        if message:
            self.status.setText(message)

    def show_preview(self, preview: dict) -> None:
        """Present object counts with overwrite as a subset of changes."""
        self._ready = preview["changed"] > 0
        self.set_busy(False)
        self.status.setText(
            f"Changed: {preview['changed']} · Unchanged: {preview['unchanged']}\n"
            f"Existing values overwritten: {preview['overwritten']} "
            "(included in changed)."
        )

    def show_error(self, message: str) -> None:
        """Retain input and require a new preview after failure."""
        self._ready = False
        self.set_busy(False)
        self.status.setText(message)

    def reject(self) -> None:
        """Allow cancellation except while a mutation is awaiting acknowledgement."""
        if not self._applying:
            super().reject()
