"""Entity Editor Widget Module.

Provides a GUI form for creating and editing Entity objects with support for wiki-style
text editing, custom attributes, tags, and relationship management.
"""

import logging
import time
import traceback
from contextlib import suppress
from typing import Any, Dict, Optional, cast

from PySide6.QtCore import QObject, QPoint, QSize, Qt, Signal, Slot
from PySide6.QtGui import QDropEvent
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QScrollArea,
    QSizePolicy,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from src.core.ai_generation import GenerationReviewResult, apply_reviewed_generation
from src.core.authoring_context import EntityAuthoringContext
from src.core.entities import Entity
from src.core.summary_data import (
    SummaryData,
    calculate_summary_source_hash,
    is_summary_stale,
)
from src.core.theme_manager import ThemeManager
from src.gui.constants import (
    EDITOR_FORM_VERTICAL_SPACING,
    EDITOR_LIST_SPACING,
    EDITOR_SECTION_SPACING,
)
from src.gui.mixins.autosave_mixin import AutoSaveManager
from src.gui.mixins.editor_mixin import BaseEditorMixin
from src.gui.utils.style_helper import StyleHelper
from src.gui.widgets.attribute_editor import AttributeEditorWidget
from src.gui.widgets.authoring_context_widget import AuthoringContextWidget
from src.gui.widgets.empty_state_widget import EmptyStateWidget
from src.gui.widgets.gallery_widget import GalleryWidget
from src.gui.widgets.llm_generation_widget import LLMGenerationWidget
from src.gui.widgets.relation_item_widget import RelationItemWidget
from src.gui.widgets.sheet_builder import SheetBuilderWidget
from src.gui.widgets.splitter_tab_inspector import SplitterTabInspector
from src.gui.widgets.standard_buttons import (
    DestructiveButton,
    PrimaryButton,
    StandardButton,
    StandardCheckbox,
)
from src.gui.widgets.summary_widget import SummaryWidget
from src.gui.widgets.tag_editor import TagEditorWidget
from src.gui.widgets.timeline_display_widget import TimelineDisplayWidget
from src.gui.widgets.wiki_text_edit import ResizableWikiTextEditField, WikiTextEdit

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
    navigate_to_map = Signal(str)
    dirty_changed = Signal(bool)
    return_to_present_requested = Signal()
    inject_ui_requested = Signal(str)
    summary_generation_requested = Signal(object)
    completion_prefix_changed = Signal(str)
    create_new_requested = Signal()
    authoring_context_refresh_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initializes the EntityEditorWidget.

        Args:
            parent (QWidget, optional): The parent widget. Defaults to None.

        """
        super().__init__(parent)
        self._current_entity_id: str | None = None
        self.autosave_manager = AutoSaveManager(self)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        main_layout = self._build_editor_shell()
        self._build_header(main_layout)

        # Splitter-based tab inspector for vertical stacking
        self.inspector = SplitterTabInspector()
        main_layout.addWidget(self.inspector)

        self._build_details_tab()

        self._build_secondary_tabs(parent)
        self._build_action_buttons(main_layout)
        self._initialize_editor_state()

    def _build_editor_shell(self) -> QVBoxLayout:
        """Build empty/content containers and return the content layout."""
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        outer_layout = QVBoxLayout(self)
        StyleHelper.apply_no_margins(outer_layout)
        self._empty_state = EmptyStateWidget(
            "No Entity Selected",
            "Select an entity from the list to view and edit its details.",
        )
        self._empty_state.add_action(
            "New Entity", self.create_new_requested.emit, primary=True
        )
        outer_layout.addWidget(self._empty_state)
        self._empty_state.show()
        self._content_widget = QWidget()
        content_layout = QVBoxLayout(self._content_widget)
        StyleHelper.apply_form_spacing(content_layout)
        outer_layout.addWidget(self._content_widget)
        self._content_widget.hide()
        return content_layout

    def _build_details_tab(self) -> None:
        """Build the scrollable details tab and its collapsible sections."""
        self.tab_details = QWidget()
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
        self.form_layout.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )
        self.form_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        self.form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.desc_edit = WikiTextEdit()
        self.desc_edit.link_clicked.connect(self.link_clicked.emit)
        self.desc_edit.completion_prefix_changed.connect(
            self.completion_prefix_changed.emit
        )
        self.description_field = ResizableWikiTextEditField(self.desc_edit)
        self.form_layout.addRow("Description:", self.description_field)
        self._build_timeline_section()
        self._build_summary_section()
        self._build_llm_section()
        self._build_raster_appearances_section()
        details_layout.addLayout(self.form_layout)
        self.inspector.add_tab(
            self.tab_details,
            "Details",
            "Core entity details, description, and AI summary",
        )

    def _build_timeline_section(self) -> None:
        """Build the collapsible entity timeline section."""
        self.timeline_container = QWidget()
        section_layout = QVBoxLayout(self.timeline_container)
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(EDITOR_SECTION_SPACING)
        self.timeline_checkbox = StandardCheckbox("")
        section_layout.addWidget(self.timeline_checkbox)
        self.timeline_display = TimelineDisplayWidget()
        self.timeline_display.setMinimumWidth(self.desc_edit.minimumWidth())
        self.desc_edit.minimum_width_changed.connect(
            self.timeline_display.setMinimumWidth
        )
        self.timeline_display.event_clicked.connect(self.navigate_to_relation.emit)
        self.timeline_display.setVisible(False)
        section_layout.addWidget(self.timeline_display)
        self.timeline_checkbox.toggled.connect(self.timeline_display.setVisible)
        self.form_layout.addRow("Timeline:", self.timeline_container)

    def _build_summary_section(self) -> None:
        """Build the collapsible entity summary section."""
        self.summary_container = QWidget()
        section_layout = QVBoxLayout(self.summary_container)
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(EDITOR_SECTION_SPACING)
        self.summary_checkbox = StandardCheckbox("")
        section_layout.addWidget(self.summary_checkbox)
        self.summary_widget = SummaryWidget()
        self.summary_widget.setVisible(False)
        self.summary_widget.generate_requested.connect(
            self._on_summary_generate_requested
        )
        self.summary_widget.edit_committed.connect(self._on_summary_edit_committed)
        self.summary_widget.delete_requested.connect(
            self._on_summary_delete_requested
        )
        section_layout.addWidget(self.summary_widget)
        self.summary_checkbox.toggled.connect(self.summary_widget.setVisible)
        self.form_layout.addRow("Summary:", self.summary_container)

    def _build_llm_section(self) -> None:
        """Build the collapsible description-generation section."""
        self.llm_container = QWidget()
        section_layout = QVBoxLayout(self.llm_container)
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(EDITOR_SECTION_SPACING)
        self.llm_checkbox = StandardCheckbox("")
        section_layout.addWidget(self.llm_checkbox)
        self.llm_generator = LLMGenerationWidget(self, context_provider=self)
        self.llm_generator.setVisible(False)
        self.llm_generator.text_generated.connect(self._on_text_generated)
        section_layout.addWidget(self.llm_generator)
        self.llm_checkbox.toggled.connect(self.llm_generator.setVisible)
        self.form_layout.addRow("LLM Generation:", self.llm_container)

    def _build_raster_appearances_section(self) -> None:
        """Build the read-only collapsible raster-appearance section."""
        self.raster_appearances_container = QWidget()
        section_layout = QVBoxLayout(self.raster_appearances_container)
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(EDITOR_SECTION_SPACING)
        self.raster_appearances_checkbox = StandardCheckbox("")
        section_layout.addWidget(self.raster_appearances_checkbox)
        self.raster_appearances_label = QLabel("Not linked to any raster map.")
        self.raster_appearances_label.setWordWrap(True)
        self.raster_appearances_label.setVisible(False)
        section_layout.addWidget(self.raster_appearances_label)
        self.raster_appearances_checkbox.toggled.connect(
            self.raster_appearances_label.setVisible
        )
        self.form_layout.addRow("Raster Maps:", self.raster_appearances_container)

    def _build_header(self, main_layout: QVBoxLayout) -> None:
        """Build the persistent entity name, type, and inject header."""
        self.header_widget = QWidget()
        header_layout = QVBoxLayout(self.header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        self.btn_inject = QToolButton()
        self.btn_inject.setText("Fast Inject")
        self.btn_inject.setToolTip("Quickly apply templates or snippets to this entity")
        self.btn_inject.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.btn_inject.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.btn_inject.setStyleSheet(
            StyleHelper.get_tool_button_style()
            + " QToolButton::menu-indicator { image: none; }"
        )
        self.inject_menu = QMenu(self.btn_inject)
        self.btn_inject.setMenu(self.inject_menu)
        self.inject_menu.aboutToShow.connect(self._populate_inject_menu)
        ThemeManager().theme_changed.connect(self._on_theme_changed)
        self.header_form = QFormLayout()
        self.header_form.setVerticalSpacing(EDITOR_FORM_VERTICAL_SPACING)
        self.header_form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )
        self.header_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        self.header_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.name_edit = QLineEdit()
        self.type_edit = QComboBox()
        self.type_edit.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.type_edit.addItems(["Character", "Location", "Faction", "Item", "Concept"])
        self.type_edit.setEditable(True)
        name_layout = QHBoxLayout()
        name_layout.addWidget(self.name_edit)
        name_layout.addWidget(self.btn_inject)
        self.header_form.addRow("Name:", name_layout)
        self.header_form.addRow("Type:", self.type_edit)
        header_layout.addLayout(self.header_form)
        main_layout.addWidget(self.header_widget)

    def _build_secondary_tabs(self, parent: Optional[QWidget]) -> None:
        """Build tags, relations, gallery, attributes, and sheet tabs."""
        self._build_context_tab()
        self._build_tags_tab()
        self._build_relations_tab()
        self._build_gallery_tab(parent)
        self._build_attributes_tab()
        self._build_sheet_tab()

    def _build_context_tab(self) -> None:
        """Build the read-only durable World Context tab."""
        self.tab_context = QWidget()
        layout = QVBoxLayout(self.tab_context)
        StyleHelper.apply_no_margins(layout)
        self.authoring_context = AuthoringContextWidget(object_label="Entity")
        self.authoring_context.navigate_requested.connect(
            self.navigate_to_relation.emit
        )
        self.authoring_context.map_requested.connect(self.navigate_to_map.emit)
        self.authoring_context.attachment_requested.connect(
            self._show_context_attachment
        )
        layout.addWidget(self.authoring_context)
        self.inspector.add_tab(
            self.tab_context,
            "Context",
            "View deterministic persisted facts known about this Entity",
        )

    @Slot(str)
    def _show_context_attachment(self, attachment_id: str) -> None:
        """Open the Gallery tab and select a captioned attachment."""
        for tabs in self.inspector.findChildren(QTabWidget):
            index = tabs.indexOf(self.tab_gallery)
            if index >= 0:
                tabs.setCurrentIndex(index)
                break
        for index in range(self.gallery.list_widget.count()):
            item = self.gallery.list_widget.item(index)
            if item.data(Qt.ItemDataRole.UserRole) == attachment_id:
                self.gallery.list_widget.setCurrentItem(item)
                self.gallery.list_widget.scrollToItem(item)
                break

    def _build_tags_tab(self) -> None:
        """Build the entity tags tab."""
        self.tab_tags = QWidget()
        tags_layout = QVBoxLayout(self.tab_tags)
        StyleHelper.apply_no_margins(tags_layout)
        self.tag_editor = TagEditorWidget()
        tags_layout.addWidget(self.tag_editor)
        self.inspector.add_tab(
            self.tab_tags, "Tags", "Manage organizational tags and metadata"
        )

    def _build_relations_tab(self) -> None:
        """Build relation actions and the relation list."""
        self.tab_relations = QWidget()
        rel_layout = QVBoxLayout(self.tab_relations)
        StyleHelper.apply_compact_spacing(rel_layout)
        buttons = QHBoxLayout()
        self.btn_add_rel = StandardButton("Add Relation")
        self.btn_add_rel.clicked.connect(self._on_add_relation)
        buttons.addWidget(self.btn_add_rel)
        self.btn_edit_rel = StandardButton("Edit")
        self.btn_edit_rel.clicked.connect(self._on_edit_selected_relation)
        self.btn_edit_rel.setEnabled(False)
        buttons.addWidget(self.btn_edit_rel)
        self.btn_remove_rel = DestructiveButton("Remove")
        self.btn_remove_rel.clicked.connect(self._on_remove_selected_relation)
        self.btn_remove_rel.setEnabled(False)
        buttons.addWidget(self.btn_remove_rel)
        buttons.addStretch()
        rel_layout.addLayout(buttons)
        self.rel_list = QListWidget()
        self.rel_list.setSpacing(EDITOR_LIST_SPACING)
        self.rel_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.rel_list.customContextMenuRequested.connect(self._show_rel_menu)
        self.rel_list.itemDoubleClicked.connect(self._on_edit_relation)
        self.rel_list.itemSelectionChanged.connect(self._update_relation_button_states)
        self.rel_list.viewport().installEventFilter(self)
        self.rel_list.setProperty("_relation_list_widget", True)
        rel_layout.addWidget(self.rel_list)
        self.inspector.add_tab(
            self.tab_relations,
            "Relations",
            "View and edit connections to other entities and events",
        )

    def _build_gallery_tab(self, parent: Optional[QWidget]) -> None:
        """Build the image gallery tab."""
        self.tab_gallery = QWidget()
        gallery_layout = QVBoxLayout(self.tab_gallery)
        gallery_layout.setContentsMargins(0, 0, 0, 0)
        self.gallery = GalleryWidget(parent)
        gallery_layout.addWidget(self.gallery)
        self.inspector.add_tab(
            self.tab_gallery, "Gallery", "Manage images and media attachments"
        )

    def _build_attributes_tab(self) -> None:
        """Build the structured attributes tab."""
        self.tab_attributes = QWidget()
        attr_layout = QVBoxLayout(self.tab_attributes)
        StyleHelper.apply_no_margins(attr_layout)
        self.attribute_editor = AttributeEditorWidget()
        attr_layout.addWidget(self.attribute_editor)
        self.inspector.add_tab(
            self.tab_attributes, "Attributes", "Edit custom structured data fields"
        )

    def _build_sheet_tab(self) -> None:
        """Build the configurable character-sheet tab."""
        self.tab_sheet = QWidget()
        sheet_layout = QVBoxLayout(self.tab_sheet)
        StyleHelper.apply_no_margins(sheet_layout)
        self.sheet_builder = SheetBuilderWidget()
        sheet_layout.addWidget(self.sheet_builder)
        self.inspector.add_tab(
            self.tab_sheet,
            "Sheet",
            "Configure the visual layout for the character sheet",
        )

    def _build_action_buttons(self, main_layout: QVBoxLayout) -> None:
        """Build persistent discard and save controls."""
        buttons = QHBoxLayout()
        self.btn_save = PrimaryButton("Save Changes")
        self.btn_save.clicked.connect(self._on_save)
        self.btn_discard = StandardButton("Discard")
        self.btn_discard.setEnabled(False)
        self.btn_discard.clicked.connect(self._on_discard)
        buttons.addStretch()
        buttons.addWidget(self.btn_discard)
        buttons.addWidget(self.btn_save)
        main_layout.addLayout(buttons)

    def _initialize_editor_state(self) -> None:
        """Initialize mutable state and dirty tracking for an empty editor."""
        self._current_created_at = 0.0
        self._is_dirty = False
        self._is_loading = False
        self._pending_summary_changed = False
        self._pending_summary_data: dict | None = None
        self._connect_dirty_signals()
        self.summary_service = None
        self.setAcceptDrops(True)
        self._drop_hint_label: QLabel | None = None
        self._is_drag_over = False
        self._type_picker: Any = None
        self._selected_relation_type = "related"

    def _get_current_item_id(self) -> str | None:
        """Return the UUID of the entity currently loaded in the editor.

        Returns:
            The entity UUID string, or ``None`` if no entity is loaded.

        """
        return self._current_entity_id

    def _get_editor_label(self) -> str:
        """Return a human-readable label identifying this editor type.

        Used in log messages to distinguish between the event and entity
        editors when the same base-class code is shared.

        Returns:
            The string ``"EntityEditor"``.

        """
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
        """Handle a drop event to create a relation from the dragged item.

        Accepts drops carrying the custom MIME type
        ``application/x-kraken-item`` (see
        :data:`~src.gui.widgets.unified_list.KRAKEN_ITEM_MIME_TYPE`).  The
        MIME payload is a UTF-8–encoded JSON object with the keys:

        - ``"id"`` (str): UUID of the dragged item.
        - ``"type"`` (str): Domain type, e.g. ``"entity"`` or ``"event"``.
        - ``"name"`` (str): Display name of the dragged item.

        If the **Shift** key is held during the drop, a type-picker popup is
        shown so the user can choose a specific relation type.  Otherwise the
        default relation type ``"related"`` is used.

        Args:
            event: The Qt drop event carrying the MIME data.

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
            data = json.loads(bytes(mime_data.data()).decode("utf-8"))

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
        """Emit the signal to create a new directed relation via drop.

        Logs the creation attempt and emits :attr:`add_relation_requested` so
        that the application coordinator can execute the corresponding command.
        Cleans up drop-UI state (overlay and type-picker) after emitting.

        Args:
            source_id: UUID of the item that was dropped onto this editor.
            source_type: Domain type of the dropped item (e.g. ``"entity"``
                or ``"event"``).
            source_name: Display name of the dropped item, used for logging.
            rel_type: Relation type label to assign (e.g. ``"related"``).

        """
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
        """Set the summary service used to generate and check entity summaries.

        Args:
            service: An object implementing ``generate(entity)`` and
                ``is_stale(entity) -> bool``, or ``None`` to disable
                summary functionality.

        """
        self.summary_service = service

    def set_project_root(self, path: Any) -> None:
        """Set the project root directory for child widgets that need file paths.

        Propagates the path to the gallery widget so it can resolve image
        paths relative to the world directory.

        Args:
            path: A :class:`pathlib.Path` (or path-like) object pointing to
                the active world's root directory.

        """
        if hasattr(self, "gallery"):
            self.gallery.set_project_root(path)

    def _connect_dirty_signals(self) -> None:
        """Connect form-field change signals to the dirty-state tracker.

        After this call, any user edit to the name, type, description, tags,
        or attributes fields will mark the editor as having unsaved changes via
        :meth:`set_dirty`.

        """
        self.name_edit.textChanged.connect(lambda: self.set_dirty(True))
        self.type_edit.currentTextChanged.connect(lambda: self.set_dirty(True))
        self.desc_edit.textChanged.connect(lambda: self.set_dirty(True))
        self.tag_editor.tags_changed.connect(lambda: self.set_dirty(True))

        # Connect attribute and sheet builder changes to both dirty state AND sync
        self.attribute_editor.attributes_changed.connect(self._on_attributes_changed)
        self.sheet_builder.attributes_changed.connect(self._on_sheet_changed)

    def _on_attributes_changed(self) -> None:
        """Handle changes from the attribute editor table."""
        self.set_dirty(True)
        self._sync_attributes(source="table")

    def _on_sheet_changed(self) -> None:
        """Handle changes from the sheet builder."""
        self.set_dirty(True)
        self._sync_attributes(source="sheet")

    def _sync_attributes(self, source: str) -> None:
        """Synchronize values between Attribute Editor and Sheet Builder.

        Args:
            source (str): "table" if the change originated in the attribute editor,
                or "sheet" if it originated in the sheet builder.
        """
        if self._is_loading:
            return

        if source == "sheet":
            sheet_attrs = self.sheet_builder.get_attributes()
            attr_attrs = self.attribute_editor.get_attributes()

            for key, val in sheet_attrs.items():
                if key in attr_attrs and attr_attrs[key] != val:
                    self.attribute_editor.update_attribute_value(key, val)
                elif key not in attr_attrs:
                    self.attribute_editor._block_signals = True
                    self.attribute_editor._add_row(key, val)
                    self.attribute_editor._block_signals = False

            for key in list(attr_attrs.keys()):
                if key not in sheet_attrs and key in self.sheet_builder._pairs:
                    # User removed an attribute from the table?
                    pass
        elif source == "table":
            sheet_attrs = self.sheet_builder.get_attributes()
            attr_attrs = self.attribute_editor.get_attributes()

            for key, val in attr_attrs.items():
                if key in sheet_attrs and sheet_attrs[key] != val:
                    self.sheet_builder.update_attribute_value(key, val)
                elif key not in sheet_attrs and key in self.sheet_builder._pairs:
                    # Attribute was added to the table, but the sheet only shows
                    # things in its layout. We don't auto-add to the sheet layout.
                    pass

            # If removed from table, remove from sheet
            for key in list(sheet_attrs.keys()):
                if key not in attr_attrs:
                    setattr(self.sheet_builder, "_block_signals", True)
                    self.sheet_builder.remove_attribute(key)
                    setattr(self.sheet_builder, "_block_signals", False)

    def update_suggestions(
        self,
        items: list[tuple[str, str, str]] | None = None,
        names: list[str] | None = None,
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

        # Store for RelationEditDialog
        self._suggestion_items = items or []

    def merge_wiki_completions(self, names: list[str]) -> None:
        """Merge semantic suggestion names into the description field completer.

        Args:
            names: Additional display names to add.

        """
        self.desc_edit.merge_completions(names)

    def update_tag_suggestions(self, tags: list[str]) -> None:
        """Update the tag autocomplete suggestions in the tag editor.

        Args:
            tags: List of known tag strings to offer as suggestions.

        """
        self.tag_editor.update_suggestions(tags)

    def update_attribute_suggestions(self, keys: list[str]) -> None:
        """Update the attribute key autocomplete suggestions.

        Args:
            keys: List of known attribute key strings to offer as suggestions.

        """
        self.attribute_editor.update_suggestions(keys)

    def update_relation_type_suggestions(self, types: list[str]) -> None:
        """Update the relation type suggestions used in the relation dialog.

        Args:
            types: List of known relation type strings (e.g. ``["caused",
                "mentions", "related"]``).

        """
        self._suggestion_types = types

    def update_entity_type_suggestions(self, types: list[str]) -> None:
        """Update the entity type combobox with database-sourced type suggestions.

        Merges the provided types with the built-in default types and
        refreshes the combobox while preserving the current selection.

        Args:
            types: Entity type strings fetched from the database to merge
                with the hard-coded defaults.

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
        self,
        entity: Entity | None,
        relations: list[Any] | None = None,
        incoming_relations: list[Any] | None = None,
        maps_data: list[Any] | None = None,
    ) -> None:
        """Populate the editor UI with data from the given entity and its relations.

        Loads all editable fields (name, type, description), attributes, tags,
        gallery images, and the summary widget.  Outgoing and incoming
        relations are rendered in the Relations tab.  The editor is enabled and
        the dirty flag is cleared after loading.

        Args:
            entity: The entity whose data will be loaded into the editor.
            relations: Outgoing relation dicts to display; each dict must
                contain at least ``"target_id"``, ``"rel_type"``, and ``"id"``.
                Pass ``None`` to display no outgoing relations.
            incoming_relations: Incoming relation dicts to display; each dict
                must contain at least ``"source_id"``, ``"rel_type"``, and
                ``"id"``.  Pass ``None`` to display no incoming relations.
            maps_data: List of :class:`~src.core.map.Map` objects used to
                populate the read-only Raster Maps section.  Pass ``None``
                to leave the section unchanged.

        """
        # Handle missing entity (e.g., deleted)
        if entity is None:
            self._current_entity_id = None
            self._current_created_at = 0.0
            self._reset_pending_summary()
            self.summary_widget.clear_summary()
            self._empty_state.show()
            self._content_widget.hide()
            self.set_dirty(False)
            self.gallery.set_owner("", "")
            self.clear_authoring_context()
            return

        self._is_loading = True
        try:
            self._reset_pending_summary()
            self._current_entity_id = entity.id
            self._current_created_at = entity.created_at

            # Preserve scroll position and description cursor across reload
            scroll_pos = self.scroll_area.verticalScrollBar().value()
            desc_cursor, desc_had_focus = self._save_desc_cursor_state()

            # Block signals
            self._set_input_signals_blocked(True)

            from src.core.theme_manager import ThemeManager

            theme = ThemeManager().get_theme()
            self.tag_editor.set_base_color(theme["entity_main"])

            # Block signals to prevent dirty trigger during load
            self.name_edit.blockSignals(True)
            self.type_edit.blockSignals(True)
            self.desc_edit.blockSignals(True)

            self._load_entity_fields(entity)
            self._load_entity_attributes(entity)
            self.exit_read_only_mode()
            self._load_entity_relations(relations, incoming_relations)

            self._empty_state.hide()
            self._content_widget.show()
            self.setEnabled(True)

            # Unblock & Reset
            self.name_edit.blockSignals(False)
            self.type_edit.blockSignals(False)
            self.desc_edit.blockSignals(False)
            self.set_dirty(False)

            # Restore scroll position and description cursor
            self.scroll_area.verticalScrollBar().setValue(scroll_pos)
            self._restore_desc_cursor_state(desc_cursor, desc_had_focus)
        finally:
            self._is_loading = False

        self._update_raster_appearances(maps_data or [])
        self.authoring_context_refresh_requested.emit()

    @property
    def current_entity_id(self) -> str | None:
        """Return the Entity currently shown by the editor."""
        return self._current_entity_id

    def set_authoring_context_loading(self) -> None:
        """Show the Context tab's loading state."""
        self.authoring_context.set_loading()

    def clear_authoring_context(self) -> None:
        """Clear the Context tab when no Entity is selected."""
        self.authoring_context.clear_context()

    def set_authoring_context_unavailable(self) -> None:
        """Show a non-fatal context lookup failure."""
        self.authoring_context.set_unavailable()

    def set_authoring_context(self, context: EntityAuthoringContext) -> None:
        """Render a validated Entity context snapshot."""
        self.authoring_context.set_entity_context(context)

    def _update_raster_appearances(self, maps_data: list) -> None:
        """Refresh the Raster Maps panel for the current entity.

        Args:
            maps_data: List of :class:`~src.core.map.Map` objects from the
                current project.  Pass an empty list to clear the panel.
        """
        current_entity_id = self._current_entity_id
        if not current_entity_id:
            return

        from src.gui.widgets.map.raster_mapping import (
            build_item_raster_index,
            resolve_node_name,
        )

        maps_dicts = [
            {"id": m.id, "attributes": getattr(m, "attributes", None) or {}}
            for m in maps_data
        ]
        index = build_item_raster_index(maps_dicts)
        refs = index.get(current_entity_id, [])

        if not refs:
            self.raster_appearances_label.setText("Not linked to any raster map.")
            return

        map_by_id = {m.id: m for m in maps_data}
        lines = []
        for ref in refs:
            map_obj = map_by_id.get(ref.map_id)
            map_name = getattr(map_obj, "name", ref.map_id) if map_obj else ref.map_id
            layer_name = (
                resolve_node_name(getattr(map_obj, "layers", None), ref.node_id)
                if map_obj
                else None
            ) or ref.node_id
            if ref.mode == "linked":
                lines.append(f"• {map_name} / {layer_name}  (continuous layer)")
            else:
                value_str = (
                    f"value {ref.value}"
                    if ref.mode == "exact"
                    else f"range {ref.min}–{ref.max}"
                )
                label = ref.label.strip() if ref.label else "(unlabelled)"
                lines.append(f"• {label}  ·  {map_name} / {layer_name}  ({value_str})")

        self.raster_appearances_label.setText("\n".join(lines))

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

        # Load sheet builder with the same display attributes + stored layout
        sheet_layout = entity.attributes.get("_sheet_layout")
        self.sheet_builder.blockSignals(True)
        try:
            self.sheet_builder.load_attributes(display_attrs, sheet_layout)
        finally:
            self.sheet_builder.blockSignals(False)

        self.tag_editor.blockSignals(True)
        try:
            self.tag_editor.load_tags(entity.tags)
        finally:
            self.tag_editor.blockSignals(False)

        self.gallery.set_owner("entity", entity.id)

        self.summary_widget.clear_summary()
        summary_data = entity.attributes.get("_summary_data")
        if summary_data:
            with suppress(Exception):
                data = SummaryData.from_dict(summary_data)
                self.summary_widget.set_summary(data)

            self.summary_widget.set_stale(is_summary_stale(entity))

    def _load_entity_relations(
        self, relations: list | None, incoming_relations: list | None
    ) -> None:
        """Loads outgoing and incoming relations into the relation list widget.

        Args:
            relations: List of outgoing relation dicts, or None.
            incoming_relations: List of incoming relation dicts, or None.

        """
        self.rel_list.clear()

        this_name = self.name_edit.text() or "this"

        if relations:
            for rel in relations:
                target_display = rel.get("target_name") or rel["target_id"]
                label = f"{this_name} --{rel['rel_type']}--> {target_display}"

                widget = RelationItemWidget(
                    label=label,
                    target_id=rel["target_id"],
                    target_name=target_display,
                    attributes=cast(dict[str, Any], rel.get("attributes")),
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
                label = f"{source_display} --{rel['rel_type']}--> {this_name}"

                widget = RelationItemWidget(
                    label=label,
                    target_id=rel["source_id"],
                    target_name=source_display,
                    attributes=cast(dict[str, Any], rel.get("attributes")),
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

        # Timeline should only show relations from events, not entity-to-entity relations
        event_relations = [
            rel for rel in (incoming_relations or [])
            if rel.get("source_event_date") is not None
        ]
        self.timeline_display.set_relations(event_relations)

    @Slot(dict)
    def _on_theme_changed(self, theme: dict) -> None:
        """Apply a new theme to editor UI elements.

        Re-applies stylesheets that cannot be handled by Qt's global QSS
        (e.g. tool-button menu-indicator overrides).

        Args:
            theme: Theme token dict emitted by
                :class:`~src.core.theme_manager.ThemeManager`.

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
        """Handle the Save button click.

        Assembles the current form data into a dict and emits
        :attr:`save_requested`.  If the save button currently reads
        *"Return to Present"* (temporal-view mode), emits
        :attr:`return_to_present_requested` instead and returns early.

        The emitted dict contains the keys ``"id"``, ``"name"``, ``"type"``,
        ``"description"``, ``"attributes"``, and ``"tags"``.  Tags are also
        stored inside ``"attributes"`` under the ``"_tags"`` key.  Any hidden
        (underscore-prefixed) attributes loaded with the entity are restored
        before emitting, and a pending AI-generated summary (if any) is
        overlaid under ``"_summary_data"``.

        Note:
            The dirty flag is **not** cleared here.  It is cleared when the
            saved entity is reloaded via :meth:`load_entity`, which avoids
            race conditions between the signal-processing pipeline and the
            reload cycle.

        """
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

            if self._pending_summary_changed:
                if self._pending_summary_data is None:
                    base_attrs.pop("_summary_data", None)
                else:
                    base_attrs["_summary_data"] = self._pending_summary_data

            # Persist the sheet layout arrangement
            sheet_layout = self.sheet_builder.get_layout()
            if sheet_layout:
                base_attrs["_sheet_layout"] = sheet_layout

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
        """Discard unsaved changes by emitting a signal to reload the current entity.

        Emits :attr:`discard_requested` with the current entity ID so the
        coordinator can re-fetch the entity from the database and call
        :meth:`load_entity`, effectively reverting all unsaved edits.

        """
        if not self._current_entity_id:
            return

        self.discard_requested.emit(self._current_entity_id)

    def clear(self) -> None:
        """Clear all editor fields and return to the empty state.

        Resets the internal entity ID, clears the name, description, and
        relation list, then hides the content widget and shows the empty state.

        """
        self._current_entity_id = None
        self._reset_pending_summary()
        self.summary_widget.clear_summary()
        self.name_edit.clear()
        self.desc_edit.clear()
        self.rel_list.clear()
        self._content_widget.hide()
        self._empty_state.show()

    @Slot()
    def _on_add_relation(self) -> None:
        """Open the relation dialog to add a new outgoing relation.

        Launches :class:`~src.gui.dialogs.relation_dialog.RelationEditDialog`
        pre-populated with known entity/event items and relation types for
        autocompletion.  On acceptance, emits :attr:`add_relation_requested`
        with the chosen target, type, bidirectional flag, and extra attributes.

        Returns early if no entity is currently loaded.

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
        rel_data = item.data(Qt.ItemDataRole.UserRole) or {}
        is_automatic = rel_data.get("rel_type") == "mentions"
        edit_action.setEnabled(not is_automatic)
        remove_action.setEnabled(not is_automatic)
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
        if rel_data.get("rel_type") == "mentions":
            return
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
        if rel_data.get("rel_type") == "mentions":
            return

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
        selected = self.rel_list.selectedItems()
        is_editable = bool(selected) and (
            selected[0].data(Qt.ItemDataRole.UserRole).get("rel_type") != "mentions"
        )
        self.btn_edit_rel.setEnabled(is_editable)
        self.btn_remove_rel.setEnabled(is_editable)

    def eventFilter(self, obj: QObject, event: Any) -> bool:
        """Event filter to handle clicks on empty space in relation lists."""
        from PySide6.QtCore import QEvent
        from PySide6.QtGui import QMouseEvent

        try:
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
                            parent.setCurrentItem(cast(QListWidgetItem, None))
                            return False  # Let Qt handle the event normally
                        elif item.isSelected():
                            # Clicked on already-selected item - deselect it
                            parent.clearSelection()
                            parent.setCurrentItem(cast(QListWidgetItem, None))
                            return True  # Prevent re-selection
        except RuntimeError:
            return False

        return super().eventFilter(obj, event)

    def get_generation_context(self) -> Dict[str, Any]:
        """Get context for LLM generation.

        Returns:
            Dict[str, Any]: Context dictionary containing:
                - 'name' (str): Entity name
                - 'type' (str): Entity type
                - 'existing_description' (str): Current description text
                - 'object_id' (str): Entity UUID for spatial-context lookup
                - 'object_type' (str): Always ``"entity"``

        """
        return {
            "name": self.name_edit.text(),
            "type": self.type_edit.currentText(),
            "existing_description": self.desc_edit.toPlainText(),
            "object_id": self._current_entity_id or "",
            "object_type": "entity",
        }

    @Slot(object)
    def _on_text_generated(self, result: GenerationReviewResult) -> None:
        """Apply explicitly reviewed generated text to the description."""
        if not isinstance(result, GenerationReviewResult) or not result.text:
            return

        current = self.desc_edit.toPlainText()
        new_text = apply_reviewed_generation(current, result)
        if new_text == current:
            return

        self.desc_edit.setPlainText(new_text)
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

    def display_temporal_state(
        self,
        entity_id: str,
        attributes: dict,
        playhead_time: float | None = None,
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
        current_layout = self.sheet_builder.get_layout()

        dlg = CreateTemplateDialog(
            source_tags=current_tags,
            source_attributes=current_attrs,
            source_type=current_type,
            source_layout=current_layout,
            parent=self,
        )

        if dlg.exec():
            # Emit signal to save this template
            # create_template_requested = Signal(dict)
            self.create_template_requested.emit(dlg.result_data)

    create_template_requested = Signal(dict)

    def set_read_only_mode(
        self, readonly: bool, reason: str | None = None
    ) -> None:
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
        self.summary_widget.set_controls_enabled(not readonly)

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
        """Handle a summary-generation request from the summary widget.

        Builds a temporary :class:`~src.core.entities.Entity` from the current
        form state and emits :attr:`summary_generation_requested` so the
        worker thread can call the LLM service.  The generate button is
        disabled while generation is in progress; it is re-enabled by
        :meth:`on_summary_generated`.

        Returns early if no entity is currently loaded.

        """
        logger.debug(
            f"[EntityEditor] _on_summary_generate_requested ID: "
            f"{self._current_entity_id}"
        )
        if not self._current_entity_id:
            logger.debug(
                "[EntityEditor] Aborting summary request: no current entity ID"
            )
            return

        # Construct temporary entity from form
        temp_entity = Entity(
            name=self.name_edit.text(),
            type=self.type_edit.currentText(),
            description=self.desc_edit.get_wiki_text(),
            id=self._current_entity_id,
            attributes=self.attribute_editor.get_attributes(),
        )
        logger.debug(
            f"[EntityEditor] Emitting summary_generation_requested for "
            f"{temp_entity.name}"
        )

        # Disable button
        self.summary_widget.generate_btn.setEnabled(False)
        self.summary_widget.generate_btn.setText("Generating...")

        self.summary_generation_requested.emit(temp_entity)

    @Slot(str)
    def _on_summary_edit_committed(self, text: str) -> None:
        """Stage a manually edited summary for the next item save."""
        if not self._current_entity_id:
            return
        item = self._current_summary_entity()
        summary = SummaryData(
            text=text,
            hash=calculate_summary_source_hash(item),
            timestamp=time.time(),
            model="",
            origin="manual",
        )
        self._pending_summary_changed = True
        self._pending_summary_data = summary.to_dict()
        self.summary_widget.set_summary(summary)
        self.summary_widget.set_stale(False)
        self.set_dirty(True)

    @Slot()
    def _on_summary_delete_requested(self) -> None:
        """Stage summary removal for the next item save."""
        self._pending_summary_changed = True
        self._pending_summary_data = None
        self.set_dirty(True)

    def _current_summary_entity(self) -> Entity:
        """Build an entity snapshot from the current editor fields."""
        return Entity(
            name=self.name_edit.text(),
            type=self.type_edit.currentText(),
            description=self.desc_edit.get_wiki_text(),
            id=self._current_entity_id or "",
            attributes=self.attribute_editor.get_attributes(),
        )

    def _reset_pending_summary(self) -> None:
        """Reset staged summary state after an item load or clear."""
        self._pending_summary_changed = False
        self._pending_summary_data = None

    @Slot(object)
    def on_summary_generated(self, summary_data: SummaryData) -> None:
        """Apply a freshly generated summary to the editor UI.

        Re-enables the generate button, updates the summary widget display,
        stores the summary dict as pending data to be merged on the next save,
        and marks the editor dirty so the user is prompted to save.

        Args:
            summary_data: The :class:`~src.core.summary.SummaryData` object
                returned by the LLM worker.

        """
        self.summary_widget.generate_btn.setEnabled(True)
        self.summary_widget.generate_btn.setText("Regenerate")

        try:
            self.summary_widget.set_summary(summary_data)
            self._pending_summary_changed = True
            self._pending_summary_data = summary_data.to_dict()
            self.set_dirty(True)
        except Exception as e:
            logger.error(f"Error applying summary: {e}")

    @Slot()
    def on_summary_generation_failed(self) -> None:
        """Reset UI state when summary generation fails.

        Re-enables the generate button and resets its text to allow retry.
        """
        self.summary_widget.generate_btn.setEnabled(True)
        # Keep existing button text (Generate/Regenerate) based on current state
        if self.summary_widget.generate_btn.text() == "Generating...":
            self.summary_widget.generate_btn.setText("Generate")
