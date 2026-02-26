"""Fast Inject Dialog Module.

Provides the UI for listing, previewing, and applying Fast Inject templates.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.core.fast_inject import FastInjectManager, FastInjectTemplate
from src.gui.utils.style_helper import StyleHelper
from src.gui.widgets.standard_buttons import PrimaryButton, StandardButton

logger = logging.getLogger(__name__)


class FastInjectDialog(QDialog):
    """Dialog for selecting and applying Fast Inject templates."""

    def __init__(
        self,
        templates: List[FastInjectTemplate],
        target_name: str = "Target",
        parent: Optional[QWidget] = None,
        manager: Optional[FastInjectManager] = None,
    ) -> None:
        """Initialize the dialog.

        Args:
            templates: List of available templates.
            target_name: Name of the target entity/event (for display).
            parent: Parent widget.
            manager: FastInjectManager instance (for saving changes).

        """
        super().__init__(parent)
        self.templates = templates
        self.target_name = target_name
        self.manager = manager

        self.selected_template: Optional[FastInjectTemplate] = None
        self.variable_values: Dict[str, str] = {}
        self.should_overwrite = False

        self.setWindowTitle(f"Fast Inject - {target_name}")
        self.resize(900, 650)  # Slightly larger for editor

        self._setup_ui()
        self._populate_list()

    def _setup_ui(self) -> None:
        """Setup the UI layout."""
        layout = QVBoxLayout(self)
        StyleHelper.apply_standard_list_spacing(layout)
        base_style = StyleHelper.get_dialog_base_style()
        scroll_style = StyleHelper.get_scrollbar_style()
        self.setStyleSheet(base_style + scroll_style)

        # Main Splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: Template List
        left_widget = QWidget()
        left_widget.setStyleSheet("background-color: transparent;")
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        left_layout.addWidget(QLabel("Available Templates:"))
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet(StyleHelper.get_input_field_style())
        self.list_widget.currentItemChanged.connect(self._on_template_selected)
        left_layout.addWidget(self.list_widget)

        splitter.addWidget(left_widget)

        # Right: Tab Widget (Configure vs Source)
        self.right_tabs = QTabWidget()
        self.right_tabs.setStyleSheet("background-color: transparent;")

        self.tab_configure = QWidget()
        self._setup_configure_tab(self.tab_configure)
        self.right_tabs.addTab(self.tab_configure, "Configure")

        self.tab_source = QWidget()
        self._setup_source_tab(self.tab_source)
        self.right_tabs.addTab(self.tab_source, "Edit Source")

        # Connect tab change to refresh source if needed
        self.right_tabs.currentChanged.connect(self._on_tab_changed)

        splitter.addWidget(self.right_tabs)
        splitter.setSizes([240, 660])
        layout.addWidget(splitter)

        # Bottom Buttons
        btn_layout = QHBoxLayout()
        self.btn_import = StandardButton("Import...")
        self.btn_import.clicked.connect(self._on_import_clicked)
        btn_layout.addWidget(self.btn_import)

        btn_layout.addStretch()

        self.btn_cancel = StandardButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)

        self.btn_apply = PrimaryButton("Apply Template")
        self.btn_apply.setEnabled(False)
        self.btn_apply.clicked.connect(self._on_apply)

        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_apply)
        layout.addLayout(btn_layout)

    def _setup_configure_tab(self, parent_widget: QWidget) -> None:
        """Setup the configuration tab."""
        layout = QVBoxLayout(parent_widget)
        layout.setContentsMargins(10, 10, 10, 10)

        # Header
        self.lbl_name = QLabel("Select a template")
        self.lbl_name.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.lbl_desc = QLabel("")
        self.lbl_desc.setWordWrap(True)
        self.lbl_desc.setStyleSheet("color: gray;")
        layout.addWidget(self.lbl_name)
        layout.addWidget(self.lbl_desc)
        layout.addSpacing(10)

        # Scroll Area for Attributes
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background-color: transparent; border: none;")

        self.form_container = QWidget()
        self.form_layout = QGridLayout(self.form_container)
        self.form_layout.setContentsMargins(0, 0, 0, 0)
        self.form_layout.setVerticalSpacing(8)
        self.form_layout.setColumnStretch(1, 1)  # Stretch value column

        scroll.setWidget(self.form_container)
        layout.addWidget(scroll)

        # Options
        self.chk_overwrite = QCheckBox("Overwrite existing values if keys exist")
        self.chk_overwrite.setChecked(True)
        layout.addWidget(self.chk_overwrite)

    def _setup_source_tab(self, parent_widget: QWidget) -> None:
        """Setup the JSON source editing tab."""
        layout = QVBoxLayout(parent_widget)
        layout.setContentsMargins(10, 10, 10, 10)

        layout.addWidget(QLabel("Edit Template JSON (Strict Format):"))

        self.txt_source = QTextEdit()
        self.txt_source.setStyleSheet(
            StyleHelper.get_input_field_style() + "font-family: Consolas, monospace;"
        )
        layout.addWidget(self.txt_source)

        btn_bar = QHBoxLayout()
        self.btn_save_source = PrimaryButton("Save Changes")
        self.btn_save_source.clicked.connect(self._on_save_source)
        self.btn_save_source.setEnabled(False)
        btn_bar.addStretch()
        btn_bar.addWidget(self.btn_save_source)
        layout.addLayout(btn_bar)

        self.txt_source.textChanged.connect(
            lambda: self.btn_save_source.setEnabled(True)
        )

    def _populate_list(self) -> None:
        """Populate the template list widget with available templates."""
        self.list_widget.clear()
        for t in self.templates:
            item = QListWidgetItem(t.name)
            item.setData(Qt.ItemDataRole.UserRole, t)
            self.list_widget.addItem(item)

    def _on_template_selected(
        self, current: QListWidgetItem, previous: QListWidgetItem
    ) -> None:
        """Handle template selection change in the list.

        Args:
            current: Currently selected list item.
            previous: Previously selected list item.
        """
        if not current:
            self.selected_template = None
            self.btn_apply.setEnabled(False)
            self._clear_configure_ui()
            self.txt_source.clear()
            self.btn_save_source.setEnabled(False)
            return

        template: FastInjectTemplate = current.data(Qt.ItemDataRole.UserRole)
        self.selected_template = template
        self.btn_apply.setEnabled(True)

        self._update_configure_ui(template)

        # If Source tab is active, update it
        if self.right_tabs.indexOf(self.tab_source) == self.right_tabs.currentIndex():
            self._load_source_view(template)

    def _on_tab_changed(self, index: int) -> None:
        """Handle tab switching."""
        if not self.selected_template:
            return

        if self.right_tabs.widget(index) == self.tab_source:
            self._load_source_view(self.selected_template)
        elif self.right_tabs.widget(index) == self.tab_configure:
            pass  # Already up to date via selection or save

    def _load_source_view(self, template: FastInjectTemplate) -> None:
        """Load JSON into source view."""
        try:
            content = json.dumps(template.to_dict(), indent=2, ensure_ascii=False)
            self.txt_source.setPlainText(content)
            self.btn_save_source.setEnabled(False)
        except Exception as e:
            self.txt_source.setPlainText(f"Error loading JSON: {e}")

    def _on_save_source(self) -> None:
        """Parse JSON, update object, and save to disk."""
        if not self.selected_template or not self.manager:
            return

        json_text = self.txt_source.toPlainText()
        try:
            data = json.loads(json_text)
            # Update object in place? Or replace?
            # Re-parsing using from_dict is safest
            new_template = FastInjectTemplate.from_dict(
                data, path=self.selected_template.source_path
            )

            # Preserve the object reference in the list widget if possible,
            # OR update the reference in the list item

            self.selected_template.name = new_template.name
            self.selected_template.description = new_template.description
            self.selected_template.tags = new_template.tags
            self.selected_template.attributes = new_template.attributes
            self.selected_template.type_value = new_template.type_value
            self.selected_template.target_type = new_template.target_type

            # Save using manager
            self.manager.save_template(self.selected_template)

            # Refresh UI
            self._update_configure_ui(self.selected_template)

            # Update List Item text if name changed
            curr_item = self.list_widget.currentItem()
            if curr_item:
                curr_item.setText(self.selected_template.name)

            self.btn_save_source.setEnabled(False)
            QMessageBox.information(
                self, "Saved", "Template verified and saved successfully."
            )

        except json.JSONDecodeError as e:
            QMessageBox.critical(self, "Invalid JSON", f"JSON Error: {e}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save: {e}")

    def _clear_configure_ui(self) -> None:
        """Clear the configuration UI form."""
        self.lbl_name.setText("Select a template")
        self.lbl_desc.setText("")
        while self.form_layout.count():
            child = self.form_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def _update_configure_ui(self, template: FastInjectTemplate) -> None:
        """Update the configuration UI with template details.

        Args:
            template: The template to display configuration for.
        """
        self.lbl_name.setText(template.name)
        self.lbl_desc.setText(template.description)
        self._build_form(template)

    def _build_form(self, template: FastInjectTemplate) -> None:
        """Build the unified attribute/tag editor form."""
        # Clear old
        while self.form_layout.count():
            child = self.form_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        self._form_widgets = (
            []
        )  # List of (Type, Key, Checkbox, InputWidget, OriginalType)

        row = 0

        # Headers
        if template.attributes or template.tags:
            self.form_layout.addWidget(QLabel("<b>Attribute</b>"), row, 0)
            self.form_layout.addWidget(QLabel("<b>Value / Result</b>"), row, 1)
            self.form_layout.addWidget(QLabel("<b>Include</b>"), row, 2)
            row += 1

        import re

        # Match {{VAR}} or {{VAR:Options}}
        # Unanchored to find within strings
        self.var_pattern = re.compile(r"\{\{([A-Za-z0-9_]+)(?::([^}]+))?\}\}")

        # 1. Attributes
        for key, value in template.attributes.items():
            if key == "_sheet_layout":
                continue

            # Flatten complex types into individual rows
            if isinstance(value, dict):
                for sub_key, sub_value in value.items():
                    self._add_row(row, f"{key}.{sub_key}", sub_value, "attr")
                    row = self.form_layout.rowCount()
            elif isinstance(value, list):
                for idx, item in enumerate(value):
                    self._add_row(row, f"{key}[{idx}]", item, "attr")
                    row = self.form_layout.rowCount()
            else:
                self._add_row(row, key, value, "attr")
                row = self.form_layout.rowCount()

        # 2. Tags
        for tag in template.tags:
            self._add_row(row, "Tag", tag, "tag")
            row = self.form_layout.rowCount()

        # 3. Spacer
        self.form_layout.setRowStretch(row, 1)

    def _add_row(self, row: int, key: str, value: Any, type_: str) -> None:
        """Add a row for an attribute or tag."""
        import re

        # Expect scalar values only (string, int, etc.)
        display_value = str(value)
        original_type = type(value)

        # Check if this is a pure variable (entire value is {{VAR}} or {{VAR:opts}})
        pure_var_pattern = re.compile(r"^\{\{([A-Za-z0-9_]+)(?::([^}]+))?\}\}$")
        match = pure_var_pattern.match(display_value)

        # UI Elements
        chk = QCheckBox()
        chk.setChecked(True)
        lbl = QLabel(f"{key}:")

        # Determine input widget type
        input_widget = None
        has_sub_controls = False

        if match:
            # Pure variable - use dropdown or text input in main row
            options = match.group(2)

            if options:
                # Variable with choices -> Dropdown
                input_widget = QComboBox()
                input_widget.setStyleSheet(StyleHelper.get_input_field_style())
                opts = [o.strip() for o in options.split("|")]
                input_widget.addItems(opts)
            else:
                # Variable without choices -> Text input with placeholder
                input_widget = QLineEdit()
                input_widget.setStyleSheet(StyleHelper.get_input_field_style())
                input_widget.setPlaceholderText(display_value)
        else:
            # Check for mixed content (variables embedded in text)
            var_pattern = re.compile(r"\{\{([A-Za-z0-9_]+)(?::([^}]+))?\}\}")
            matches = list(var_pattern.finditer(display_value))

            if matches:
                # Mixed content with variables - show result + sub-controls
                has_sub_controls = True
                input_widget = QLineEdit()
                input_widget.setStyleSheet(StyleHelper.get_input_field_style())
                input_widget.setReadOnly(True)  # Make read-only for mixed content
                # Will set text after creating sub-controls
            else:
                # Fixed value -> Text input
                input_widget = QLineEdit(display_value)
                input_widget.setStyleSheet(StyleHelper.get_input_field_style())

        self.form_layout.addWidget(lbl, row, 0)
        self.form_layout.addWidget(input_widget, row, 1)
        self.form_layout.addWidget(chk, row, 2)

        self._form_widgets.append((type_, key, chk, input_widget, original_type))

        # Add sub-controls for mixed content
        if has_sub_controls:
            sub_vars = {}  # VarName -> Widget

            # Extract unique variables
            unique_vars = {}
            for m in matches:
                v_name = m.group(1)
                opts = m.group(2)
                if v_name not in unique_vars:
                    unique_vars[v_name] = opts
                elif opts and not unique_vars.get(v_name):
                    unique_vars[v_name] = opts

            # Create sub-rows for each variable
            for v_name, opts in unique_vars.items():
                row += 1

                sub_lbl = QLabel(f"  ↳ {v_name}:")
                sub_lbl.setStyleSheet("color: #888888; font-style: italic;")

                sub_inp = None
                if opts:
                    sub_inp = QComboBox()
                    sub_inp.setStyleSheet(StyleHelper.get_input_field_style())
                    sub_inp.addItems([o.strip() for o in opts.split("|")])
                else:
                    sub_inp = QLineEdit()
                    sub_inp.setPlaceholderText(f"Value for {v_name}")
                    sub_inp.setStyleSheet(StyleHelper.get_input_field_style())

                # Position in grid (no checkbox for sub-controls)
                self.form_layout.addWidget(sub_lbl, row, 0)
                self.form_layout.addWidget(sub_inp, row, 1)

                sub_vars[v_name] = sub_inp

                # Connect signal to update main input
                if isinstance(sub_inp, QComboBox):
                    sub_inp.currentTextChanged.connect(
                        lambda _, m=input_widget, t=display_value, s=sub_vars: (
                            self._update_result_field(m, t, s)
                        )
                    )
                else:
                    sub_inp.textChanged.connect(
                        lambda _, m=input_widget, t=display_value, s=sub_vars: (
                            self._update_result_field(m, t, s)
                        )
                    )

            # Store the sub-controls reference on the main widget for later retrieval
            input_widget.setProperty("sub_vars", sub_vars)
            input_widget.setProperty("template_str", display_value)

            # Initial update to show resolved result
            self._update_result_field(input_widget, display_value, sub_vars)

    def _update_result_field(
        self, result_field: QLineEdit, template_str: str, sub_vars: Dict[str, QWidget]
    ) -> None:
        """Update result field based on sub-variable values."""
        import re

        var_pattern = re.compile(r"\{\{([A-Za-z0-9_]+)(?::([^}]+))?\}\}")

        def replacer(match: re.Match[str]) -> str:
            """Replace template variable with actual value.

            Args:
                match: Regex match object for template variable.

            Returns:
                Replacement value from form widgets.
            """
            v_name = match.group(1)
            if v_name in sub_vars:
                widget = sub_vars[v_name]
                if isinstance(widget, QComboBox):
                    return widget.currentText()
                else:
                    return widget.text()
            return match.group(0)  # Keep original if no replacement

        result_text = var_pattern.sub(replacer, template_str)
        result_field.setText(result_text)

    def _on_apply(self) -> None:  # noqa: C901
        """Collect values and create resolved template."""
        if not self.selected_template:
            return

        # Collect all values first
        flat_attrs = {}  # key -> value
        new_tags = []

        for type_, key, chk, widget, orig_type in self._form_widgets:
            if not chk.isChecked():
                continue

            # Get value from widget (could be QComboBox or QLineEdit)
            val_str = ""
            if isinstance(widget, QComboBox):
                val_str = widget.currentText().strip()
            else:  # QLineEdit
                val_str = widget.text().strip()

            # Attempt to restore type
            final_val = val_str
            if orig_type is int:
                try:
                    final_val = int(val_str)
                except ValueError:
                    pass
            # Could add float, bool, etc.

            if type_ == "attr":
                flat_attrs[key] = final_val
            elif type_ == "tag":
                if val_str:
                    new_tags.append(val_str)

        # Reconstruct nested structures from flat keys
        new_attrs = {}
        for key, value in flat_attrs.items():
            # Check if key indicates nested structure
            if "." in key:
                # Dict: "parent.child" -> parent: {child: value}
                parts = key.split(".", 1)
                parent_key = parts[0]
                child_key = parts[1]

                if parent_key not in new_attrs:
                    new_attrs[parent_key] = {}
                if isinstance(new_attrs[parent_key], dict):
                    new_attrs[parent_key][child_key] = value
            elif "[" in key and key.endswith("]"):
                # List: "parent[0]" -> parent: [value0, value1, ...]
                base_key = key[: key.index("[")]
                idx_str = key[key.index("[") + 1 : -1]
                try:
                    idx = int(idx_str)
                    if base_key not in new_attrs:
                        new_attrs[base_key] = []
                    if isinstance(new_attrs[base_key], list):
                        # Extend list if needed
                        while len(new_attrs[base_key]) <= idx:
                            new_attrs[base_key].append(None)
                        new_attrs[base_key][idx] = value
                except ValueError:
                    # Malformed index, treat as regular key
                    new_attrs[key] = value
            else:
                # Simple key
                new_attrs[key] = value

        import copy

        if "_sheet_layout" in self.selected_template.attributes:
            new_attrs["_sheet_layout"] = copy.deepcopy(
                self.selected_template.attributes["_sheet_layout"]
            )

        resolved_template = copy.deepcopy(self.selected_template)
        resolved_template.attributes = new_attrs
        resolved_template.tags = new_tags

        self.selected_template = resolved_template
        self.variable_values = {}
        self.should_overwrite = self.chk_overwrite.isChecked()
        self.accept()

    def _on_import_clicked(self) -> None:
        """Handle import button click to load templates from files."""
        from pathlib import Path

        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Import Fast Inject Templates",
            "",
            "Fast Inject Templates (*.fastinject);;All Files (*)",
        )
        if not file_paths:
            return
        self._import_paths = [Path(p) for p in file_paths]
        self.done(2)
