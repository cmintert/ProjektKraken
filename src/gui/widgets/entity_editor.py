"""
Entity Editor Widget Module.

Provides a GUI form for creating and editing Entity objects with support
for wiki-style text editing, custom attributes, tags, and relationship management.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from src.core.entities import Entity
from src.gui.widgets.attribute_editor import AttributeEditorWidget
from src.gui.widgets.splitter_tab_inspector import SplitterTabInspector
from src.gui.widgets.standard_buttons import PrimaryButton, StandardButton
from src.gui.widgets.tag_editor import TagEditorWidget
from src.gui.widgets.wiki_text_edit import WikiTextEdit


class EntityEditorWidget(QWidget):
    """
    A form to edit the details of an Entity.
    Emits 'save_requested' signal with the modified Entity object.
    """

    save_requested = Signal(dict)
    discard_requested = Signal(str)  # item_id to reload
    add_relation_requested = Signal(str, str, str, bool)  # src, tgt, type, bi
    remove_relation_requested = Signal(str)
    update_relation_requested = Signal(str, str, str)
    link_clicked = Signal(str)
    dirty_changed = Signal(bool)

    def __init__(self, parent=None):
        """
        Initializes the EntityEditorWidget.

        Args:
            parent (QWidget, optional): The parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)

        # Set size policy to prevent dock collapse
        from PySide6.QtWidgets import QSizePolicy

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.layout = QVBoxLayout(self)
        from src.gui.utils.style_helper import StyleHelper

        StyleHelper.apply_form_spacing(self.layout)

        # Splitter-based tab inspector for vertical stacking
        self.inspector = SplitterTabInspector()
        self.layout.addWidget(self.inspector)

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
        self.inspector.add_tab(self.tab_details, "Details")

        # --- Tab 2: Tags ---
        self.tab_tags = QWidget()
        tags_layout = QVBoxLayout(self.tab_tags)
        self.tag_editor = TagEditorWidget()
        tags_layout.addWidget(self.tag_editor)
        self.inspector.add_tab(self.tab_tags, "Tags")

        # --- Tab 3: Relations ---
        self.tab_relations = QWidget()
        rel_tab_layout = QVBoxLayout(self.tab_relations)

        # Buttons first
        rel_btn_layout = QHBoxLayout()
        self.btn_add_rel = StandardButton("Add Relation")
        self.btn_add_rel.clicked.connect(self._on_add_relation)
        rel_btn_layout.addWidget(self.btn_add_rel)

        self.btn_edit_rel = StandardButton("Edit")
        self.btn_edit_rel.clicked.connect(self._on_edit_selected_relation)
        rel_btn_layout.addWidget(self.btn_edit_rel)

        self.btn_remove_rel = StandardButton("Remove")
        self.btn_remove_rel.setStyleSheet(StyleHelper.get_destructive_button_style())
        self.btn_remove_rel.clicked.connect(self._on_remove_selected_relation)
        rel_btn_layout.addWidget(self.btn_remove_rel)

        rel_btn_layout.addStretch()
        rel_tab_layout.addLayout(rel_btn_layout)

        # List second
        self.rel_list = QListWidget()
        self.rel_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.rel_list.customContextMenuRequested.connect(self._show_rel_menu)
        self.rel_list.itemDoubleClicked.connect(self._on_edit_relation)
        rel_tab_layout.addWidget(self.rel_list)

        self.inspector.add_tab(self.tab_relations, "Relations")

        # --- Tab 4: Gallery ---
        self.tab_gallery = QWidget()
        gallery_layout = QVBoxLayout(self.tab_gallery)
        gallery_layout.setContentsMargins(0, 0, 0, 0)
        from src.gui.widgets.gallery_widget import GalleryWidget

        self.gallery = GalleryWidget(parent)
        gallery_layout.addWidget(self.gallery)
        self.inspector.add_tab(self.tab_gallery, "Gallery")

        # --- Tab 5: Attributes ---
        self.tab_attributes = QWidget()
        attr_layout = QVBoxLayout(self.tab_attributes)
        self.attribute_editor = AttributeEditorWidget()
        attr_layout.addWidget(self.attribute_editor)
        self.inspector.add_tab(self.tab_attributes, "Attributes")

        # Buttons
        btn_layout = QHBoxLayout()
        self.btn_save = PrimaryButton("Save Changes")
        self.btn_save.clicked.connect(self._on_save)

        self.btn_discard = StandardButton("Discard")
        self.btn_discard.setEnabled(False)
        self.btn_discard.clicked.connect(self._on_discard)

        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_discard)
        btn_layout.addWidget(self.btn_save)

        self.layout.addLayout(btn_layout)

        # Internal State
        self._current_entity_id = None
        self._current_created_at = 0.0
        self._is_dirty = False

        self._connect_dirty_signals()

        # Start disabled
        self.setEnabled(False)

    def _connect_dirty_signals(self):
        """Connects inputs to dirty state."""
        self.name_edit.textChanged.connect(lambda: self.set_dirty(True))
        self.type_edit.currentTextChanged.connect(lambda: self.set_dirty(True))
        self.desc_edit.textChanged.connect(lambda: self.set_dirty(True))
        self.tag_editor.tags_changed.connect(lambda: self.set_dirty(True))
        self.attribute_editor.attributes_changed.connect(lambda: self.set_dirty(True))

    def set_dirty(self, dirty: bool):
        """Sets dirty state and updates UI."""
        if self._current_entity_id is None and dirty:
            return

        if self._is_dirty != dirty:
            self._is_dirty = dirty
            self.dirty_changed.emit(dirty)
            self.btn_save.setEnabled(dirty)
            self.btn_discard.setEnabled(dirty)
            if dirty:
                self.btn_save.setText("Save Changes *")
            else:
                self.btn_save.setText("Save Changes")

    def has_unsaved_changes(self) -> bool:
        """Returns True if dirty."""
        return self._is_dirty

    def update_suggestions(
        self, items: list[tuple[str, str, str]] = None, names: list[str] = None
    ):
        """
        Updates the autocomplete suggestions for the description field.

        Can be called with either:
        - items: List of (id, name, type) tuples for ID-based completion
        - names: List of names for legacy name-based completion

        Args:
            items: List of (id, name, type) tuples for entities/events.
            names: Legacy list of names (for backward compatibility).
        """
        self.desc_edit.set_completer(items=items, names=names)

        # Re-render wiki text if already loaded to apply new validation
        if self.desc_edit._current_wiki_text:
            self.desc_edit.set_wiki_text(self.desc_edit._current_wiki_text)

        # Store for RelationEditDialog
        if items:
            self._suggestion_items = items
        else:
            self._suggestion_items = []

    def load_entity(
        self, entity: Entity, relations: list = None, incoming_relations: list = None
    ):
        """
        Populates the form with entity data and relations.
        """
        self._current_entity_id = entity.id
        self._current_created_at = entity.created_at

        # Block signals
        self.name_edit.blockSignals(True)
        self.type_edit.blockSignals(True)
        self.desc_edit.blockSignals(True)

        self.name_edit.setText(entity.name)
        self.type_edit.setCurrentText(entity.type)
        self.desc_edit.set_wiki_text(entity.description)

        # Load Attributes (filter out _tags for display)
        display_attrs = {k: v for k, v in entity.attributes.items() if k != "_tags"}
        self.attribute_editor.load_attributes(display_attrs)

        # Load Tags
        self.tag_editor.load_tags(entity.tags)

        # Load Gallery
        self.gallery.set_owner("entity", entity.id)

        self.rel_list.clear()

        # Outgoing
        if relations:
            for rel in relations:
                target_display = rel.get("target_name") or rel["target_id"]
                label = f"-> {target_display} [{rel['rel_type']}]"
                item = QListWidgetItem(label)
                item.setData(Qt.UserRole, rel)
                self.rel_list.addItem(item)

        # Incoming
        if incoming_relations:
            for rel in incoming_relations:
                source_display = rel.get("source_name") or rel["source_id"]
                label = f"<- {source_display} [{rel['rel_type']}]"
                item = QListWidgetItem(label)
                item.setData(Qt.UserRole, rel)
                item.setForeground(Qt.gray)
                self.rel_list.addItem(item)

        self.setEnabled(True)

        # Unblock & Reset
        self.name_edit.blockSignals(False)
        self.type_edit.blockSignals(False)
        self.desc_edit.blockSignals(False)
        self.set_dirty(False)

    def _on_save(self):
        """
        Collects data and emits save signal.
        """
        if not self._current_entity_id:
            return

        # Merge tags into attributes
        base_attrs = self.attribute_editor.get_attributes()
        base_attrs["_tags"] = self.tag_editor.get_tags()

        entity_data = {
            "id": self._current_entity_id,
            "name": self.name_edit.text(),
            "type": self.type_edit.currentText(),
            "description": self.desc_edit.get_wiki_text(),
            "attributes": base_attrs,
            "tags": self.tag_editor.get_tags(),
        }

        self.save_requested.emit(entity_data)
        self.set_dirty(False)

    def _on_discard(self):
        """
        Discards changes by emitting signal to reload the current entity.
        """
        if not self._current_entity_id:
            return

        self.discard_requested.emit(self._current_entity_id)

    def clear(self):
        """Clears the editor."""
        self._current_entity_id = None
        self.name_edit.clear()
        self.desc_edit.clear()
        self.rel_list.clear()  # Clear relations
        self.setEnabled(False)

    def _on_add_relation(self):
        """
        Handles adding a new relation.
        Uses RelationEditDialog with autocompletion.
        """
        if not self._current_entity_id:
            return

        from src.gui.dialogs.relation_dialog import RelationEditDialog

        dlg = RelationEditDialog(
            parent=self, suggestion_items=getattr(self, "_suggestion_items", [])
        )

        if dlg.exec():
            target_id, rel_type, is_bidirectional = dlg.get_data()
            if target_id:
                self.add_relation_requested.emit(
                    self._current_entity_id, target_id, rel_type, is_bidirectional
                )

    def _show_rel_menu(self, pos):
        """
        Shows a context menu for relation items.

        Args:
            pos (QPoint): The position where the menu should appear.
        """
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
        """
        Handles removing a relation item.

        Args:
            item (QListWidgetItem): The relation item to remove.
        """
        rel_data = item.data(Qt.UserRole)
        target_id = rel_data.get("target_id", "?")
        target_name = rel_data.get("target_name", target_id)

        confirm = QMessageBox.question(
            self,
            "Confirm Remove",
            f"Remove relation to {target_name}?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm == QMessageBox.Yes:
            self.remove_relation_requested.emit(rel_data["id"])

    def _on_edit_relation(self, item):
        """
        Handles editing a relation item.

        Args:
            item (QListWidgetItem): The relation item to edit.
        """
        rel_data = item.data(Qt.UserRole)

        from src.gui.dialogs.relation_dialog import RelationEditDialog

        dlg = RelationEditDialog(
            parent=self,
            target_id=rel_data["target_id"],
            rel_type=rel_data["rel_type"],
            is_bidirectional=False,
            # Editing existing relation implies directional update typically
            suggestion_items=getattr(self, "_suggestion_items", []),
        )

        # Hide bidirectional check for editing as logic might be complex
        # handling existing reverse links
        dlg.bi_check.setVisible(False)

        if dlg.exec():
            target_id, rel_type, _ = dlg.get_data()
            if target_id:
                self.update_relation_requested.emit(rel_data["id"], target_id, rel_type)

    def _on_edit_selected_relation(self):
        """
        Handles editing the currently selected relation.
        """
        item = self.rel_list.currentItem()
        if item:
            self._on_edit_relation(item)

    def _on_remove_selected_relation(self):
        """
        Handles removing the currently selected relation.
        """
        item = self.rel_list.currentItem()
        if item:
            self._on_remove_relation_item(item)

    def minimumSizeHint(self):
        """
        Override to prevent dock collapse.

        Returns:
            QSize: Minimum size for usable entity editor.
        """
        from PySide6.QtCore import QSize

        return QSize(300, 200)  # Width for form labels, height for controls

    def sizeHint(self):
        """
        Preferred size for the entity editor.

        Returns:
            QSize: Comfortable working size for editing entities.
        """
        from PySide6.QtCore import QSize

        return QSize(400, 600)  # Ideal size for editing
