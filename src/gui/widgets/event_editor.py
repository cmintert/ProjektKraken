"""
Event Editor Widget Module.

Provides a form interface for editing event details including name, date,
description, attributes, and relations.
"""

import logging
from typing import Any, Optional

from PySide6.QtCore import QPoint, QSize, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from src.core.events import Event
from src.gui.widgets.attribute_editor import AttributeEditorWidget
from src.gui.widgets.compact_date_widget import CompactDateWidget
from src.gui.widgets.compact_duration_widget import CompactDurationWidget
from src.gui.widgets.relation_item_widget import RelationItemWidget
from src.gui.widgets.splitter_tab_inspector import SplitterTabInspector
from src.gui.widgets.standard_buttons import PrimaryButton, StandardButton
from src.gui.widgets.tag_editor import TagEditorWidget
from src.gui.widgets.wiki_text_edit import WikiTextEdit

logger = logging.getLogger(__name__)


class EventEditorWidget(QWidget):
    """
    A form to edit the details of an Event.
    Emits 'save_requested' signal with the modified Event object.
    Emits 'add_relation_requested' signal (source, target, type).
    """

    save_requested = Signal(dict)
    discard_requested = Signal(str)  # item_id to reload
    add_relation_requested = Signal(
        str, str, str, dict, bool
    )  # source_id, target_id, type, attributes, bidirectional
    remove_relation_requested = Signal(str)  # rel_id
    update_relation_requested = Signal(
        str, str, str, dict
    )  # rel_id, target_id, rel_type, attributes, attributes

    # ... (omitted)

    link_clicked = Signal(str)  # target_name
    navigate_to_relation = Signal(str)  # target_id for Go to button
    dirty_changed = Signal(bool)
    current_data_changed = Signal(dict)  # Emits current event data for preview

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Initializes the editor widget with form fields.

        Args:
            parent: The parent widget, if any.
        """
        super().__init__(parent)

        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        # Set size policy to prevent dock collapse
        from PySide6.QtWidgets import QSizePolicy

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        main_layout = QVBoxLayout(self)
        from src.gui.utils.style_helper import StyleHelper

        StyleHelper.apply_form_spacing(main_layout)

        self._is_loading = False
        self._is_dirty = False
        self._calendar_converter = None

        # Splitter-based tab inspector for vertical stacking
        self.inspector = SplitterTabInspector()
        main_layout.addWidget(self.inspector)

        # --- Tab 1: Details ---
        self.tab_details = QWidget()
        details_layout = QVBoxLayout(self.tab_details)
        StyleHelper.apply_compact_spacing(details_layout)

        self.form_layout = QFormLayout()
        # Configure form layout to respect widget minimum sizes
        self.form_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        self.form_layout.setRowWrapPolicy(QFormLayout.DontWrapRows)

        self.name_edit = QLineEdit()

        # Lore date widget with structured input
        self.date_edit = CompactDateWidget()

        self.type_edit = QComboBox()
        self.type_edit.addItems(
            ["generic", "cosmic", "historical", "personal", "session", "combat"]
        )
        self.type_edit.setEditable(True)

        self.desc_edit = WikiTextEdit()
        self.desc_edit.link_clicked.connect(self.link_clicked.emit)
        self.desc_edit.link_added.connect(self._on_wikilink_added)

        self.form_layout.addRow("Name:", self.name_edit)
        self.form_layout.addRow("Lore Date:", self.date_edit)

        # Duration & End Date
        self.duration_widget = CompactDurationWidget()
        self.duration_widget.set_calendar_converter(self._calendar_converter)
        self.duration_widget.value_changed.connect(self._on_duration_changed)

        self.end_date_edit = CompactDateWidget()
        self.end_date_edit.set_calendar_converter(self._calendar_converter)
        self.end_date_edit.value_changed.connect(self._on_end_date_changed)

        self.form_layout.addRow("Duration:", self.duration_widget)
        self.form_layout.addRow("End Date:", self.end_date_edit)

        self.form_layout.addRow("Type:", self.type_edit)
        self.form_layout.addRow("Description:", self.desc_edit)

        details_layout.addLayout(self.form_layout)

        # Add LLM Generation Widget below description in a collapsible group
        from src.gui.widgets.llm_generation_widget import LLMGenerationWidget

        self.llm_group = QGroupBox("LLM Generation")
        self.llm_group.setCheckable(True)
        self.llm_group.setChecked(False)  # Start collapsed
        llm_layout = QVBoxLayout(self.llm_group)
        from src.gui.utils.style_helper import StyleHelper

        StyleHelper.apply_compact_spacing(llm_layout)

        self.llm_generator = LLMGenerationWidget(self, context_provider=self)
        self.llm_generator.text_generated.connect(self._on_text_generated)
        llm_layout.addWidget(self.llm_generator)

        # Connect toggled signal to properly collapse/expand
        def _toggle_llm_section(checked: bool) -> None:
            """Toggle visibility of LLM generation section when checkbox is clicked."""
            self.llm_generator.setVisible(checked)
            if not checked:
                # Collapse to just show checkbox/title
                self.llm_group.setMinimumHeight(20)  # Just checkbox height
                self.llm_group.setMaximumHeight(20)  # Lock to checkbox height
                llm_layout.setContentsMargins(0, 0, 0, 0)
                llm_layout.setSpacing(0)
            else:
                # Restore normal size
                self.llm_group.setMinimumHeight(0)  # No minimum constraint
                self.llm_group.setMaximumHeight(16777215)  # Qt's QWIDGETSIZE_MAX
                StyleHelper.apply_compact_spacing(llm_layout)

        self.llm_group.toggled.connect(_toggle_llm_section)
        _toggle_llm_section(False)  # Start collapsed

        details_layout.addWidget(self.llm_group)

        # Set minimum height on details tab to ensure it doesn't collapse
        self.tab_details.setMinimumHeight(400)
        self.inspector.add_tab(self.tab_details, "Details")

        # Connect Start Date change to Duration Context
        self.date_edit.value_changed.connect(self._on_start_date_changed)

        # Connect modifications to dirty check and live preview
        self.name_edit.textChanged.connect(self._on_field_changed)
        self.date_edit.value_changed.connect(lambda val: self._on_field_changed())
        self.type_edit.editTextChanged.connect(self._on_field_changed)
        self.type_edit.currentIndexChanged.connect(self._on_field_changed)
        self.desc_edit.textChanged.connect(self._on_field_changed)
        self.duration_widget.value_changed.connect(lambda val: self._on_field_changed())

        # --- Tab 2: Tags ---
        self.tab_tags = QWidget()
        tags_layout = QVBoxLayout(self.tab_tags)
        StyleHelper.apply_no_margins(tags_layout)
        self.tag_editor = TagEditorWidget()
        tags_layout.addWidget(self.tag_editor)
        self.inspector.add_tab(self.tab_tags, "Tags")

        # --- Tab 3: Relations ---
        self.tab_relations = QWidget()
        self._setup_relations_tab()
        self.inspector.add_tab(self.tab_relations, "Relations")

        # --- Tab 4: Gallery ---
        self.tab_gallery = QWidget()
        gallery_layout = QVBoxLayout(self.tab_gallery)
        gallery_layout.setContentsMargins(0, 0, 0, 0)
        from src.gui.widgets.gallery_widget import GalleryWidget

        self.gallery = GalleryWidget(parent)  # parent should be main_window
        gallery_layout.addWidget(self.gallery)
        self.inspector.add_tab(self.tab_gallery, "Gallery")

        # --- Tab 5: Attributes ---
        self.tab_attributes = QWidget()
        attr_layout = QVBoxLayout(self.tab_attributes)
        StyleHelper.apply_no_margins(attr_layout)
        self.attribute_editor = AttributeEditorWidget()
        attr_layout.addWidget(self.attribute_editor)
        self.inspector.add_tab(self.tab_attributes, "Attributes")

        # Buttons
        btn_layout = QHBoxLayout()
        self.btn_save = PrimaryButton("Save Changes")
        self.btn_save.setEnabled(False)
        self.btn_save.clicked.connect(self._on_save)

        self.btn_discard = StandardButton("Discard")
        self.btn_discard.setEnabled(False)
        self.btn_discard.clicked.connect(self._on_discard)

        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_discard)
        btn_layout.addWidget(self.btn_save)

        main_layout.addLayout(btn_layout)

        # Internal State
        self._current_event_id = None
        self._current_created_at = 0.0
        self._is_dirty = False

        # Connect signals for dirty tracking
        self._connect_dirty_signals()

        # Start disabled until specific event loaded
        self.setEnabled(False)

    def _setup_relations_tab(self) -> None:
        """Configures the Relations tab with categorized sections."""
        from src.gui.utils.style_helper import StyleHelper

        layout = QVBoxLayout(self.tab_relations)
        StyleHelper.apply_compact_spacing(layout)

        # Helper to create a section
        def create_section(
            title: str, add_slot: Any, placeholder: str = ""
        ) -> tuple[QWidget, QListWidget, StandardButton]:
            """Create a section with title, list widget, and add button."""
            group = QWidget()
            vbox = QVBoxLayout(group)
            vbox.setContentsMargins(0, 0, 0, 0)
            vbox.setSpacing(4)

            # Header
            hbox = QHBoxLayout()
            from PySide6.QtWidgets import QLabel

            lbl = QLabel(title)
            lbl.setStyleSheet("font-weight: bold; color: gray;")
            hbox.addWidget(lbl)

            btn_add = StandardButton("+")
            btn_add.setFixedSize(
                32, 32
            )  # Increased from 24x24 for better touch targets
            btn_add.clicked.connect(add_slot)
            hbox.addWidget(btn_add)
            hbox.addStretch()
            vbox.addLayout(hbox)

            # List
            lst = QListWidget()
            lst.setSpacing(2)
            lst.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            lst.customContextMenuRequested.connect(
                lambda pos: self._show_rel_menu(pos, lst)
            )
            lst.itemDoubleClicked.connect(self._on_edit_relation)
            # Fixed height for compactness, but expandable
            lst.setMinimumHeight(80)

            # Store placeholder for later use
            if placeholder:
                lst.setProperty("placeholderText", placeholder)

            vbox.addWidget(lst)

            return group, lst, btn_add

        # 1. Participants
        self.grp_participants, self.participant_list, self.btn_add_participant = (
            create_section(
                "Participants",
                self._on_add_participant,
                "No participants yet. Click + to link a character or entity.",
            )
        )
        layout.addWidget(self.grp_participants)

        # 2. Locations
        self.grp_locations, self.location_list, self.btn_add_location = create_section(
            "Locations",
            self._on_add_location,
            "No locations specified. Click + to link a place.",
        )
        layout.addWidget(self.grp_locations)

        # 3. Custom Relations (renamed from "Other Relations" for clarity)
        self.grp_relations, self.rel_list, self.btn_add_rel = create_section(
            "Custom Relations",
            self._on_add_relation,
            "No custom relations. Click + to add a link.",
        )
        layout.addWidget(self.grp_relations)

    def _on_add_participant(self) -> None:
        """Quick add participant."""
        self._on_add_relation(rel_type="involved")

    def _on_add_location(self) -> None:
        """Quick add location."""
        self._on_add_relation(rel_type="located_at")

    def _connect_dirty_signals(self) -> None:
        """Connects input widget signals to set_dirty(True)."""
        self.name_edit.textChanged.connect(lambda: self.set_dirty(True))
        self.date_edit.value_changed.connect(lambda: self.set_dirty(True))
        # Duration/End Date logic triggers each other, but ultimately user interaction
        # should trigger dirty. Value changed is fine.
        self.duration_widget.value_changed.connect(lambda: self.set_dirty(True))
        self.type_edit.currentTextChanged.connect(lambda: self.set_dirty(True))
        self.desc_edit.textChanged.connect(lambda: self.set_dirty(True))
        self.tag_editor.tags_changed.connect(lambda: self.set_dirty(True))
        self.attribute_editor.attributes_changed.connect(lambda: self.set_dirty(True))

    def set_dirty(self, dirty: bool) -> None:
        """
        Sets the dirty state of the editor.

        Args:
            dirty (bool): True if changes are unsaved, False otherwise.
        """
        if self._current_event_id is None and dirty:
            return

        if self._is_dirty != dirty:
            self._is_dirty = dirty
            self.dirty_changed.emit(dirty)
            self.btn_save.setEnabled(dirty)
            self.btn_discard.setEnabled(dirty)
            # Maybe change button text or style?
            if dirty:
                self.btn_save.setText("Save Changes *")
            else:
                self.btn_save.setText("Save Changes")

    def has_unsaved_changes(self) -> bool:
        """Returns True if the editor has unsaved changes."""
        return self._is_dirty

    def _on_start_date_changed(self, new_start: float) -> None:
        """Updates duration widget context and recalculates end date."""
        self.duration_widget.set_start_date(new_start)
        # Re-calc End Date based on current duration (preserved)
        current_duration = self.duration_widget.get_value()
        self.end_date_edit.set_value(new_start + current_duration)

    def _on_duration_changed(self, duration: float) -> None:
        """Syncs End Date when Duration changes."""
        start = self.date_edit.get_value()
        self.end_date_edit.blockSignals(True)
        self.end_date_edit.set_value(start + duration)
        self.end_date_edit.blockSignals(False)

    def _on_end_date_changed(self, end_date: float) -> None:
        """Syncs Duration when End Date changes."""
        start = self.date_edit.get_value()
        duration = max(0.0, end_date - start)
        self.duration_widget.blockSignals(True)
        self.duration_widget.set_value(duration)
        self.duration_widget.blockSignals(False)

    def set_calendar_converter(self, converter: Any) -> None:
        """
        Sets the calendar converter for date formatting.

        Args:
            converter: CalendarConverter instance or None.
        """
        self._calendar_converter = converter
        self.date_edit.set_calendar_converter(converter)
        if hasattr(self, "duration_widget"):
            self.duration_widget.set_calendar_converter(converter)
            self.end_date_edit.set_calendar_converter(converter)

    def update_suggestions(
        self, items: list[tuple[str, str, str]] = None, names: list[str] = None
    ) -> None:
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

    def load_event(
        self, event: Event, relations: list = None, incoming_relations: list = None
    ) -> None:
        """
        Populates the form with event data and relationships.

        Args:
            event (Event): The event to edit.
            relations (list): List of outgoing relation dicts.
            incoming_relations (list): List of incoming relation dicts.
        """
        self._current_event_id = event.id
        self._current_created_at = event.created_at  # Preserve validation data

        self._is_loading = True
        try:
            # Block signals to prevent dirty trigger during load
            # Block signals to prevent dirty trigger during load
            self.name_edit.blockSignals(True)
            self.date_edit.blockSignals(True)
            self.duration_widget.blockSignals(True)
            self.end_date_edit.blockSignals(True)
            self.type_edit.blockSignals(True)
            self.desc_edit.blockSignals(True)
            # Custom widgets might not need blocking if we don't
            # connect to them directly or emit on programmatic set.
            # TagEditor and AttributeEditor emit on programmatic load usually?
            # Let's check their code.. load_tags calls clear() -> might trigger?
            # TagEditor.load_tags clears and adds items. It does NOT emit tags_changed.
            # AttributeEditor.load_attributes sets _block_signals=True internally.

            self.name_edit.setText(event.name)
            self.date_edit.set_value(event.lore_date)

            # Initialize duration widgets
            self.duration_widget.set_start_date(event.lore_date)
            self.duration_widget.set_value(event.lore_duration)
            self.end_date_edit.set_value(event.lore_date + event.lore_duration)

            self.type_edit.setCurrentText(event.type)
            self.desc_edit.set_wiki_text(event.description)

            # Load Attributes (filter out _tags for display)
            display_attrs = {k: v for k, v in event.attributes.items() if k != "_tags"}
            self.attribute_editor.load_attributes(display_attrs)

            # Load Tags
            self.tag_editor.load_tags(event.tags)

            # Load Gallery
            self.gallery.set_owner("event", event.id)

            # Load relations
            self.rel_list.clear()
            self.participant_list.clear()
            self.location_list.clear()

            # Helper to create widget and item
            def add_relation_item(
                list_widget: QListWidget, rel: dict, prefix: str = "→"
            ) -> None:
                """Add a relation item to the specified list widget."""
                # Determine display name
                if prefix == "→":
                    target_display = rel.get("target_name") or rel["target_id"]
                    other_id = rel["target_id"]
                else:
                    target_display = rel.get("source_name") or rel["source_id"]
                    other_id = rel["source_id"]

                label = f"{prefix} {target_display} [{rel['rel_type']}]"

                # Create custom widget with Go to button
                widget = RelationItemWidget(
                    label=label,
                    target_id=other_id,
                    target_name=target_display,
                    attributes=rel.get("attributes"),
                )
                widget.go_to_clicked.connect(
                    lambda tid, tn: self.navigate_to_relation.emit(tid)
                )

                if prefix == "←":
                    widget.label.setStyleSheet("color: gray;")

                # Create list item
                item = QListWidgetItem()
                item.setData(Qt.ItemDataRole.UserRole, rel)
                item.setSizeHint(QSize(200, 36))

                list_widget.addItem(item)
                list_widget.setItemWidget(item, widget)

            # Outgoing
            if relations:
                for rel in relations:
                    rtype = rel.get("rel_type")
                    if rtype in ("involved", "participated_in", "member_of"):
                        add_relation_item(self.participant_list, rel, "→")
                    elif rtype == "located_at":
                        add_relation_item(self.location_list, rel, "→")
                    else:
                        add_relation_item(self.rel_list, rel, "→")

            # Incoming (Always goes to Other Relations for now,
            # or maybe context dependent?)
            # Usually incoming are less structural context and more backlinks.
            if incoming_relations:
                for rel in incoming_relations:
                    add_relation_item(self.rel_list, rel, "←")

            # Unblock signals
            self.name_edit.blockSignals(False)
            self.date_edit.blockSignals(False)
            self.duration_widget.blockSignals(False)
            self.end_date_edit.blockSignals(False)
            self.type_edit.blockSignals(False)
            self.desc_edit.blockSignals(False)

            self.set_dirty(False)
            self.setEnabled(True)
        finally:
            self._is_loading = False

    def _on_save(self) -> None:
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
            "lore_duration": self.duration_widget.get_value(),
            "type": self.type_edit.currentText(),
            "description": self.desc_edit.get_wiki_text(),
            "attributes": base_attrs,
            "tags": self.tag_editor.get_tags(),
        }

        self.save_requested.emit(event_data)
        self.set_dirty(False)

    def _on_discard(self) -> None:
        """
        Discards changes by emitting signal to reload the current event.
        """
        if not self._current_event_id:
            return

        self.discard_requested.emit(self._current_event_id)

    def _on_add_relation(self, rel_type: Any = "involved") -> None:
        """
        Prompts user for relation details and emits signal.
        Uses RelationEditDialog with autocompletion.
        """
        if not self._current_event_id:
            return

        # Handle signals passing 'checked' boolean
        if isinstance(rel_type, bool):
            rel_type = "involved"

        from src.gui.dialogs.relation_dialog import RelationEditDialog

        dlg = RelationEditDialog(
            parent=self,
            rel_type=rel_type,
            suggestion_items=getattr(self, "_suggestion_items", []),
            calendar_converter=self._calendar_converter,
            source_event_date=(
                self.date_edit.get_value() if self._current_event_id else None
            ),
            source_event_name=self.name_edit.text() if self._current_event_id else None,
        )

        if dlg.exec():
            target_id, rel_type, is_bidirectional, attributes = dlg.get_data()
            if target_id:
                self.add_relation_requested.emit(
                    self._current_event_id,
                    target_id,
                    rel_type,
                    attributes,
                    is_bidirectional,
                )

    def _show_rel_menu(self, pos: QPoint, list_widget: QListWidget = None) -> None:
        """Shows context menu for relation items."""
        # Check if list_widget is passed (from new lambda) or use default (legacy/safe)
        target_list = list_widget or self.rel_list

        item = target_list.itemAt(pos)
        if not item:
            return

        menu = QMenu()
        edit_action = menu.addAction("Edit")
        remove_action = menu.addAction("Remove")
        action = menu.exec(target_list.mapToGlobal(pos))

        if action == remove_action:
            self._on_remove_relation_item(item)
        elif action == edit_action:
            self._on_edit_relation(item)

    def _on_remove_relation_item(self, item: QListWidgetItem) -> None:
        """Emits remove signal."""
        rel_data = item.data(Qt.ItemDataRole.UserRole)
        target_id = rel_data.get("target_id", "?")
        target_name = rel_data.get("target_name", target_id)

        confirm = QMessageBox.question(
            self,
            "Confirm Remove",
            f"Remove relation to {target_name}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.remove_relation_requested.emit(rel_data["id"])

    def _on_edit_relation(self, item: QListWidgetItem) -> None:
        """Emits update signal after dialogs."""
        rel_data = item.data(Qt.ItemDataRole.UserRole)

        from src.gui.dialogs.relation_dialog import RelationEditDialog

        dlg = RelationEditDialog(
            parent=self,
            target_id=rel_data["target_id"],
            rel_type=rel_data["rel_type"],
            is_bidirectional=False,  # Editing existing
            attributes=rel_data.get("attributes"),  # Pass existing attributes
            suggestion_items=getattr(self, "_suggestion_items", []),
            calendar_converter=self._calendar_converter,
            source_event_date=(
                self.date_edit.get_value() if self._current_event_id else None
            ),
            source_event_name=(
                self.name_edit.text() if self._current_event_id else None
            ),
        )

        # Hide bidirectional check for editing
        dlg.bi_check.setVisible(False)

        if dlg.exec():
            target_id, rel_type, _, attributes = dlg.get_data()
            if target_id:
                self.update_relation_requested.emit(
                    rel_data["id"], target_id, rel_type, attributes
                )

    def _on_edit_selected_relation(self) -> None:
        """Edits the currently selected relation."""
        item = self.rel_list.currentItem()
        if item:
            self._on_edit_relation(item)
        else:
            QMessageBox.information(
                self, "Selection", "Please select a relation to edit."
            )

    def _on_remove_selected_relation(self) -> None:
        """Removes the currently selected relation."""
        item = self.rel_list.currentItem()
        if item:
            self._on_remove_relation_item(item)
        else:
            QMessageBox.information(
                self, "Selection", "Please select a relation to remove."
            )

    def get_generation_context(self) -> dict:
        """
        Get context for LLM generation.

        Returns:
            dict: Context dictionary with 'name', 'type', 'lore_date', etc.
        """
        context = {
            "name": self.name_edit.text(),
            "type": self.type_edit.currentText(),
            "existing_description": self.desc_edit.toPlainText(),
        }

        # Add formatted date if available
        if hasattr(self.date_edit, "lbl_preview"):
            text = self.date_edit.lbl_preview.text()
            if text:
                context["lore_date"] = text

        return context

    def _on_field_changed(self) -> None:
        """Marks the editor as dirty and emits live preview signal."""
        if not self._is_loading:
            self.set_dirty(True)  # Use set_dirty to properly enable save button
            self._emit_current_data()

    def _emit_current_data(self) -> None:
        """Emits the current form data for live preview."""
        if self._is_loading:
            return

        try:
            data = {
                "id": self._current_event_id,
                "name": self.name_edit.text(),
                "lore_date": self.date_edit.get_value(),
                "type": self.type_edit.currentText(),
                "description": self.desc_edit.toPlainText(),
                "lore_duration": self.duration_widget.get_value(),
                # Include other fields if necessary for preview
                # (e.g. attributes not yet)
            }
            self.current_data_changed.emit(data)
        except (AttributeError, RuntimeError) as e:
            # Widgets may not be fully initialized during loading or partial state
            logger.debug(f"Could not emit current data: {e}")

    def _on_text_generated(self, text: str) -> None:
        """
        Handle text generated from LLM.

        Appends generated text to the description field.

        Args:
            text: Generated text from LLM.
        """
        if not text:
            return

        # Get current description
        current = self.desc_edit.toPlainText()

        # Append generated text with newline separator if there's existing content
        if current.strip():
            new_text = current + "\n\n" + text
        else:
            new_text = text

        # Update description
        self.desc_edit.setPlainText(new_text)

        # Mark as dirty
        self.set_dirty(True)

    def minimumSizeHint(self) -> QSize:
        """
        Override to prevent dock collapse.

        Returns:
            QSize: Minimum size for usable event editor.
        """
        return QSize(300, 200)  # Width for form labels, height for controls

    def sizeHint(self) -> QSize:
        """
        Preferred size for the event editor.

        Returns:
            QSize: Comfortable working size for editing events.
        """
        return QSize(400, 600)  # Ideal size for editing

    def _on_wikilink_added(self, target_id: str, target_name: str) -> None:
        """
        Handles a new wikilink addition.
        Checks setting and prompts for relation creation if enabled.
        """
        from PySide6.QtCore import QSettings

        from src.app.constants import (
            SETTINGS_AUTO_RELATION_KEY,
            WINDOW_SETTINGS_APP,
            WINDOW_SETTINGS_KEY,
        )
        from src.gui.dialogs.relation_dialog import RelationEditDialog

        settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
        if not settings.value(SETTINGS_AUTO_RELATION_KEY, False, type=bool):
            return

        if not self._current_event_id:
            return  # Can't add relation if we don't exist yet

        # Open Dialog
        dialog = RelationEditDialog(
            self, target_id=target_id, rel_type="mentions", is_bidirectional=False
        )
        # Lock target field since it comes from the link
        dialog.target_edit.setEnabled(False)

        if dialog.exec():
            _, rel_type, is_bidirectional, attributes = dialog.get_data()
            self.add_relation_requested.emit(
                self._current_event_id,
                target_id,
                rel_type,
                attributes,
                is_bidirectional,
            )
