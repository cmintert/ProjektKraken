"""Entity Editor Widget Module.

Provides a GUI form for creating and editing Entity objects with support for wiki-style
text editing, custom attributes, tags, and relationship management.
"""

import logging
import traceback
from typing import Optional

from PySide6.QtCore import QPoint, QSize, Qt, Signal, Slot
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
from src.core.summary_data import SummaryData
from src.gui.mixins.autosave_mixin import AutoSaveManager
from src.gui.widgets.attribute_editor import AttributeEditorWidget
from src.gui.widgets.relation_item_widget import RelationItemWidget
from src.gui.widgets.splitter_tab_inspector import SplitterTabInspector
from src.gui.widgets.standard_buttons import PrimaryButton, StandardButton
from src.gui.widgets.summary_widget import SummaryWidget
from src.gui.widgets.tag_editor import TagEditorWidget
from src.gui.widgets.wiki_text_edit import WikiTextEdit

logger = logging.getLogger(__name__)


class EntityEditorWidget(QWidget):
    """A form to edit the details of an Entity.

    Emits 'save_requested' signal with the modified Entity object.
    """

    save_requested = Signal(dict)
    discard_requested = Signal(str)  # item_id to reload
    inject_requested = Signal(
        dict
    )  # Signals that main window should run the inject command
    add_relation_requested = Signal(
        str, str, str, dict, bool
    )  # src, tgt, type, attrs, bi
    remove_relation_requested = Signal(str)
    update_relation_requested = Signal(str, str, str, dict)
    link_clicked = Signal(str)
    navigate_to_relation = Signal(str)  # target_id for Go to button
    dirty_changed = Signal(bool)
    return_to_present_requested = Signal()  # Request to exit past/future view
    inject_ui_requested = Signal(str)  # entity_id
    summary_generation_requested = Signal(object)  # entity object

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initializes the EntityEditorWidget.

        Args:
            parent (QWidget, optional): The parent widget. Defaults to None.

        """
        super().__init__(parent)
        self.autosave_manager = AutoSaveManager(self)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        # Set size policy to prevent dock collapse
        from PySide6.QtWidgets import QSizePolicy

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        main_layout = QVBoxLayout(self)
        from src.gui.utils.style_helper import StyleHelper

        StyleHelper.apply_form_spacing(main_layout)

        # Splitter-based tab inspector for vertical stacking
        self.inspector = SplitterTabInspector()
        main_layout.addWidget(self.inspector)

        # --- Tab 1: Details ---
        # --- Tab 1: Details ---
        self.tab_details = QWidget()

        # Scroll Area Wrapper
        from PySide6.QtWidgets import QFrame, QScrollArea

        tab_layout = QVBoxLayout(self.tab_details)
        tab_layout.setContentsMargins(0, 0, 0, 0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setStyleSheet(StyleHelper.get_scroll_area_style())

        self.details_container = QWidget()
        details_layout = QVBoxLayout(self.details_container)
        StyleHelper.apply_compact_spacing(details_layout)

        self.scroll_area.setWidget(self.details_container)
        tab_layout.addWidget(self.scroll_area)

        # Header with Name and inject button
        header_layout = QHBoxLayout()
        self.form_layout = QFormLayout()
        self.form_layout.setVerticalSpacing(12)
        self.form_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        self.form_layout.setRowWrapPolicy(QFormLayout.DontWrapRows)
        self.form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # Inject Button (QToolButton with Menu)
        from PySide6.QtWidgets import QToolButton

        self.btn_inject = QToolButton()
        self.btn_inject.setText("Fast Inject")  # Down arrow
        self.btn_inject.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.btn_inject.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.btn_inject.setStyleSheet(
            StyleHelper.get_tool_button_style()
            + " QToolButton::menu-indicator { image: none; }"
        )

        self.inject_menu = QMenu(self.btn_inject)
        self.btn_inject.setMenu(self.inject_menu)
        self.inject_menu.aboutToShow.connect(self._populate_inject_menu)

        # Connect to theme changes
        from src.core.theme_manager import ThemeManager

        ThemeManager().theme_changed.connect(self._on_theme_changed)

        # We'll place it at the top right, or embedded in form row?
        # Plan said "beside Name or separate header row".
        # Let's put it on top right of the tab.
        header_layout.addStretch()
        header_layout.addWidget(self.btn_inject)

        details_layout.addLayout(header_layout)

        self.name_edit = QLineEdit()
        self.type_edit = QComboBox()
        from PySide6.QtWidgets import QSizePolicy

        self.type_edit.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.type_edit.addItems(["Character", "Location", "Faction", "Item", "Concept"])
        self.type_edit.setEditable(True)
        self.desc_edit = WikiTextEdit()
        self.desc_edit.link_clicked.connect(self.link_clicked.emit)
        self.desc_edit.link_added.connect(self._on_wikilink_added)

        self.form_layout.addRow("Name:", self.name_edit)
        self.form_layout.addRow("Type:", self.type_edit)
        self.form_layout.addRow("Description:", self.desc_edit)

        # Add Timeline Display Widget (above LLM section)
        from src.gui.widgets.timeline_display_widget import TimelineDisplayWidget

        from PySide6.QtWidgets import QCheckBox

        self.timeline_container = QWidget()
        timeline_outer_layout = QVBoxLayout(self.timeline_container)
        timeline_outer_layout.setContentsMargins(0, 0, 0, 0)
        timeline_outer_layout.setSpacing(4)

        self.timeline_checkbox = QCheckBox("")  # Text in form label
        self.timeline_checkbox.setStyleSheet(StyleHelper.get_checkbox_style())
        timeline_outer_layout.addWidget(self.timeline_checkbox)

        self.timeline_display = TimelineDisplayWidget()
        self.timeline_display.setVisible(False)
        timeline_outer_layout.addWidget(self.timeline_display)

        self.timeline_checkbox.toggled.connect(self.timeline_display.setVisible)

        self.form_layout.addRow("Timeline:", self.timeline_container)

        # Add Summary Widget (Collapsible)
        # Add Summary Widget (Collapsible)
        self.summary_container = QWidget()
        summary_outer_layout = QVBoxLayout(self.summary_container)
        summary_outer_layout.setContentsMargins(0, 0, 0, 0)
        summary_outer_layout.setSpacing(4)

        self.summary_checkbox = QCheckBox("")
        self.summary_checkbox.setStyleSheet(StyleHelper.get_checkbox_style())
        summary_outer_layout.addWidget(self.summary_checkbox)

        self.summary_widget = SummaryWidget()
        self.summary_widget.setVisible(False)
        self.summary_widget.generate_requested.connect(
            self._on_summary_generate_requested
        )
        summary_outer_layout.addWidget(self.summary_widget)

        self.summary_checkbox.toggled.connect(self.summary_widget.setVisible)

        self.form_layout.addRow("Summary:", self.summary_container)

        # Add LLM Generation Widget below description in a collapsible group
        from src.gui.widgets.llm_generation_widget import LLMGenerationWidget

        self.llm_container = QWidget()
        llm_outer_layout = QVBoxLayout(self.llm_container)
        llm_outer_layout.setContentsMargins(0, 0, 0, 0)
        llm_outer_layout.setSpacing(4)

        self.llm_checkbox = QCheckBox("")
        self.llm_checkbox.setStyleSheet(StyleHelper.get_checkbox_style())
        llm_outer_layout.addWidget(self.llm_checkbox)

        self.llm_generator = LLMGenerationWidget(self, context_provider=self)
        self.llm_generator.setVisible(False)
        self.llm_generator.text_generated.connect(self._on_text_generated)
        llm_outer_layout.addWidget(self.llm_generator)

        self.llm_checkbox.toggled.connect(self.llm_generator.setVisible)

        self.form_layout.addRow("LLM Generation:", self.llm_container)

        details_layout.addLayout(self.form_layout)

        self.inspector.add_tab(self.tab_details, "Details")

        # --- Tab 2: Tags ---
        self.tab_tags = QWidget()
        tags_layout = QVBoxLayout(self.tab_tags)
        StyleHelper.apply_no_margins(tags_layout)
        self.tag_editor = TagEditorWidget()
        tags_layout.addWidget(self.tag_editor)
        self.inspector.add_tab(self.tab_tags, "Tags")

        # --- Tab 3: Relations ---
        self.tab_relations = QWidget()
        rel_tab_layout = QVBoxLayout(self.tab_relations)
        StyleHelper.apply_compact_spacing(rel_tab_layout)

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
        self.rel_list.setSpacing(2)  # Add spacing between items
        self.rel_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
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
        StyleHelper.apply_no_margins(attr_layout)
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

        main_layout.addLayout(btn_layout)

        # Internal State
        self._current_entity_id = None
        self._current_created_at = 0.0
        self._is_dirty = False
        self._is_loading = False  # Guard against dirty during load

        self._connect_dirty_signals()

        # Start disabled
        self.setEnabled(False)
        self.summary_service = None

    def set_summary_service(self, service) -> None:
        """Sets the summary service for generation and staleness checks."""
        self.summary_service = service

    def _connect_dirty_signals(self) -> None:
        """Connects signals that should trigger dirty state."""
        self.name_edit.textChanged.connect(lambda: self.set_dirty(True))
        self.type_edit.currentTextChanged.connect(lambda: self.set_dirty(True))
        self.desc_edit.textChanged.connect(lambda: self.set_dirty(True))
        self.tag_editor.tags_changed.connect(lambda: self.set_dirty(True))
        self.attribute_editor.attributes_changed.connect(lambda: self.set_dirty(True))

    def set_dirty(self, dirty: bool) -> None:
        """Sets dirty state and updates UI."""
        # Don't set dirty during loading
        if self._is_loading and dirty:
            logger.debug(
                f"[EntityEditor] set_dirty({dirty}) ignored - loading in progress"
            )
            return

        if self._current_entity_id is None and dirty:
            logger.debug(
                f"[EntityEditor] set_dirty({dirty}) ignored - no entity loaded"
            )
            return

        if self._is_dirty != dirty:
            logger.info(
                f"[EntityEditor] set_dirty: {self._is_dirty} -> {dirty} "
                f"(entity_id={self._current_entity_id})"
            )
            if not dirty:
                # Log stack trace when clearing dirty to trace the source
                logger.debug(
                    f"[EntityEditor] Clearing dirty state. Stack trace:\n"
                    f"{traceback.format_stack(limit=10)}"
                )
            self._is_dirty = dirty
            self.dirty_changed.emit(dirty)
            self.btn_save.setEnabled(dirty)
            self.btn_discard.setEnabled(dirty)
            if dirty:
                self.btn_save.setText("Save Changes *")
                self.autosave_manager.start_timer()
            else:
                self.btn_save.setText("Save Changes")
                self.autosave_manager.stop_timer()

    def has_unsaved_changes(self) -> bool:
        """Returns True if dirty."""
        return self._is_dirty

    def update_suggestions(
        self, items: list[tuple[str, str, str]] = None, names: list[str] = None
    ) -> None:
        """Updates the autocomplete suggestions for the description field.

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
            self.desc_edit.blockSignals(True)
            try:
                self.desc_edit.set_wiki_text(self.desc_edit._current_wiki_text)
            finally:
                self.desc_edit.blockSignals(False)

        # Store for RelationEditDialog
        if items:
            self._suggestion_items = items
        else:
            self._suggestion_items = []

    def update_tag_suggestions(self, tags: list[str]) -> None:
        """Updates tag suggestions."""
        self.tag_editor.update_suggestions(tags)

    def update_attribute_suggestions(self, keys: list[str]) -> None:
        """Updates attribute key suggestions."""
        self.attribute_editor.update_suggestions(keys)

    def update_relation_type_suggestions(self, types: list[str]) -> None:
        """Updates relation type suggestions."""
        self._suggestion_types = types

    def update_entity_type_suggestions(self, types: list[str]) -> None:
        """Updates entity type suggestions.

        Merges fetched types with default types and updates the combobox.
        """
        current = self.type_edit.currentText()
        default_types = ["Character", "Location", "Faction", "Item", "Concept"]
        all_types = sorted(list(set(default_types + types)))

        self.type_edit.blockSignals(True)
        self.type_edit.clear()
        self.type_edit.addItems(all_types)
        self.type_edit.setCurrentText(current)
        self.type_edit.blockSignals(False)

    def load_entity(
        self, entity: Entity, relations: list = None, incoming_relations: list = None
    ) -> None:
        """Populates the form with entity data and relations."""
        self._is_loading = True
        try:
            self._current_entity_id = entity.id
            self._current_created_at = entity.created_at

            # Block signals
            self.name_edit.blockSignals(True)
            self.type_edit.blockSignals(True)
            self.desc_edit.blockSignals(True)

            if self.name_edit.text() != entity.name:
                self.name_edit.setText(entity.name)

            if self.type_edit.currentText() != entity.type:
                self.type_edit.setCurrentText(entity.type)

            # Check against the actual current content of the editor instead of internal
            # storage. This ensures we don't reload if the text is effectively the same.
            # (resolving cursor reset)
            if self.desc_edit.get_wiki_text() != entity.description:
                self.desc_edit.set_wiki_text(entity.description)

            # Load Attributes (filter out _tags for display)
            # Store hidden attributes to preserve them on save
            self._hidden_attributes = {
                k: v for k, v in entity.attributes.items() if k.startswith("_")
            }
            # Also ensure _summary_data is in there

            display_attrs = {
                k: v for k, v in entity.attributes.items() if not k.startswith("_")
            }
            self.attribute_editor.blockSignals(True)
            try:
                self.attribute_editor.load_attributes(display_attrs)
            finally:
                self.attribute_editor.blockSignals(False)

            # Load Tags
            self.tag_editor.blockSignals(True)
            try:
                self.tag_editor.load_tags(entity.tags)
            finally:
                self.tag_editor.blockSignals(False)

            # Load Gallery
            self.gallery.set_owner("entity", entity.id)

            # Load Summary
            if self.summary_service:
                summary_data = entity.attributes.get("_summary_data")
                if summary_data:
                    try:
                        data = SummaryData.from_dict(summary_data)
                        self.summary_widget.set_summary(data)
                        # Open if summary exists ? Or keep user preference?
                        # Keep existing state or open if user preference set (later)
                    except Exception:
                        pass

                is_stale = self.summary_service.is_stale(entity)
                self.summary_widget.set_stale(is_stale)

                # Auto-generate if configured (TODO check config)

            # Reset Read-Only mode (in case we were in temporal view)
            self.exit_read_only_mode()

            self.rel_list.clear()

            # Outgoing
            if relations:
                for rel in relations:
                    target_display = rel.get("target_name") or rel["target_id"]
                    label = f"→ {target_display} [{rel['rel_type']}]"

                    # Create custom widget with Go to button
                    widget = RelationItemWidget(
                        label=label,
                        target_id=rel["target_id"],
                        target_name=target_display,
                        attributes=rel.get("attributes"),
                    )
                    widget.go_to_clicked.connect(
                        lambda tid, tn: self.navigate_to_relation.emit(tid)
                    )

                    # Create list item with explicit size hint BEFORE adding
                    item = QListWidgetItem()
                    item.setData(Qt.ItemDataRole.UserRole, rel)
                    item.setSizeHint(QSize(200, 36))  # Explicit height for button
                    self.rel_list.addItem(item)
                    self.rel_list.setItemWidget(item, widget)

            # Incoming
            if incoming_relations:
                for rel in incoming_relations:
                    source_display = rel.get("source_name") or rel["source_id"]
                    label = f"← {source_display} [{rel['rel_type']}]"

                    # Create custom widget - navigate to source for incoming
                    widget = RelationItemWidget(
                        label=label,
                        target_id=rel["source_id"],
                        target_name=source_display,
                        attributes=rel.get("attributes"),
                    )
                    widget.go_to_clicked.connect(
                        lambda tid, tn: self.navigate_to_relation.emit(tid)
                    )
                    widget.label.setStyleSheet("color: gray;")

                    # Create list item with explicit size hint BEFORE adding
                    item = QListWidgetItem()
                    item.setData(Qt.ItemDataRole.UserRole, rel)
                    item.setSizeHint(QSize(200, 36))  # Explicit height for button
                    self.rel_list.addItem(item)
                    self.rel_list.setItemWidget(item, widget)

            # Populate Timeline Display with incoming relations (sorted by date)
            self.timeline_display.set_relations(incoming_relations or [])

            self.setEnabled(True)

            # Unblock & Reset
            self.name_edit.blockSignals(False)
            self.type_edit.blockSignals(False)
            self.desc_edit.blockSignals(False)
            self.set_dirty(False)
        finally:
            self._is_loading = False

    @Slot(dict)
    def _on_theme_changed(self, theme: dict) -> None:
        """Updates UI elements when the theme changes.

        Args:
            theme (dict): The new theme data.

        """
        from src.gui.utils.style_helper import StyleHelper

        # Update Inject Button
        self.btn_inject.setStyleSheet(
            StyleHelper.get_tool_button_style()
            + " QToolButton::menu-indicator { image: none; }"
        )

        # Update Checkboxes
        self.timeline_checkbox.setStyleSheet(StyleHelper.get_checkbox_style())
        self.summary_checkbox.setStyleSheet(StyleHelper.get_checkbox_style())
        self.llm_checkbox.setStyleSheet(StyleHelper.get_checkbox_style())

    @Slot()
    def _on_save(self) -> None:
        """Collects data and emits save signal."""
        logger.info(
            f"[EntityEditor] _on_save() called (entity_id={self._current_entity_id})"
        )

        # Handle "Return to Present" action in special read-only mode
        if self.btn_save.text() == "Return to Present":
            logger.debug("[EntityEditor] Return to Present action triggered")
            self.return_to_present_requested.emit()
            return

        if not self._current_entity_id:
            logger.warning("[EntityEditor] _on_save aborted - no current entity ID")
            return

        try:
            # Merge tags into attributes
            base_attrs = self.attribute_editor.get_attributes()
            base_attrs["_tags"] = self.tag_editor.get_tags()

            # Inject pending summary if exists
            if hasattr(self, "_pending_summary_data") and self._pending_summary_data:
                base_attrs["_summary_data"] = self._pending_summary_data
            # Else? If we loaded an entity, it had _summary_data.
            # If we didn't touch it, AttributeEditor didn't have it (filtered).
            # So we lose it on save?!
            # FIX: We must store the originally loaded hidden attributes and merge them back.
            # This is a general issue with the editor if it filters attrs.
            # Assuming AttributeEditor might hold onto them?
            # Let's check AttributeEditor.
            # If not, we need to cache hidden attrs on load.
            elif hasattr(self, "_hidden_attributes"):
                for k, v in self._hidden_attributes.items():
                    if k not in base_attrs:
                        base_attrs[k] = v

            entity_data = {
                "id": self._current_entity_id,
                "name": self.name_edit.text(),
                "type": self.type_edit.currentText(),
                "description": self.desc_edit.get_wiki_text(),
                "attributes": base_attrs,
                "tags": self.tag_editor.get_tags(),
            }

            logger.info(
                f"[EntityEditor] Emitting save_requested for entity '{entity_data['name']}' "
                f"(id={entity_data['id']}, "
                f"desc_len={len(entity_data['description'])})"
            )
            self.save_requested.emit(entity_data)

            # NOTE: We do NOT call set_dirty(False) here.
            # The Save command triggers a reload of the entity data.
            # load_entity() will be called, and THAT is where set_dirty(False) happens.
            # This prevents race conditions where we clear dirty, but signals from
            # widgets (processing the current data) fire before the reload completes.
            logger.debug(
                "[EntityEditor] _on_save emitted signal. "
                "Waiting for reload to clear dirty state."
            )

        except Exception as e:
            logger.error(
                f"[EntityEditor] Exception in _on_save: {e}\n{traceback.format_exc()}"
            )
            raise

    @Slot()
    def _on_discard(self) -> None:
        """Discards changes by emitting signal to reload the current entity."""
        if not self._current_entity_id:
            return

        self.discard_requested.emit(self._current_entity_id)

    def clear(self) -> None:
        """Clears the editor."""
        self._current_entity_id = None
        self.name_edit.clear()
        self.desc_edit.clear()
        self.rel_list.clear()  # Clear relations
        self.setEnabled(False)

    @Slot()
    def _on_add_relation(self) -> None:
        """Handles adding a new relation.

        Uses RelationEditDialog with autocompletion.
        """
        if not self._current_entity_id:
            return

        from src.gui.dialogs.relation_dialog import RelationEditDialog

        dlg = RelationEditDialog(
            parent=self,
            suggestion_items=getattr(self, "_suggestion_items", []),
            known_types=getattr(self, "_suggestion_types", []),
        )

        if dlg.exec():
            target_id, rel_type, is_bidirectional, attributes = dlg.get_data()
            if target_id:
                self.add_relation_requested.emit(
                    self._current_entity_id,
                    target_id,
                    rel_type,
                    attributes,
                    is_bidirectional,
                )

    def _show_rel_menu(self, pos: QPoint) -> None:
        """Shows a context menu for relation items.

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

    def _on_remove_relation_item(self, item: QListWidgetItem) -> None:
        """Handles removing a relation item.

        Args:
            item (QListWidgetItem): The relation item to remove.

        """
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

    @Slot(QListWidgetItem)
    def _on_edit_relation(self, item: QListWidgetItem) -> None:
        """Handles editing a relation item.

        Args:
            item (QListWidgetItem): The relation item to edit.

        """
        rel_data = item.data(Qt.ItemDataRole.UserRole)

        from src.gui.dialogs.relation_dialog import RelationEditDialog

        dlg = RelationEditDialog(
            parent=self,
            target_id=rel_data["target_id"],
            rel_type=rel_data["rel_type"],
            is_bidirectional=False,
            attributes=rel_data.get("attributes"),
            # Editing existing relation implies directional update typically
            suggestion_items=getattr(self, "_suggestion_items", []),
            known_types=getattr(self, "_suggestion_types", []),
        )

        # Hide bidirectional check for editing as logic might be complex
        # handling existing reverse links
        dlg.bi_check.setVisible(False)

        if dlg.exec():
            target_id, rel_type, _, attributes = dlg.get_data()
            if target_id:
                self.update_relation_requested.emit(
                    rel_data["id"], target_id, rel_type, attributes
                )

    @Slot()
    def _on_edit_selected_relation(self) -> None:
        """Handles editing the currently selected relation."""
        item = self.rel_list.currentItem()
        if item:
            self._on_edit_relation(item)

    @Slot()
    def _on_remove_selected_relation(self) -> None:
        """Handles removing the currently selected relation."""
        item = self.rel_list.currentItem()
        if item:
            self._on_remove_relation_item(item)

    def get_generation_context(self) -> dict:
        """Get context for LLM generation.

        Returns:
            dict: Context dictionary with 'name', 'type', etc.

        """
        context = {
            "name": self.name_edit.text(),
            "type": self.type_edit.currentText(),
            "existing_description": self.desc_edit.toPlainText(),
        }
        return context

    @Slot(str)
    def _on_text_generated(self, text: str) -> None:
        """Handle text generated from LLM.

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
        """Override to prevent dock collapse.

        Returns:
            QSize: Minimum size for usable entity editor.

        """
        from PySide6.QtCore import QSize

        return QSize(300, 200)  # Width for form labels, height for controls

    def sizeHint(self) -> QSize:
        """Preferred size for the entity editor.

        Returns:
            QSize: Comfortable working size for editing entities.

        """
        from PySide6.QtCore import QSize

        return QSize(400, 600)  # Ideal size for editing

    @Slot(str, str)
    def _on_wikilink_added(self, target_id: str, target_name: str) -> None:
        """Handles a new wikilink addition.

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

        if not self._current_entity_id:
            return  # Can't add relation if we don't exist yet

        # Open Dialog
        dialog = RelationEditDialog(
            self,
            target_id=target_id,
            rel_type="mentions",
            is_bidirectional=False,
            known_types=getattr(self, "_suggestion_types", []),
        )
        # Lock target field since it comes from the link
        dialog.target_edit.setEnabled(False)

        if dialog.exec():
            _, rel_type, is_bidirectional, attributes = dialog.get_data()
            self.add_relation_requested.emit(
                self._current_entity_id,
                target_id,
                rel_type,
                attributes,
                is_bidirectional,
            )

    def display_temporal_state(
        self, entity_id: str, attributes: dict, playhead_time: float = None
    ) -> None:
        """Displays the resolved temporal state for the current entity. Sets the editor
        to read-only mode.

        Args:
            entity_id: ID of the entity being displayed.
            attributes: Resolved temporal attributes.
            playhead_time: Current playhead time for timeline highlighting.

        """
        if entity_id != self._current_entity_id:
            return

        # Load attributes (filter internal keys)
        display_attrs = {k: v for k, v in attributes.items() if k != "_tags"}
        self.attribute_editor.load_attributes(display_attrs)

        # Update timeline display with playhead time for highlighting
        if playhead_time is not None:
            self.timeline_display.set_playhead_time(playhead_time)

        # We need to update _on_save to include _pending_summary_data if present
        # OR we rely on loading the entity fresh? No, overwrite is full replace.

        # Enter Read-Only Mode
        self.set_read_only_mode(True, reason="Viewing Past/Future State")

    def _populate_inject_menu(self) -> None:
        """Populate the Fast Inject menu."""
        self.inject_menu.clear()

        # Quick Slots (Top 3 - Placeholder logic for now, or just basic "Open Dialog")
        # In a real app we'd query usage stats.

        action_dialog = self.inject_menu.addAction("Open Inject Dialog...")
        action_dialog.triggered.connect(self._open_inject_dialog)

        self.inject_menu.addSeparator()

        action_save_tmpl = self.inject_menu.addAction("Save Selection as Template...")
        action_save_tmpl.triggered.connect(self._open_create_template_dialog)

    def _open_inject_dialog(self) -> None:
        """Open the Fast Inject Dialog."""
        if not self._current_entity_id:
            return

        self.inject_ui_requested.emit(self._current_entity_id)

    def _open_create_template_dialog(self) -> None:
        """Open create template dialog."""
        if not self._current_entity_id:
            return

        from src.gui.dialogs.create_template_dialog import CreateTemplateDialog

        # Collect current data
        current_tags = self.tag_editor.get_tags()
        current_attrs = self.attribute_editor.get_attributes()
        current_type = self.type_edit.currentText()

        dlg = CreateTemplateDialog(
            source_tags=current_tags,
            source_attributes=current_attrs,
            source_type=current_type,
            parent=self,
        )

        if dlg.exec():
            # Emit signal to save this template
            # create_template_requested = Signal(dict)
            self.create_template_requested.emit(dlg.result_data)

    create_template_requested = Signal(dict)

    def set_read_only_mode(self, readonly: bool, reason: str = None) -> None:
        """Sets the editor to read-only mode."""
        # Disable form fields
        self.name_edit.setReadOnly(readonly)
        self.type_edit.setEnabled(not readonly)
        self.desc_edit.setReadOnly(readonly)

        # Disable attribute editor
        self.attribute_editor.setEnabled(not readonly)
        self.tag_editor.setEnabled(not readonly)

        # Disable Relation buttons (viewing relations is still fine)
        self.btn_add_rel.setEnabled(not readonly)
        self.btn_edit_rel.setEnabled(not readonly)
        self.btn_remove_rel.setEnabled(not readonly)

        # Disable Save/Discard
        self.btn_save.setEnabled(not readonly)
        self.btn_discard.setEnabled(not readonly)

        if readonly:
            if reason == "Viewing Past/Future State":
                self.btn_save.setText("Return to Present")
                self.btn_save.setEnabled(True)
                self.btn_save.setStyleSheet(
                    "background-color: #2196F3; color: white; font-weight: bold;"
                )
            else:
                self.btn_save.setText(reason or "Read Only")
                self.btn_save.setEnabled(False)
                self.btn_save.setStyleSheet("")
        else:
            self.btn_save.setText("Save Changes")
            self.btn_save.setEnabled(True)
            self.btn_save.setStyleSheet("")

    def exit_read_only_mode(self) -> None:
        """Restores normal editing mode."""
        self.set_read_only_mode(False)

    @Slot()
    def _on_summary_generate_requested(self) -> None:
        """Handles summary generation request."""
        print(f"[DEBUG] _on_summary_generate_requested ID: {self._current_entity_id}")
        if not self._current_entity_id:
            print("[DEBUG] Aborting: No current entity ID")
            return

        # Construct temporary entity from form
        temp_entity = Entity(
            name=self.name_edit.text(),
            type=self.type_edit.currentText(),
            description=self.desc_edit.get_wiki_text(),
            id=self._current_entity_id,
            attributes=self.attribute_editor.get_attributes(),
        )
        print(f"[DEBUG] Emitting summary_generation_requested for {temp_entity.name}")

        # Disable button
        self.summary_widget.generate_btn.setEnabled(False)
        self.summary_widget.generate_btn.setText("Generating...")

        self.summary_generation_requested.emit(temp_entity)

    @Slot(object)
    def on_summary_generated(self, summary_data: SummaryData) -> None:
        """Callback when summary is generated."""
        self.summary_widget.generate_btn.setEnabled(True)
        self.summary_widget.generate_btn.setText("Regenerate")

        try:
            self.summary_widget.set_summary(summary_data)
            self._pending_summary_data = summary_data.to_dict()
            self.set_dirty(True)
        except Exception as e:
            logger.error(f"Error applying summary: {e}")
