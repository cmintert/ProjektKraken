"""Fast Inject Dialog Module.

Provides the UI for listing, previewing, and applying Fast Inject templates.
"""

import logging
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.core.fast_inject import FastInjectTemplate
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
    ) -> None:
        """Initialize the dialog.

        Args:
            templates: List of available templates.
            target_name: Name of the target entity/event (for display).
            parent: Parent widget.
        """
        super().__init__(parent)
        self.templates = templates
        self.target_name = target_name

        self.selected_template: Optional[FastInjectTemplate] = None
        self.variable_values: Dict[str, str] = {}
        self.should_overwrite = False

        self.setWindowTitle(f"Fast Inject - {target_name}")
        self.resize(800, 600)

        self._setup_ui()
        self._populate_list()

    def _setup_ui(self) -> None:
        """Setup the UI layout."""
        layout = QVBoxLayout(self)
        StyleHelper.apply_standard_list_spacing(layout)
        # Apply base dialog theme + scrollbars
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

        # Right: Details & Preview
        right_widget = QWidget()
        right_widget.setStyleSheet("background-color: transparent;")
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # Header Info
        self.lbl_name = QLabel("Select a template")
        self.lbl_name.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.lbl_desc = QLabel("")
        self.lbl_desc.setWordWrap(True)
        self.lbl_desc.setStyleSheet("color: gray;")

        right_layout.addWidget(self.lbl_name)
        right_layout.addWidget(self.lbl_desc)
        right_layout.addSpacing(10)

        # Variables Section (Dynamic)
        self.grp_vars = QGroupBox("Variables")
        self.layout_vars = QFormLayout(self.grp_vars)
        self.grp_vars.setVisible(False)
        right_layout.addWidget(self.grp_vars)

        # Preview Section
        group_preview = QGroupBox("Content Preview")
        preview_layout = QVBoxLayout(group_preview)

        self.txt_preview = QTextEdit()
        self.txt_preview.setStyleSheet(StyleHelper.get_input_field_style())
        self.txt_preview.setReadOnly(True)
        preview_layout.addWidget(self.txt_preview)

        right_layout.addWidget(group_preview)

        # Options
        self.chk_overwrite = QCheckBox("Overwrite existing attribute values")
        self.chk_overwrite.setToolTip(
            "If checked, existing attribute keys will be replaced by template values."
        )
        right_layout.addWidget(self.chk_overwrite)

        splitter.addWidget(right_widget)

        # Set splitter ratio (30% list, 70% content)
        splitter.setSizes([240, 560])
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

    def _populate_list(self) -> None:
        """Populate the list widget."""
        self.list_widget.clear()
        for t in self.templates:
            item = QListWidgetItem(t.name)
            item.setData(Qt.ItemDataRole.UserRole, t)
            # Optional: Add icon based on target_type
            self.list_widget.addItem(item)

    def _on_template_selected(
        self, current: QListWidgetItem, previous: QListWidgetItem
    ) -> None:
        """Handle template selection."""
        if not current:
            self.selected_template = None
            self.btn_apply.setEnabled(False)
            self.grp_vars.setVisible(False)
            self.txt_preview.clear()
            self.lbl_name.setText("Select a template")
            self.lbl_desc.setText("")
            return

        template: FastInjectTemplate = current.data(Qt.ItemDataRole.UserRole)
        self.selected_template = template
        self.btn_apply.setEnabled(True)

        self.lbl_name.setText(template.name)
        self.lbl_desc.setText(template.description)

        self._build_preview(template)
        self._build_variables_form(template)

    def _build_preview(self, template: FastInjectTemplate) -> None:
        """Build text preview of what will be injected."""
        lines = []
        if template.type_value:
            lines.append(f"Type: {template.type_value}")
            lines.append("")

        if template.tags:
            lines.append(f"Tags: {', '.join(template.tags)}")
            lines.append("")

        if template.attributes:
            lines.append("Attributes:")
            for k, v in template.attributes.items():
                lines.append(f"  {k}: {v}")

        self.txt_preview.setPlainText("\n".join(lines))

    def _build_variables_form(self, template: FastInjectTemplate) -> None:
        """Dynamically create input fields for variables."""
        # clear old
        while self.layout_vars.count():
            child = self.layout_vars.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Find vars (Naive scan or use manager helper if available,
        # but UI shouldn't depend on manager ideally?
        # We'll implement a simple scanner here to keep UI self-contained or
        # assume manager helper logic is replicated)

        import re

        vars_found = set()
        pattern = re.compile(r"\{\{([A-Za-z0-9_]+)\}\}")

        def scan(val: Any) -> List[str]:
            if isinstance(val, str):
                return pattern.findall(val)
            elif isinstance(val, list):
                res = []
                for v in val:
                    res.extend(scan(v))
                return res
            elif isinstance(val, dict):
                res = []
                for v in val.values():
                    res.extend(scan(v))
                return res
            return []

        for v in template.attributes.values():
            vars_found.update(scan(v))

        if not vars_found:
            self.grp_vars.setVisible(False)
            return

        self.grp_vars.setVisible(True)
        self._var_inputs = {}

        sorted_vars = sorted(list(vars_found))
        for var in sorted_vars:
            inp = QLineEdit()
            inp.setStyleSheet(StyleHelper.get_input_field_style())
            inp.setPlaceholderText(f"Value for {var}")
            self.layout_vars.addRow(f"{var}:", inp)
            self._var_inputs[var] = inp

    def _on_apply(self) -> None:
        """Validate and accept."""
        if not self.selected_template:
            return

        # Collect variables
        if self.grp_vars.isVisible():
            for var, inp in self._var_inputs.items():
                val = inp.text().strip()
                if not val:
                    QMessageBox.warning(
                        self, "Missing Variable", f"Please enter a value for {var}"
                    )
                    inp.setFocus()
                    return
                self.variable_values[var] = val

        self.should_overwrite = self.chk_overwrite.isChecked()
        self.accept()

    def _on_import_clicked(self) -> None:
        """Handle import request."""
        # Signal parent or handle locally?
        # For M1, we'll just show message or return a special code?
        # Actually better to emit a custom signal or let parent handle via
        # separate button.
        # But Requirement says button is IN dialog.
        # Minimal implementation: Just close with a special result code or emit signal?
        self.done(2)  # Custom code 2 = Import Requested
