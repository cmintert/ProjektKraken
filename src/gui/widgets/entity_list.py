"""Entity List Widget Module.

Displays a list of entities with controls for creating, refreshing, and deleting.
"""

from typing import List, Optional

from PySide6.QtCore import QSize, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.entities import Entity
from src.gui.utils.help_context import declare_inspection
from src.gui.utils.style_helper import StyleHelper
from src.gui.widgets.empty_state_widget import EmptyStateWidget
from src.gui.widgets.standard_buttons import StandardButton as QPushButton


class EntityListWidget(QWidget):
    """A dumb widget that purely displays a list of entities.

    Emits signals when user interacts.
    """

    # Signals for user actions
    entity_selected = Signal(str)  # entity_id
    refresh_requested = Signal()
    delete_requested = Signal(str)  # entity_id
    create_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initializes the EntityListWidget.

        Args:
            parent (QWidget, optional): The parent widget. Defaults to None.

        """
        super().__init__(parent)
        if parent:
            self.setParent(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        main_layout = QVBoxLayout(self)
        StyleHelper.apply_standard_list_spacing(main_layout)

        # Controls
        self.btn_create = declare_inspection(
            QPushButton("New Entity"),
            "src-gui-widgets-entity-list-entitylistwidget-init-self-btn-create|authoring.create|help-inspect-src-gui-widgets-entity-list-entitylistwidget-init-self-btn-create",
        )
        self.btn_create.clicked.connect(self.create_requested.emit)

        self.btn_refresh = declare_inspection(
            QPushButton("Refresh"),
            "src-gui-widgets-entity-list-entitylistwidget-init-self-btn-refresh|explorer.browsing|help-inspect-src-gui-widgets-entity-list-entitylistwidget-init-self-btn-refresh",
        )
        self.btn_refresh.clicked.connect(self.refresh_requested.emit)

        self.btn_delete = declare_inspection(
            QPushButton("Delete"),
            "src-gui-widgets-entity-list-entitylistwidget-init-self-btn-delete|authoring.delete|help-inspect-src-gui-widgets-entity-list-entitylistwidget-init-self-btn-delete",
        )
        self.btn_delete.clicked.connect(self._on_delete_clicked)
        self.btn_delete.setEnabled(False)

        top_bar = QHBoxLayout()
        top_bar.addWidget(self.btn_create)
        top_bar.addWidget(self.btn_refresh)
        top_bar.addWidget(self.btn_delete)
        main_layout.addLayout(top_bar)

        # List View
        self.list_widget = declare_inspection(
            QListWidget(),
            "src-gui-widgets-entity-list-entitylistwidget-init-self-list-widget|explorer.browsing|help-inspect-src-gui-widgets-entity-list-entitylistwidget-init-self-list-widget",
        )
        self.list_widget.itemSelectionChanged.connect(self._on_selection_changed)
        main_layout.addWidget(self.list_widget)

        # Empty State
        self.empty_state = EmptyStateWidget(
            title="No Entities Found",
            description=(
                "Entities are the characters, locations, and artifacts of your world."
            ),
            parent=self,
        )
        declare_inspection(
            self.empty_state.add_action(
                "Create First Entity", self.create_requested.emit, primary=True
            ),
            "empty.EntityListWidget.__init__.80|authoring.create|help-inspect-empty-entitylistwidget-init-80",
        )
        main_layout.addWidget(self.empty_state)

    def set_entities(self, entities: List[Entity]) -> None:
        """Populates the list widget with the provided entities."""
        self.list_widget.clear()

        if not entities:
            self.list_widget.hide()
            self.empty_state.show()
            return

        self.list_widget.show()
        self.empty_state.hide()

        for entity in entities:
            # Display: Name (Type)
            label = f"{entity.name} ({entity.type})"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, entity.id)
            self.list_widget.addItem(item)

    @Slot()
    def _on_selection_changed(self) -> None:
        """Handles entity selection changes.

        Emits the entity_selected signal and enables/disables the delete button.
        """
        items = self.list_widget.selectedItems()
        if items:
            entity_id = items[0].data(Qt.ItemDataRole.UserRole)
            self.entity_selected.emit(entity_id)
            self.btn_delete.setEnabled(True)
        else:
            self.btn_delete.setEnabled(False)

    @Slot()
    def _on_delete_clicked(self) -> None:
        """Handles delete button clicks.

        Emits the delete_requested signal with the selected entity ID.
        """
        items = self.list_widget.selectedItems()
        if items:
            entity_id = items[0].data(Qt.ItemDataRole.UserRole)
            self.delete_requested.emit(entity_id)

    def minimumSizeHint(self) -> QSize:
        """Override to prevent dock collapse.

        Returns:
            QSize: Minimum size for usable entity list.

        """
        from PySide6.QtCore import QSize

        return QSize(250, 200)

    def sizeHint(self) -> QSize:
        """Preferred size for the entity list.

        Returns:
            QSize: Comfortable working size.

        """
        from PySide6.QtCore import QSize

        return QSize(350, 500)
