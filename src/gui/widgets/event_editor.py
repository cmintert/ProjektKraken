"""
Event Editor Widget Module.

Provides a form interface for editing event details including name, date,
description, attributes, and relations.
"""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QComboBox,
    QPushButton,
    QHBoxLayout,
    QDoubleSpinBox,
    QGroupBox,
    QListWidget,
    QMessageBox,
    QListWidgetItem,
    QMenu,
)
from PySide6.QtCore import Signal, Qt
from src.core.events import Event
from src.gui.widgets.attribute_editor import AttributeEditorWidget
from src.gui.widgets.wiki_text_edit import WikiTextEdit
from src.gui.widgets.lore_date_widget import LoreDateWidget
from src.gui.widgets.tag_editor import TagEditorWidget
from src.gui.widgets.splitter_tab_inspector import SplitterTabInspector


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
    link_clicked = Signal(str)  # target_name

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

        # Splitter-based tab inspector for vertical stacking
        self.inspector = SplitterTabInspector()
        self.layout.addWidget(self.inspector)

        # --- Tab 1: Details ---
        self.tab_details = QWidget()
        details_layout = QVBoxLayout(self.tab_details)

        self.form_layout = QFormLayout()
        self.name_edit = QLineEdit()

        # Lore date widget with structured input
        self.date_edit = LoreDateWidget()

        self.type_edit = QComboBox()
        self.type_edit.addItems(
            ["generic", "cosmic", "historical", "personal", "session", "combat"]
        )
        self.type_edit.setEditable(True)

        self.desc_edit = WikiTextEdit()
        self.desc_edit.link_clicked.connect(self.link_clicked.emit)

        self.form_layout.addRow("Name:", self.name_edit)
        self.form_layout.addRow("Lore Date:", self.date_edit)

        self.duration_edit = QDoubleSpinBox()
        self.duration_edit.setRange(0.0, 1e9)  # Large range, non-negative
        self.duration_edit.setDecimals(4)
        self.duration_edit.setSuffix(" days")
        self.form_layout.addRow("Duration:", self.duration_edit)
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
        self.inspector.add_tab(self.tab_relations, "Relations")

        # --- Tab 4: Attributes ---
        self.tab_attributes = QWidget()
        attr_layout = QVBoxLayout(self.tab_attributes)
        self.attribute_editor = AttributeEditorWidget()
        attr_layout.addWidget(self.attribute_editor)
        self.inspector.add_tab(self.tab_attributes, "Attributes")

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
        self._calendar_converter = None  # Will be set when calendar loaded

        # Start disabled until specific event loaded
        self.setEnabled(False)

    def set_calendar_converter(self, converter):
        """
        Sets the calendar converter for date formatting.

        Args:
            converter: CalendarConverter instance or None.
        """
        self._calendar_converter = converter
        self.date_edit.set_calendar_converter(converter)

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

        # Store for RelationEditDialog
        if items:
            self._suggestion_items = items
        else:
            self._suggestion_items = []

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
        self.date_edit.set_value(event.lore_date)
        self.duration_edit.setValue(event.lore_duration)
        self.type_edit.setCurrentText(event.type)
        self.desc_edit.set_wiki_text(event.description)

        # Load Attributes (filter out _tags for display)
        display_attrs = {k: v for k, v in event.attributes.items() if k != "_tags"}
        self.attribute_editor.load_attributes(display_attrs)

        # Load Tags
        self.tag_editor.load_tags(event.tags)

        # Load relations
        self.rel_list.clear()

        # Outgoing
        if relations:
            for rel in relations:
                # Format: -> TargetID [Type]
                target_display = rel.get("target_name") or rel["target_id"]
                label = f"-> {target_display} [{rel['rel_type']}]"
                item = QListWidgetItem(label)
                item.setData(Qt.UserRole, rel)
                # Differentiate visually? Maybe standard color.
                self.rel_list.addItem(item)

        # Incoming
        if incoming_relations:
            for rel in incoming_relations:
                # Format: <- SourceID [Type]
                source_display = rel.get("source_name") or rel["source_id"]
                label = f"<- {source_display} [{rel['rel_type']}]"
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

        # Merge tags into attributes
        base_attrs = self.attribute_editor.get_attributes()
        base_attrs["_tags"] = self.tag_editor.get_tags()

        event_data = {
            "id": self._current_event_id,
            "name": self.name_edit.text(),
            "lore_date": self.date_edit.get_value(),
            "lore_duration": self.duration_edit.value(),
            "type": self.type_edit.currentText(),
            "description": self.desc_edit.get_wiki_text(),
            "attributes": base_attrs,
            "tags": self.tag_editor.get_tags(),
        }

        self.save_requested.emit(event_data)

    def _on_add_relation(self):
        """
        Prompts user for relation details and emits signal.
        Uses RelationEditDialog with autocompletion.
        """
        if not self._current_event_id:
            return

        from src.gui.dialogs.relation_dialog import RelationEditDialog

        dlg = RelationEditDialog(
            parent=self, suggestion_items=getattr(self, "_suggestion_items", [])
        )

        if dlg.exec():
            target_id, rel_type, is_bidirectional = dlg.get_data()
            if target_id:
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
        """Emits update signal after dialogs."""
        rel_data = item.data(Qt.UserRole)

        from src.gui.dialogs.relation_dialog import RelationEditDialog

        dlg = RelationEditDialog(
            parent=self,
            target_id=rel_data["target_id"],
            rel_type=rel_data["rel_type"],
            is_bidirectional=False,  # Editing existing
            suggestion_items=getattr(self, "_suggestion_items", []),
        )

        # Hide bidirectional check for editing
        dlg.bi_check.setVisible(False)

        if dlg.exec():
            target_id, rel_type, _ = dlg.get_data()
            if target_id:
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
