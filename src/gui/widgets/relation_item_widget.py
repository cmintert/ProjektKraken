"""
Relation Item Widget Module.

Provides a custom widget for relation list items with an embedded
"Go to" button for quick navigation to related entities/events.
"""

from PySide6.QtCore import Signal
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

    def __init__(self, label: str, target_id: str, target_name: str, parent=None):
        """
        Initializes the relation item widget.

        Args:
            label: The relation label text (e.g., "→ Alice [friend]")
            target_id: The UUID of the target entity/event
            target_name: The display name of the target
            parent: Parent widget
        """
        super().__init__(parent)
        self._target_id = target_id
        self._target_name = target_name

        self._setup_ui(label)

    def _setup_ui(self, label: str):
        """Sets up the widget UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(8)

        # Relation label (left-aligned, expanding)
        self.label = QLabel(label)
        self.label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout.addWidget(self.label)

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

    def sizeHint(self):
        """
        Returns the preferred size hint to ensure proper row height.

        Returns:
            QSize: Size that accommodates the button plus margins.
        """
        from PySide6.QtCore import QSize

        # Button is 22px + 2px top margin + 2px bottom margin = 26px minimum
        return QSize(200, 28)

    def _on_go_to_clicked(self):
        """Handles the Go to button click."""
        self.go_to_clicked.emit(self._target_id, self._target_name)
