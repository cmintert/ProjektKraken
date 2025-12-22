"""
Entity List Widget Module.

Displays a list of entities with controls for creating, refreshing, and deleting.
"""
from typing import List

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.core.entities import Entity
from src.gui.utils.style_helper import StyleHelper


class EntityListWidget(QWidget):
    """
    A dumb widget that purely displays a list of entities.
    Emits signals when user interacts.
    """

    # Signals for user actions
    entity_selected = Signal(str)  # entity_id
    refresh_requested = Signal()
    delete_requested = Signal(str)  # entity_id
    create_requested = Signal()

    def __init__(self, parent=None):
        """
        Initializes the EntityListWidget.

        Args:
            parent (QWidget, optional): The parent widget. Defaults to None.
        """
        super().__init__(parent)
        if parent:
            self.setParent(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.layout = QVBoxLayout(self)
        StyleHelper.apply_standard_list_spacing(self.layout)

        # Controls
        self.btn_create = QPushButton("New Entity")
        self.btn_create.clicked.connect(self.create_requested.emit)

        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.clicked.connect(self.refresh_requested.emit)

        self.btn_delete = QPushButton("Delete")
        self.btn_delete.clicked.connect(self._on_delete_clicked)
        self.btn_delete.setEnabled(False)

        top_bar = QHBoxLayout()
        top_bar.addWidget(self.btn_create)
        top_bar.addWidget(self.btn_refresh)
        top_bar.addWidget(self.btn_delete)
        self.layout.addLayout(top_bar)

        # List View
        self.list_widget = QListWidget()
        self.list_widget.itemSelectionChanged.connect(self._on_selection_changed)
        self.layout.addWidget(self.list_widget)

        # Empty State
        self.empty_label = QLabel("No Entities Loaded")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet(StyleHelper.get_empty_state_style())
        self.layout.addWidget(self.empty_label)
        self.empty_label.hide()

    def set_entities(self, entities: List[Entity]):
        """
        Populates the list widget with the provided entities.
        """
        self.list_widget.clear()

        if not entities:
            self.list_widget.hide()
            self.empty_label.show()
            return

        self.list_widget.show()
        self.empty_label.hide()

        for entity in entities:
            # Display: Name (Type)
            label = f"{entity.name} ({entity.type})"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, entity.id)
            self.list_widget.addItem(item)

    def _on_selection_changed(self):
        """
        Handles entity selection changes.

        Emits the entity_selected signal and enables/disables the delete button.
        """
        items = self.list_widget.selectedItems()
        if items:
            entity_id = items[0].data(Qt.UserRole)
            self.entity_selected.emit(entity_id)
            self.btn_delete.setEnabled(True)
        else:
            self.btn_delete.setEnabled(False)

    def _on_delete_clicked(self):
        """
        Handles delete button clicks.

        Emits the delete_requested signal with the selected entity ID.
        """
        items = self.list_widget.selectedItems()
        if items:
            entity_id = items[0].data(Qt.UserRole)
            self.delete_requested.emit(entity_id)
