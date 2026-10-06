"""Relation Edit Dialog Module.

Provides a consolidated dialog for adding or editing relations, featuring autocompletion
for target entities/events.
"""

from copy import deepcopy
from math import isfinite
from typing import Any, Dict, Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QAbstractButton,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLayoutItem,
    QListWidget,
    QMessageBox,
    QRadioButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.gui.utils.style_helper import StyleHelper
from src.gui.widgets.attribute_editor import AttributeEditorWidget
from src.gui.widgets.choice_inputs import ScrollSafeComboBox
from src.gui.widgets.compact_date_widget import CompactDateWidget
from src.gui.widgets.numeric_inputs import ScrollSafeDoubleSpinBox
from src.gui.widgets.relation_target import RelationTargetEdit
from src.gui.widgets.standard_buttons import DestructiveButton, StandardButton
from src.gui.widgets.wiki_text_edit import WikiTextEdit


def take_form_row(
    layout: QFormLayout, index: int
) -> tuple[QLayoutItem | None, QLayoutItem | None]:
    """Detach a row using typed layout items (Qt's result fields lack stubs)."""
    label = layout.itemAt(index, QFormLayout.ItemRole.LabelRole)
    field = layout.itemAt(index, QFormLayout.ItemRole.FieldRole)
    if field is None:
        field = layout.itemAt(index, QFormLayout.ItemRole.SpanningRole)
    layout.takeRow(index)
    return label, field


class RelationForm(QWidget):
    """A dialog for adding or editing a relationship.

    Supports autocompletion for the target field.
    """

    changed = Signal()

    def __init__(  # noqa: C901
        self,
        parent: Optional[QWidget] = None,
        target_id: str = "",
        rel_type: str = "involved",
        is_bidirectional: bool = False,
        attributes: Optional[Dict[str, Any]] = None,
        suggestion_items: Optional[
            list[tuple[str, str, str]]
        ] = None,  # (id, name, type)
        calendar_converter: Any = None,
        source_event_date: Optional[float] = None,
        source_event_name: Optional[str] = None,
        known_types: Optional[list[str]] = None,
        source_name: Optional[str] = None,
        target_kind: Optional[str] = None,
        playhead_time: float | None = None,
    ) -> None:
        """Initializes the dialog.

        Args:
            parent: Parent widget.
            target_id: Initial target ID (for editing).
            rel_type: Initial relation type.
            is_bidirectional: Initial bidirectional state.
            attributes: Initial relation attributes.
            suggestion_items: List of (id, name, type) for autocompletion.
            source_event_date: Optional lore_date of the source event.
            source_event_name: Optional name of the source event.
            known_types: Optional list of known relation types for suggestions.
            source_name: Display name of the source entity for the live preview.
            target_kind: Authoritative kind of an existing target when known.

        """
        super().__init__(parent)
        self.setStyleSheet(StyleHelper.get_dialog_base_style())

        self.attributes = deepcopy(attributes or {})
        self._preserve_original = attributes is not None
        self._changed_fields: set[str] = set()
        self._playhead_time = playhead_time
        self._fixed_now: dict[str, float] = {}
        self.calendar_converter = calendar_converter
        self.source_event_date = source_event_date
        self.source_event_name = source_event_name
        self._source_name = source_name or "Source"
        self._initial_target_id = target_id
        self._initial_target_kind = target_kind.casefold() if target_kind else None

        main_layout = QVBoxLayout(self)

        # Keep the approval buttons reachable when an event relation has a
        # large state-change payload. Only the form scrolls.
        self.form_scroll_area = QScrollArea()
        self.form_scroll_area.setWidgetResizable(True)
        self.form_scroll_area.setStyleSheet(
            StyleHelper.get_scroll_area_style() + StyleHelper.get_scrollbar_style()
        )
        self.form_container = QWidget()
        self.form_layout = QFormLayout(self.form_container)

        self._setup_target_field(target_id, suggestion_items)

        # 2. Relation Type
        self.type_edit = ScrollSafeComboBox()
        default_types = [
            "birth",
            "caused",
            "death",
            "involved",
            "located_at",
            "member_of",
            "owns",
            "parent_of",
            "related",
        ]

        # Merge with known types
        if known_types:
            # Use set to unique, but keep defaults if we want specific order?
            # Or just sort everything.
            all_types = sorted(
                relation_type
                for relation_type in set(default_types + known_types)
                if relation_type != "mentions"
            )
        else:
            all_types = default_types

        self.type_edit.addItems(all_types)
        self.type_edit.setEditable(True)
        self.type_edit.setCurrentText(rel_type)
        self.form_layout.addRow("Type:", self.type_edit)

        # Live direction preview
        self.preview_label = QLabel()
        self.preview_label.setWordWrap(True)
        self.preview_label.setStyleSheet(StyleHelper.get_preview_label_style())
        self.form_layout.addRow("Preview:", self.preview_label)
        self._update_preview()

        self.target_edit.textChanged.connect(self._update_preview)
        self.type_edit.currentTextChanged.connect(self._update_preview)

        # 3. Attributes Section
        self.attributes_group = QGroupBox("Attributes (Optional)")
        # Checkboxes removed per user request - always enabled, implicit save

        attr_layout = QFormLayout()

        # Weight
        self.weight_spin = ScrollSafeDoubleSpinBox()
        self.weight_spin.setRange(0.0, 10.0)
        self.weight_spin.setSingleStep(0.1)
        self.weight_spin.setValue(self.attributes.get("weight", 1.0))
        attr_layout.addRow("Weight:", self.weight_spin)

        # Confidence
        self.confidence_spin = ScrollSafeDoubleSpinBox()
        self.confidence_spin.setRange(0.0, 1.0)
        self.confidence_spin.setSingleStep(0.1)
        self.confidence_spin.setValue(self.attributes.get("confidence", 1.0))
        attr_layout.addRow("Confidence:", self.confidence_spin)

        # Source removed per user request

        # Notes
        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("Additional context...")
        self.notes_edit.setMinimumHeight(72)
        self.notes_edit.setMaximumHeight(110)
        self.notes_edit.setStyleSheet(StyleHelper.get_input_field_style())
        self.notes_edit.setPlainText(str(self.attributes.get("notes", "")))
        attr_layout.addRow("Notes:", self.notes_edit)

        self.attributes_group.setLayout(attr_layout)
        self.form_layout.addRow(self.attributes_group)

        # 4. Timeline Logic (Dynamic Binding)
        # Only show if we have a source event context
        if self.source_event_date is not None:
            self.logic_group = QGroupBox(
                f"Timeline Logic (Source: {self.source_event_name})"
            )

            # Add tooltip to the group box
            self.logic_group.setToolTip(
                "Choose how this relation tracks time.\n\n"
                "• Dynamic options automatically update if the event date changes.\n"
                "• Manual mode uses fixed dates that don't change."
            )

            logic_layout = QVBoxLayout()

            self.logic_btn_group = QButtonGroup(self)

            self.rb_absolute = QRadioButton("Absolute Dates (Manual)")
            self.rb_starts = QRadioButton("Starts at Event")
            self.rb_ends = QRadioButton("Ends at Event")
            self.rb_at_event = QRadioButton("Only valid at Event")

            self.logic_btn_group.addButton(self.rb_absolute)
            self.logic_btn_group.addButton(self.rb_starts)
            self.logic_btn_group.addButton(self.rb_ends)
            self.logic_btn_group.addButton(self.rb_at_event)

            logic_layout.addWidget(self.rb_starts)
            logic_layout.addWidget(self.rb_ends)
            logic_layout.addWidget(self.rb_at_event)
            logic_layout.addWidget(self.rb_absolute)

            # Initial State
            temporal = self.attributes.get("temporal", {})
            is_start_event = self.attributes.get("valid_from_event", False) or (
                temporal.get("start", {}).get("binding") == "source_event"
            )
            is_end_event = self.attributes.get("valid_to_event", False) or (
                temporal.get("end", {}).get("binding") == "source_event"
            )
            is_at_event = self.attributes.get("valid_at_event", False) or (
                is_start_event and is_end_event
            )

            if temporal:
                self.rb_absolute.setChecked(True)
            elif is_at_event:
                self.rb_at_event.setChecked(True)
            elif is_start_event:
                self.rb_starts.setChecked(True)
            elif is_end_event:
                self.rb_ends.setChecked(True)
            elif attributes is not None:
                self.rb_absolute.setChecked(True)
            else:
                # State changes caused by an Event take effect at that Event.
                # Users can still opt into fixed/manual timing explicitly.
                self.rb_starts.setChecked(True)

            # Connect Logic
            self.logic_btn_group.buttonToggled.connect(self._on_logic_changed)

            self.logic_group.setLayout(logic_layout)
            self.form_layout.addRow(self.logic_group)

        # 4b. Temporal Settings (Absolute/Manual Mode)
        self.temporal_group = QGroupBox("Timing")
        temp_layout = QFormLayout()

        # Valid From
        self.check_from = QCheckBox("Valid From:")
        self.valid_from = CompactDateWidget(text_first=True)
        self.valid_from.setEnabled(False)  # Default disabled (infinite)

        if self.calendar_converter:
            self.valid_from.set_calendar_converter(self.calendar_converter)

        initial_from = self.attributes.get("valid_from")
        if initial_from is not None:
            self.check_from.setChecked(True)
            self.valid_from.setEnabled(True)
            self.valid_from.set_value(initial_from)

        # Connect checkbox
        self.check_from.toggled.connect(self.valid_from.setEnabled)
        temp_layout.addRow(self.check_from, self.valid_from)

        # Valid To
        self.check_to = QCheckBox("Valid To:")
        self.valid_to = CompactDateWidget(text_first=True)
        self.valid_to.setEnabled(False)  # Default disabled (infinite)

        if self.calendar_converter:
            self.valid_to.set_calendar_converter(self.calendar_converter)

        initial_to = self.attributes.get("valid_to")
        if initial_to is not None:
            self.check_to.setChecked(True)
            self.valid_to.setEnabled(True)
            self.valid_to.set_value(initial_to)

        # Connect checkbox
        self.check_to.toggled.connect(self.valid_to.setEnabled)
        temp_layout.addRow(self.check_to, self.valid_to)

        from src.core.temporal_expression import TemporalExpression

        spec = self.attributes.get("temporal", {})
        for side, widget, checkbox in (
            ("start", self.valid_from, self.check_from),
            ("end", self.valid_to, self.check_to),
        ):
            boundary = spec.get(side, {})
            if "exact" in boundary:
                checkbox.setChecked(True)
                widget.set_value(boundary["exact"])
                self._fixed_now[side] = float(boundary["exact"])
            if "expression" in boundary:
                checkbox.setChecked(True)
                widget.setEnabled(True)
                widget.set_expression(
                    TemporalExpression.from_dict(boundary["expression"])
                )

        self._setup_boundary_choices(temp_layout, suggestion_items or [])
        self.temporal_group.setLayout(temp_layout)
        self._setup_now_actions()
        self.form_layout.addRow(self.temporal_group)

        # Trigger initial visibility/state update if we have event context
        if self.source_event_date is not None:
            self._on_logic_changed(self.logic_btn_group.checkedButton(), True)

        if self.source_event_date is not None:
            self._setup_state_changes()

        # 5. Bidirectional
        self.bi_check = QCheckBox("Bidirectional (Create reverse link)")
        self.bi_check.setChecked(is_bidirectional)
        self.form_layout.addRow("", self.bi_check)

        self._group_boundaries()

        self.form_scroll_area.setWidget(self.form_container)
        main_layout.addWidget(self.form_scroll_area, 1)

        self._track_changes()

    def _group_boundaries(self) -> None:
        """Keep each boundary's intent, input and shortcut in one visual block."""
        from src.gui.widgets.editor_presentation import DisclosureButton

        layout = self.temporal_group.layout()
        assert isinstance(layout, QFormLayout)
        while layout.rowCount():
            label, _field = take_form_row(layout, 0)
            label_widget = label.widget() if label is not None else None
            if label_widget is not None:
                label_widget.hide()
        layout.addRow("Meaning", self.temporal_behavior)
        self.boundary_previews: dict[str, QLabel] = {}
        for side, widget, check, button in (
            ("start", self.valid_from, self.check_from, self.starts_now_button),
            ("end", self.valid_to, self.check_to, self.ends_now_button),
        ):
            group = QGroupBox("Starts" if side == "start" else "Ends")
            fields = QFormLayout(group)
            fields.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
            choice = self._boundary_choices[side]
            for value, text in (
                ("manual", "From a date" if side == "start" else "Until a date"),
                ("open", "No start limit" if side == "start" else "No end limit"),
                ("unknown", "Date unknown"),
                (
                    "source_event",
                    "Begins with this event"
                    if side == "start"
                    else "Ends with this event",
                ),
            ):
                index = choice.findData(value)
                if index >= 0:
                    choice.setItemText(index, text)
            fields.addRow(choice)
            check.setText("Date")
            fields.addRow(check, widget)
            fields.addRow(button)
            preview = QLabel()
            preview.setWordWrap(True)
            self.boundary_previews[side] = preview
            fields.addRow(preview)
            advanced = QWidget()
            extra = QFormLayout(advanced)
            extra.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
            extra.addRow("Relative to event", self._anchor_relations[side])
            extra.addRow("Offset", self._boundary_offsets[side])
            disclosure = DisclosureButton("Event offset…")
            disclosure.toggled.connect(advanced.setVisible)
            fields.addRow(disclosure)
            fields.addRow(advanced)
            has_offset = bool(self._boundary_offsets[side].value()) or (
                self._anchor_relations[side].currentData() != "at"
            )
            disclosure.setChecked(has_offset)
            advanced.setVisible(has_offset)
            layout.addRow(group)
            choice.currentIndexChanged.connect(self._refresh_boundary_previews)
            widget.value_changed.connect(self._refresh_boundary_previews)
        self._refresh_boundary_previews()

    def _refresh_boundary_previews(self, *args: Any) -> None:
        """Explain fixed dates and rescheduling without changing authored timing."""
        for side, preview in self.boundary_previews.items():
            choice = self._boundary_choices[side]
            value = str(choice.currentData())
            if value == "source_event":
                date = (
                    self.calendar_converter.format_datetime(self.source_event_date)
                    if self.calendar_converter and self.source_event_date is not None
                    else str(self.source_event_date)
                )
                text = f"Follows {self.source_event_name or 'this event'} ({date}) when rescheduled."
            elif value.startswith("event:"):
                text = f"Follows {choice.currentText()} when rescheduled."
            elif value == "manual":
                widget = self.valid_from if side == "start" else self.valid_to
                date = (
                    self.calendar_converter.format_datetime(widget.get_value())
                    if self.calendar_converter
                    else str(widget.get_value())
                )
                text = f"Fixed date: {date}. Event rescheduling will not move it."
            elif value == "unknown":
                text = "The boundary exists, but its date is unknown."
            else:
                text = "No date limit on this side."
            preview.setText(text)

    def _setup_now_actions(self) -> None:
        """Offer fixed boundaries using the opening playhead snapshot."""
        row = QHBoxLayout()
        time = self._playhead_time
        available = time is not None and isfinite(time) and self.calendar_converter
        self.now_label = QLabel(
            f"Viewed date = {self.calendar_converter.format_datetime(time)}"
            if available
            else "Playhead date unavailable"
        )
        self.now_label.setWordWrap(True)
        row.addWidget(self.now_label, 1)
        self.starts_now_button = StandardButton("Use viewed date for start")
        self.ends_now_button = StandardButton("Use viewed date for end")
        for side, button, widget in (
            ("start", self.starts_now_button, self.valid_from),
            ("end", self.ends_now_button, self.valid_to),
        ):
            button.setEnabled(bool(available))
            button.setToolTip(
                "Use a fixed playhead date; event bindings remain dynamic."
            )
            button.clicked.connect(lambda _checked=False, s=side: self._use_now(s))
            widget.value_changed.connect(
                lambda _value, s=side: self._fixed_now.pop(s, None)
            )
            widget.draft_changed.connect(
                lambda dirty, s=side: self._fixed_now.pop(s, None) if dirty else None
            )
            row.addWidget(button)
        self.form_layout.addRow(row)

    def _use_now(self, side: str) -> None:
        """Replace one boundary while retaining the opposite source binding."""
        if self._playhead_time is None or self.calendar_converter is None:
            return
        if hasattr(self, "rb_absolute") and not self.rb_absolute.isChecked():
            for boundary, bound in (
                ("start", self.rb_starts.isChecked() or self.rb_at_event.isChecked()),
                ("end", self.rb_ends.isChecked() or self.rb_at_event.isChecked()),
            ):
                choice = self._boundary_choices[boundary]
                choice.setCurrentIndex(
                    choice.findData("source_event" if bound else "open")
                )
            self.rb_absolute.setChecked(True)
        choice = self._boundary_choices[side]
        choice.setCurrentIndex(choice.findData("manual"))
        widget = self.valid_from if side == "start" else self.valid_to
        widget.set_value(self._playhead_time)
        self._fixed_now[side] = self._playhead_time

    def _setup_target_field(
        self,
        target_id: str,
        suggestion_items: Optional[list[tuple[str, str, str]]],
    ) -> None:
        """Install the shared canonical target resolver."""
        self.target_edit = RelationTargetEdit(suggestion_items or [], target_id)
        self._display_to_id = self.target_edit.display_to_id
        self._id_to_display = self.target_edit.id_to_display
        self._id_to_kind = self.target_edit.id_to_kind
        self._name_to_ids = self.target_edit.name_to_ids
        self.form_layout.addRow("Target:", self.target_edit)

    def _track_changes(self) -> None:
        """Keep untouched stored values lossless despite input precision limits."""

        def track(field: str) -> None:
            self._changed_fields.add(field)
            self.changed.emit()

        self.target_edit.textChanged.connect(lambda: track("target"))
        self.type_edit.currentTextChanged.connect(lambda: track("type"))
        self.notes_edit.textChanged.connect(lambda: track("notes"))
        self.weight_spin.valueChanged.connect(lambda: track("weight"))
        self.confidence_spin.valueChanged.connect(lambda: track("confidence"))
        self.temporal_behavior.currentIndexChanged.connect(lambda: track("timing"))
        for side, widget, check in (
            ("start", self.valid_from, self.check_from),
            ("end", self.valid_to, self.check_to),
        ):
            for signal in (
                widget.value_changed,
                widget.draft_changed,
                check.toggled,
                self._boundary_choices[side].currentIndexChanged,
                self._boundary_offsets[side].valueChanged,
                self._anchor_relations[side].currentIndexChanged,
            ):
                signal.connect(lambda *args, field=side: track(field))
        if hasattr(self, "logic_btn_group"):
            self.logic_btn_group.buttonToggled.connect(lambda: track("timing"))
        if hasattr(self, "state_changes_group"):
            for signal in (
                self.state_attribute_editor.attributes_changed,
                self.change_description_check.toggled,
                self.state_description_edit.textChanged,
                self.unset_attributes_list.model().rowsInserted,
                self.unset_attributes_list.model().rowsRemoved,
            ):
                signal.connect(lambda *args: track("payload"))

    def _setup_state_changes(self) -> None:
        """Build Payload v2 controls for an Event-sourced relation."""
        self.state_changes_guidance = QLabel(
            "State changes are carried by Event \u2192 Entity relations and apply "
            "while the relation is active."
        )
        self.state_changes_guidance.setWordWrap(True)
        self.state_changes_guidance.setStyleSheet(StyleHelper.get_preview_label_style())
        self.form_layout.addRow(self.state_changes_guidance)

        self.state_changes_unavailable_label = QLabel()
        self.state_changes_unavailable_label.setWordWrap(True)
        self.form_layout.addRow(self.state_changes_unavailable_label)

        self.state_changes_group = QGroupBox("State Changes to Target Entity")
        state_layout = QVBoxLayout()

        state_layout.addWidget(QLabel("Set / Change Attributes"))
        self.state_attribute_editor = AttributeEditorWidget(allow_null=True)
        payload = self.attributes.get("payload")
        payload_data = payload if isinstance(payload, dict) else {}
        set_attributes = payload_data.get("attributes", {})
        self.state_attribute_editor.load_attributes(
            set_attributes if isinstance(set_attributes, dict) else {}
        )
        self.state_attribute_editor.attributes_changed.connect(
            self._fit_state_attribute_editor_to_contents
        )
        self._fit_state_attribute_editor_to_contents()
        state_layout.addWidget(self.state_attribute_editor)

        state_layout.addWidget(QLabel("Remove Attributes"))
        self.unset_attributes_list = QListWidget()
        self.unset_attributes_list.setMaximumHeight(96)
        unset_attributes = payload_data.get("unset_attributes", [])
        if isinstance(unset_attributes, list):
            self.unset_attributes_list.addItems(
                [key for key in unset_attributes if isinstance(key, str)]
            )
        self.unset_attributes_list.model().rowsInserted.connect(
            self._fit_unset_attributes_list_to_contents
        )
        self.unset_attributes_list.model().rowsRemoved.connect(
            self._fit_unset_attributes_list_to_contents
        )
        self._fit_unset_attributes_list_to_contents()
        state_layout.addWidget(self.unset_attributes_list)

        unset_buttons = QHBoxLayout()
        self.btn_add_unset = StandardButton("Add")
        self.btn_remove_unset = DestructiveButton("Remove")
        self.btn_remove_unset.setEnabled(False)
        self.btn_add_unset.clicked.connect(self._add_unset_attribute)
        self.btn_remove_unset.clicked.connect(self._remove_unset_attribute)
        self.unset_attributes_list.itemSelectionChanged.connect(
            lambda: self.btn_remove_unset.setEnabled(
                self.unset_attributes_list.currentRow() >= 0
            )
        )
        unset_buttons.addWidget(self.btn_add_unset)
        unset_buttons.addWidget(self.btn_remove_unset)
        unset_buttons.addStretch()
        state_layout.addLayout(unset_buttons)

        self.change_description_check = QCheckBox("Change Description")
        self.state_description_edit = WikiTextEdit()
        self.state_description_edit.setMaximumHeight(180)
        has_description = "description" in payload_data
        self.change_description_check.setChecked(has_description)
        if has_description and isinstance(payload_data["description"], str):
            self.state_description_edit.set_wiki_text(payload_data["description"])
        self.state_description_edit.setEnabled(has_description)
        self.state_description_edit.setVisible(has_description)
        self.change_description_check.toggled.connect(
            self.state_description_edit.setEnabled
        )
        self.change_description_check.toggled.connect(
            self.state_description_edit.setVisible
        )
        state_layout.addWidget(self.change_description_check)
        state_layout.addWidget(self.state_description_edit)

        self.state_changes_group.setLayout(state_layout)
        self.form_layout.addRow(self.state_changes_group)
        self.target_edit.textChanged.connect(self._update_state_changes_visibility)
        self._update_state_changes_visibility()

    def _fit_state_attribute_editor_to_contents(self) -> None:
        """Size the state attribute table to its visible rows."""
        table = self.state_attribute_editor.table
        row_height = sum(table.rowHeight(row) for row in range(table.rowCount()))
        table_height = (
            table.horizontalHeader().height() + row_height + (2 * table.frameWidth())
        )
        table.setFixedHeight(table_height)

        layout = self.state_attribute_editor.layout()
        if layout is None:
            return

        margins = layout.contentsMargins()
        editor_height = (
            margins.top()
            + self.state_attribute_editor.toolbar_layout.sizeHint().height()
            + layout.spacing()
            + table_height
            + margins.bottom()
        )
        self.state_attribute_editor.setFixedHeight(editor_height)

    def _fit_unset_attributes_list_to_contents(self) -> None:
        """Size the removed-attribute list to its visible entries."""
        row_height = sum(
            self.unset_attributes_list.sizeHintForRow(row)
            for row in range(self.unset_attributes_list.count())
        )
        list_height = row_height + (2 * self.unset_attributes_list.frameWidth())
        self.unset_attributes_list.setFixedHeight(list_height)

    def _is_event_to_entity(self) -> bool:
        """Return whether the current source and resolved target permit mutation."""
        if self.source_event_date is None:
            return False
        target_id = self._resolve_target_id(self.target_edit.text())
        if not target_id:
            return False
        target_kind = self._target_kind(target_id)
        if target_kind == "entity":
            return True
        return (
            target_kind is None
            and target_id == self._initial_target_id
            and isinstance(self.attributes.get("payload"), dict)
        )

    def _target_kind(self, target_id: str) -> Optional[str]:
        """Resolve a target kind, retaining authoritative edit context."""
        if target_id == self._initial_target_id and self._initial_target_kind:
            return self._initial_target_kind
        return self._id_to_kind.get(target_id)

    def _update_state_changes_visibility(self) -> None:
        """Expose mutation controls only for Event-to-Entity relations."""
        if hasattr(self, "state_changes_group"):
            enabled = self._is_event_to_entity()
            self.state_changes_group.setVisible(enabled)
            self.state_changes_group.setEnabled(enabled)
            self.state_changes_unavailable_label.setVisible(not enabled)
            if enabled:
                return

            target_id = self._resolve_target_id(self.target_edit.text())
            if target_id and self._target_kind(target_id) == "event":
                message = (
                    "State changes are unavailable for an Event target. "
                    "Select an entity to create an Event \u2192 Entity relation."
                )
            else:
                message = (
                    "Select an entity target to configure state changes carried "
                    "by this relation."
                )
            self.state_changes_unavailable_label.setText(message)

    def _add_unset_attribute(self) -> None:
        """Add one unique attribute key to the removal list."""
        set_keys = self.state_attribute_editor.get_attributes().keys()
        existing = [
            self.unset_attributes_list.item(row).text()
            for row in range(self.unset_attributes_list.count())
        ]
        suggestions = sorted(set(set_keys) | set(existing), key=str.casefold)
        key, accepted = QInputDialog.getItem(
            self,
            "Remove Attribute",
            "Attribute Name:",
            suggestions,
            0,
            True,
        )
        key = key.strip()
        if accepted and key and key not in existing:
            self.unset_attributes_list.addItem(key)

    def _remove_unset_attribute(self) -> None:
        """Remove the selected key from the removal list."""
        row = self.unset_attributes_list.currentRow()
        if row >= 0:
            self.unset_attributes_list.takeItem(row)

    def _collect_state_payload(self) -> dict[str, Any]:
        """Collect the canonical Payload v2 object from visible controls."""
        if not self._is_event_to_entity():
            return {}

        payload: dict[str, Any] = {}
        attributes = self.state_attribute_editor.get_attributes()
        if attributes:
            payload["attributes"] = attributes

        unset_attributes = [
            self.unset_attributes_list.item(row).text().strip()
            for row in range(self.unset_attributes_list.count())
            if self.unset_attributes_list.item(row).text().strip()
        ]
        if unset_attributes:
            payload["unset_attributes"] = unset_attributes

        if self.change_description_check.isChecked():
            payload["description"] = (
                self.state_description_edit.get_wiki_text()
                if self.state_description_edit.toPlainText()
                else ""
            )
        return payload

    def _update_preview(self) -> None:
        """Refresh the live direction preview label."""
        target_text = self.target_edit.text().strip() or "Target"
        rel = self.type_edit.currentText().strip() or "relation"
        self.preview_label.setText(f"{self._source_name} --{rel}--> {target_text}")

    def _setup_boundary_choices(
        self,
        layout: QFormLayout,
        suggestions: list[tuple[str, str, str]],
    ) -> None:
        """Expose unknown/open intent and named event anchors without numeric bounds."""
        self.temporal_behavior = ScrollSafeComboBox()
        for label, value in (
            ("Active state", "stateful"),
            ("Historical fact", "historical"),
            ("Occurrence", "occurrence"),
            ("Timeless association", "atemporal"),
        ):
            self.temporal_behavior.addItem(label, value)
        self.temporal_behavior.setCurrentIndex(
            max(
                0,
                self.temporal_behavior.findData(
                    self.attributes.get("temporal", {}).get("behavior", "stateful")
                ),
            )
        )
        self.temporal_behavior.setToolTip(
            "Active states follow their validity dates. Historical facts remain available after they happen. Occurrences appear in history views. Timeless associations do not depend on the playhead."
        )
        layout.addRow("Meaning", self.temporal_behavior)
        self._boundary_choices: dict[str, QComboBox] = {}
        self._boundary_offsets: dict[str, ScrollSafeDoubleSpinBox] = {}
        self._anchor_relations: dict[str, QComboBox] = {}
        temporal = self.attributes.get("temporal", {})
        for side, widget, checked in (
            ("start", self.valid_from, self.check_from),
            ("end", self.valid_to, self.check_to),
        ):
            choice = ScrollSafeComboBox()
            choice.addItem("Manual date", "manual")
            if self.source_event_date is not None:
                choice.addItem("At source event (dynamic)", "source_event")
            choice.addItem("Date not known", "unknown")
            choice.addItem("Unbounded", "open")
            for event_id, name, kind in suggestions:
                if kind.casefold() == "event":
                    choice.addItem(f"At event: {name}", f"event:{event_id}")
            boundary = temporal.get(side, {})
            selected = boundary.get("anchor", {}).get("anchor_id")
            if boundary.get("binding") == "source_event":
                selected = "source_event"
            if selected is None:
                selected = boundary.get(
                    "status", "manual" if checked.isChecked() else "open"
                )
            if selected == "known":
                selected = "manual"
            index = choice.findData(selected)
            if index < 0:
                choice.addItem("Referenced event (unavailable)", selected)
                index = choice.count() - 1
            choice.setCurrentIndex(index)
            choice.setAccessibleName(f"Relation {side} boundary")
            layout.insertRow(
                0 if side == "start" else 1,
                "Starts" if side == "start" else "Ends",
                choice,
            )
            self._boundary_choices[side] = choice
            relative = ScrollSafeComboBox()
            for title, value in (
                ("At event", "at"),
                ("Before event", "before"),
                ("After event", "after"),
            ):
                relative.addItem(title, value)
            relative.setCurrentIndex(
                max(
                    0,
                    relative.findData(boundary.get("anchor", {}).get("relation", "at")),
                )
            )
            relative.setAccessibleName(f"{side.title()} relative to event")
            relative.setEnabled(str(choice.currentData()).startswith("event:"))
            choice.currentIndexChanged.connect(
                lambda _index, c=choice, r=relative: r.setEnabled(
                    str(c.currentData()).startswith("event:")
                )
            )
            layout.addRow(f"{side.title()} relative to event", relative)
            self._anchor_relations[side] = relative
            offset = ScrollSafeDoubleSpinBox()
            offset.setRange(-1e12, 1e12)
            offset.setDecimals(6)
            offset.setSuffix(" days")
            offset.setValue(float(boundary.get("anchor", {}).get("offset_days", 0)))
            offset.setAccessibleName(f"{side.title()} event offset")
            offset.setToolTip(
                "Zero shares the event's exact transition. A signed offset shifts both evidence bounds by this many lore days."
            )
            self._boundary_offsets[side] = offset
            layout.addRow(f"{side.title()} event offset", offset)
            offset.setEnabled(str(choice.currentData()).startswith("event:"))
            choice.currentIndexChanged.connect(
                lambda _index, c=choice, o=offset: o.setEnabled(
                    str(c.currentData()).startswith("event:")
                )
            )
            choice.currentIndexChanged.connect(
                lambda _index, c=choice, w=widget, check=checked: self._select_boundary(
                    c, w, check
                )
            )
            # Checking the existing manual-date affordance also selects manual mode.
            checked.clicked.connect(
                lambda enabled, c=choice: c.setCurrentIndex(
                    c.findData("manual" if enabled else "open")
                )
            )
            self._select_boundary(choice, widget, checked)

    @staticmethod
    def _select_boundary(
        choice: QComboBox, widget: CompactDateWidget, check: QCheckBox
    ) -> None:
        """Update presentation for the chosen boundary intent."""
        manual = choice.currentData() == "manual"
        check.setChecked(manual)
        widget.setEnabled(manual)
        widget.setVisible(manual)
        check.setVisible(manual)

    def _on_logic_changed(self, button: QAbstractButton | None, checked: bool) -> None:
        """Handle logic radio button changes."""
        if not checked:
            return

        event_date = self.source_event_date
        if button != self.rb_absolute and event_date is None:
            return

        if button == self.rb_absolute:
            # Show Temporal Settings for manual configuration
            self.temporal_group.setVisible(True)
            # Re-enable controls, user can manual set
            if self.check_from.isChecked():
                self.valid_from.setEnabled(True)
            if self.check_to.isChecked():
                self.valid_to.setEnabled(True)

        elif button == self.rb_starts:
            assert event_date is not None
            # Hide Temporal Settings (managed automatically)
            self.temporal_group.setVisible(False)
            # Starts at Event
            # Force Valid From = Checked, Value = Event Date, Disabled
            self.check_from.setChecked(True)
            self.valid_from.set_value(event_date)
            self.valid_from.setEnabled(False)
            # Clear Valid To (indefinite)
            self.check_to.setChecked(False)

        elif button == self.rb_ends:
            assert event_date is not None
            # Hide Temporal Settings (managed automatically)
            self.temporal_group.setVisible(False)
            # Ends at Event
            # Force Valid To = Checked, Value = Event Date, Disabled
            self.check_to.setChecked(True)
            self.valid_to.set_value(event_date)
            self.valid_to.setEnabled(False)
            # Clear Valid From (from beginning)
            self.check_from.setChecked(False)

        elif button == self.rb_at_event:
            assert event_date is not None
            # Hide Temporal Settings (managed automatically)
            self.temporal_group.setVisible(False)
            # Only valid at Event (both start and end at event date)
            self.check_from.setChecked(True)
            self.valid_from.set_value(event_date)
            self.valid_from.setEnabled(False)
            self.check_to.setChecked(True)
            self.valid_to.set_value(event_date)
            self.valid_to.setEnabled(False)

    def _get_attributes(self) -> Dict[str, Any]:
        """Collects attributes from UI fields."""
        managed = {
            "weight",
            "confidence",
            "notes",
            "payload",
            "temporal",
            "valid_from",
            "valid_to",
            "valid_from_event",
            "valid_to_event",
            "valid_at_event",
        }
        attrs: Dict[str, Any] = {
            key: value for key, value in self.attributes.items() if key not in managed
        }

        # Standard Attributes
        # Only include non-default values to keep data clean
        weight = self.weight_spin.value()
        if weight != 1.0:
            attrs["weight"] = weight

        confidence = self.confidence_spin.value()
        if confidence != 1.0:
            attrs["confidence"] = confidence

        # Source removed

        notes = self.notes_edit.toPlainText().strip()
        if notes:
            attrs["notes"] = notes

        payload = (
            self._collect_state_payload()
            if hasattr(self, "state_changes_group")
            else {}
        )
        if payload:
            attrs["payload"] = payload

        # Temporal Keys
        if self.check_from.isChecked():
            attrs["valid_from"] = self.valid_from.get_value()

        if self.check_to.isChecked():
            v_to = self.valid_to.get_value()
            # Simple validation: To must be > From if both exist
            # If only To exists, it's valid (start = -inf)
            if "valid_from" in attrs and v_to < attrs["valid_from"]:
                # Just clamp it? Or maybe don't save invalid ranges?
                # For now let's trust user or they will fix it.
                pass
            attrs["valid_to"] = v_to

        # Save Dynamic Flags
        if self.source_event_date is not None and hasattr(self, "rb_at_event"):
            if self.rb_at_event.isChecked():
                # Only valid at Event - both start and end
                attrs["valid_at_event"] = True
                attrs["valid_from_event"] = True
                attrs["valid_to_event"] = True
                attrs["valid_from"] = self.source_event_date
                attrs["valid_to"] = self.source_event_date

            elif self.rb_starts.isChecked():
                attrs["valid_from_event"] = True
                # Ensure date is synced (in case they unchecked
                # it manually then re-clicked radio?)
                # _on_logic_changed handles UI, this handles data
                attrs["valid_from"] = self.source_event_date

            elif self.rb_ends.isChecked():
                attrs["valid_to_event"] = True
                attrs["valid_to"] = self.source_event_date

        attrs = self._with_temporal_attributes(attrs)
        return self._preserve_untouched(attrs, managed)

    def _preserve_untouched(
        self, attrs: dict[str, Any], managed: set[str]
    ) -> dict[str, Any]:
        """Restore untouched authored values rather than input projections."""
        if self._preserve_original:
            for key in ("notes", "weight", "confidence", "payload"):
                if (
                    key == "payload"
                    and hasattr(self, "state_changes_group")
                    and not self._is_event_to_entity()
                ):
                    attrs.pop(key, None)
                    continue
                if key not in self._changed_fields:
                    if key in self.attributes:
                        attrs[key] = deepcopy(self.attributes[key])
                    else:
                        attrs.pop(key, None)
            timing_keys = managed - {"notes", "weight", "confidence", "payload"}
            if not self._changed_fields.intersection({"start", "end", "timing"}):
                for key in timing_keys:
                    if key in self.attributes:
                        attrs[key] = deepcopy(self.attributes[key])
                    else:
                        attrs.pop(key, None)
            elif "timing" not in self._changed_fields and "temporal" in attrs:
                for side, legacy in (("start", "from"), ("end", "to")):
                    if side not in self._changed_fields:
                        original = self.attributes.get("temporal", {}).get(side)
                        if original is not None:
                            attrs["temporal"][side] = deepcopy(original)
                        for key in (f"valid_{legacy}", f"valid_{legacy}_event"):
                            if key in self.attributes:
                                attrs[key] = deepcopy(self.attributes[key])
                            else:
                                attrs.pop(key, None)
        return attrs

    def _with_temporal_attributes(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Collect precision-aware boundaries separately from relation evidence."""
        from src.core.temporal_expression import TemporalExpression

        temporal = self.attributes.get("temporal", {})
        choices = {
            side: choice.currentData()
            for side, choice in self._boundary_choices.items()
        }
        dynamic = any(
            attrs.get(key)
            for key in ("valid_from_event", "valid_to_event", "valid_at_event")
        )
        if (
            temporal
            or dynamic
            or self.temporal_behavior.currentData() != "stateful"
            or any(value != "open" for value in choices.values())
        ):
            spec = {
                **temporal,
                "schema": 1,
                "behavior": self.temporal_behavior.currentData(),
            }
            for side, widget, checked, legacy in (
                ("start", self.valid_from, self.check_from.isChecked(), "from"),
                ("end", self.valid_to, self.check_to.isChecked(), "to"),
            ):
                expression = widget.get_expression()
                if attrs.get(f"valid_{legacy}_event"):
                    spec[side] = {"binding": "source_event"}
                elif choices[side] == "source_event":
                    spec[side] = {"binding": "source_event"}
                    attrs[f"valid_{legacy}_event"] = True
                    attrs[f"valid_{legacy}"] = self.source_event_date
                elif side in self._fixed_now and choices[side] == "manual":
                    spec[side] = {"exact": self._fixed_now[side]}
                    attrs[f"valid_{legacy}"] = self._fixed_now[side]
                elif choices[side] == "unknown":
                    spec[side] = {"status": "unknown"}
                    attrs.pop(f"valid_{legacy}", None)
                elif str(choices[side]).startswith("event:"):
                    spec[side] = {
                        "anchor": {
                            "anchor_id": choices[side],
                            "relation": self._anchor_relations[side].currentData(),
                            "offset_days": self._boundary_offsets[side].value(),
                        }
                    }
                    attrs.pop(f"valid_{legacy}", None)
                elif checked and isinstance(expression, TemporalExpression):
                    spec[side] = {"expression": expression.to_dict()}
                elif checked:
                    spec[side] = {"exact": widget.get_value()}
                else:
                    spec[side] = {"status": "open"}
            if attrs.get("valid_at_event"):
                spec["at"] = {"binding": "source_event"}
                spec["behavior"] = "occurrence"
            elif spec["behavior"] == "occurrence":
                spec["at"] = spec["start"]
            else:
                spec.pop("at", None)
            attrs["temporal"] = spec
        return attrs

    def get_data(self) -> tuple[str, str, bool, Dict[str, Any]]:
        """Returns the dialog data.

        Returns:
            tuple: (target_id, rel_type, is_bidirectional, attributes)

        """
        target_id = self._resolve_target_id(self.target_edit.text())

        rel_type = self.type_edit.currentText().strip()
        is_bidirectional = self.bi_check.isChecked()
        attributes = self._get_attributes()

        return target_id or "", rel_type, is_bidirectional, attributes

    def _resolve_target_id(self, text: str) -> Optional[str]:
        """Resolve the target using the same picker as inline capture."""
        return self.target_edit.resolve()

    def validate(self) -> bool:
        """Accept only canonical targets and manually supported relation types."""
        from src.core.temporal_state import validate_payload

        if not self.valid_from.commit_draft() or not self.valid_to.commit_draft():
            return False

        target_id, rel_type, _, _ = self.get_data()
        if not target_id:
            QMessageBox.warning(
                self,
                "Unknown relation target",
                "Select an existing entity or event from the target suggestions.",
            )
            return False
        if rel_type == "mentions":
            QMessageBox.warning(
                self,
                "Automatic relation",
                "Mentions are managed from description wikilinks.",
            )
            return False
        payload = (
            self._collect_state_payload()
            if hasattr(self, "state_changes_group")
            else {}
        )
        if payload:
            try:
                validate_payload(payload)
            except ValueError as exc:
                QMessageBox.warning(self, "Invalid Entity State Changes", str(exc))
                return False
        return True
