"""
Filter Widget Module.

Provides a reusable widget for configuring inclusion/exclusion rules
for a list of text items (tags, types, etc.).
"""

from typing import Any, Dict, List, Optional, Set

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)


class FilterWidget(QWidget):
    """
    Reusable widget for configuring include/exclude filters.
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        available_items: List[str] = None,
        current_config: Dict[str, Any] = None,
        title_include: str = "Include:",
        title_exclude: str = "Exclude:",
    ) -> None:
        """
        Initialize the filter widget.

        Args:
            parent: Parent widget.
            available_items: List of string items to filter.
            current_config: Current configuration dictionary.
            title_include: Label for include section.
            title_exclude: Label for exclude section.
        """
        super().__init__(parent)
        self.items = sorted(available_items or [])
        self.current_config = current_config or {}
        self.title_include = title_include
        self.title_exclude = title_exclude

        self._setup_ui()
        self._load_config()

    def _setup_ui(self) -> None:
        """Sets up the widget UI."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # --- Include Section ---
        main_layout.addWidget(QLabel(f"<b>{self.title_include}</b>"))
        self.list_include = QListWidget()
        self._populate_list(self.list_include)
        main_layout.addWidget(self.list_include)

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
        main_layout.addLayout(mode_layout_in)

        main_layout.addSpacing(10)

        # --- Exclude Section ---
        main_layout.addWidget(QLabel(f"<b>{self.title_exclude}</b>"))
        self.list_exclude = QListWidget()
        self._populate_list(self.list_exclude)
        main_layout.addWidget(self.list_exclude)

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
        main_layout.addLayout(mode_layout_ex)

        main_layout.addSpacing(10)

        # --- Options (Case Sensitivity) ---
        self.check_case = QCheckBox("Case Sensitive")
        main_layout.addWidget(self.check_case)

    def _load_config(self) -> None:
        """Restores UI state from self.current_config."""
        if not self.current_config:
            return

        # Include
        include_items = set(self.current_config.get("include", []))
        self._set_checked_items(self.list_include, include_items)

        if self.current_config.get("include_mode") == "all":
            self.radio_include_all.setChecked(True)
        else:
            self.radio_include_any.setChecked(True)

        # Exclude
        exclude_items = set(self.current_config.get("exclude", []))
        self._set_checked_items(self.list_exclude, exclude_items)

        if self.current_config.get("exclude_mode") == "all":
            self.radio_exclude_all.setChecked(True)
        else:
            self.radio_exclude_any.setChecked(True)

        # Case Sensitive
        self.check_case.setChecked(self.current_config.get("case_sensitive", False))

    def _populate_list(self, list_widget: QListWidget) -> None:
        """Populates a list widget with checkboxes for each item."""
        list_widget.clear()
        for item_text in self.items:
            item = QListWidgetItem(item_text)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            list_widget.addItem(item)

    def get_config(self) -> Dict[str, Any]:
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
        include_items = self._get_checked_items(self.list_include)
        exclude_items = self._get_checked_items(self.list_exclude)

        return {
            "include": include_items,
            "include_mode": "all" if self.radio_include_all.isChecked() else "any",
            "exclude": exclude_items,
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

    def _set_checked_items(
        self, list_widget: QListWidget, items_to_check: Set[str]
    ) -> None:
        """Sets checked state for items present in the set."""
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            if item.text() in items_to_check:
                item.setCheckState(Qt.CheckState.Checked)
            else:
                item.setCheckState(Qt.CheckState.Unchecked)

    def set_available_items(self, items: List[str]) -> None:
        """Updates the list of available items."""
        self.items = sorted(items)
        # We need to preserve checked state if possible, or just reset?
        # Typically set_available_items is called on init or reload.
        # Let's try to preserve current config if possible.
        current_config = self.get_config()
        self._populate_list(self.list_include)
        self._populate_list(self.list_exclude)
        # Restore checks
        self.current_config = current_config
        self._load_config()
