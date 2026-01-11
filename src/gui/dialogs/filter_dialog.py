from typing import Any, Dict, List, Optional

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QVBoxLayout,
    QWidget,
)

from src.gui.widgets.filter_widget import FilterWidget


class FilterDialog(QDialog):
    """
    Advanced filter configuration dialog.
    Wraps FilterWidget for backward compatibility.
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        available_tags: List[str] = None,
        current_config: Dict[str, Any] = None,
    ) -> None:
        """Initialize the filter dialog."""
        super().__init__(parent)
        self.setWindowTitle("Advanced Filter")
        self.resize(500, 600)

        main_layout = QVBoxLayout(self)

        self.filter_widget = FilterWidget(
            self,
            available_items=available_tags,
            current_config=current_config,
            title_include="Include Tags:",
            title_exclude="Exclude Tags:",
        )
        main_layout.addWidget(self.filter_widget)

        # --- Dialog Buttons ---
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        main_layout.addWidget(self.buttons)

    def get_filter_config(self) -> Dict[str, Any]:
        """Returns the current filter configuration from the widget."""
        return self.filter_widget.get_config()
