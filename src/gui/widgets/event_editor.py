from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QTextEdit,
    QDoubleSpinBox,
    QComboBox,
    QPushButton,
    QHBoxLayout,
    QGroupBox,
    QListWidget,
    QInputDialog,
    QMessageBox,
    QListWidgetItem,
    QMenu,
    QTabWidget,
)
from PySide6.QtCore import Signal, Qt
from src.core.events import Event
from src.gui.widgets.attribute_editor import AttributeEditorWidget


class EventEditorWidget(QWidget):
    """
    A form to edit the details of an Event.
    Emits 'save_requested' signal with the modified Event object.
    Emits 'add_relation_requested' signal (source, target, type).
    """

    save_requested = Signal(dict)
    add_relation_requested = Signal(
        str, str, str, bool
    )  # source_id, target_id, type, bidirectional
    remove_relation_requested = Signal(str)  # rel_id
    update_relation_requested = Signal(str, str, str)  # rel_id, target_id, rel_type

    def __init__(self, parent=None):
        """
        Initializes the editor widget with form fields.

        Args:
            parent: The parent widget, if any.
        """
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(8)
        self.layout.setContentsMargins(16, 16, 16, 16)

        # Form Layout
        # Main Layout -> Tabs
        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs)

        # --- Tab 1: Details ---
        self.tab_details = QWidget()
        details_layout = QVBoxLayout(self.tab_details)

        self.form_layout = QFormLayout()
        self.name_edit = QLineEdit()
        self.date_edit = QDoubleSpinBox()
        self.date_edit.setRange(-1e12, 1e12)  # Cosmic scale
        self.date_edit.setDecimals(2)

        self.type_edit = QComboBox()
        self.type_edit.addItems(
            ["generic", "cosmic", "historical", "personal", "session", "combat"]
        )
        self.type_edit.setEditable(True)

        self.desc_edit = QTextEdit()

        self.form_layout.addRow("Name:", self.name_edit)
        self.form_layout.addRow("Lore Date:", self.date_edit)
        self.form_layout.addRow("Type:", self.type_edit)
        self.form_layout.addRow("Description:", self.desc_edit)

        details_layout.addLayout(self.form_layout)
        self.tabs.addTab(self.tab_details, "Details")

        # --- Tab 2: Relations ---
        self.tab_relations = QWidget()
        rel_tab_layout = QVBoxLayout(self.tab_relations)

        self.rel_group = QGroupBox("Relationships")
        self.rel_layout = QVBoxLayout()
        # ... logic continues for relations list ...
        self.rel_list = QListWidget()
        self.rel_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.rel_list.customContextMenuRequested.connect(self._show_rel_menu)
        self.rel_list.itemDoubleClicked.connect(self._on_edit_relation)
        self.rel_layout.addWidget(self.rel_list)

        rel_btn_layout = QHBoxLayout()
        self.btn_add_rel = QPushButton("Add Relation")
        self.btn_add_rel.clicked.connect(self._on_add_relation)
        rel_btn_layout.addWidget(self.btn_add_rel)

        self.btn_edit_rel = QPushButton("Edit")
        self.btn_edit_rel.clicked.connect(self._on_edit_selected_relation)
        rel_btn_layout.addWidget(self.btn_edit_rel)

        self.btn_remove_rel = QPushButton("Remove")
        self.btn_remove_rel.clicked.connect(self._on_remove_selected_relation)
        rel_btn_layout.addWidget(self.btn_remove_rel)

        self.rel_layout.addLayout(rel_btn_layout)
        self.rel_group.setLayout(self.rel_layout)

        rel_tab_layout.addWidget(self.rel_group)
        self.tabs.addTab(self.tab_relations, "Relations")

        # --- Tab 3: Attributes ---
        self.tab_attributes = QWidget()
        attr_layout = QVBoxLayout(self.tab_attributes)
        self.attribute_editor = AttributeEditorWidget()
        attr_layout.addWidget(self.attribute_editor)
        self.tabs.addTab(self.tab_attributes, "Attributes")

        # Buttons
        btn_layout = QHBoxLayout()
        self.btn_save = QPushButton("Save Changes")
        self.btn_save.clicked.connect(self._on_save)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_save)

        self.layout.addLayout(btn_layout)

        # Internal State
        self._current_event_id = None
        self._current_created_at = 0.0

        # Start disabled until specific event loaded
        self.setEnabled(False)

    def load_event(
        self, event: Event, relations: list = None, incoming_relations: list = None
    ):
        """
        Populates the form with event data and relationships.

        Args:
            event (Event): The event to edit.
            relations (list): List of outgoing relation dicts.
            incoming_relations (list): List of incoming relation dicts.
        """
        self._current_event_id = event.id
        self._current_created_at = event.created_at  # Preserve validation data

        self.name_edit.setText(event.name)
        self.date_edit.setValue(event.lore_date)
        self.type_edit.setCurrentText(event.type)
        self.desc_edit.setPlainText(event.description)

        # Load Attributes
        self.attribute_editor.load_attributes(event.attributes)

        # Load relations
        self.rel_list.clear()

        # Outgoing
        if relations:
            for rel in relations:
                # Format: -> TargetID [Type]
                # In real app, we'd look up Target Name.
                label = f"-> {rel['target_id']} [{rel['rel_type']}]"
                item = QListWidgetItem(label)
                item.setData(Qt.UserRole, rel)
                # Differentiate visually? Maybe standard color.
                self.rel_list.addItem(item)

        # Incoming
        if incoming_relations:
            for rel in incoming_relations:
                # Format: <- SourceID [Type]
                label = f"<- {rel['source_id']} [{rel['rel_type']}]"
                item = QListWidgetItem(label)
                item.setData(Qt.UserRole, rel)
                item.setForeground(Qt.gray)  # Visually distinct
                self.rel_list.addItem(item)

        self.setEnabled(True)

    def _on_save(self):
        """
        Collects data from form fields and emits the `save_requested` signal.
        Emits a dictionary with the updated properties and the ID.
        """
        if not self._current_event_id:
            return

        event_data = {
            "id": self._current_event_id,
            "name": self.name_edit.text(),
            "lore_date": self.date_edit.value(),
            "type": self.type_edit.currentText(),
            "description": self.desc_edit.toPlainText(),
            "attributes": self.attribute_editor.get_attributes(),
        }

        self.save_requested.emit(event_data)

    def _on_add_relation(self):
        """
        Prompts user for relation details and emits signal.

        Shows input dialogs for 'Target ID' and 'Relation Type'.
        If valid input is received, emits `add_relation_requested`.
        """
        if not self._current_event_id:
            return

        target_id, ok = QInputDialog.getText(self, "Add Relation", "Target ID:")
        if not ok or not target_id:
            return

        rel_type, ok = QInputDialog.getItem(
            self,
            "Relation Type",
            "Type:",
            ["caused", "involved", "located_at", "parent_of"],
            0,
            True,
        )
        if not ok:
            return

        # Prompt for Bidirectional
        title = "Bidirectional?"
        msg = "Is this relation mutual (creates reverse link)?"
        reply = QMessageBox.question(self, title, msg, QMessageBox.Yes | QMessageBox.No)
        is_bidirectional = reply == QMessageBox.Yes

        self.add_relation_requested.emit(
            self._current_event_id, target_id, rel_type, is_bidirectional
        )

    def _show_rel_menu(self, pos):
        """Shows context menu for relation items."""
        item = self.rel_list.itemAt(pos)
        if not item:
            return

        menu = QMenu()
        edit_action = menu.addAction("Edit")
        remove_action = menu.addAction("Remove")
        action = menu.exec(self.rel_list.mapToGlobal(pos))

        if action == remove_action:
            self._on_remove_relation_item(item)
        elif action == edit_action:
            self._on_edit_relation(item)

    def _on_remove_relation_item(self, item):
        """Emits remove signal."""
        rel_data = item.data(Qt.UserRole)
        confirm = QMessageBox.question(
            self,
            "Confirm Remove",
            f"Remove relation to {rel_data['target_id']}?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm == QMessageBox.Yes:
            self.remove_relation_requested.emit(rel_data["id"])

    def _on_edit_relation(self, item):
        """Emits update signal after dialogs."""
        rel_data = item.data(Qt.UserRole)

        # Edit Target
        target_id, ok = QInputDialog.getText(
            self, "Edit Relation", "Target ID:", text=rel_data["target_id"]
        )
        if not ok or not target_id:
            return

        # Edit Type
        current_type_idx = 0
        types = ["caused", "involved", "located_at", "parent_of"]
        if rel_data["rel_type"] in types:
            current_type_idx = types.index(rel_data["rel_type"])

        rel_type, ok = QInputDialog.getItem(
            self, "Edit Type", "Type:", types, current_type_idx, True
        )
        if not ok:
            return

        self.update_relation_requested.emit(rel_data["id"], target_id, rel_type)

    def _on_edit_selected_relation(self):
        """Edits the currently selected relation."""
        item = self.rel_list.currentItem()
        if item:
            self._on_edit_relation(item)
        else:
            QMessageBox.information(
                self, "Selection", "Please select a relation to edit."
            )

    def _on_remove_selected_relation(self):
        """Removes the currently selected relation."""
        item = self.rel_list.currentItem()
        if item:
            self._on_remove_relation_item(item)
        else:
            QMessageBox.information(
                self, "Selection", "Please select a relation to remove."
            )
