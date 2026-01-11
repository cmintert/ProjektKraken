"""
Graph Filter Dialog Module.

Provides a tabbed dialog for configuring advanced filters for the Graph View,
allowing inclusion/exclusion of both Tags and Relation Types.
"""

from typing import Any, Dict, List, Optional

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.gui.widgets.filter_widget import FilterWidget


class GraphFilterDialog(QDialog):
    """
    Advanced filter configuration dialog for Graph View.
    Contains tabs for Tags and Relation Types.
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        available_tags: List[str] = None,
        available_rel_types: List[str] = None,
        current_config: Dict[str, Any] = None,
    ) -> None:
        """
        Initialize the graph filter dialog.

        Args:
            parent: Optional parent widget.
            available_tags: List of available tags.
            available_rel_types: List of available relation types.
            current_config: Current configuration dictionary with keys 'tags' and 'rel_types'.
        """
        super().__init__(parent)
        self.setWindowTitle("Graph Advanced Filter")
        self.resize(500, 650)

        self.current_config = current_config or {}

        main_layout = QVBoxLayout(self)

        # Tabs
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # Tag Filter Tab
        tag_config = self.current_config.get("tags", {})
        # Handle backward compatibility (if config was just list)
        if isinstance(tag_config, list):
            tag_config = {"include": tag_config}

        self.tag_filter_widget = FilterWidget(
            self,
            available_items=available_tags,
            current_config=tag_config,
            title_include="Include Tags:",
            title_exclude="Exclude Tags:",
        )
        self.tabs.addTab(self.tag_filter_widget, "Tags")

        # Relation Type Filter Tab
        rel_config = self.current_config.get("rel_types", {})
        # Handle backward compatibility
        if isinstance(rel_config, list):
            rel_config = {"include": rel_config}

        self.rel_filter_widget = FilterWidget(
            self,
            available_items=available_rel_types,
            current_config=rel_config,
            title_include="Include Relation Types:",
            title_exclude="Exclude Relation Types:",
        )
        self.tabs.addTab(self.rel_filter_widget, "Relation Types")

        # --- Dialog Buttons ---
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        main_layout.addWidget(self.buttons)

    def get_filter_config(self) -> Dict[str, Any]:
        """
        Returns the combined filter configuration.

        Returns:
            Dict: {
                "tags": Dict (filter config),
                "rel_types": Dict (filter config)
            }
        """
        return {
            "tags": self.tag_filter_widget.get_config(),
            "rel_types": self.rel_filter_widget.get_config(),
        }
