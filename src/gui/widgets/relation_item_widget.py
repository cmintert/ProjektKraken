"""
Relation Item Widget Module.

Provides a custom widget for relation list items with an embedded
"Go to" button for quick navigation to related entities/events.
"""

from typing import Any, Dict, Optional

from PySide6.QtCore import QSize, Signal, Slot
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QWidget

from src.gui.widgets.standard_buttons import StandardButton


class RelationItemWidget(QWidget):
    """
    A custom widget for displaying a relation item with a navigation button.

    Displays the relation label (→ Target [type]) on the left and a small
    "Go to →" button on the right for quick navigation.

    Signals:
        go_to_clicked(str, str): Emitted when Go to button is clicked.
                                 Args: target_id, target_name
    """

    go_to_clicked = Signal(str, str)  # target_id, target_name

    def __init__(
        self,
        label: str,
        target_id: str,
        target_name: str,
        attributes: Dict[str, Any] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        """
        Initializes the relation item widget.

        Args:
            label: The relation label text (e.g., "→ Alice [friend]")
            target_id: The UUID of the target entity/event
            target_name: The display name of the target
            attributes: Optional dictionary of relation attributes
            parent: Parent widget
        """
        super().__init__(parent)
        self._target_id = target_id
        self._target_name = target_name
        self.attributes = attributes or {}

        self._setup_ui(label)

    def _setup_ui(self, label: str) -> None:
        """Sets up the widget UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(8)

        # Relation label (left-aligned, expanding)
        self.label = QLabel(label)
        self.label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        layout.addWidget(self.label)

        # Attributes label (gray, small)
        if self.attributes:
            attr_text = self._format_attributes()
            self.attr_label = QLabel(attr_text)
            self.attr_label.setStyleSheet("color: #888; font-size: 11px;")
            layout.addWidget(self.attr_label)

        # Go to button (compact, icon-style)
        self.btn_go_to = StandardButton("→")
        self.btn_go_to.setFixedSize(22, 22)
        self.btn_go_to.setToolTip(f"Go to {self._target_name}")
        self.btn_go_to.clicked.connect(self._on_go_to_clicked)

        # Apply compact styling
        self.btn_go_to.setStyleSheet(
            """
            QPushButton {
                font-size: 12px;
                font-weight: bold;
                padding: 0px;
                border: 1px solid #555;
                border-radius: 3px;
                background-color: #3a3a3a;
                color: #aaa;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
                color: #fff;
                border-color: #777;
            }
            QPushButton:pressed {
                background-color: #2a2a2a;
            }
        """
        )

        layout.addWidget(self.btn_go_to)

    def _format_attributes(self) -> str:
        """Format attributes for display."""
        parts = []

        if "weight" in self.attributes:
            parts.append(f"weight={self.attributes['weight']}")

        if "confidence" in self.attributes:
            parts.append(f"confidence={self.attributes['confidence']}")

        if "start_date" in self.attributes:
            parts.append(f"start={self.attributes['start_date']}")

        return " • ".join(parts)

    def sizeHint(self) -> QSize:
        """
        Returns the preferred size hint to ensure proper row height.

        Returns:
            QSize: Size that accommodates the button plus margins.
        """
        from PySide6.QtCore import QSize

        # Button is 22px + 2px top margin + 2px bottom margin = 26px minimum
        return QSize(200, 28)

    @Slot()
    def _on_go_to_clicked(self) -> None:
        """Handles the Go to button click."""
        self.go_to_clicked.emit(self._target_id, self._target_name)
