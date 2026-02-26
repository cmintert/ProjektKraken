"""Create Template Dialog Module.

Provides a dialog to create a new Fast Inject template from an existing target. Allows
selecting which properties to include.
"""

from typing import Any, Dict, List, Optional

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.gui.utils.style_helper import StyleHelper
from src.gui.widgets.standard_buttons import PrimaryButton, StandardButton


class CreateTemplateDialog(QDialog):
    """Dialog to save the current entity/event state as a template."""

    def __init__(
        self,
        source_tags: List[str],
        source_attributes: Dict[str, Any],
        source_type: Optional[str] = None,
        source_layout: Optional[List[List[Any]]] = None,
        default_name: str = "New Template",
        parent: Optional[QWidget] = None,
    ) -> None:
        """Initialize the create template dialog.

        Args:
            source_tags: List of tags from the source entity/event.
            source_attributes: Attributes from the source entity/event.
            source_type: Type of the source entity/event.
            source_layout: Optional visual layout array.
            default_name: Default name for the template.
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle("Save Selection as Template")
        self.resize(500, 600)

        self.source_tags = source_tags
        self.source_attributes = {
            k: v for k, v in source_attributes.items() if not k.startswith("_")
        }
        self.source_layout = source_layout
        self.source_type = source_type

        self.result_data: Dict[str, Any] = {}

        self._setup_ui(default_name)

    def _setup_ui(self, default_name: str) -> None:
        """Set up the user interface.

        Args:
            default_name: Default name to populate in the name field.
        """
        layout = QVBoxLayout(self)
        StyleHelper.apply_standard_list_spacing(layout)
        self.setStyleSheet(StyleHelper.get_dialog_base_style())

        # Meta Section
        form = QFormLayout()
        self.name_edit = QLineEdit(default_name)
        self.desc_edit = QLineEdit()
        self.desc_edit.setPlaceholderText("Optional description")

        # Apply input styles
        input_style = StyleHelper.get_input_field_style()
        self.name_edit.setStyleSheet(input_style)
        self.desc_edit.setStyleSheet(input_style)

        form.addRow("Template Name:", self.name_edit)
        form.addRow("Description:", self.desc_edit)
        layout.addLayout(form)

        # Selection Scroll Area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        # Apply transparency so dialog background shows through, plus scrollbar style
        scroll.setStyleSheet(
            "QScrollArea { background-color: transparent; border: none; }"
            + StyleHelper.get_scrollbar_style()
        )
        content = QWidget()
        content.setStyleSheet("background-color: transparent;")
        self.content_layout = QVBoxLayout(content)

        # Tags Section
        if self.source_tags:
            group_tags = QGroupBox("Tags to Include")
            vbox_tags = QVBoxLayout(group_tags)
            self.tag_checks: List[QCheckBox] = []

            # Select All / None
            hbox_tools = QHBoxLayout()
            btn_all = StandardButton("Select All")
            btn_none = StandardButton("Select None")
            btn_all.clicked.connect(
                lambda: [c.setChecked(True) for c in self.tag_checks]
            )
            btn_none.clicked.connect(
                lambda: [c.setChecked(False) for c in self.tag_checks]
            )
            hbox_tools.addWidget(btn_all)
            hbox_tools.addWidget(btn_none)
            hbox_tools.addStretch()
            vbox_tags.addLayout(hbox_tools)

            for tag in self.source_tags:
                chk = QCheckBox(tag)
                chk.setChecked(True)
                vbox_tags.addWidget(chk)
                self.tag_checks.append(chk)

            self.content_layout.addWidget(group_tags)

        # Type Section
        if self.source_type:
            group_type = QGroupBox("Type to Include")
            vbox_type = QVBoxLayout(group_type)
            self.chk_type = QCheckBox(f"Type: {self.source_type}")
            self.chk_type.setChecked(True)
            vbox_type.addWidget(self.chk_type)
            self.content_layout.addWidget(group_type)

        # Attributes Section
        if self.source_attributes:
            group_attrs = QGroupBox("Attributes to Include")
            vbox_attrs = QVBoxLayout(group_attrs)
            self.attr_checks: Dict[str, QCheckBox] = {}

            # Tools
            hbox_tools_attr = QHBoxLayout()
            btn_all_a = StandardButton("Select All")
            btn_none_a = StandardButton("Select None")
            btn_all_a.clicked.connect(
                lambda: [c.setChecked(True) for c in self.attr_checks.values()]
            )
            btn_none_a.clicked.connect(
                lambda: [c.setChecked(False) for c in self.attr_checks.values()]
            )
            hbox_tools_attr.addWidget(btn_all_a)
            hbox_tools_attr.addWidget(btn_none_a)
            hbox_tools_attr.addStretch()
            vbox_attrs.addLayout(hbox_tools_attr)

            for key, val in self.source_attributes.items():
                label = f"{key}: {str(val)[:50]}"  # Truncate long values
                chk = QCheckBox(label)
                chk.setChecked(True)
                # Store key reference
                chk.setProperty("attr_key", key)
                vbox_attrs.addWidget(chk)
                self.attr_checks[key] = chk

            self.content_layout.addWidget(group_attrs)

        # Layout Section
        if self.source_layout:
            group_layout = QGroupBox("Layout Options")
            vbox_layout = QVBoxLayout(group_layout)
            self.chk_layout = QCheckBox("Include Visual Sheet Layout")
            self.chk_layout.setChecked(True)
            vbox_layout.addWidget(self.chk_layout)
            self.content_layout.addWidget(group_layout)

        self.content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_cancel = StandardButton("Cancel")
        btn_save = PrimaryButton("Save Template")

        btn_cancel.clicked.connect(self.reject)
        btn_save.clicked.connect(self._on_save)

        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_save)
        layout.addLayout(btn_layout)

    def _on_save(self) -> None:  # noqa: C901
        """Collect data and accept."""
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(
                self, "Missing Name", "Please enter a name for the template."
            )
            return

        # Collect content
        tags = [c.text() for c in getattr(self, "tag_checks", []) if c.isChecked()]

        attrs = {}
        if hasattr(self, "attr_checks"):
            for key, chk in self.attr_checks.items():
                if chk.isChecked():
                    # Look up value from source_attributes
                    if key in self.source_attributes:
                        attrs[key] = self.source_attributes[key]

        type_val = None
        if hasattr(self, "chk_type") and self.chk_type.isChecked():
            type_val = self.source_type

        if (
            hasattr(self, "chk_layout")
            and self.chk_layout.isChecked()
            and self.source_layout
        ):
            pruned_layout = []
            for row in self.source_layout:
                new_row = []
                for item in row:
                    if isinstance(item, str):
                        if item in attrs:
                            new_row.append(item)
                    elif isinstance(item, dict) and "key" in item:
                        if item["key"] in attrs:
                            new_row.append(item)
                    else:
                        new_row.append(item)
                if new_row:
                    pruned_layout.append(new_row)
            if pruned_layout:
                attrs["_sheet_layout"] = pruned_layout

        self.result_data = {
            "name": name,
            "description": self.desc_edit.text().strip(),
            "selected_tags": tags,
            "selected_attributes": attrs,
            "type_value": type_val,
        }

        self.accept()
