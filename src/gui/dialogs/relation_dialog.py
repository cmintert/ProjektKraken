"""Relation Edit Dialog Module.

Provides a consolidated dialog for adding or editing relations, featuring autocompletion
for target entities/events.
"""

from collections import Counter
from typing import Any, Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QAbstractButton,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QCompleter,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
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
from src.gui.widgets.compact_date_widget import CompactDateWidget
from src.gui.widgets.standard_buttons import DestructiveButton, StandardButton
from src.gui.widgets.wiki_text_edit import WikiTextEdit


class RelationEditDialog(QDialog):
    """A dialog for adding or editing a relationship.

    Supports autocompletion for the target field.
    """

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

        """
        super().__init__(parent)
        self.setWindowTitle("Edit Relation")
        self.setMinimumWidth(400)
        self.setStyleSheet(StyleHelper.get_dialog_base_style())
        self._limit_height_to_available_screen()

        self.attributes = attributes or {}
        self.calendar_converter = calendar_converter
        self.source_event_date = source_event_date
        self.source_event_name = source_event_name
        self._source_name = source_name or "Source"

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
        self.type_edit = QComboBox()
        default_types = [
            "birth",
            "caused",
            "death",
            "involved",
            "located_at",
            "member_of",
            "owns",
            "parent_of",
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
        self.weight_spin = QDoubleSpinBox()
        self.weight_spin.setRange(0.0, 10.0)
        self.weight_spin.setSingleStep(0.1)
        self.weight_spin.setValue(self.attributes.get("weight", 1.0))
        attr_layout.addRow("Weight:", self.weight_spin)

        # Confidence
        self.confidence_spin = QDoubleSpinBox()
        self.confidence_spin.setRange(0.0, 1.0)
        self.confidence_spin.setSingleStep(0.1)
        self.confidence_spin.setValue(self.attributes.get("confidence", 1.0))
        attr_layout.addRow("Confidence:", self.confidence_spin)

        # Source removed per user request

        # Notes
        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("Additional context...")
        self.notes_edit.setMaximumHeight(60)
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
            is_start_event = self.attributes.get("valid_from_event", False)
            is_end_event = self.attributes.get("valid_to_event", False)
            is_at_event = self.attributes.get("valid_at_event", False) or (
                is_start_event and is_end_event
            )

            if is_at_event:
                self.rb_at_event.setChecked(True)
            elif is_start_event:
                self.rb_starts.setChecked(True)
            elif is_end_event:
                self.rb_ends.setChecked(True)
            else:
                # State changes caused by an Event take effect at that Event.
                # Users can still opt into fixed/manual timing explicitly.
                self.rb_starts.setChecked(True)

            # Connect Logic
            self.logic_btn_group.buttonToggled.connect(self._on_logic_changed)

            self.logic_group.setLayout(logic_layout)
            self.form_layout.addRow(self.logic_group)

        # 4b. Temporal Settings (Absolute/Manual Mode)
        self.temporal_group = QGroupBox("Temporal Settings")
        temp_layout = QFormLayout()

        # Valid From
        self.check_from = QCheckBox("Valid From:")
        self.valid_from = CompactDateWidget()
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
        self.valid_to = CompactDateWidget()
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

        self.temporal_group.setLayout(temp_layout)
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

        self.form_scroll_area.setWidget(self.form_container)
        main_layout.addWidget(self.form_scroll_area, 1)

        # Buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

        # Initial focus
        self.target_edit.setFocus()

    def _limit_height_to_available_screen(self) -> None:
        """Keep the dialog within the usable vertical screen area."""
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return

        available_height = screen.availableGeometry().height()
        self.setMaximumHeight(max(400, int(available_height * 0.85)))

    def _setup_target_field(
        self,
        target_id: str,
        suggestion_items: Optional[list[tuple[str, str, str]]],
    ) -> None:
        """Build the target field and its disambiguating completer."""
        self.target_edit = QLineEdit()
        self.target_edit.setPlaceholderText("Search for entity or event...")
        self._display_to_id: dict[str, str] = {}
        self._id_to_display: dict[str, str] = {}
        self._id_to_kind: dict[str, str] = {}
        self._name_to_ids: dict[str, list[str]] = {}
        display_names: list[str] = []
        if suggestion_items:
            name_counts = Counter(name.casefold() for _, name, _ in suggestion_items)
            for item_id, name, item_type in suggestion_items:
                display = name
                if name_counts[name.casefold()] > 1:
                    display = f"{name} ({item_type}, {item_id[:8]})"
                self._display_to_id[display] = item_id
                self._id_to_display[item_id] = display
                self._id_to_kind[item_id] = item_type.casefold()
                self._name_to_ids.setdefault(name.casefold(), []).append(item_id)
                display_names.append(display)
            display_names.sort(key=str.lower)
        completer = QCompleter(display_names, self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.target_edit.setCompleter(completer)
        if target_id:
            self.target_edit.setText(self._id_to_display.get(target_id, target_id))
        self.form_layout.addRow("Target:", self.target_edit)

    def _setup_state_changes(self) -> None:
        """Build Payload v2 controls for an Event-sourced relation."""
        self.state_changes_group = QGroupBox("Entity State Changes")
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
        return bool(target_id and self._id_to_kind.get(target_id) == "entity")

    def _update_state_changes_visibility(self) -> None:
        """Expose mutation controls only for Event-to-Entity relations."""
        if hasattr(self, "state_changes_group"):
            enabled = self._is_event_to_entity()
            self.state_changes_group.setVisible(enabled)
            self.state_changes_group.setEnabled(enabled)

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
        self.preview_label.setText(
            f"{self._source_name} --{rel}--> {target_text}"
        )

    def _on_logic_changed(
        self, button: QAbstractButton | None, checked: bool
    ) -> None:
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
        attrs: Dict[str, Any] = {}

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

        payload = self._collect_state_payload() if hasattr(
            self, "state_changes_group"
        ) else {}
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
        """Resolve a displayed target without allowing arbitrary persistence values."""
        candidate = text.strip()
        if candidate in self._display_to_id:
            return self._display_to_id[candidate]
        if candidate in self._id_to_display:
            return candidate

        matching_ids = self._name_to_ids.get(candidate.casefold(), [])
        if len(matching_ids) == 1:
            return matching_ids[0]
        return None

    def accept(self) -> None:
        """Accept only canonical targets and manually supported relation types."""
        from src.core.temporal_state import validate_payload

        target_id, rel_type, _, _ = self.get_data()
        if not target_id:
            QMessageBox.warning(
                self,
                "Unknown relation target",
                "Select an existing entity or event from the target suggestions.",
            )
            return
        if rel_type == "mentions":
            QMessageBox.warning(
                self,
                "Automatic relation",
                "Mentions are managed from description wikilinks.",
            )
            return
        payload = self._collect_state_payload() if hasattr(
            self, "state_changes_group"
        ) else {}
        if payload:
            try:
                validate_payload(payload)
            except ValueError as exc:
                QMessageBox.warning(self, "Invalid Entity State Changes", str(exc))
                return
        super().accept()
