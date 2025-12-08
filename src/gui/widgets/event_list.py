from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QHBoxLayout,
    QLabel,
)
from PySide6.QtCore import Qt
from PySide6.QtCore import Signal
from typing import List
from src.core.events import Event


class EventListWidget(QWidget):
    """
    A dumb widget that purely displays a list of events.
    Emits signals when user interacts.
    Does NOT query the database itself.
    """

    # Signals for user actions
    event_selected = Signal(str)  # event_id
    refresh_requested = Signal()
    delete_requested = Signal(str)  # event_id

    def __init__(self, parent=None):
        """
        Initializes the EventListWidget.

        Args:
            parent: The parent widget, if any.
        """
        super().__init__(parent)
        if parent:
            self.setParent(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(8)
        self.layout.setContentsMargins(16, 16, 16, 16)

        # Controls
        self.btn_refresh = QPushButton("Refresh List")
        self.btn_refresh.clicked.connect(self.refresh_requested.emit)

        self.btn_delete = QPushButton("Delete Selected")
        self.btn_delete.clicked.connect(self._on_delete_clicked)
        self.btn_delete.setEnabled(False)

        top_bar = QHBoxLayout()
        top_bar.addWidget(self.btn_refresh)
        top_bar.addWidget(self.btn_delete)
        self.layout.addLayout(top_bar)

        # List View
        self.list_widget = QListWidget()
        self.list_widget.itemSelectionChanged.connect(self._on_selection_changed)
        self.layout.addWidget(self.list_widget)

        # Empty State (Spec 7.2)
        self.empty_label = QLabel("No Events Loaded")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet(
            "color: #757575; font-size: 14pt;"
        )  # Hardcoded dim fallback
        self.layout.addWidget(self.empty_label)
        self.empty_label.hide()

    def set_events(self, events: List[Event]):
        """
        Populates the list widget with the provided events.

        Args:
            events (List[Event]): A list of Event objects to display.
        """
        self.list_widget.clear()

        if not events:
            self.list_widget.hide()
            self.empty_label.show()
            return

        self.list_widget.show()
        self.empty_label.hide()

        for event in events:
            # Display: Date - Name (Type)
            label = f"[{event.lore_date}] {event.name} ({event.type})"
            item = QListWidgetItem(label)
            item.setData(100, event.id)  # Store ID in custom role
            self.list_widget.addItem(item)

    def _on_selection_changed(self):
        items = self.list_widget.selectedItems()
        if items:
            event_id = items[0].data(100)
            self.event_selected.emit(event_id)
            self.btn_delete.setEnabled(True)
        else:
            self.btn_delete.setEnabled(False)

    def _on_delete_clicked(self):
        items = self.list_widget.selectedItems()
        if items:
            event_id = items[0].data(100)
            self.delete_requested.emit(event_id)
