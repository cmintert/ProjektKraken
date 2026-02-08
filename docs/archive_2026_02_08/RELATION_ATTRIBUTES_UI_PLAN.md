# Relation Attributes UI Integration Plan

## Overview

This document outlines how to integrate relation attributes editing into the ProjektKraken event and entity editors. The goal is to provide a user-friendly way to view, add, and edit relation metadata (weight, confidence, dates, etc.) directly from the object editors.

## Current State

### Existing Components

1. **RelationDialog** (`src/gui/dialogs/relation_dialog.py`)
   - Creates/edits relations
   - Currently supports: source, target, type, bidirectional flag
   - Does NOT currently support attributes editing

2. **Event/Entity Editors** 
   - Display relations in a list widget
   - Show "Go to" buttons for navigation
   - Do NOT display relation attributes

3. **CLI** (`src/cli/relation.py`)
   - Already supports `--attr key=value` for attributes
   - Can create/update relations with attributes

4. **Commands** (`src/commands/relation_commands.py`)
   - `AddRelationCommand`, `UpdateRelationCommand` already accept attributes dict
   - Ready to use once UI passes attributes

## Integration Plan

### Phase 1: Extend RelationDialog (Minimal)

**Goal:** Allow users to add basic relation attributes when creating/editing relations.

**Changes to `src/gui/dialogs/relation_dialog.py`:**

1. Add a new section below the relation type selector:
   ```python
   # Attributes Section (collapsible)
   self.attributes_group = QGroupBox("Relation Attributes (Optional)")
   attributes_layout = QFormLayout()
   
   # Common attribute fields
   self.weight_spin = QDoubleSpinBox()
   self.weight_spin.setRange(0.0, 1.0)
   self.weight_spin.setSingleStep(0.1)
   self.weight_spin.setValue(1.0)
   attributes_layout.addRow("Weight:", self.weight_spin)
   
   self.confidence_spin = QDoubleSpinBox()
   self.confidence_spin.setRange(0.0, 1.0)
   self.confidence_spin.setSingleStep(0.1)
   self.confidence_spin.setValue(1.0)
   attributes_layout.addRow("Confidence:", self.confidence_spin)
   
   self.source_edit = QLineEdit()
   self.source_edit.setPlaceholderText("e.g., Chapter 5, page 42")
   attributes_layout.addRow("Source:", self.source_edit)
   
   self.notes_edit = QTextEdit()
   self.notes_edit.setPlaceholderText("Additional notes...")
   self.notes_edit.setMaximumHeight(60)
   attributes_layout.addRow("Notes:", self.notes_edit)
   
   self.attributes_group.setLayout(attributes_layout)
   main_layout.addWidget(self.attributes_group)
   ```

2. Add method to collect attributes:
   ```python
   def get_attributes(self) -> Dict[str, Any]:
       """Get attributes from the dialog fields."""
       attrs = {}
       
       # Only include non-default values
       weight = self.weight_spin.value()
       if weight != 1.0:
           attrs["weight"] = weight
       
       confidence = self.confidence_spin.value()
       if confidence != 1.0:
           attrs["confidence"] = confidence
       
       source = self.source_edit.text().strip()
       if source:
           attrs["source"] = source
       
       notes = self.notes_edit.toPlainText().strip()
       if notes:
           attrs["notes"] = notes
       
       return attrs
   ```

3. Update the dialog's accept handler to pass attributes to the command:
   ```python
   def accept(self):
       """Handle OK button click."""
       # ... existing validation ...
       
       attributes = self.get_attributes()
       
       # Create or update relation command with attributes
       if self.is_editing:
           cmd = UpdateRelationCommand(
               self.rel_id,
               self.target_id,
               self.rel_type,
               attributes
           )
       else:
           cmd = AddRelationCommand(
               self.source_id,
               self.target_id,
               self.rel_type,
               attributes,
               self.bidirectional
           )
       
       # ... execute command ...
   ```

### Phase 2: Display Attributes in Relation Lists

**Goal:** Show relation attributes in the event/entity editor relation lists.

**Changes to `src/gui/widgets/relation_item_widget.py`:**

1. Extend the widget to display key attributes:
   ```python
   class RelationItemWidget(QWidget):
       def __init__(self, label: str, target_id: str, target_name: str,
                    attributes: Dict[str, Any] = None, parent=None):
           super().__init__(parent)
           self.attributes = attributes or {}
           
           # ... existing layout ...
           
           # Add attributes display
           if self.attributes:
               attr_str = self._format_attributes()
               attr_label = QLabel(attr_str)
               attr_label.setStyleSheet("color: gray; font-size: 9pt;")
               layout.addWidget(attr_label)
   
   def _format_attributes(self) -> str:
       """Format attributes for display."""
       parts = []
       
       if "weight" in self.attributes:
           parts.append(f"weight={self.attributes['weight']:.2f}")
       
       if "confidence" in self.attributes:
           parts.append(f"confidence={self.attributes['confidence']:.2f}")
       
       if "start_date" in self.attributes:
           parts.append(f"from {self.attributes['start_date']}")
       
       if "end_date" in self.attributes:
           parts.append(f"to {self.attributes['end_date']}")
       
       return " • ".join(parts) if parts else ""
   ```

2. Update event/entity editors to pass attributes when creating widgets:
   ```python
   # In EventEditor/EntityEditor load_relations method:
   for rel in relations:
       widget = RelationItemWidget(
           label=f"→ {target_name} [{rel['rel_type']}]",
           target_id=rel["target_id"],
           target_name=target_name,
           attributes=rel.get("attributes", {}),  # Pass attributes
           parent=self
       )
   ```

### Phase 3: Advanced Attributes Editor (Optional)

**Goal:** Provide a dedicated dialog for editing complex relation attributes.

**New Component: `src/gui/dialogs/relation_attributes_dialog.py`:**

```python
class RelationAttributesDialog(QDialog):
    """
    Advanced dialog for editing relation attributes.
    
    Provides:
    - Predefined fields for common attributes (weight, confidence, etc.)
    - Key-value editor for custom attributes
    - JSON preview/validation
    """
    
    def __init__(self, attributes: Dict[str, Any] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Relation Attributes")
        self.attributes = attributes.copy() if attributes else {}
        
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        # Common attributes section
        common_group = QGroupBox("Common Attributes")
        common_layout = QFormLayout()
        
        self.weight_spin = QDoubleSpinBox()
        self.weight_spin.setRange(0.0, 10.0)
        self.weight_spin.setValue(self.attributes.get("weight", 1.0))
        common_layout.addRow("Weight:", self.weight_spin)
        
        self.confidence_spin = QDoubleSpinBox()
        self.confidence_spin.setRange(0.0, 1.0)
        self.confidence_spin.setValue(self.attributes.get("confidence", 1.0))
        common_layout.addRow("Confidence:", self.confidence_spin)
        
        # Date pickers (if available) or text fields
        self.start_date_edit = QLineEdit()
        self.start_date_edit.setText(str(self.attributes.get("start_date", "")))
        common_layout.addRow("Start Date:", self.start_date_edit)
        
        self.end_date_edit = QLineEdit()
        self.end_date_edit.setText(str(self.attributes.get("end_date", "")))
        common_layout.addRow("End Date:", self.end_date_edit)
        
        common_group.setLayout(common_layout)
        layout.addWidget(common_group)
        
        # Custom attributes section (key-value table)
        custom_group = QGroupBox("Custom Attributes")
        custom_layout = QVBoxLayout()
        
        self.custom_table = QTableWidget()
        self.custom_table.setColumnCount(2)
        self.custom_table.setHorizontalHeaderLabels(["Key", "Value"])
        self.custom_table.horizontalHeader().setStretchLastSection(True)
        
        # Populate with existing custom attributes
        for key, value in self.attributes.items():
            if key not in ["weight", "confidence", "start_date", "end_date"]:
                self._add_custom_row(key, str(value))
        
        custom_layout.addWidget(self.custom_table)
        
        # Add/Remove buttons
        button_layout = QHBoxLayout()
        add_btn = QPushButton("Add Row")
        add_btn.clicked.connect(lambda: self._add_custom_row())
        remove_btn = QPushButton("Remove Selected")
        remove_btn.clicked.connect(self._remove_selected_row)
        button_layout.addWidget(add_btn)
        button_layout.addWidget(remove_btn)
        button_layout.addStretch()
        custom_layout.addLayout(button_layout)
        
        custom_group.setLayout(custom_layout)
        layout.addWidget(custom_group)
        
        # JSON preview (read-only)
        preview_group = QGroupBox("JSON Preview")
        preview_layout = QVBoxLayout()
        self.json_preview = QTextEdit()
        self.json_preview.setReadOnly(True)
        self.json_preview.setMaximumHeight(100)
        self._update_json_preview()
        preview_layout.addWidget(self.json_preview)
        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)
        
        # Dialog buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        # Connect value changes to update preview
        self.weight_spin.valueChanged.connect(self._update_json_preview)
        self.confidence_spin.valueChanged.connect(self._update_json_preview)
    
    def _add_custom_row(self, key: str = "", value: str = ""):
        """Add a row to the custom attributes table."""
        row = self.custom_table.rowCount()
        self.custom_table.insertRow(row)
        self.custom_table.setItem(row, 0, QTableWidgetItem(key))
        self.custom_table.setItem(row, 1, QTableWidgetItem(value))
    
    def _remove_selected_row(self):
        """Remove the selected row from the custom attributes table."""
        current_row = self.custom_table.currentRow()
        if current_row >= 0:
            self.custom_table.removeRow(current_row)
    
    def _update_json_preview(self):
        """Update the JSON preview with current values."""
        import json
        attrs = self.get_attributes()
        json_str = json.dumps(attrs, indent=2)
        self.json_preview.setPlainText(json_str)
    
    def get_attributes(self) -> Dict[str, Any]:
        """Get all attributes from the dialog."""
        attrs = {}
        
        # Common attributes
        weight = self.weight_spin.value()
        if weight != 1.0:
            attrs["weight"] = weight
        
        confidence = self.confidence_spin.value()
        if confidence != 1.0:
            attrs["confidence"] = confidence
        
        start_date = self.start_date_edit.text().strip()
        if start_date:
            try:
                attrs["start_date"] = float(start_date)
            except ValueError:
                attrs["start_date"] = start_date
        
        end_date = self.end_date_edit.text().strip()
        if end_date:
            try:
                attrs["end_date"] = float(end_date)
            except ValueError:
                attrs["end_date"] = end_date
        
        # Custom attributes from table
        for row in range(self.custom_table.rowCount()):
            key_item = self.custom_table.item(row, 0)
            value_item = self.custom_table.item(row, 1)
            
            if key_item and value_item:
                key = key_item.text().strip()
                value_str = value_item.text().strip()
                
                if key:
                    # Try to parse value as number or JSON
                    try:
                        import json
                        value = json.loads(value_str)
                    except:
                        # Keep as string
                        value = value_str
                    
                    attrs[key] = value
        
        return attrs
```

**Usage in RelationItemWidget:**

Add a context menu or "Edit Attributes" button:

```python
class RelationItemWidget(QWidget):
    attributes_changed = Signal(str, dict)  # rel_id, new_attributes
    
    def __init__(self, rel_id: str, label: str, ..., attributes: Dict = None):
        super().__init__(parent)
        self.rel_id = rel_id
        # ...
        
        # Add edit attributes button
        edit_attrs_btn = QPushButton("⚙")
        edit_attrs_btn.setMaximumWidth(30)
        edit_attrs_btn.setToolTip("Edit relation attributes")
        edit_attrs_btn.clicked.connect(self._edit_attributes)
        layout.addWidget(edit_attrs_btn)
    
    def _edit_attributes(self):
        """Open the attributes editor dialog."""
        dialog = RelationAttributesDialog(self.attributes, self)
        if dialog.exec() == QDialog.Accepted:
            new_attributes = dialog.get_attributes()
            # Emit signal for parent to handle update
            self.attributes_changed.emit(self.rel_id, new_attributes)
```

## Implementation Order

1. **Phase 1 (Minimal)** - Extend RelationDialog
   - Estimated effort: 2-3 hours
   - Provides immediate value for most common use cases
   - No changes to existing relation display

2. **Phase 2** - Display attributes in lists
   - Estimated effort: 1-2 hours
   - Makes existing attributes visible
   - Improves information density

3. **Phase 3 (Optional)** - Advanced editor
   - Estimated effort: 4-6 hours
   - For power users with complex metadata needs
   - Can be deferred if not immediately needed

## Testing Checklist

- [ ] Create relation with attributes via dialog
- [ ] Update relation attributes via dialog
- [ ] Verify attributes persist to database
- [ ] Verify attributes display in relation lists
- [ ] Test with empty attributes (should default to {})
- [ ] Test with complex nested attributes
- [ ] Verify undo/redo works with attributes
- [ ] Test bidirectional relations with attributes
- [ ] Verify attributes survive round-trip through UI

## Design Considerations

### User Experience

1. **Progressive Disclosure**: Start with simple fields (weight, confidence), hide advanced editor behind a button
2. **Sensible Defaults**: weight=1.0, confidence=1.0, so users don't need to fill everything
3. **Visual Feedback**: Show key attributes (weight, confidence) directly in relation list items
4. **Validation**: Ensure numeric fields have appropriate ranges

### Technical Considerations

1. **Backward Compatibility**: Existing relations without attributes should continue to work
2. **JSON Validation**: Consider adding JSON validation for custom attributes
3. **Performance**: Don't load all attributes upfront if not displayed
4. **Consistency**: Use same attribute keys across CLI and GUI

## Future Enhancements

1. **Attribute Templates**: Predefined sets of attributes for common relation types
2. **Bulk Edit**: Edit attributes for multiple relations at once
3. **Attribute Inheritance**: Relations inherit default attributes from their type
4. **Visualization**: Show weight as edge thickness in relation graph views
5. **Search/Filter**: Filter relations by attribute values (e.g., confidence > 0.8)

## References

- Relation dataclass: `src/core/relations.py`
- Database methods: `src/services/db_service.py`
- Commands: `src/commands/relation_commands.py`
- CLI example: `src/cli/relation.py`
- NetworkX example: `scripts/networkx_example.py`
