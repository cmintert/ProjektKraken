"""Shared inline capture and progressive refinement in lore inspectors."""

from copy import deepcopy
from typing import Any, cast
from uuid import uuid4

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QApplication,
    QFormLayout,
    QLabel,
    QMessageBox,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from src.core.theme_manager import ThemeManager
from src.gui.utils.style_helper import StyleHelper
from src.gui.widgets.choice_inputs import ScrollSafeComboBox
from src.gui.widgets.editor_presentation import DisclosureButton
from src.gui.widgets.overflow_toolbar import OverflowToolBar
from src.gui.widgets.relation_drop_target import RelationDropTarget
from src.gui.widgets.relation_form import RelationForm, take_form_row
from src.gui.widgets.relation_target import RelationTargetEdit
from src.gui.widgets.standard_buttons import StandardButton

MEANINGS = {
    "related": "Connected — kind not specified",
    "member_of": "Member of",
    "involved": "Participant in",
    "located_at": "Located at",
    "owns": "Owns",
    "parent_of": "Parent of",
    "caused": "Caused",
}


class RelationAuthoring(QWidget):
    """Own only local relation drafts; emit serializable mutation intent."""

    def __init__(self, editor: Any) -> None:
        """Install shared controls without replacing either inspector's lists."""
        super().__init__(editor.tab_relations)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self.editor = editor
        editor.tab_relations.setObjectName("ConnectionsInspector")
        editor.tab_relations.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._apply_theme()
        ThemeManager().theme_changed.connect(self._apply_theme)
        self.form: RelationForm | None = None
        self.target: RelationTargetEdit | None = None
        self.relation: dict[str, Any] | None = None
        self.source_id = ""
        self.source_name = ""
        self.capture_type = "related"
        self.pending_id = ""
        self.preferred_id = ""
        self.reversed = False
        self.capture_open = False
        self._drop_capture: dict[str, str] | None = None
        self._layout = QVBoxLayout(self)
        StyleHelper.apply_no_margins(self._layout)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self._layout.addWidget(self.status)
        self.drop_target = RelationDropTarget(self)
        self._layout.addWidget(self.drop_target)
        self.body = QWidget()
        self.body_layout = QVBoxLayout(self.body)
        StyleHelper.apply_no_margins(self.body_layout)
        self.body_scroll = QScrollArea()
        self.body_scroll.setWidgetResizable(True)
        self.body_scroll.setMaximumHeight(500)
        self.body_scroll.setStyleSheet(
            StyleHelper.get_scroll_area_style() + StyleHelper.get_scrollbar_style()
        )
        self.body_scroll.setWidget(self.body)
        self.body.setAutoFillBackground(False)
        self.body_scroll.viewport().setAutoFillBackground(False)
        self._layout.addWidget(self.body_scroll)
        self.body_scroll.hide()
        self.footer = QWidget()
        self.footer.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.footer_layout = QVBoxLayout(self.footer)
        StyleHelper.apply_no_margins(self.footer_layout)
        self._layout.addWidget(self.footer)
        self.footer.hide()
        menu_button = QToolButton()
        menu_button.setText("More actions")
        menu_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        from PySide6.QtWidgets import QMenu

        menu = QMenu(menu_button)
        menu.addAction("Add detailed relation…", self._add_full)
        menu.addAction("Full relation editor…", self._edit_full)
        menu_button.setMenu(menu)
        menu_button.setStyleSheet(StyleHelper.get_tool_button_style())
        self._layout.addWidget(menu_button)
        self.status.setText("Choose Connected to… to record a connection.")

    def _apply_theme(self, *_args: Any) -> None:
        self.editor.tab_relations.setStyleSheet(
            StyleHelper.get_connection_inspector_style()
        )
        if hasattr(self, "drop_target"):
            self.drop_target.apply_theme()

    def _current_id(self) -> str:
        return str(
            getattr(self.editor, "_current_entity_id", None)
            or getattr(self.editor, "_current_event_id", None)
            or ""
        )

    def _clear_body(self) -> None:
        if self.form is not None:
            self.form.deleteLater()
        while self.body_layout.count():
            item = self.body_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()
        self.form = None
        self.target = None
        self.relation = None
        self.capture_open = False
        self._drop_capture = None
        self.reversed = False
        while self.footer_layout.count():
            item = self.footer_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()

    def capture(self, rel_type: str = "related") -> None:
        """Start one-choice capture without assigning timing or metadata."""
        if (
            not self.isEnabled()
            or not self._current_id()
            or not self.prepare_to_leave()
        ):
            return
        self._clear_body()
        self.source_id = self._current_id()
        self.source_name = self.editor.name_edit.text()
        self.capture_type = rel_type
        self.capture_open = True
        self.target = RelationTargetEdit(getattr(self.editor, "_suggestion_items", []))
        self.body_layout.addWidget(
            QLabel(
                "Add participant"
                if rel_type == "involved"
                else "Add location"
                if rel_type == "located_at"
                else "Connected to…"
            )
        )
        self.body_layout.addWidget(self.target)
        self.body_layout.addStretch()
        self._actions("Connect")
        self.status.setText(
            "Choose an existing object. You can refine the connection later."
        )
        self.body_scroll.setMinimumHeight(100)
        self.body_scroll.setMaximumHeight(100)
        self.body_scroll.show()
        self.target.setFocus()
        self.target.returnPressed.connect(self._capture_enter)
        self.target.installEventFilter(self)

    def _capture_enter(self) -> None:
        if self.target is not None:
            completer = self.target.completer()
            popup = completer.popup() if completer is not None else None
            if popup is not None and popup.isVisible():
                return
        self.apply()

    def resolve_drop(self, item_id: str, kind: str) -> dict[str, str] | None:
        """Resolve a drop against current serializable suggestions and editability."""
        if not self.isEnabled() or not self._current_id() or self.pending_id:
            return None
        if item_id == self._current_id():
            self.status.setText(
                "An entry cannot be dropped onto its own Connections target."
            )
            return None
        for known_id, name, known_kind in getattr(self.editor, "_suggestion_items", []):
            if known_id == item_id and known_kind.casefold() == kind:
                return {"id": item_id, "name": name, "type": kind}
        self.status.setText(
            "Choose an existing Entity or Event to prepare a connection."
        )
        return None

    def stage_drop(self, payload: dict[str, str]) -> bool:
        """Prepare a directed connection without replacing an unfinished draft."""
        resolved = self.resolve_drop(payload["id"], payload["type"])
        if resolved is None or not self.prepare_to_leave():
            return False
        self.capture()
        if self.target is None:
            return False
        target_id = self._current_id()
        self.source_id = resolved["id"]
        self.source_name = resolved["name"]
        self.target.initial_id = target_id
        self.target.setText(target_id)
        self.target.hide()
        capture_label = self.body_layout.itemAt(0).widget()
        if capture_label is not None:
            capture_label.hide()
        self._drop_capture = {**resolved, "target_id": target_id}
        preview = QLabel(
            f"{self.source_name} → {self.editor.name_edit.text()}: "
            "connection — kind not specified"
        )
        preview.setWordWrap(True)
        self.body_layout.insertWidget(0, preview)
        meaning = ScrollSafeComboBox()
        for value, title in MEANINGS.items():
            meaning.addItem(title, value)
        self.body_layout.insertWidget(1, meaning)
        meaning.currentIndexChanged.connect(
            lambda: self._set_drop_meaning(str(meaning.currentData()), preview)
        )
        self.body_scroll.setMinimumHeight(150)
        self.body_scroll.setMaximumHeight(200)
        self.status.setText(
            "Connection prepared. Connect saves it; Cancel discards it."
        )
        self.apply_button.setFocus()
        return True

    def _set_drop_meaning(self, kind: str, preview: QLabel) -> None:
        self.capture_type = kind
        preview.setText(
            f"{self.source_name} → {self.editor.name_edit.text()}: {MEANINGS[kind]}"
        )

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Own only the draft action keys after nested controls handled them."""
        if event.key() == Qt.Key.Key_Escape:
            self.cancel()
            event.accept()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and (
            QApplication.focusWidget() is getattr(self, "apply_button", None)
        ):
            self.apply()
            event.accept()
        else:
            super().keyPressEvent(event)

    def refine(self, relation: dict[str, Any]) -> None:
        """Open the existing row with advanced data retained in its snapshot."""
        if (
            not self.isEnabled()
            or relation.get("rel_type") == "mentions"
            or not self.prepare_to_leave()
        ):
            return
        self._clear_body()
        self.relation = deepcopy(relation)
        self.source_id = relation.get("source_id", self._current_id())
        self.relation["source_id"] = self.source_id
        self.source_name = relation.get("source_name") or self.editor.name_edit.text()
        is_source = self.source_id == self._current_id()
        is_event = bool(getattr(self.editor, "_current_event_id", None)) and is_source
        source_date = (
            self.editor.temporal_widget.get_start()
            if is_event
            else relation.get("source_event_date")
        )
        self.form = RelationForm(
            self.body,
            target_id=relation["target_id"],
            rel_type=relation["rel_type"],
            attributes=relation.get("attributes", {}),
            suggestion_items=getattr(self.editor, "_suggestion_items", []),
            known_types=getattr(self.editor, "_suggestion_types", []),
            source_name=self.source_name,
            source_event_date=source_date,
            source_event_name=self.source_name if source_date is not None else None,
            target_kind=relation.get("target_kind"),
            calendar_converter=getattr(self.editor, "_relation_calendar", None)
            or getattr(self.editor, "_calendar_converter", None),
            playhead_time=getattr(self.editor, "_relation_playhead_time", None),
        )
        self._progressive_form()
        self._actions("Apply")
        self.body_scroll.setMinimumHeight(380)
        self.body_scroll.setMaximumHeight(500)
        self.body_scroll.show()
        self.status.setText(
            "Refine this connection. Apply changes the same saved relation."
        )
        self._preview()

    @staticmethod
    def _take_widget(layout: QFormLayout, widget: QWidget) -> None:
        # PySide's stub returns object; runtime returns (row, ItemRole).
        index, _role = cast(tuple[int, Any], layout.getWidgetPosition(widget))
        label, _field = take_form_row(layout, index)
        label_widget = label.widget() if label is not None else None
        if label_widget is not None:
            label_widget.hide()

    def _progressive_form(self) -> None:
        """Rehouse the shared controls with ordinary fields before disclosures."""
        assert self.form is not None and self.relation is not None
        form = self.form
        # Move the reusable form's content out of its dialog-sized scroll wrapper.
        content = form.form_scroll_area.takeWidget()
        assert content is not None
        content.setAutoFillBackground(False)
        self.body_layout.addWidget(content)
        content.show()
        form.hide()
        fields = form.form_layout
        fields.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        fields.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self._take_widget(fields, form.target_edit)
        form.target_edit.hide()
        self._take_widget(fields, form.type_edit)
        self._take_widget(fields, form.preview_label)
        self._take_widget(fields, form.bi_check)
        form.bi_check.hide()
        attributes = form.attributes_group.layout()
        assert isinstance(attributes, QFormLayout)
        self._take_widget(attributes, form.notes_edit)
        form.notes_edit.show()

        advanced = QWidget()
        advanced_layout = QVBoxLayout(advanced)
        StyleHelper.apply_no_margins(advanced_layout)
        # All remaining non-timing form rows are advanced configuration.
        timing = form.temporal_group
        self._take_widget(fields, timing)
        while fields.rowCount():
            label, field = take_form_row(fields, 0)
            widget = field.widget() if field is not None else None
            row_layout = field.layout() if field is not None else None
            if widget is not None:
                advanced_layout.addWidget(widget)
            elif row_layout is not None:
                advanced_layout.addLayout(row_layout)
            label_widget = label.widget() if label is not None else None
            if label_widget is not None:
                label_widget.hide()
        advanced_layout.insertWidget(0, form.type_edit)
        advanced_layout.insertWidget(0, QLabel("Custom type (stored name)"))
        advanced_layout.addWidget(
            QLabel(
                "Confidence is your certainty in the connection; weight describes its strength."
            )
        )

        self.meaning = ScrollSafeComboBox()
        for value, title in MEANINGS.items():
            self.meaning.addItem(title, value)
        if self.meaning.findData(self.relation["rel_type"]) < 0:
            self.meaning.addItem(self.relation["rel_type"], self.relation["rel_type"])
        self.meaning.addItem("Custom type…", None)
        self.meaning.setCurrentIndex(self.meaning.findData(self.relation["rel_type"]))
        self.meaning.currentIndexChanged.connect(self._meaning_changed)
        fields.addRow("Meaning", self.meaning)
        fields.addRow(form.preview_label)
        form.preview_label.show()
        self.reverse_button = StandardButton("Reverse direction")
        self.reverse_button.clicked.connect(self._reverse)
        fields.addRow(self.reverse_button)
        fields.addRow("Notes", form.notes_edit)

        timing_fields = timing.layout()
        assert isinstance(timing_fields, QFormLayout)
        self._take_widget(timing_fields, form.temporal_behavior)
        advanced_layout.addWidget(QLabel("Timing meaning"))
        advanced_layout.addWidget(form.temporal_behavior)
        # Convert legacy radio presets to the same per-boundary choices without
        # dirtying the snapshot or requiring a second temporal editing model.
        if hasattr(form, "rb_absolute") and not form.rb_absolute.isChecked():
            for side, bound in (
                ("start", form.rb_starts.isChecked() or form.rb_at_event.isChecked()),
                ("end", form.rb_ends.isChecked() or form.rb_at_event.isChecked()),
            ):
                choice = form._boundary_choices[side]
                choice.setCurrentIndex(
                    choice.findData("source_event" if bound else "open")
                )
            form.rb_absolute.setChecked(True)
        form._changed_fields.clear()
        if hasattr(form, "logic_group"):
            form.logic_group.hide()
        self.timing_disclosure = DisclosureButton("Timing…")
        summary = "Timing: not specified"
        attrs = self.relation.get("attributes", {})
        if any(
            key in attrs
            for key in (
                "temporal",
                "valid_from",
                "valid_to",
                "valid_from_event",
                "valid_to_event",
            )
        ):
            summary = "Timing is recorded — expand to inspect dates and event links."
        caption = QLabel(summary)
        caption.setWordWrap(True)
        self.timing_caption = caption
        form.changed.connect(self._timing_changed)
        fields.addRow(caption)
        self.timing_disclosure.toggled.connect(timing.setVisible)
        fields.addRow(self.timing_disclosure)
        fields.addRow(timing)
        timing.hide()
        has_advanced = any(key in attrs for key in ("payload", "confidence", "weight"))
        self.advanced_disclosure = DisclosureButton(
            "Advanced details… (recorded)" if has_advanced else "Advanced details…"
        )
        self.advanced_disclosure.toggled.connect(advanced.setVisible)
        fields.addRow(self.advanced_disclosure)
        fields.addRow(advanced)
        advanced.hide()
        form.type_edit.currentTextChanged.connect(self._preview)
        form.installEventFilter(self)
        content.installEventFilter(self)

    def _timing_changed(self) -> None:
        if self.form is not None and self.form._changed_fields.intersection(
            {"start", "end", "timing"}
        ):
            self.timing_caption.setText("Timing changed — Apply to record these dates.")

    def _meaning_changed(self) -> None:
        assert self.form is not None
        value = self.meaning.currentData()
        if value is None:
            self.advanced_disclosure.setChecked(True)
            self.form.type_edit.setFocus()
        else:
            self.form.type_edit.setCurrentText(str(value))
        self._preview()

    def _preview(self, *args: Any) -> None:
        if self.form is None or self.relation is None:
            return
        target_name = self.relation.get("target_name") or self.form.target_edit.text()
        source_name = self.source_name
        if self.reversed:
            source_name, target_name = target_name, source_name
        kind = self.form.type_edit.currentText()
        if kind == "related":
            sentence = (
                f"{source_name} is connected to {target_name}; kind not specified."
            )
        elif kind == "involved":
            sentence = (
                f"{target_name} participates in {source_name}."
                if self.form.source_event_date is not None and not self.reversed
                else f"{source_name} participates in {target_name}."
            )
        else:
            sentence = f"{source_name} → {target_name}: {MEANINGS.get(kind, kind)}"
        self.form.preview_label.setText(sentence)

    def _reverse(self) -> None:
        assert self.form is not None and self.relation is not None
        attrs = self.form.get_data()[3]
        if (
            attrs.get("payload")
            or any(
                attrs.get(key)
                for key in ("valid_from_event", "valid_to_event", "valid_at_event")
            )
            or ("source_event" in str(attrs.get("temporal", {})))
        ):
            self.status.setText(
                "This relation uses its source event for timing or state changes. "
                "Refine those details before reversing its direction."
            )
            return
        self.reversed = not self.reversed
        self.reverse_button.setText(
            "Restore direction" if self.reversed else "Reverse direction"
        )
        self._preview()

    def _actions(self, title: str) -> None:
        actions = OverflowToolBar()
        self.apply_button = StandardButton(title)
        self.apply_button.clicked.connect(self.apply)
        actions.add_button(self.apply_button, priority=10)
        cancel = StandardButton("Cancel")
        cancel.clicked.connect(self.cancel)
        actions.add_button(cancel)
        self.footer_layout.addWidget(actions)
        self.footer.show()

    def is_dirty(self) -> bool:
        """Return whether this local operation contains uncommitted input."""
        return bool(
            self.pending_id
            or self.reversed
            or (self.target is not None and self.target.text().strip())
            or (self.form is not None and self.form._changed_fields)
        )

    def prepare_to_leave(self) -> bool:
        """Resolve only the local relation draft, independently of prose edits."""
        if self.pending_id:
            self.status.setText(
                "Saving this connection. Keep editing after it finishes."
            )
            return False
        if not self.is_dirty():
            return True
        box = QMessageBox(self)
        box.setWindowTitle("Unfinished connection")
        box.setText("Apply this connection edit before leaving it?")
        apply = box.addButton("Apply", QMessageBox.ButtonRole.AcceptRole)
        keep = box.addButton("Keep editing", QMessageBox.ButtonRole.RejectRole)
        discard = box.addButton("Discard", QMessageBox.ButtonRole.DestructiveRole)
        box.setDefaultButton(keep)
        box.exec()
        if box.clickedButton() is apply:
            self.apply()
            return False
        if box.clickedButton() is discard:
            self.cancel()
            return True
        return False

    def cancel(self) -> None:
        """Discard the local relation draft without altering inspector fields."""
        if self.pending_id:
            return
        self._clear_body()
        self.body_scroll.hide()
        self.footer.hide()
        self.status.setText("Connection edit cancelled.")

    def apply(self) -> None:
        """Validate local fields and emit one capture or refinement request."""
        if self.pending_id or not self.isEnabled() or not self.apply_button.isEnabled():
            return
        if self._drop_capture is not None and (
            self._current_id() != self._drop_capture["target_id"]
            or self.resolve_drop(self.source_id, self._drop_capture["type"]) is None
        ):
            self.status.setText(
                "This connection's target changed. Cancel and prepare it again."
            )
            return
        request: dict[str, Any] = {"source_id": self.source_id}
        if self.target is not None:
            target = self.target.resolve()
            if not target:
                self.status.setText("Choose an existing object from the suggestions.")
                return
            request.update(
                operation="capture",
                target_id=target,
                rel_type=self.capture_type,
                attributes={},
            )
        elif self.form is not None and self.relation is not None:
            if not self.form.validate():
                return
            target, kind, _, attrs = self.form.get_data()
            if self.reversed and (
                attrs.get("payload")
                or any(
                    attrs.get(key)
                    for key in ("valid_from_event", "valid_to_event", "valid_at_event")
                )
                or "source_event" in str(attrs.get("temporal", {}))
            ):
                self.status.setText(
                    "Keep the source direction for source-event timing or state changes."
                )
                return
            if not kind:
                self.status.setText("Choose a meaning or enter a custom type.")
                return
            request.update(
                operation="refine",
                id=self.relation["id"],
                target_id=target,
                rel_type=kind,
                attributes=attrs,
                expected=deepcopy(self.relation),
            )
            if self.reversed:
                request["source_id"], request["target_id"] = target, self.source_id
        else:
            return
        self.pending_id = str(uuid4())
        request["request_id"] = self.pending_id
        self.body.setEnabled(False)
        self.apply_button.setEnabled(False)
        self.status.setText("Saving connection…")
        self.editor.relation_authoring_requested.emit(request)

    def on_finished(self, result: dict[str, Any]) -> None:
        """Accept only the worker result belonging to this pending local edit."""
        if result.get("request_id") != self.pending_id or not self.pending_id:
            return
        self.pending_id = ""
        self.body.setEnabled(True)
        self.apply_button.setEnabled(True)
        if result.get("success"):
            self.preferred_id = str(result.get("relation_id", ""))
            self._clear_body()
            self.body_scroll.hide()
            self.footer.hide()
            self.status.setText("Connection saved. Select it to refine its details.")
            self._select_saved()
        else:
            self.status.setText(
                str(result.get("message", "Could not save connection."))
            )

    def _lists(self) -> list[Any]:
        return [
            getattr(self.editor, name)
            for name in ("rel_list", "participant_list", "location_list")
            if hasattr(self.editor, name)
        ]

    def _select_saved(self) -> None:
        for widget in self._lists():
            for index in range(widget.count()):
                item = widget.item(index)
                if item.data(Qt.ItemDataRole.UserRole).get("id") == self.preferred_id:
                    widget.setCurrentItem(item)
                    return

    def refresh(self, relations: list[Any]) -> None:
        """Retain a local draft across refresh; disable stale edits of deleted rows."""
        if self.relation is not None and not self.pending_id:
            exists = any(row.get("id") == self.relation["id"] for row in relations)
            self.apply_button.setEnabled(exists)
            if not exists:
                self.status.setText(
                    "This relation no longer exists. Cancel this draft."
                )
        self._select_saved()

    def remember_selection(self) -> None:
        """Remember row identity before lists are replaced by a worker snapshot."""
        if self.pending_id:
            return
        for widget in self._lists():
            item = widget.currentItem()
            if item is not None:
                self.preferred_id = item.data(Qt.ItemDataRole.UserRole).get("id", "")
                return

    def _add_full(self) -> None:
        if self.prepare_to_leave():
            self.cancel()
            self.editor._on_add_detailed_relation()

    def _edit_full(self) -> None:
        if not self.prepare_to_leave():
            return
        selected = next(
            (
                lst.currentItem()
                for lst in self._lists()
                if lst.currentItem() is not None
            ),
            None,
        )
        if selected is not None:
            self.cancel()
            self.editor._on_edit_relation_full(selected)

    def eventFilter(self, obj: Any, event: Any) -> bool:
        """Let popup and multiline owners handle Enter; Escape cancels locally."""
        from PySide6.QtCore import QEvent

        if event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Escape:
            self.cancel()
            return True
        return super().eventFilter(obj, event)
