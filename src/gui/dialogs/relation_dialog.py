"""
Relation Edit Dialog Module.

Provides a consolidated dialog for adding or editing relations,
featuring autocompletion for target entities/events.
"""

from typing import Any, Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QCompleter,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLineEdit,
    QRadioButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.gui.widgets.compact_date_widget import CompactDateWidget


class RelationEditDialog(QDialog):
    """
    A dialog for adding or editing a relationship.
    Supports autocompletion for the target field.
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        target_id: str = "",
        rel_type: str = "involved",
        is_bidirectional: bool = False,
        attributes: Dict[str, Any] = None,
        suggestion_items: list[tuple[str, str, str]] = None,  # (id, name, type)
        calendar_converter: Any = None,
        source_event_date: Optional[float] = None,
        source_event_name: Optional[str] = None,
    ) -> None:
        """
        Initializes the dialog.

        Args:
            parent: Parent widget.
            target_id: Initial target ID (for editing).
            rel_type: Initial relation type.
            is_bidirectional: Initial bidirectional state.
            attributes: Initial relation attributes.
            suggestion_items: List of (id, name, type) for autocompletion.
            source_event_date: Optional lore_date of the source event.
            source_event_name: Optional name of the source event.
        """
        super().__init__(parent)
        self.setWindowTitle("Edit Relation")
        self.setMinimumWidth(400)

        self.attributes = attributes or {}
        self.calendar_converter = calendar_converter
        self.source_event_date = source_event_date
        self.source_event_name = source_event_name

        main_layout = QVBoxLayout(self)

        # Form
        self.form_layout = QFormLayout()

        # 1. Target Input with Autocomplete
        self.target_edit = QLineEdit()
        self.target_edit.setPlaceholderText("Search for entity or event...")

        # Setup Completer
        self._name_to_id = {}
        self._id_to_name = {}

        display_names = []
        if suggestion_items:
            for item_id, name, item_type in suggestion_items:
                self._name_to_id[name] = item_id
                self._id_to_name[item_id] = name
                display_names.append(name)

            # Sort names for better UX
            display_names.sort(key=str.lower)

        completer = QCompleter(display_names, self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        self.target_edit.setCompleter(completer)

        # Pre-fill if editing
        if target_id:
            # Try to resolve ID to name for display, otherwise fallback to ID
            initial_text = self._id_to_name.get(target_id, target_id)
            self.target_edit.setText(initial_text)

        self.form_layout.addRow("Target:", self.target_edit)

        # 2. Relation Type
        self.type_edit = QComboBox()
        self.type_edit.addItems(
            ["caused", "involved", "located_at", "parent_of", "member_of", "owns"]
        )
        self.type_edit.setEditable(True)
        self.type_edit.setCurrentText(rel_type)
        self.form_layout.addRow("Type:", self.type_edit)

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
            is_at_event = is_start_event and is_end_event

            if is_at_event:
                self.rb_at_event.setChecked(True)
            elif is_start_event:
                self.rb_starts.setChecked(True)
            elif is_end_event:
                self.rb_ends.setChecked(True)
            else:
                self.rb_absolute.setChecked(True)

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

        # 5. Payload / Custom Attributes
        self.custom_attrs_group = QGroupBox("Payload / Attributes")

        # Check if there are any non-standard attributes to load
        # Standard now includes temporal keys and payload
        standard_keys = {
            "weight",
            "confidence",
            "notes",
            "valid_from",
            "valid_to",
            "payload",
        }

        # Merge 'payload' dict into the custom attribute editor for easy editing
        # We flatten 'payload' into the attribute list for the user,
        # but re-nest it when saving IF it was originally nested,
        # OR we just let the attribute editor handle flat keys and later we decide what goes into payload?
        # DECISION: For MVP, we treat the 'Attribute Editor'
        # as the place to put Payload data.
        # We will map these back to 'payload' in _get_attributes.

        custom_attrs = {
            k: v for k, v in self.attributes.items() if k not in standard_keys
        }
        # If there is an existing payload dict, flatten it for the editor
        if "payload" in self.attributes and isinstance(
            self.attributes["payload"], dict
        ):
            for k, v in self.attributes["payload"].items():
                custom_attrs[k] = v

        custom_layout = QVBoxLayout()
        from src.gui.widgets.attribute_editor import AttributeEditorWidget

        self.custom_attr_editor = AttributeEditorWidget()
        self.custom_attr_editor.load_attributes(custom_attrs)
        custom_layout.addWidget(self.custom_attr_editor)
        self.custom_attrs_group.setLayout(custom_layout)

        self.form_layout.addRow(self.custom_attrs_group)

        # 5. Bidirectional
        self.bi_check = QCheckBox("Bidirectional (Create reverse link)")
        self.bi_check.setChecked(is_bidirectional)
        self.form_layout.addRow("", self.bi_check)

        main_layout.addLayout(self.form_layout)

        # Buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

        # Initial focus
        self.target_edit.setFocus()

    def _on_logic_changed(self, button: QRadioButton, checked: bool) -> None:
        """Handle logic radio button changes."""
        if not checked:
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
            # Hide Temporal Settings (managed automatically)
            self.temporal_group.setVisible(False)
            # Starts at Event
            # Force Valid From = Checked, Value = Event Date, Disabled
            self.check_from.setChecked(True)
            self.valid_from.set_value(self.source_event_date)
            self.valid_from.setEnabled(False)
            # Clear Valid To (indefinite)
            self.check_to.setChecked(False)

        elif button == self.rb_ends:
            # Hide Temporal Settings (managed automatically)
            self.temporal_group.setVisible(False)
            # Ends at Event
            # Force Valid To = Checked, Value = Event Date, Disabled
            self.check_to.setChecked(True)
            self.valid_to.set_value(self.source_event_date)
            self.valid_to.setEnabled(False)
            # Clear Valid From (from beginning)
            self.check_from.setChecked(False)

        elif button == self.rb_at_event:
            # Hide Temporal Settings (managed automatically)
            self.temporal_group.setVisible(False)
            # Only valid at Event (both start and end at event date)
            self.check_from.setChecked(True)
            self.valid_from.set_value(self.source_event_date)
            self.valid_from.setEnabled(False)
            self.check_to.setChecked(True)
            self.valid_to.set_value(self.source_event_date)
            self.valid_to.setEnabled(False)

    def _get_attributes(self) -> Dict[str, Any]:
        """Collects attributes from UI fields."""
        attrs = {}

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

        # Custom Attributes / Payload
        custom = self.custom_attr_editor.get_attributes()

        # Standard keys to exclude from payload
        standard_keys = {"weight", "confidence", "notes", "valid_from", "valid_to"}

        # Payload accumulator
        payload = {}

        for k, v in custom.items():
            if k in standard_keys:
                continue
            # For MVP: Everything in the Attribute Editor that isn't a standard key
            # is considered part of the "Payload" (the state override).
            # This is a simplification but aligns with the goal "State at Time T".
            payload[k] = v

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
        """
        Returns the dialog data.

        Returns:
            tuple: (target_id, rel_type, is_bidirectional, attributes)
        """
        text = self.target_edit.text().strip()

        # Resolve name to ID if possible, else use text as ID
        # (This handles manual ID entry or cross-project links)
        target_id = self._name_to_id.get(text, text)

        rel_type = self.type_edit.currentText().strip()
        is_bidirectional = self.bi_check.isChecked()
        attributes = self._get_attributes()

        return target_id, rel_type, is_bidirectional, attributes
