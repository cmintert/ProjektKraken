"""
Graph Filter Bar Module.

Private internal component providing filter controls for the graph view.
"""

import logging
from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

logger = logging.getLogger(__name__)


class GraphFilterBar(QWidget):
    """
    Internal filter toolbar for graph view.

    Provides multi-select filters for tags and relation types.
    This is a private internal component - use GraphWidget for public API.

    Signals:
        filters_changed: Emitted when any filter selection changes.
        refresh_requested: Emitted when the refresh button is clicked.
    """

    filters_changed = Signal()
    refresh_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Initializes the GraphFilterBar.

        Args:
            parent: Parent widget.
        """
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Sets up the filter bar UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        # Tag filter
        layout.addWidget(QLabel("Tags:"))
        self._tag_combo = QComboBox()
        self._tag_combo.setMinimumWidth(150)
        self._tag_combo.setEditable(False)
        self._tag_combo.addItem("All Tags", None)
        self._tag_combo.currentIndexChanged.connect(self._on_filter_changed)
        layout.addWidget(self._tag_combo)

        # Relation type filter
        layout.addWidget(QLabel("Relation Types:"))
        self._rel_type_combo = QComboBox()
        self._rel_type_combo.setMinimumWidth(150)
        self._rel_type_combo.setEditable(False)
        self._rel_type_combo.addItem("All Types", None)
        self._rel_type_combo.currentIndexChanged.connect(self._on_filter_changed)
        layout.addWidget(self._rel_type_combo)

        # Refresh button
        self._refresh_btn = QPushButton("🔄 Refresh")
        self._refresh_btn.clicked.connect(self.refresh_requested.emit)
        layout.addWidget(self._refresh_btn)

        # Stretch to push controls to the left
        layout.addStretch()

    def _on_filter_changed(self) -> None:
        """Handles filter combo box changes."""
        self.filters_changed.emit()

    def set_available_tags(self, tags: list[str]) -> None:
        """
        Populates the tag filter with available options.

        Args:
            tags: List of tag names.
        """
        current = self._tag_combo.currentData()
        self._tag_combo.blockSignals(True)
        self._tag_combo.clear()
        self._tag_combo.addItem("All Tags", None)
        for tag in sorted(tags):
            self._tag_combo.addItem(tag, tag)

        # Restore selection if still valid
        if current:
            idx = self._tag_combo.findData(current)
            if idx >= 0:
                self._tag_combo.setCurrentIndex(idx)

        self._tag_combo.blockSignals(False)

    def set_available_relation_types(self, rel_types: list[str]) -> None:
        """
        Populates the relation type filter with available options.

        Args:
            rel_types: List of relation type names.
        """
        current = self._rel_type_combo.currentData()
        self._rel_type_combo.blockSignals(True)
        self._rel_type_combo.clear()
        self._rel_type_combo.addItem("All Types", None)
        for rel_type in sorted(rel_types):
            self._rel_type_combo.addItem(rel_type, rel_type)

        # Restore selection if still valid
        if current:
            idx = self._rel_type_combo.findData(current)
            if idx >= 0:
                self._rel_type_combo.setCurrentIndex(idx)

        self._rel_type_combo.blockSignals(False)

    def get_selected_tags(self) -> list[str]:
        """
        Returns the currently selected tags for filtering.

        Returns:
            List of selected tag names, or empty list for "All".
        """
        data = self._tag_combo.currentData()
        return [data] if data else []

    def get_selected_relation_types(self) -> list[str]:
        """
        Returns the currently selected relation types for filtering.

        Returns:
            List of selected rel_type names, or empty list for "All".
        """
        data = self._rel_type_combo.currentData()
        return [data] if data else []
