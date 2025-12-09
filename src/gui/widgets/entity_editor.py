from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QTextEdit,
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
from src.core.entities import Entity
from src.gui.widgets.attribute_editor import AttributeEditorWidget
from src.gui.widgets.wiki_text_edit import WikiTextEdit


class EntityEditorWidget(QWidget):
    """
    A form to edit the details of an Entity.
    Emits 'save_requested' signal with the modified Entity object.
    """

    save_requested = Signal(dict)
    add_relation_requested = Signal(str, str, str, bool)  # src, tgt, type, bi
    remove_relation_requested = Signal(str)
    update_relation_requested = Signal(str, str, str)
    link_clicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(8)
        self.layout.setContentsMargins(16, 16, 16, 16)

        # Form Layout
        # Tabs Layout
        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs)

        # --- Tab 1: Details ---
        self.tab_details = QWidget()
        details_layout = QVBoxLayout(self.tab_details)

        self.form_layout = QFormLayout()
        self.name_edit = QLineEdit()
        self.type_edit = QComboBox()
        self.type_edit.addItems(["Character", "Location", "Faction", "Item", "Concept"])
        self.type_edit.setEditable(True)
        self.desc_edit = WikiTextEdit()
        self.desc_edit.link_clicked.connect(self.link_clicked.emit)

        self.form_layout.addRow("Name:", self.name_edit)
        self.form_layout.addRow("Type:", self.type_edit)
        self.form_layout.addRow("Description:", self.desc_edit)

        details_layout.addLayout(self.form_layout)
        self.tabs.addTab(self.tab_details, "Details")

        # --- Tab 2: Relations ---
        self.tab_relations = QWidget()
        rel_tab_layout = QVBoxLayout(self.tab_relations)

        self.rel_group = QGroupBox("Relationships")
        self.rel_layout = QVBoxLayout()

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
        self._current_entity_id = None
        self._current_created_at = 0.0

        # Start disabled
        self.setEnabled(False)

    def load_entity(
        self, entity: Entity, relations: list = None, incoming_relations: list = None
    ):
        """
        Populates the form with entity data and relations.
        """
        self._current_entity_id = entity.id
        self._current_created_at = entity.created_at

        self.name_edit.setText(entity.name)
        self.type_edit.setCurrentText(entity.type)
        self.desc_edit.setPlainText(entity.description)

        # Load Attributes
        self.attribute_editor.load_attributes(entity.attributes)

        self.rel_list.clear()

        # Outgoing
        if relations:
            for rel in relations:
                label = f"-> {rel['target_id']} [{rel['rel_type']}]"
                item = QListWidgetItem(label)
                item.setData(Qt.UserRole, rel)
                self.rel_list.addItem(item)

        # Incoming
        if incoming_relations:
            for rel in incoming_relations:
                label = f"<- {rel['source_id']} [{rel['rel_type']}]"
                item = QListWidgetItem(label)
                item.setData(Qt.UserRole, rel)
                item.setForeground(Qt.gray)
                self.rel_list.addItem(item)

        self.setEnabled(True)

    def _on_save(self):
        """
        Collects data and emits save signal.
        """
        if not self._current_entity_id:
            return

        entity_data = {
            "id": self._current_entity_id,
            "name": self.name_edit.text(),
            "type": self.type_edit.currentText(),
            "description": self.desc_edit.toPlainText(),
            "attributes": self.attribute_editor.get_attributes(),
        }

        self.save_requested.emit(entity_data)

    def clear(self):
        """Clears the editor."""
        self._current_entity_id = None
        self.name_edit.clear()
        self.desc_edit.clear()
        self.rel_list.clear()  # Clear relations
        self.setEnabled(False)

    def _on_add_relation(self):
        if not self._current_entity_id:
            return

        target_id, ok = QInputDialog.getText(self, "Add Relation", "Target ID:")
        if not ok or not target_id:
            return

        rel_type, ok = QInputDialog.getItem(
            self,
            "Relation Type",
            "Type:",
            ["caused", "involved", "located_at", "parent_of", "member_of", "owns"],
            0,
            True,
        )
        if not ok:
            return

        title = "Bidirectional?"
        msg = "Is this relation mutual?"
        reply = QMessageBox.question(self, title, msg, QMessageBox.Yes | QMessageBox.No)
        is_bidirectional = reply == QMessageBox.Yes

        self.add_relation_requested.emit(
            self._current_entity_id, target_id, rel_type, is_bidirectional
        )

    def _show_rel_menu(self, pos):
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
        rel_data = item.data(Qt.UserRole)
        confirm = QMessageBox.question(
            self,
            "Confirm Remove",
            f"Remove relation to {rel_data.get('target_id', '?')}?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm == QMessageBox.Yes:
            self.remove_relation_requested.emit(rel_data["id"])

    def _on_edit_relation(self, item):
        rel_data = item.data(Qt.UserRole)
        target_id, ok = QInputDialog.getText(
            self, "Edit Relation", "Target ID:", text=rel_data["target_id"]
        )
        if not ok or not target_id:
            return

        # Simple text for now, could be improved
        current_type = rel_data["rel_type"]
        rel_type, ok = QInputDialog.getText(
            self, "Edit Type", "Type:", text=current_type
        )
        if not ok:
            return

        self.update_relation_requested.emit(rel_data["id"], target_id, rel_type)

    def _on_edit_selected_relation(self):
        item = self.rel_list.currentItem()
        if item:
            self._on_edit_relation(item)

    def _on_remove_selected_relation(self):
        item = self.rel_list.currentItem()
        if item:
            self._on_remove_relation_item(item)
