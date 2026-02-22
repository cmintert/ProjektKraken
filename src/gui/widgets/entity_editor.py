"""Entity Editor Widget Module.

Provides a GUI form for creating and editing Entity objects with support for wiki-style
text editing, custom attributes, tags, and relationship management.
"""

import logging
import traceback
from contextlib import suppress
from typing import Any, Dict, Optional

from PySide6.QtCore import QPoint, QSize, Qt, Signal, Slot
from PySide6.QtGui import QDropEvent
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
from src.gui.mixins.editor_mixin import BaseEditorMixin
from src.gui.widgets.attribute_editor import AttributeEditorWidget
from src.gui.widgets.relation_item_widget import RelationItemWidget
from src.gui.widgets.splitter_tab_inspector import SplitterTabInspector
from src.gui.widgets.standard_buttons import (
    DestructiveButton,
    PrimaryButton,
    StandardButton,
    StandardCheckbox,
)
from src.gui.widgets.summary_widget import SummaryWidget
from src.gui.widgets.tag_editor import TagEditorWidget
from src.gui.widgets.wiki_text_edit import WikiTextEdit

logger = logging.getLogger(__name__)


class EntityEditorWidget(BaseEditorMixin, QWidget):
    """A form to edit the details of an Entity.

    Emits 'save_requested' signal with the modified Entity object.

    Signals:
        save_requested(dict): Emitted when user clicks Save; payload is entity data.
        discard_requested(str): Emitted when user discards changes; payload is item_id.
        inject_requested(dict): Request to run inject command with given data.
        add_relation_requested(str, str, str, dict, bool): Request to create a relation
            (source_id, target_id, rel_type, attributes, bidirectional).
        remove_relation_requested(str): Request to delete a relation by rel_id.
        update_relation_requested(str, str, str, dict): Request to update a relation
            (rel_id, target_id, rel_type, attributes).
        link_clicked(str): Emitted when a wiki link is clicked; payload is target_name.
        navigate_to_relation(str): Emitted when Go-to is clicked; payload is target_id.
        dirty_changed(bool): Emitted when the editor's dirty state changes.
        return_to_present_requested(): Emitted to exit temporal past/future view.
        inject_ui_requested(str): Request to open inject dialog for an entity_id.
        summary_generation_requested(object): Request AI summary for the given Entity.
    """

    save_requested = Signal(dict)
    discard_requested = Signal(str)
    inject_requested = Signal(dict)
    add_relation_requested = Signal(str, str, str, dict, bool)
    remove_relation_requested = Signal(str)
    update_relation_requested = Signal(str, str, str, dict)
    link_clicked = Signal(str)
    navigate_to_relation = Signal(str)
    dirty_changed = Signal(bool)
    return_to_present_requested = Signal()
    inject_ui_requested = Signal(str)
    summary_generation_requested = Signal(object)

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

        # --- Persistent Header ---
        self.header_widget = QWidget()
        header_layout = QVBoxLayout(self.header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        # It seems StyleHelper is imported inside __init__ in original code at line 84
        # Inject Button (QToolButton with Menu)
        from PySide6.QtWidgets import QToolButton

        from src.gui.utils.style_helper import StyleHelper

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

        from src.app.constants import (
            EDITOR_FORM_VERTICAL_SPACING,
            EDITOR_LIST_SPACING,
            EDITOR_SECTION_SPACING,
        )

        # Header Form Layout
        self.header_form = QFormLayout()
        self.header_form.setVerticalSpacing(EDITOR_FORM_VERTICAL_SPACING)
        self.header_form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        self.header_form.setRowWrapPolicy(QFormLayout.DontWrapRows)
        self.header_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.name_edit = QLineEdit()
        self.type_edit = QComboBox()
        from PySide6.QtWidgets import QSizePolicy

        self.type_edit.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.type_edit.addItems(["Character", "Location", "Faction", "Item", "Concept"])
        self.type_edit.setEditable(True)

        # Name row with Inject button
        name_layout = QHBoxLayout()
        name_layout.addWidget(self.name_edit)
        name_layout.addWidget(self.btn_inject)

        self.header_form.addRow("Name:", name_layout)
        self.header_form.addRow("Type:", self.type_edit)

        header_layout.addLayout(self.header_form)

        main_layout.addWidget(self.header_widget)

        # Splitter-based tab inspector for vertical stacking
        self.inspector = SplitterTabInspector()
        main_layout.addWidget(self.inspector)

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

        self.form_layout = QFormLayout()
        self.form_layout.setVerticalSpacing(EDITOR_FORM_VERTICAL_SPACING)
        self.form_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        self.form_layout.setRowWrapPolicy(QFormLayout.DontWrapRows)
        self.form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.desc_edit = WikiTextEdit()
        self.desc_edit.link_clicked.connect(self.link_clicked.emit)
        self.desc_edit.link_added.connect(self._on_wikilink_added)

        self.form_layout.addRow("Description:", self.desc_edit)

        # Add Timeline Display Widget (above LLM section)
        from PySide6.QtWidgets import QCheckBox

        from src.gui.widgets.timeline_display_widget import TimelineDisplayWidget

        self.timeline_container = QWidget()
        timeline_outer_layout = QVBoxLayout(self.timeline_container)
        timeline_outer_layout.setContentsMargins(0, 0, 0, 0)
        timeline_outer_layout.setSpacing(EDITOR_SECTION_SPACING)

        self.timeline_checkbox = StandardCheckbox("")  # Text in form label

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
        summary_outer_layout.setSpacing(EDITOR_SECTION_SPACING)

        self.summary_checkbox = StandardCheckbox("")

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
        llm_outer_layout.setSpacing(EDITOR_SECTION_SPACING)

        self.llm_checkbox = StandardCheckbox("")

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
        self.btn_edit_rel.setEnabled(False)
        rel_btn_layout.addWidget(self.btn_edit_rel)

        self.btn_remove_rel = DestructiveButton("Remove")
        self.btn_remove_rel.clicked.connect(self._on_remove_selected_relation)
        self.btn_remove_rel.setEnabled(False)
        rel_btn_layout.addWidget(self.btn_remove_rel)

        rel_btn_layout.addStretch()
        rel_tab_layout.addLayout(rel_btn_layout)

        # List second
        self.rel_list = QListWidget()
        self.rel_list.setSpacing(EDITOR_LIST_SPACING)  # Add spacing between items
        self.rel_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.rel_list.customContextMenuRequested.connect(self._show_rel_menu)
        self.rel_list.itemDoubleClicked.connect(self._on_edit_relation)
        self.rel_list.itemSelectionChanged.connect(self._update_relation_button_states)

        # Allow deselection by clicking on empty space or selected item
        self.rel_list.viewport().installEventFilter(self)
        self.rel_list.setProperty("_relation_list_widget", True)

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

        # Enable drag-and-drop for relation creation
        self.setAcceptDrops(True)

        # Create drop hint label (Sprint 1 - visual feedback)
        self._drop_hint_label = None
        self._is_drag_over = False

        # Type picker for relation type selection (activated by Shift key)
        self._type_picker = None
        self._selected_relation_type = "related"  # Default type

    def _get_current_item_id(self) -> str | None:
        """Returns the current entity ID or None."""
        return self._current_entity_id

    def _get_editor_label(self) -> str:
        """Returns the editor label for logging."""
        return "EntityEditor"

    def _show_drop_hint(self, rel_type: str = "related") -> None:
        """Show drop hint overlay during drag-over.

        Args:
            rel_type: Relation type to display in hint.
        """
        if self._drop_hint_label is None:
            from PySide6.QtWidgets import QLabel

            self._drop_hint_label = QLabel(self)
            from src.gui.utils.style_helper import StyleHelper

            self._drop_hint_label.setStyleSheet(StyleHelper.get_drag_overlay_style())
            self._drop_hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._drop_hint_label.setText(f"→ {rel_type}")
        self._drop_hint_label.setGeometry(self.rect())
        self._drop_hint_label.show()
        self._drop_hint_label.raise_()

    def _hide_drop_hint(self) -> None:
        """Hide drop hint overlay."""
        if self._drop_hint_label:
            self._drop_hint_label.hide()

    def dropEvent(self, event: QDropEvent) -> None:
        """Handle drop event to create relation from dragged item to current entity.

        Args:
            event: QDropEvent with MIME data.
        """
        import json

        from src.gui.widgets.unified_list import KRAKEN_ITEM_MIME_TYPE

        if not event.mimeData().hasFormat(KRAKEN_ITEM_MIME_TYPE):
            event.ignore()
            return

        if not self._current_entity_id:
            logger.warning("Cannot drop: No entity loaded in editor")
            event.ignore()
            return

        try:
            # Parse MIME data
            mime_data = event.mimeData().data(KRAKEN_ITEM_MIME_TYPE)
            data = json.loads(bytes(mime_data).decode("utf-8"))

            dropped_id = data.get("id")
            dropped_type = data.get("type")
            dropped_name = data.get("name", "Unknown")

            if not dropped_id or not dropped_type:
                logger.error("Invalid MIME data: missing id or type")
                event.ignore()
                return

            # Check if Shift key is pressed - show type picker
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                # Post-drop selection flow
                self._initiated_relation_drop = {
                    "source_id": dropped_id,
                    "source_type": dropped_type,
                    "source_name": dropped_name,
                }
                event.acceptProposedAction()
                self._show_type_picker(event.pos())
                return

            # Standard Flow (Default "related")
            self._create_relation(dropped_id, dropped_type, dropped_name, "related")
            event.acceptProposedAction()

        except Exception as e:
            logger.error(f"Error handling drop event: {e}", exc_info=True)
            event.ignore()
            self._hide_drop_hint()

            if self._type_picker and self._type_picker.isVisible():
                self._type_picker.hide()

    def _create_relation(
        self, source_id: str, source_type: str, source_name: str, rel_type: str
    ) -> None:
        """Helper to emit relation creation signal."""
        logger.info(
            f"EntityEditor: Creating relation {source_id} -> {self._current_entity_id} "
            f"(dropped {source_type}: {source_name}, type: {rel_type})"
        )

        self.add_relation_requested.emit(
            source_id,
            self._current_entity_id,
            rel_type,
            {},
            False,
        )

        # Cleanup UI
        self._is_drag_over = False
        self._hide_drop_hint()
        if self._type_picker:
            self._type_picker.hide()

    def set_summary_service(self, service: Any) -> None:
        """Sets the summary service for generation and staleness checks."""
        self.summary_service = service

    def set_project_root(self, path: Any) -> None:
        """Sets the project root for child widgets."""
        if hasattr(self, "gallery"):
            self.gallery.set_project_root(path)

    def _connect_dirty_signals(self) -> None:
        """Connects signals that should trigger dirty state."""
        self.name_edit.textChanged.connect(lambda: self.set_dirty(True))
        self.type_edit.currentTextChanged.connect(lambda: self.set_dirty(True))
        self.desc_edit.textChanged.connect(lambda: self.set_dirty(True))
        self.tag_editor.tags_changed.connect(lambda: self.set_dirty(True))
        self.attribute_editor.attributes_changed.connect(lambda: self.set_dirty(True))

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
        self._suggestion_items = items or []

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
        """Populates the form with entity data and relations.

        Args:
            entity: The entity to edit.
            relations: List of outgoing relation dicts.
            incoming_relations: List of incoming relation dicts.

        """
        self._is_loading = True
        try:
            self._current_entity_id = entity.id
            self._current_created_at = entity.created_at

            # Block signals
            self._set_input_signals_blocked(True)

            self._load_entity_fields(entity)
            self._load_entity_attributes(entity)
            self.exit_read_only_mode()
            self._load_entity_relations(relations, incoming_relations)

            self.setEnabled(True)

            # Unblock & Reset
            self._set_input_signals_blocked(False)
            self.set_dirty(False)
        finally:
            self._is_loading = False

    def _load_entity_fields(self, entity: Entity) -> None:
        """Loads core form fields from the entity, skipping redundant updates.

        Args:
            entity: The entity whose fields to load.

        """
        if self.name_edit.text() != entity.name:
            self.name_edit.setText(entity.name)

        if self.type_edit.currentText() != entity.type:
            self.type_edit.setCurrentText(entity.type)

        if self.desc_edit.get_wiki_text() != entity.description:
            self.desc_edit.set_wiki_text(entity.description)

    def _load_entity_attributes(self, entity: Entity) -> None:
        """Loads attributes, tags, summary, and gallery from the entity.

        Separates hidden (underscore-prefixed) attributes from display attributes
        so that internal keys like ``_tags`` and ``_summary_data`` are preserved
        on save without being shown in the attribute editor.

        Args:
            entity: The entity whose attributes to load.

        """
        display_attrs = self._extract_hidden_attributes(entity.attributes)
        self.attribute_editor.blockSignals(True)
        try:
            self.attribute_editor.load_attributes(display_attrs)
        finally:
            self.attribute_editor.blockSignals(False)

        self.tag_editor.blockSignals(True)
        try:
            self.tag_editor.load_tags(entity.tags)
        finally:
            self.tag_editor.blockSignals(False)

        self.gallery.set_owner("entity", entity.id)

        summary_data = entity.attributes.get("_summary_data")
        if summary_data:
            with suppress(Exception):
                data = SummaryData.from_dict(summary_data)
                self.summary_widget.set_summary(data)

            if self.summary_service:
                is_stale = self.summary_service.is_stale(entity)
                self.summary_widget.set_stale(is_stale)

    def _load_entity_relations(
        self, relations: list | None, incoming_relations: list | None
    ) -> None:
        """Loads outgoing and incoming relations into the relation list widget.

        Args:
            relations: List of outgoing relation dicts, or None.
            incoming_relations: List of incoming relation dicts, or None.

        """
        self.rel_list.clear()

        if relations:
            for rel in relations:
                target_display = rel.get("target_name") or rel["target_id"]
                label = f"→ {target_display} [{rel['rel_type']}]"

                widget = RelationItemWidget(
                    label=label,
                    target_id=rel["target_id"],
                    target_name=target_display,
                    attributes=rel.get("attributes"),
                )
                widget.go_to_clicked.connect(
                    lambda tid, tn: self.navigate_to_relation.emit(tid)
                )

                item = QListWidgetItem()
                item.setData(Qt.ItemDataRole.UserRole, rel)
                item.setSizeHint(QSize(200, 36))
                self.rel_list.addItem(item)
                self.rel_list.setItemWidget(item, widget)

        if incoming_relations:
            for rel in incoming_relations:
                source_display = rel.get("source_name") or rel["source_id"]
                label = f"← {source_display} [{rel['rel_type']}]"

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

                item = QListWidgetItem()
                item.setData(Qt.ItemDataRole.UserRole, rel)
                item.setSizeHint(QSize(200, 36))
                self.rel_list.addItem(item)
                self.rel_list.setItemWidget(item, widget)

        self.timeline_display.set_relations(incoming_relations or [])

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
        # StandardCheckbox handles its own styling on theme change


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

            # Restore hidden attributes first, then overlay pending summary
            self._merge_hidden_attributes(base_attrs)

            # Pending summary takes precedence over any existing _summary_data
            if hasattr(self, "_pending_summary_data") and self._pending_summary_data:
                base_attrs["_summary_data"] = self._pending_summary_data

            entity_data = {
                "id": self._current_entity_id,
                "name": self.name_edit.text(),
                "type": self.type_edit.currentText(),
                "description": self.desc_edit.get_wiki_text(),
                "attributes": base_attrs,
                "tags": self.tag_editor.get_tags(),
            }

            logger.info(
                f"[EntityEditor] Emitting save_requested for entity "
                f"'{entity_data['name']}' "
                f"(id={entity_data['id']}, desc_len={len(entity_data['description'])})"
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
        if item := self.rel_list.currentItem():
            self._on_edit_relation(item)

    @Slot()
    def _on_remove_selected_relation(self) -> None:
        """Handles removing the currently selected relation."""
        if item := self.rel_list.currentItem():
            self._on_remove_relation_item(item)

    def _update_relation_button_states(self) -> None:
        """Updates enabled states for Edit and Remove buttons based on selection."""
        has_selection = len(self.rel_list.selectedItems()) > 0
        self.btn_edit_rel.setEnabled(has_selection)
        self.btn_remove_rel.setEnabled(has_selection)

    def eventFilter(self, obj: QWidget, event: Any) -> bool:
        """Event filter to handle clicks on empty space in relation lists.

        Args:
            obj: Object that received the event.
            event: The event.

        Returns:
            True if event was handled, False otherwise.

        """
        from PySide6.QtCore import QEvent
        from PySide6.QtGui import QMouseEvent

        # Check if this is a mouse press on a relation list viewport
        if (
            isinstance(event, QMouseEvent)
            and event.type() == QEvent.Type.MouseButtonPress
        ):
            if event.button() == Qt.MouseButton.LeftButton:
                # Find the list widget this viewport belongs to
                parent = obj.parent()
                if isinstance(parent, QListWidget) and parent.property(
                    "_relation_list_widget"
                ):
                    # Get the item at the click position
                    item = parent.itemAt(event.pos())

                    if item is None:
                        # Clicked on empty space - clear selection
                        parent.clearSelection()
                        parent.setCurrentItem(None)
                        return False  # Let Qt handle the event normally
                    elif item.isSelected():
                        # Clicked on already-selected item - deselect it
                        parent.clearSelection()
                        parent.setCurrentItem(None)
                        return True  # Consume the event to prevent re-selection

        return super().eventFilter(obj, event)

    def get_generation_context(self) -> Dict[str, Any]:
        """Get context for LLM generation.

        Returns:
            Dict[str, Any]: Context dictionary containing:
                - 'name' (str): Entity name
                - 'type' (str): Entity type
                - 'existing_description' (str): Current description text

        """
        return {
            "name": self.name_edit.text(),
            "type": self.type_edit.currentText(),
            "existing_description": self.desc_edit.toPlainText(),
        }

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
        new_text = current + "\n\n" + text if current.strip() else text

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
        """Populate the Fast Inject menu with available actions.

        Clears and rebuilds the inject menu with:
        - "Open Inject Dialog..." action to launch the inject UI
        - Separator
        - "Save Selection as Template..." action to create templates

        This method is typically called when the menu is about to show,
        ensuring the menu content is always up-to-date.
        """
        self.inject_menu.clear()

        # Quick Slots (Top 3 - Placeholder logic for now, or just basic "Open Dialog")
        # In a real app we'd query usage stats.

        action_dialog = self.inject_menu.addAction("Open Inject Dialog...")
        action_dialog.triggered.connect(self._open_inject_dialog)

        self.inject_menu.addSeparator()

        action_save_tmpl = self.inject_menu.addAction("Save Selection as Template...")
        action_save_tmpl.triggered.connect(self._open_create_template_dialog)

    def _open_inject_dialog(self) -> None:
        """Open the Fast Inject dialog for the current entity.

        Emits the inject_ui_requested signal with the current entity ID,
        allowing the main window or coordinator to display the Fast Inject
        dialog for quick data entry.

        Note:
            Returns early if no entity is currently loaded in the editor.
        """
        if not self._current_entity_id:
            return

        self.inject_ui_requested.emit(self._current_entity_id)

    def _open_create_template_dialog(self) -> None:
        """Open the template creation dialog for the current entity.

        Collects current form data (tags, attributes, description) and
        opens a dialog allowing the user to save it as a reusable template
        for Fast Inject operations.

        The template data is emitted via create_template_requested signal
        if the user accepts the dialog.

        Note:
            Returns early if no entity is currently loaded.
        """
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
        """Set the editor to read-only or editable mode.

        When in read-only mode, all form fields, buttons, and editors are
        disabled to prevent modifications. This is typically used when viewing
        historical entity states or when the user lacks edit permissions.

        Args:
            readonly: If True, disables all editing controls. If False, enables
                normal editing mode.
            reason: Optional string explaining why read-only mode is active.
                Special handling for "Viewing Past/Future State" shows a
                "Return to Present" button. Other reasons show generic read-only
                state. If None, displays "Read Only".

        Note:
            The save button is repurposed in read-only mode: for temporal views
            it becomes "Return to Present" button, otherwise it shows the reason
            text and is disabled.
        """
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
                from src.core.theme_manager import ThemeManager

                theme = ThemeManager().get_theme()
                self._update_save_button(
                    "Return to Present",
                    True,
                    f"background-color: {theme['accent_secondary']}; "
                    f"color: white; font-weight: bold;",
                )
            else:
                self._update_save_button(reason or "Read Only", False)
        else:
            self._update_save_button("Save Changes", True)

    def _update_save_button(self, text: str, enabled: bool, style: str = "") -> None:
        """Update the save button's text, state, and styling.

        Args:
            text: New button text to display.
            enabled: Whether the button should be clickable.
            style: Optional Qt stylesheet string to apply custom styling.
                Defaults to empty string (no custom styling).
        """
        self.btn_save.setText(text)
        self.btn_save.setEnabled(enabled)
        self.btn_save.setStyleSheet(style)

    def _set_input_signals_blocked(self, blocked: bool) -> None:
        """Block or unblock signals from input fields during updates.

        Args:
            blocked: If True, prevents fields from emitting change signals.
                If False, re-enables signal emission.

        Note:
            Used to prevent cascading field updates when programmatically
            setting form values (e.g., when loading an entity from database).
        """
        self.name_edit.blockSignals(blocked)
        self.type_edit.blockSignals(blocked)
        self.desc_edit.blockSignals(blocked)

    def exit_read_only_mode(self) -> None:
        """Exit read-only mode and restore normal editing capabilities.

        Re-enables all form fields, buttons, and editors that were disabled
        by set_read_only_mode(). Typically called when returning from viewing
        a historical entity state to the present.
        """
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
