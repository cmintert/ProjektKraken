"""
Filter Dialog Module.

Provides a dialog for configuring filters for events and entities
based on various criteria like date ranges, tags, and types.
"""

from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)


class FilterDialog(QDialog):
    """
    Advanced filter configuration dialog.
    Allows users to set include/exclude rules for tags with Any/All logic.
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        available_tags: List[str] = None,
        current_config: Dict[str, Any] = None,
    ) -> None:
        """Initialize the filter dialog.

        Args:
            parent: Optional parent widget.
            available_tags: List of available tags to filter by.
            current_config: Current filter configuration to restore.
        """
        super().__init__(parent)
        self.setWindowTitle("Advanced Filter")
        self.resize(500, 600)
        self.tags = sorted(available_tags or [])
        self.current_config = current_config or {}

        self.layout = QVBoxLayout(self)

        # --- Include Section ---
        self.layout.addWidget(QLabel("<b>Include Tags:</b>"))
        self.list_include = QListWidget()
        self._populate_list(self.list_include)
        self.layout.addWidget(self.list_include)

        # Include Mode
        mode_layout_in = QHBoxLayout()
        self.radio_include_any = QRadioButton("Any (OR)")
        self.radio_include_all = QRadioButton("All (AND)")
        self.radio_include_any.setChecked(True)

        self.group_include = QButtonGroup(self)
        self.group_include.addButton(self.radio_include_any)
        self.group_include.addButton(self.radio_include_all)

        mode_layout_in.addWidget(QLabel("Match Mode:"))
        mode_layout_in.addWidget(self.radio_include_any)
        mode_layout_in.addWidget(self.radio_include_all)
        mode_layout_in.addStretch()
        self.layout.addLayout(mode_layout_in)

        self.layout.addSpacing(10)

        # --- Exclude Section ---
        self.layout.addWidget(QLabel("<b>Exclude Tags:</b>"))
        self.list_exclude = QListWidget()
        self._populate_list(self.list_exclude)
        self.layout.addWidget(self.list_exclude)

        # Exclude Mode
        mode_layout_ex = QHBoxLayout()
        self.radio_exclude_any = QRadioButton("Any (OR)")
        self.radio_exclude_all = QRadioButton("All (AND)")
        self.radio_exclude_any.setChecked(True)  # Default

        self.group_exclude = QButtonGroup(self)
        self.group_exclude.addButton(self.radio_exclude_any)
        self.group_exclude.addButton(self.radio_exclude_all)

        mode_layout_ex.addWidget(QLabel("Match Mode:"))
        mode_layout_ex.addWidget(self.radio_exclude_any)
        mode_layout_ex.addWidget(self.radio_exclude_all)
        mode_layout_ex.addStretch()
        self.layout.addLayout(mode_layout_ex)

        self.layout.addSpacing(10)

        # --- Options (Case Sensitivity) ---
        self.check_case = QCheckBox("Case Sensitive")
        self.layout.addWidget(self.check_case)

        # --- Dialog Buttons ---
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.layout.addWidget(self.buttons)

        # Restore State
        self._load_config()

    def _load_config(self) -> None:
        """Restores UI state from self.current_config."""
        if not self.current_config:
            return

        # Include
        include_tags = set(self.current_config.get("include", []))
        self._set_checked_items(self.list_include, include_tags)

        if self.current_config.get("include_mode") == "all":
            self.radio_include_all.setChecked(True)
        else:
            self.radio_include_any.setChecked(True)

        # Exclude
        exclude_tags = set(self.current_config.get("exclude", []))
        self._set_checked_items(self.list_exclude, exclude_tags)

        if self.current_config.get("exclude_mode") == "all":
            self.radio_exclude_all.setChecked(True)
        else:
            self.radio_exclude_any.setChecked(True)

        # Case Sensitive
        self.check_case.setChecked(self.current_config.get("case_sensitive", False))

    def _populate_list(self, list_widget: QListWidget) -> None:
        """Populates a list widget with checkboxes for each tag."""
        for tag in self.tags:
            item = QListWidgetItem(tag)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            list_widget.addItem(item)

    def get_filter_config(self) -> Dict[str, Any]:
        """
        Returns the current filter configuration.

        Returns:
            Dict: {
                "include": List[str],
                "include_mode": "any" | "all",
                "exclude": List[str],
                "exclude_mode": "any" | "all",
                "case_sensitive": bool
            }
        """
        include_tags = self._get_checked_items(self.list_include)
        exclude_tags = self._get_checked_items(self.list_exclude)

        return {
            "include": include_tags,
            "include_mode": "all" if self.radio_include_all.isChecked() else "any",
            "exclude": exclude_tags,
            "exclude_mode": "all" if self.radio_exclude_all.isChecked() else "any",
            "case_sensitive": self.check_case.isChecked(),
        }

    def _get_checked_items(self, list_widget: QListWidget) -> List[str]:
        """Returns a list of text from checked items."""
        checked = []
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                checked.append(item.text())
        return checked

    def _set_checked_items(self, list_widget: QListWidget, items_to_check: set) -> None:
        """Sets checked state for items present in the set."""
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            if item.text() in items_to_check:
                item.setCheckState(Qt.CheckState.Checked)
            else:
                item.setCheckState(Qt.CheckState.Unchecked)
