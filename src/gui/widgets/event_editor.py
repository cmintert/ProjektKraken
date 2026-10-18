"""Event Editor Widget Module.

Provides a form interface for editing event details including name, date, description,
attributes, and relations.
"""

import logging
import math
import time
import traceback
from contextlib import suppress
from copy import deepcopy
from typing import Any, Dict

from PySide6.QtCore import QSize, Qt, Signal, Slot
from PySide6.QtGui import QDropEvent
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from src.core.ai_generation import GenerationReviewResult, apply_reviewed_generation
from src.core.authoring_context import EventAuthoringContext
from src.core.command import LoreMutationEffect
from src.core.events import Event
from src.core.summary_data import (
    SummaryData,
    calculate_summary_source_hash,
    is_summary_stale,
)
from src.core.theme_manager import ThemeManager
from src.gui.constants import (
    EDITOR_FORM_VERTICAL_SPACING,
    EDITOR_SECTION_SPACING,
)
from src.gui.mixins.autosave_mixin import AutoSaveManager
from src.gui.mixins.editor_mixin import BaseEditorMixin
from src.gui.utils.help_context import declare_inspection
from src.gui.utils.style_helper import StyleHelper
from src.gui.utils.suggestion_effects import apply_suggestion_effects
from src.gui.widgets.attribute_editor import AttributeEditorWidget
from src.gui.widgets.authoring_context_widget import AuthoringContextWidget
from src.gui.widgets.choice_inputs import ScrollSafeComboBox
from src.gui.widgets.connections_overview import ConnectionsOverview
from src.gui.widgets.editor_presentation import DisclosureButton, EditorPresentation
from src.gui.widgets.empty_state_widget import EmptyStateWidget
from src.gui.widgets.gallery_widget import GalleryWidget
from src.gui.widgets.llm_generation_widget import LLMGenerationWidget
from src.gui.widgets.relation_authoring import RelationAuthoring
from src.gui.widgets.sheet_builder import SheetBuilderWidget
from src.gui.widgets.splitter_tab_inspector import SplitterTabInspector
from src.gui.widgets.standard_buttons import (
    DestructiveButton,
    StandardButton,
)
from src.gui.widgets.summary_widget import SummaryWidget
from src.gui.widgets.tag_editor import TagEditorWidget
from src.gui.widgets.temporal_range_widget import TemporalRangeWidget
from src.gui.widgets.wiki_text_edit import ResizableWikiTextEditField, WikiTextEdit
from src.gui.widgets.wrapping_buttons import WrappingPrimaryButton as PrimaryButton

logger = logging.getLogger(__name__)


class EventEditorWidget(BaseEditorMixin, QWidget):
    """A form to edit the details of an Event.

    Emits 'save_requested' signal with the modified Event object. Emits
    'add_relation_requested' signal (source, target, type).

    Signals:
        save_requested(dict): Emitted when user clicks Save; payload is the event data.
        discard_requested(str): Emitted when user discards changes; payload is item_id.
        add_relation_requested(str, str, str, dict, bool): Request to create a relation
            (source_id, target_id, rel_type, attributes, bidirectional).
        remove_relation_requested(str): Request to delete a relation by rel_id.
        update_relation_requested(str, str, str, dict): Request to update a relation
            (rel_id, target_id, rel_type, attributes).
        inject_ui_requested(str): Request to open the inject dialog for an event_id.
        create_template_requested(dict): Request to create a new template from data.
        summary_generation_requested(object): Request AI summary for the given Event.
        link_clicked(str): Emitted when a wiki link is clicked; payload is target_name.
        navigate_to_relation(str): Emitted when Go-to is clicked; payload is target_id.
        dirty_changed(bool): Emitted when the editor's dirty state changes.
        current_data_changed(dict): Emitted with current event data for live preview.
    """

    save_requested = Signal(dict)
    chronology_requested = Signal(list)
    discard_requested = Signal(str)
    connections: ConnectionsOverview
    relation_authoring: RelationAuthoring
    btn_add_rel: StandardButton
    btn_edit_rel: StandardButton
    btn_remove_rel: DestructiveButton

    add_relation_requested = Signal(str, str, str, dict, bool)
    remove_relation_requested = Signal(str)
    update_relation_requested = Signal(str, str, str, dict)
    relation_authoring_requested = Signal(dict)

    inject_ui_requested = Signal(str)
    create_template_requested = Signal(dict)
    summary_generation_requested = Signal(object)

    # ... (omitted)

    link_clicked = Signal(str)
    peek_requested = Signal(str)
    navigate_to_relation = Signal(str)
    dirty_changed = Signal(bool)
    focus_writing_requested = Signal()
    current_data_changed = Signal(dict)
    completion_prefix_changed = Signal(str)
    create_new_requested = Signal()
    authoring_context_refresh_requested = Signal()
    show_world_at_event_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initializes the editor widget with form fields.

        Args:
            parent: The parent widget, if any.

        """
        QWidget.__init__(self, parent)
        self._current_event_id: str | None = None
        self._temporal_metadata: dict[str, Any] = {}
        self._chronology_events: list[Event] = []
        self._loaded_temporal_state: tuple[Any, float, float] | None = None
        self.autosave_manager = AutoSaveManager(self)

        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        main_layout = self._build_editor_shell()

        self._is_loading = False
        self._is_dirty = False
        self._calendar_converter = None

        self._build_header(main_layout)

        # Splitter-based tab inspector for vertical stacking
        self.inspector = SplitterTabInspector()
        main_layout.addWidget(self.inspector)

        self._build_details_tab()
        self._connect_field_signals()

        self._build_secondary_tabs(parent)
        self._build_action_buttons(main_layout)
        self._initialize_editor_state()
        self._date_draft_active = False
        self._date_draft_base_dirty = False
        self._date_draft_other_changes = False
        self.temporal_widget.draft_changed.connect(self._on_date_draft_changed)
        self._presentation = EditorPresentation(self)

    def _on_date_draft_changed(self, pending: bool) -> None:
        """Protect unaccepted date text from autosave and reloads."""
        if self._is_loading:
            return
        if pending and not self._date_draft_active:
            self._date_draft_active = True
            self._date_draft_base_dirty = self._is_dirty
            self._date_draft_other_changes = False
        super().set_dirty(self._is_dirty or pending)
        self._refresh_save_status()
        if pending:
            self.autosave_manager.stop_timer()
            self.btn_save.setEnabled(False)
            self.btn_save.setToolTip(
                "Apply or correct the date, or press Esc to restore."
            )
        else:
            if self._date_draft_active:
                self._date_draft_active = False
                self.set_dirty(
                    self._date_draft_base_dirty or self._date_draft_other_changes
                )
            self.btn_save.setEnabled(self._is_dirty)
            self.btn_save.setToolTip("")
            if self._is_dirty:
                self.autosave_manager.start_timer()

    def set_dirty(self, dirty: bool) -> None:
        """Keep autosave paused whenever a date draft is outstanding."""
        if dirty and getattr(self, "_date_draft_active", False):
            # Actual fields also call set_dirty; draft tracking uses the base
            # method below to distinguish cancellation from a real edit.
            self._date_draft_other_changes = True
        super().set_dirty(dirty)
        if dirty:
            self._save_failed = False
        self._refresh_save_status()
        if self.temporal_widget.has_pending_draft():
            self.autosave_manager.stop_timer()
            self.btn_save.setEnabled(False)

    def _refresh_save_status(self) -> None:
        """Render persistence separately from date validation feedback."""
        if not hasattr(self, "save_status"):
            return
        if self.save_pending:
            text = "Saving…"
        elif getattr(self, "_save_failed", False):
            text = "Save failed — changes retained"
        elif self._is_dirty or self.temporal_widget.has_pending_draft():
            text = "Unsaved changes"
        else:
            text = "Saved"
        self.save_status.setText(text)

    def begin_save(self) -> int | None:
        """Show pending delivery only after a revision has been captured."""
        revision = super().begin_save()
        if revision is not None:
            self._save_failed = False
        self._refresh_save_status()
        return revision

    def finish_save(self, revision: int, success: bool) -> bool:
        """Ignore stale acknowledgements and retain newer local drafts."""
        if getattr(self, "_pending_save_revision", None) != revision:
            return False
        complete = super().finish_save(revision, success)
        self._save_failed = not success
        self._refresh_save_status()
        return complete

    def reset_draft_tracking(self) -> None:
        """Clear delivery feedback when deliberately loading another snapshot."""
        super().reset_draft_tracking()
        self._save_failed = False
        self._refresh_save_status()

    def has_unsaved_changes(self) -> bool:
        """Include typed date drafts in navigation and close guards."""
        authoring = getattr(self, "relation_authoring", None)
        return (
            self._is_dirty
            or self.temporal_widget.has_pending_draft()
            or (authoring is not None and authoring.is_dirty())
        )

    def _build_editor_shell(self) -> QVBoxLayout:
        """Build empty/content containers and return the content layout."""
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        outer_layout = QVBoxLayout(self)
        StyleHelper.apply_no_margins(outer_layout)
        self._empty_state = EmptyStateWidget(
            "No Event Selected",
            "Select an event from the list to view and edit its details.",
        )
        declare_inspection(
            self._empty_state.add_action(
                "New Event", self.create_new_requested.emit, primary=True
            ),
            "empty.EventEditorWidget._build_editor_shell.269|authoring.create|help-inspect-empty-eventeditorwidget-build-editor-shell-269",
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
        """Build event timing, description, and collapsible detail sections."""
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
        self._build_temporal_description_fields()
        self._build_summary_section()
        self._build_llm_section()
        self._build_raster_appearances_section()
        details_layout.addLayout(self.form_layout)
        self.tab_details.setMinimumHeight(0)
        self.inspector.add_tab(
            self.tab_details, "Details", "Event timing, description, and AI summary"
        )

    def _build_temporal_description_fields(self) -> None:
        """Build the temporal range and event description fields."""
        self.desc_edit = declare_inspection(
            WikiTextEdit(),
            "src-gui-widgets-event-editor-eventeditorwidget-build-temporal-description-fields-self-desc-edit|authoring.details|help-inspect-src-gui-widgets-event-editor-eventeditorwidget-build-temporal-description-fields-self-desc-edit",
        )
        self.desc_edit.link_clicked.connect(self.link_clicked.emit)
        self.desc_edit.peek_requested.connect(self.peek_requested.emit)
        self.desc_edit.completion_prefix_changed.connect(
            self.completion_prefix_changed.emit
        )
        self.description_field = declare_inspection(
            ResizableWikiTextEditField(self.desc_edit),
            "src-gui-widgets-event-editor-eventeditorwidget-build-temporal-description-fields-self-description-field|authoring.details|help-inspect-src-gui-widgets-event-editor-eventeditorwidget-build-temporal-description-fields-self-description-field",
        )
        self.temporal_widget = TemporalRangeWidget()
        if self._calendar_converter:
            self.temporal_widget.set_calendar_converter(self._calendar_converter)
        self.form_layout.addRow(self.temporal_widget)
        from src.gui.widgets.overflow_toolbar import OverflowToolBar

        temporal_actions = OverflowToolBar()
        self.chronology_button = declare_inspection(
            QToolButton(),
            "src-gui-widgets-event-editor-eventeditorwidget-build-temporal-description-fields-self-chronology-button|event.chronology|help-inspect-src-gui-widgets-event-editor-eventeditorwidget-build-temporal-description-fields-self-chronology-button",
        )
        self.chronology_button.setText("Chronology…")
        self.chronology_button.setStyleSheet(StyleHelper.get_tool_button_style())
        self.chronology_button.clicked.connect(self._edit_chronology)
        temporal_actions.add_button(self.chronology_button)
        self.temporal_evidence_button = declare_inspection(
            QToolButton(),
            "src-gui-widgets-event-editor-eventeditorwidget-build-temporal-description-fields-self-temporal-evidence-button|date.evidence|help-inspect-src-gui-widgets-event-editor-eventeditorwidget-build-temporal-description-fields-self-temporal-evidence-button",
        )
        self.temporal_evidence_button.setText("Date evidence…")
        self.temporal_evidence_button.setStyleSheet(StyleHelper.get_tool_button_style())
        self.temporal_evidence_button.clicked.connect(self._edit_temporal_evidence)
        temporal_actions.add_button(self.temporal_evidence_button)
        from src.gui.widgets.wrapping_buttons import WrappingToolButton

        self.btn_show_world_at_event = declare_inspection(
            WrappingToolButton(),
            "src-gui-widgets-event-editor-eventeditorwidget-build-temporal-description-fields-self-btn-show-world-at-event|timeline.viewing|help-inspect-src-gui-widgets-event-editor-eventeditorwidget-build-temporal-description-fields-self-btn-show-world-at-event",
        )
        self.btn_show_world_at_event.setText("Show world at this event")
        self.btn_show_world_at_event.setStyleSheet(StyleHelper.get_tool_button_style())
        self.btn_show_world_at_event.setToolTip(
            "Move the playhead to this event's saved date. "
            "World Time and unsaved event edits stay unchanged."
        )
        self.btn_show_world_at_event.setEnabled(False)
        self.btn_show_world_at_event.clicked.connect(self._show_world_at_event)
        self.form_layout.addRow(self.btn_show_world_at_event)
        self.form_layout.addRow(temporal_actions)
        self.date_edit = self.temporal_widget.date_start
        self.end_date_edit = self.temporal_widget.date_end
        self.duration_widget = self.temporal_widget.duration_widget
        self.form_layout.addRow("Description:", self.description_field)

    def _build_summary_section(self) -> None:
        """Build the collapsible event summary section."""
        self.summary_container = QWidget()
        section_layout = QVBoxLayout(self.summary_container)
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(EDITOR_SECTION_SPACING)
        self.summary_checkbox = declare_inspection(
            DisclosureButton("Summary"),
            "src-gui-widgets-event-editor-eventeditorwidget-build-summary-section-self-summary-checkbox|authoring.details|help-inspect-src-gui-widgets-event-editor-eventeditorwidget-build-summary-section-self-summary-checkbox",
        )
        section_layout.addWidget(self.summary_checkbox)
        self.summary_widget = SummaryWidget()
        self.summary_widget.setVisible(False)
        self.summary_widget.generate_requested.connect(
            self._on_summary_generate_requested
        )
        self.summary_widget.edit_committed.connect(self._on_summary_edit_committed)
        self.summary_widget.delete_requested.connect(self._on_summary_delete_requested)
        section_layout.addWidget(self.summary_widget)
        self.summary_checkbox.toggled.connect(self.summary_widget.setVisible)
        self.form_layout.addRow(self.summary_container)

    def _build_llm_section(self) -> None:
        """Build the collapsible event description-generation section."""
        self.llm_container = QWidget()
        section_layout = QVBoxLayout(self.llm_container)
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(EDITOR_SECTION_SPACING)
        self.llm_checkbox = declare_inspection(
            DisclosureButton("Generate description"),
            "src-gui-widgets-event-editor-eventeditorwidget-build-llm-section-self-llm-checkbox|authoring.details|help-inspect-src-gui-widgets-event-editor-eventeditorwidget-build-llm-section-self-llm-checkbox",
        )
        section_layout.addWidget(self.llm_checkbox)
        self.llm_generator = LLMGenerationWidget(self, context_provider=self)
        self.llm_generator.setVisible(False)
        self.llm_generator.text_generated.connect(self._on_text_generated)
        section_layout.addWidget(self.llm_generator)
        self.llm_checkbox.toggled.connect(self.llm_generator.setVisible)
        self.form_layout.addRow(self.llm_container)

    def _build_raster_appearances_section(self) -> None:
        """Build the read-only collapsible raster-appearance section."""
        self.raster_appearances_container = QWidget()
        section_layout = QVBoxLayout(self.raster_appearances_container)
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(EDITOR_SECTION_SPACING)
        self.raster_appearances_checkbox = declare_inspection(
            DisclosureButton("Raster maps"),
            "src-gui-widgets-event-editor-eventeditorwidget-build-raster-appearances-section-self-raster-appearances-checkbox|authoring.details|help-inspect-src-gui-widgets-event-editor-eventeditorwidget-build-raster-appearances-section-self-raster-appearances-checkbox",
        )
        section_layout.addWidget(self.raster_appearances_checkbox)
        self.raster_appearances_label = QLabel("Not linked to any raster map.")
        self.raster_appearances_label.setWordWrap(True)
        self.raster_appearances_label.setVisible(False)
        section_layout.addWidget(self.raster_appearances_label)
        self.raster_appearances_checkbox.toggled.connect(
            self.raster_appearances_label.setVisible
        )
        self.form_layout.addRow(self.raster_appearances_container)

    def _connect_field_signals(self) -> None:
        """Connect editor fields to dirty tracking and live preview."""
        self.name_edit.textChanged.connect(self._on_field_changed)
        self.temporal_widget.start_changed.connect(
            lambda _value: self._on_field_changed()
        )
        self.temporal_widget.start_changed.connect(
            lambda _value: self.authoring_context_refresh_requested.emit()
        )
        self.temporal_widget.duration_changed.connect(
            lambda _value: self._on_field_changed()
        )
        self.temporal_widget.end_changed.connect(
            lambda _value: self._on_field_changed()
        )
        self.type_edit.editTextChanged.connect(self._on_field_changed)
        self.type_edit.currentIndexChanged.connect(self._on_field_changed)
        self.desc_edit.textChanged.connect(self._on_field_changed)

    def _build_header(self, main_layout: QVBoxLayout) -> None:
        """Build the persistent event name, type, and inject header."""
        self.header_widget = QWidget()
        header_layout = QVBoxLayout(self.header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        self.header_form = QFormLayout()
        self.header_form.setVerticalSpacing(EDITOR_FORM_VERTICAL_SPACING)
        self.header_form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )
        self.header_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        self.header_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        from src.gui.widgets.standard_buttons import LabelSizedToolButton

        self.btn_inject = declare_inspection(
            LabelSizedToolButton(),
            "src-gui-widgets-event-editor-eventeditorwidget-build-header-self-btn-inject|authoring.details|help-inspect-src-gui-widgets-event-editor-eventeditorwidget-build-header-self-btn-inject",
        )
        self.btn_inject.setText("Fast Inject")
        self.btn_inject.setToolTip("Quickly apply templates or snippets to this event")
        self.btn_inject.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.btn_inject.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.btn_inject.setStyleSheet(
            StyleHelper.get_tool_button_style()
            + " QToolButton::menu-indicator { image: none; }"
        )
        ThemeManager().theme_changed.connect(self._on_theme_changed)
        self.inject_menu = declare_inspection(
            QMenu(self.btn_inject),
            "src-gui-widgets-event-editor-eventeditorwidget-build-header-self-inject-menu|authoring.details|help-inspect-src-gui-widgets-event-editor-eventeditorwidget-build-header-self-inject-menu",
        )
        self.btn_inject.setMenu(self.inject_menu)
        self.inject_menu.aboutToShow.connect(self._populate_inject_menu)
        self.name_edit = declare_inspection(
            QLineEdit(),
            "src-gui-widgets-event-editor-eventeditorwidget-build-header-self-name-edit|authoring.details|help-inspect-src-gui-widgets-event-editor-eventeditorwidget-build-header-self-name-edit",
        )
        name_layout = QHBoxLayout()
        name_layout.addWidget(self.name_edit)
        name_layout.addWidget(self.btn_inject)
        self.type_edit = declare_inspection(
            ScrollSafeComboBox(),
            "src-gui-widgets-event-editor-eventeditorwidget-build-header-self-type-edit|authoring.details|help-inspect-src-gui-widgets-event-editor-eventeditorwidget-build-header-self-type-edit",
        )
        self.type_edit.addItems(
            ["generic", "cosmic", "historical", "personal", "session", "combat"]
        )
        self.type_edit.setEditable(True)
        self.type_edit.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.header_form.addRow("Name:", name_layout)
        self.header_form.addRow("Type:", self.type_edit)
        header_layout.addLayout(self.header_form)
        main_layout.addWidget(self.header_widget)

    def _build_secondary_tabs(self, parent: QWidget | None) -> None:
        """Build tags, relations, gallery, attributes, and sheet tabs."""
        self._build_context_tab()
        self._build_tags_tab()
        self.tab_relations = QWidget()
        self._setup_relations_tab()
        self.inspector.add_tab(
            self.tab_relations,
            "Relations",
            "View and edit connections to participants and locations",
        )
        self._build_gallery_tab(parent)
        self._build_attributes_tab()
        self._build_sheet_tab()

    def _build_context_tab(self) -> None:
        """Build the read-only Event authoring-context tab."""
        self.tab_context = QWidget()
        layout = QVBoxLayout(self.tab_context)
        StyleHelper.apply_no_margins(layout)
        self.authoring_context = AuthoringContextWidget()
        self.authoring_context.navigate_requested.connect(
            self.navigate_to_relation.emit
        )
        layout.addWidget(self.authoring_context)
        self.inspector.add_tab(
            self.tab_context,
            "Context",
            "What Kraken knows while writing this Event",
        )

    def _build_tags_tab(self) -> None:
        """Build the event tags tab."""
        self.tab_tags = QWidget()
        tags_layout = QVBoxLayout(self.tab_tags)
        StyleHelper.apply_no_margins(tags_layout)
        self.tag_editor = TagEditorWidget()
        tags_layout.addWidget(self.tag_editor)
        self.inspector.add_tab(
            self.tab_tags, "Tags", "Manage organizational tags and metadata"
        )

    def _build_gallery_tab(self, parent: QWidget | None) -> None:
        """Build the event image gallery tab."""
        self.tab_gallery = QWidget()
        gallery_layout = QVBoxLayout(self.tab_gallery)
        gallery_layout.setContentsMargins(0, 0, 0, 0)
        self.gallery = GalleryWidget(parent)
        gallery_layout.addWidget(self.gallery)
        self.inspector.add_tab(
            self.tab_gallery, "Gallery", "Manage images and media attachments"
        )

    def _build_attributes_tab(self) -> None:
        """Build the structured event attributes tab."""
        self.tab_attributes = QWidget()
        attr_layout = QVBoxLayout(self.tab_attributes)
        StyleHelper.apply_no_margins(attr_layout)
        self.attribute_editor = AttributeEditorWidget()
        attr_layout.addWidget(self.attribute_editor)
        self.inspector.add_tab(
            self.tab_attributes, "Attributes", "Edit custom structured data fields"
        )

    def _build_sheet_tab(self) -> None:
        """Build the configurable event-sheet tab."""
        self.tab_sheet = QWidget()
        sheet_layout = QVBoxLayout(self.tab_sheet)
        StyleHelper.apply_no_margins(sheet_layout)
        self.sheet_builder = SheetBuilderWidget()
        sheet_layout.addWidget(self.sheet_builder)
        self.inspector.add_tab(
            self.tab_sheet, "Sheet", "Configure the visual layout for the event sheet"
        )

    def _build_action_buttons(self, main_layout: QVBoxLayout) -> None:
        """Build persistent discard and save controls."""
        from src.gui.widgets.action_flow_layout import ActionFlowLayout

        self.save_status = QLabel("Saved")
        self.save_status.setObjectName("InspectorSupportCaption")
        self.save_status.setWordWrap(True)
        self.save_status.setStyleSheet(StyleHelper.get_inspector_support_style())
        main_layout.addWidget(self.save_status)
        actions = QWidget()
        buttons = ActionFlowLayout(actions, uniform_height=True)
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.btn_save = declare_inspection(
            PrimaryButton("Save Changes"),
            "src-gui-widgets-event-editor-eventeditorwidget-build-action-buttons-self-btn-save|authoring.details|help-inspect-src-gui-widgets-event-editor-eventeditorwidget-build-action-buttons-self-btn-save",
        )
        self.btn_save.setEnabled(False)
        self.btn_save.clicked.connect(self._on_save)
        self.btn_discard = declare_inspection(
            StandardButton("Discard"),
            "src-gui-widgets-event-editor-eventeditorwidget-build-action-buttons-self-btn-discard|authoring.details|help-inspect-src-gui-widgets-event-editor-eventeditorwidget-build-action-buttons-self-btn-discard",
        )
        self.btn_discard.setEnabled(False)
        self.btn_discard.clicked.connect(self._on_discard)
        buttons.addWidget(self.btn_discard)
        buttons.addWidget(self.btn_save)
        main_layout.addWidget(actions)

    def _initialize_editor_state(self) -> None:
        """Initialize mutable state and dirty tracking for an empty editor."""
        self._current_created_at = 0.0
        self._is_dirty = False
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
        """Returns the current event ID or None."""
        return self._current_event_id

    def _get_editor_label(self) -> str:
        """Returns the editor label for logging."""
        return "EventEditor"

    def _show_drop_hint(self, rel_type: str = "related") -> None:
        """Show drop hint overlay during drag-over.

        Args:
            rel_type: Relation type to display in hint.
        """
        if self._drop_hint_label is None:
            self._drop_hint_label = QLabel(self)
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
        """Ignore whole-inspector drops; the labeled Connections target owns them."""
        event.ignore()

    def _create_relation(
        self, source_id: str, source_type: str, source_name: str, rel_type: str
    ) -> None:
        """Stage legacy drop intent through the shared connection draft."""
        payload = self.relation_authoring.resolve_drop(source_id, source_type)
        if payload is not None and self.relation_authoring.stage_drop(payload):
            self.relation_authoring.capture_type = rel_type
        self._is_drag_over = False
        self._hide_drop_hint()

    def set_summary_service(self, service: Any) -> None:
        """Sets the summary service."""
        self.summary_service = service

    def set_project_root(self, path: Any) -> None:
        """Sets the project root for child widgets."""
        if hasattr(self, "gallery"):
            self.gallery.set_project_root(path)

    def _setup_relations_tab(self) -> None:
        """Build the same Connections browser used by Entity inspectors."""
        from src.gui.widgets.connections_inspector import install_connections

        install_connections(self, "event")

    def _on_add_participant(self) -> None:
        """Capture a participant without mandatory refinement."""
        self.relation_authoring.capture("involved")

    def _on_add_location(self) -> None:
        """Capture a location without mandatory refinement."""
        self.relation_authoring.capture("located_at")

    def _on_edit_selected_relation(self) -> None:
        """Open the explicitly selected connection."""
        self.connections.edit_selected()

    def _on_remove_selected_relation(self) -> None:
        """Remove through the shared selection and draft guard."""
        self.connections.remove_selected()

    def _update_rel_button_states(self) -> None:
        """Refresh shared selection actions."""
        self.connections._update_summary()

    def _connect_dirty_signals(self) -> None:
        """Connects input widget signals to set_dirty(True)."""
        self.name_edit.textChanged.connect(lambda: self.set_dirty(True))
        self.temporal_widget.start_changed.connect(lambda val: self.set_dirty(True))
        # Duration/End Date logic triggers each other, but ultimately user interaction
        # should trigger dirty. Value changed is fine.
        self.temporal_widget.duration_changed.connect(lambda val: self.set_dirty(True))
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
                    pass
        elif source == "table":
            sheet_attrs = self.sheet_builder.get_attributes()
            attr_attrs = self.attribute_editor.get_attributes()

            for key, val in attr_attrs.items():
                if key in sheet_attrs and sheet_attrs[key] != val:
                    self.sheet_builder.update_attribute_value(key, val)
                elif key not in sheet_attrs and key in self.sheet_builder._pairs:
                    pass

            # If removed from table, remove from sheet
            for key in list(sheet_attrs.keys()):
                if key not in attr_attrs:
                    setattr(self.sheet_builder, "_block_signals", True)
                    self.sheet_builder.remove_attribute(key)
                    setattr(self.sheet_builder, "_block_signals", False)

    def set_calendar_converter(self, converter: Any) -> None:
        """Sets the calendar converter for date formatting.

        Args:
            converter: CalendarConverter instance or None.

        """
        timing_was_clean = not self.has_unsaved_temporal_changes()
        self._calendar_converter = converter
        self.temporal_widget.set_calendar_converter(converter)
        if (
            timing_was_clean
            and self._current_event_id is not None
            and self._loaded_temporal_state is not None
            and self._loaded_temporal_state[0] is None
        ):
            _, start, duration = self._loaded_temporal_state
            self.temporal_widget.set_values(start, duration)

    def _edit_temporal_evidence(self) -> None:
        """Edit a local evidence snapshot; the ordinary save command persists it."""
        from PySide6.QtWidgets import QDialog

        from src.core.date_parser import DateParser
        from src.core.temporal_expression import TemporalExpression
        from src.gui.dialogs.temporal_evidence_dialog import TemporalEvidenceDialog

        if not self._current_event_id or self._calendar_converter is None:
            return
        if not self.temporal_widget.commit_drafts():
            return
        metadata = deepcopy(self._temporal_metadata)
        expression = self.temporal_widget.date_start.get_expression()
        if expression is not None:
            metadata.update(schema=1, expression=expression.to_dict())
        dialog = TemporalEvidenceDialog(
            self._current_event_id,
            metadata,
            DateParser(self._calendar_converter._config),
            getattr(self, "_suggestion_items", []),
            self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._temporal_metadata = dialog.result_metadata
            if "expression" in self._temporal_metadata:
                self.temporal_widget.date_start.set_expression(
                    TemporalExpression.from_dict(self._temporal_metadata["expression"])
                )
                self.temporal_widget._on_start_changed(
                    self.temporal_widget.date_start.get_value()
                )
            self._show_temporal_evidence_summary()
            self._on_field_changed()

    def _show_temporal_evidence_summary(self) -> None:
        """Keep separate source claims discoverable after editing or reloading."""
        claims = self._temporal_metadata.get("claims", [])
        count = len(claims)
        self.temporal_evidence_button.setText(
            f"Date evidence… ({count} sources)" if count else "Date evidence…"
        )
        if count > 1:
            from src.core.temporal_authoring import conflicting_claims

            converter = self.temporal_widget.date_start._converter
            conflicting = converter is not None and conflicting_claims(
                self._temporal_metadata, converter
            )
            self.temporal_widget.date_start.feedback.setText(
                "Conflicting source dates: the sources place this event in different periods. Review Date evidence."
                if conflicting
                else "Multiple source dates are preserved separately. Open Date evidence to choose the event date."
            )

    def update_chronology_events(self, events: list[Event]) -> None:
        """Receive worker-confirmed event snapshots for chronology editing."""
        self._chronology_events = deepcopy(events)
        current = next(
            (event for event in events if event.id == self._current_event_id), None
        )
        if current is not None:
            constraints = current.attributes.get("_temporal_v2", {}).get(
                "constraints", []
            )
            if constraints:
                self._temporal_metadata["constraints"] = deepcopy(constraints)
            else:
                self._temporal_metadata.pop("constraints", None)
        from src.services.chronology_service import (
            collect_chronology,
            direct_chronology,
        )

        count = (
            len(direct_chronology(self._current_event_id, collect_chronology(events)))
            if self._current_event_id
            else 0
        )
        self.chronology_button.setText(
            f"Chronology… ({count} orderings)" if count else "Chronology…"
        )

    def has_unsaved_temporal_changes(self) -> bool:
        """Compare authored timing, ignoring a semantic date's layout coordinate."""
        if self.temporal_widget.has_pending_draft():
            return True
        if self._loaded_temporal_state is None:
            return False
        expression = self.temporal_widget.date_start.get_expression()
        loaded_expression, loaded_start, loaded_duration = self._loaded_temporal_state
        current_expression = expression.to_dict() if expression else None
        if (
            current_expression != loaded_expression
            or self.temporal_widget.get_duration() != loaded_duration
        ):
            return True
        return current_expression is None and not math.isclose(
            self.temporal_widget.get_start(),
            loaded_start,
            rel_tol=0,
            abs_tol=1e-9,
        )

    def mark_temporal_saved(self) -> None:
        """Advance the date baseline after an acknowledged editor save."""
        expression = self.temporal_widget.date_start.get_expression()
        self._loaded_temporal_state = (
            expression.to_dict() if expression else None,
            self.temporal_widget.get_start(),
            self.temporal_widget.get_duration(),
        )

    def _edit_chronology(self) -> None:
        """Open the event-centered order editor from a persisted date state."""
        from PySide6.QtWidgets import QDialog

        from src.gui.dialogs.event_chronology_dialog import EventChronologyDialog

        if not self._current_event_id or not self._chronology_events:
            return
        if self.has_unsaved_temporal_changes():
            QMessageBox.information(
                self,
                "Save the date first",
                "The date or duration has unsaved changes. Save Changes, then open Chronology again.",
            )
            return
        dialog = EventChronologyDialog(
            self._current_event_id,
            self._chronology_events,
            self._calendar_converter,
            self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.operations:
            self.chronology_requested.emit(dialog.operations)

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
        if items:
            self._suggestion_items = items
        else:
            self._suggestion_items = []

    def merge_wiki_completions(self, names: list[str]) -> None:
        """Merge semantic suggestion names into the description field completer.

        Args:
            names: Additional display names to add.

        """
        self.desc_edit.merge_completions(names)

    def apply_suggestion_effects(self, effects: list[LoreMutationEffect]) -> None:
        """Patch WikiLink and relation-dialog suggestions in place."""
        self.desc_edit.apply_completion_effects(effects)
        self._suggestion_items = apply_suggestion_effects(
            self._suggestion_items, effects
        )

    def update_tag_suggestions(self, tags: list[str]) -> None:
        """Updates tag suggestions."""
        self.tag_editor.update_suggestions(tags)

    def update_attribute_suggestions(self, keys: list[str]) -> None:
        """Updates attribute key suggestions."""
        self.attribute_editor.update_suggestions(keys)

    def update_relation_type_suggestions(self, types: list[str]) -> None:
        """Updates relation type suggestions."""
        self._suggestion_types = types

    def load_event(
        self,
        event: Event | None,
        relations: list[Any] | None = None,
        incoming_relations: list[Any] | None = None,
        maps_data: list[Any] | None = None,
    ) -> None:
        """Populates the form with event data and relationships.

        Args:
            event (Event): The event to edit.
            relations (list): List of outgoing relation dicts.
            incoming_relations (list): List of incoming relation dicts.

        """
        if (
            event is not None
            and event.id == self._current_event_id
            and self.temporal_widget.has_pending_draft()
        ):
            return
        new_id = event.id if event is not None else None
        if new_id != self._current_event_id:
            self.desc_edit.link_authoring.cancel()
            if not self.relation_authoring.prepare_to_leave():
                return
            self.relation_authoring.cancel()
        focus = getattr(self, "_focus_controller", None)
        if (
            focus is not None
            and focus.active is self
            and (event is None or event.id != self._current_event_id)
        ):
            focus.exit()
        same_event = event is not None and event.id == self._current_event_id
        range_expanded = self.temporal_widget.range_button.isChecked()
        self.temporal_widget.cancel_drafts()
        # Handle missing event (e.g., item was deleted)
        if event is None:
            self._current_event_id = None
            self.btn_show_world_at_event.setEnabled(False)
            if focus is not None:
                focus._update_action()
            self._current_created_at = 0.0
            self._reset_pending_summary()
            self.summary_widget.clear_summary()
            self._empty_state.show()
            self._content_widget.hide()
            self.set_dirty(False)
            self.gallery.set_owner("", "")
            self.reset_draft_tracking()
            self.authoring_context.clear_context()
            self.authoring_context_refresh_requested.emit()
            return

        self._reset_pending_summary()
        self._current_event_id = event.id
        self.btn_show_world_at_event.setEnabled(True)
        if focus is not None:
            focus._update_action()
        self._current_created_at = event.created_at  # Preserve validation data

        self._is_loading = True
        try:
            # Preserve scroll position and description cursor across reload
            scroll_pos = self.scroll_area.verticalScrollBar().value()
            desc_anchor, desc_cursor, desc_had_focus = self._save_desc_cursor_state()

            # Block signals to prevent dirty trigger during load
            self.name_edit.blockSignals(True)
            self.temporal_widget.blockSignals(True)
            self.type_edit.blockSignals(True)
            self.desc_edit.blockSignals(True)

            self._load_event_fields(event)
            if same_event:
                self.temporal_widget.range_button.setChecked(range_expanded)
            self._load_event_attributes(event)
            self._load_event_relations(relations, incoming_relations)

            # Unblock signals
            self.name_edit.blockSignals(False)
            self.temporal_widget.blockSignals(False)
            self.type_edit.blockSignals(False)
            self.desc_edit.blockSignals(False)

            self.set_dirty(False)
            self._empty_state.hide()
            self.reset_draft_tracking()
            self._content_widget.show()
            self.setEnabled(True)

            # Restore scroll position and description cursor
            self.scroll_area.verticalScrollBar().setValue(scroll_pos)
            self._restore_desc_cursor_state(desc_anchor, desc_cursor, desc_had_focus)
        finally:
            self._is_loading = False

        if focus is not None and focus.active is self:
            focus._update_title(self, self.name_edit.text())
            focus._update_status(self)
        self._update_raster_appearances(maps_data or [])
        self.authoring_context_refresh_requested.emit()

    @Slot()
    def _show_world_at_event(self) -> None:
        """Request inspection at the saved date without accepting editor drafts."""
        if self._current_event_id is not None:
            self.show_world_at_event_requested.emit(self._current_event_id)

    @property
    def current_event_id(self) -> str | None:
        """Return the Event currently shown by the editor."""
        return self._current_event_id

    def set_authoring_context_loading(self) -> None:
        """Show the Context tab's loading state."""
        self.authoring_context.set_loading()

    def clear_authoring_context(self) -> None:
        """Clear the Context tab when no Event is selected."""
        self.authoring_context.clear_context()

    def set_authoring_context_unavailable(self) -> None:
        """Show a non-fatal context lookup failure."""
        self.authoring_context.set_unavailable()

    def set_authoring_context(self, context: EventAuthoringContext) -> None:
        """Render a validated Event context snapshot."""
        self.authoring_context.set_context(
            context,
            date_label=self.temporal_widget.get_formatted_start_text(),
        )

    def _update_raster_appearances(self, maps_data: list) -> None:
        """Refresh the Raster Maps panel for the current event.

        Args:
            maps_data: List of :class:`~src.core.map.Map` objects from the
                current project.  Pass an empty list to clear the panel.
        """
        current_event_id = self._current_event_id
        if not current_event_id:
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
        refs = index.get(current_event_id, [])

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

    def _load_event_fields(self, event: Event) -> None:
        """Loads core form fields from the event, skipping redundant updates.

        Args:
            event: The event whose fields to load.

        """
        if self.name_edit.text() != event.name:
            self.name_edit.setText(event.name)

        # Load temporal fields in one call; TemporalRangeWidget handles
        # internal signal suppression and end-date recalculation.
        self.temporal_widget.set_values(event.lore_date, event.lore_duration)
        from src.core.temporal_expression import (
            TemporalExpression,
            expression_from_attributes,
        )

        self._temporal_metadata = deepcopy(event.attributes.get("_temporal_v2", {}))
        expression = expression_from_attributes(event.attributes)
        if expression is not None:
            self.temporal_widget.date_start.set_expression(expression)
            end_data = event.attributes["_temporal_v2"].get("end_expression")
            if end_data:
                self.temporal_widget.date_end.set_expression(
                    TemporalExpression.from_dict(end_data)
                )
            self.temporal_widget._update_range_summary()
        self._loaded_temporal_state = (
            expression.to_dict() if expression else None,
            event.lore_date,
            event.lore_duration,
        )
        if self._chronology_events:
            self.update_chronology_events(self._chronology_events)
        self._show_temporal_evidence_summary()

        if self.type_edit.currentText() != event.type:
            self.type_edit.setCurrentText(event.type)

        if self.desc_edit.get_wiki_text() != event.description:
            self.desc_edit.set_wiki_text(event.description)

    def _load_event_attributes(self, event: Event) -> None:
        """Loads attributes, tags, summary, and gallery from the event.

        Separates hidden (underscore-prefixed) attributes from display attributes
        so that internal keys like ``_tags`` and ``_summary_data`` are preserved
        on save without being shown in the attribute editor.

        Args:
            event: The event whose attributes to load.

        """
        display_attrs = self._extract_hidden_attributes(event.attributes)
        self.attribute_editor.blockSignals(True)
        self.attribute_editor.load_attributes(display_attrs)
        self.attribute_editor.blockSignals(False)

        # Load sheet builder with the same display attributes + stored layout
        sheet_layout = event.attributes.get("_sheet_layout")
        self.sheet_builder.blockSignals(True)
        try:
            self.sheet_builder.load_attributes(display_attrs, sheet_layout)
        finally:
            self.sheet_builder.blockSignals(False)

        # Load Summary
        self.summary_widget.clear_summary()
        summary_data = event.attributes.get("_summary_data")
        if summary_data:
            with suppress(Exception):
                data = SummaryData.from_dict(summary_data)
                self.summary_widget.set_summary(data)

            self.summary_widget.set_stale(is_summary_stale(event))

        self.tag_editor.load_tags(event.tags)
        self.gallery.set_owner("event", event.id)

    def _load_event_relations(
        self, relations: list | None, incoming_relations: list | None
    ) -> None:
        """Loads outgoing and incoming relations into their respective list widgets.

        Outgoing relations are categorized into participants, locations, and
        general relations. Incoming relations are displayed as backlinks.

        Args:
            relations: List of outgoing relation dicts, or None.
            incoming_relations: List of incoming relation dicts, or None.

        """
        self.relation_authoring.remember_selection()
        self.connections.set_relations(
            relations or [],
            incoming_relations or [],
            self._current_event_id or "",
            self.name_edit.text(),
        )
        self.relation_authoring.refresh(
            [*(relations or []), *(incoming_relations or [])]
        )

    @Slot(dict)
    def _on_theme_changed(self, theme: dict) -> None:
        """
        Apply theme changes to specific UI elements.

        Updates the inject button stylesheet and the icons/styles for relation
        add-buttons using values from the provided theme. Expects the `theme`
        mapping to include a `text_main` color value used for icon tinting.

        Parameters:
            theme (dict): Theme data containing color and style values
                          (must include `text_main`).
        """
        from src.gui.utils.style_helper import StyleHelper

        # Update Inject Button
        self.btn_inject.setStyleSheet(
            StyleHelper.get_tool_button_style()
            + " QToolButton::menu-indicator { image: none; }"
        )
        action_style = StyleHelper.get_tool_button_style()
        self.chronology_button.setStyleSheet(action_style)
        self.temporal_evidence_button.setStyleSheet(action_style)
        self.btn_show_world_at_event.setStyleSheet(action_style)
        self.save_status.setStyleSheet(StyleHelper.get_inspector_support_style())

        # Update Checkboxes
        # StandardCheckbox handles its own styling on theme change

    @Slot()
    def _on_save(self) -> None:
        """Collects data from form fields and emits the `save_requested` signal.

        Emits a dictionary with the updated properties and the ID.
        """
        logger.info(
            f"[EventEditor] _on_save() called (event_id={self._current_event_id})"
        )

        if not self._current_event_id:
            logger.warning("[EventEditor] _on_save aborted - no current event ID")
            return
        if self.save_pending:
            return
        if not self.temporal_widget.commit_drafts():
            self._on_date_draft_changed(True)
            return

        try:
            # Merge tags into attributes
            base_attrs = self.attribute_editor.get_attributes()
            base_attrs["_tags"] = self.tag_editor.get_tags()

            self._merge_hidden_attributes(base_attrs)
            if self._temporal_metadata:
                base_attrs["_temporal_v2"] = deepcopy(self._temporal_metadata)
            expression = self.temporal_widget.date_start.get_expression()
            if expression is not None:
                base_attrs["_temporal_v2"] = {
                    **base_attrs.get("_temporal_v2", {}),
                    "schema": 1,
                    "expression": expression.to_dict(),
                }
            end_expression = self.temporal_widget.date_end.get_expression()
            metadata = base_attrs.get("_temporal_v2", {})
            preferred = next(
                (
                    claim
                    for claim in metadata.get("claims", [])
                    if claim.get("id") == metadata.get("preferred_claim_id")
                ),
                None,
            )
            if preferred is not None and preferred.get("expression") != metadata.get(
                "expression"
            ):
                metadata.pop("preferred_claim_id", None)
            if expression is not None and end_expression is not None:
                base_attrs["_temporal_v2"]["end_expression"] = end_expression.to_dict()
            elif "_temporal_v2" in base_attrs:
                base_attrs["_temporal_v2"].pop("end_expression", None)
            if self._pending_summary_changed:
                if self._pending_summary_data is None:
                    base_attrs.pop("_summary_data", None)
                else:
                    base_attrs["_summary_data"] = self._pending_summary_data

            # Persist the sheet layout arrangement
            sheet_layout = self.sheet_builder.get_layout()
            if sheet_layout:
                base_attrs["_sheet_layout"] = sheet_layout

            event_data = {
                "id": self._current_event_id,
                "name": self.name_edit.text(),
                "lore_date": self.temporal_widget.get_start(),
                "lore_duration": self.temporal_widget.get_duration(),
                "type": self.type_edit.currentText(),
                "description": self.desc_edit.get_wiki_text(),
                "attributes": base_attrs,
                "tags": self.tag_editor.get_tags(),
            }

            logger.info(
                f"[EventEditor] Emitting save_requested for event "
                f"'{event_data['name']}' (id={event_data['id']})"
            )
            revision = self.begin_save()
            if revision is None:
                return
            event_data["__editor_revision"] = revision
            event_data["__editor_generation"] = self.draft_generation
            self.save_requested.emit(event_data)
            logger.debug("[EventEditor] Awaiting save acknowledgement")

        except Exception as e:
            logger.error(
                f"[EventEditor] Exception in _on_save: {e}\n{traceback.format_exc()}"
            )
            raise

    @Slot()
    def _on_discard(self) -> None:
        """Discards changes by emitting signal to reload the current event."""
        if not self._current_event_id:
            return

        self.temporal_widget.cancel_drafts()
        self.discard_requested.emit(self._current_event_id)

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

        action_dialog = declare_inspection(
            self.inject_menu.addAction("Open Inject Dialog..."),
            "src-gui-widgets-event-editor-eventeditorwidget-populate-inject-menu-action-dialog|authoring.details|help-inspect-src-gui-widgets-event-editor-eventeditorwidget-populate-inject-menu-action-dialog",
        )
        if action_dialog is not None:
            action_dialog.triggered.connect(self._open_inject_dialog)

        self.inject_menu.addSeparator()

        action_save_tmpl = declare_inspection(
            self.inject_menu.addAction("Save Selection as Template..."),
            "src-gui-widgets-event-editor-eventeditorwidget-populate-inject-menu-action-save-tmpl|authoring.details|help-inspect-src-gui-widgets-event-editor-eventeditorwidget-populate-inject-menu-action-save-tmpl",
        )
        if action_save_tmpl is not None:
            action_save_tmpl.triggered.connect(self._open_create_template_dialog)

    def _open_inject_dialog(self) -> None:
        """Open the Fast Inject dialog for the current event.

        Emits the inject_ui_requested signal with the current event ID,
        allowing the main window or coordinator to display the Fast Inject
        dialog for quick data entry.

        Note:
            Does nothing if no event is currently loaded in the editor.
        """
        if self._current_event_id:
            logger.debug(f"Requesting inject UI for event {self._current_event_id}")
            self.inject_ui_requested.emit(self._current_event_id)

    def _open_create_template_dialog(self) -> None:
        """Open the template creation dialog for the current event.

        Collects current form data (tags, attributes, description) and
        opens a dialog allowing the user to save it as a reusable template
        for Fast Inject operations.

        The template data is emitted via create_template_requested signal
        if the user accepts the dialog.

        Note:
            Returns early if no event is currently loaded.
        """
        if not self._current_event_id:
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
            self.create_template_requested.emit(dlg.result_data)

    def set_relation_time_context(self, time: float, converter: Any) -> None:
        """Receive timeline context independently of editor draft time."""
        self._relation_playhead_time = time
        self._relation_calendar = converter
        self.connections.set_time_context(time, converter)

    @Slot(object)  # Allow Any/object for checked signal
    def _on_add_relation(self, rel_type: Any = "related") -> None:
        """Open shared inline capture with one existing-object choice."""
        self.relation_authoring.capture(
            rel_type if isinstance(rel_type, str) else "related"
        )

    def _on_add_detailed_relation(self, rel_type: Any = "involved") -> None:
        """Prompts user for relation details and emits signal.

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
            playhead_time=getattr(self, "_relation_playhead_time", None),
            rel_type=rel_type,
            suggestion_items=getattr(self, "_suggestion_items", []),
            calendar_converter=self._calendar_converter,
            source_event_date=(
                self.temporal_widget.get_start() if self._current_event_id else None
            ),
            source_event_name=self.name_edit.text() if self._current_event_id else None,
            known_types=getattr(self, "_suggestion_types", []),
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

    def _on_remove_relation_item(self, item: dict[str, Any]) -> None:
        """Emits remove signal."""
        rel_data = item
        if rel_data.get("rel_type") == "mentions":
            return
        outgoing = (
            rel_data.get("source_id", self._current_event_id) == self._current_event_id
        )
        endpoint = "target" if outgoing else "source"
        target_name = rel_data.get(f"{endpoint}_name") or rel_data.get(
            f"{endpoint}_id", "?"
        )

        confirm = QMessageBox.question(
            self,
            "Confirm Remove",
            f"Remove relation to {target_name}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.remove_relation_requested.emit(rel_data["id"])

    @Slot(dict)
    def _on_edit_relation(self, item: dict[str, Any]) -> None:
        """Refine the same saved connection inside this inspector."""
        self.relation_authoring.refine(item)

    def _on_edit_relation_full(self, item: dict[str, Any]) -> None:
        """Emits update signal after dialogs."""
        rel_data = item
        if rel_data.get("rel_type") == "mentions":
            return

        from src.gui.dialogs.relation_dialog import RelationEditDialog

        dlg = RelationEditDialog(
            parent=self,
            playhead_time=getattr(self, "_relation_playhead_time", None),
            source_name=rel_data.get("source_name") or self.name_edit.text(),
            target_id=rel_data["target_id"],
            rel_type=rel_data["rel_type"],
            is_bidirectional=False,  # Editing existing
            attributes=rel_data.get("attributes"),  # Pass existing attributes
            suggestion_items=getattr(self, "_suggestion_items", []),
            calendar_converter=self._calendar_converter,
            source_event_date=(
                self.temporal_widget.get_start() if self._current_event_id else None
            ),
            source_event_name=(
                self.name_edit.text() if self._current_event_id else None
            ),
            known_types=getattr(self, "_suggestion_types", []),
            target_kind=rel_data.get("target_kind"),
        )

        # Hide bidirectional check for editing
        dlg.bi_check.setVisible(False)

        if dlg.exec():
            target_id, rel_type, _, attributes = dlg.get_data()
            if target_id:
                self.update_relation_requested.emit(
                    rel_data["id"], target_id, rel_type, attributes
                )

    @Slot()
    def _on_summary_generate_requested(self) -> None:
        """Handles summary generation request."""
        if not self._current_event_id:
            return

        # Construct temporary event from form
        temp_event = Event(
            name=self.name_edit.text(),
            lore_date=self.temporal_widget.get_start(),
            lore_duration=self.temporal_widget.get_duration(),
            type=self.type_edit.currentText(),
            description=self.desc_edit.get_wiki_text(),
            id=self._current_event_id,
            attributes=self.attribute_editor.get_attributes(),
        )

        # Disable button
        self.summary_widget.generate_btn.setEnabled(False)
        self.summary_widget.generate_btn.setText("Generating...")

        self.summary_generation_requested.emit(temp_event)

    @Slot(str)
    def _on_summary_edit_committed(self, text: str) -> None:
        """Stage a manually edited summary for the next item save."""
        if not self._current_event_id:
            return
        item = self._current_summary_event()
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

    def _current_summary_event(self) -> Event:
        """Build an event snapshot from the current editor fields."""
        return Event(
            name=self.name_edit.text(),
            lore_date=self.temporal_widget.get_start(),
            lore_duration=self.temporal_widget.get_duration(),
            type=self.type_edit.currentText(),
            description=self.desc_edit.get_wiki_text(),
            id=self._current_event_id or "",
            attributes=self.attribute_editor.get_attributes(),
        )

    def _reset_pending_summary(self) -> None:
        """Reset staged summary state after an item load."""
        self._pending_summary_changed = False
        self._pending_summary_data = None

    @Slot(object)
    def on_summary_generated(self, summary_data: SummaryData) -> None:
        """Callback when summary is generated."""
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

    def get_generation_context(self) -> Dict[str, Any]:
        """Get context for LLM generation.

        Returns:
            Dict[str, Any]: Context dictionary containing:
                - 'name' (str): Event name
                - 'type' (str): Event type
                - 'existing_description' (str): Current description text
                - 'lore_date' (str, optional): Formatted date string if available
                - 'object_id' (str): Event UUID for spatial-context lookup
                - 'object_type' (str): Always ``"event"``

        """
        context = {
            "name": self.name_edit.text(),
            "type": self.type_edit.currentText(),
            "existing_description": self.desc_edit.toPlainText(),
            "object_id": self._current_event_id or "",
            "object_type": "event",
            "authoring_date": self.temporal_widget.get_start(),
        }

        formatted_date = self.temporal_widget.get_formatted_start_text()
        if formatted_date:
            context["lore_date"] = formatted_date

        return context

    @Slot()
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
                "lore_date": self.temporal_widget.get_start(),
                "type": self.type_edit.currentText(),
                "description": self.desc_edit.toPlainText(),
                "lore_duration": self.temporal_widget.get_duration(),
                # Include other fields if necessary for preview
                # (e.g. attributes not yet)
            }
            self.current_data_changed.emit(data)
        except (AttributeError, RuntimeError) as e:
            # Widgets may not be fully initialized during loading or partial state
            logger.debug(f"Could not emit current data: {e}")

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
            QSize: Minimum size for usable event editor.

        """
        return QSize(300, 200)  # Width for form labels, height for controls

    def sizeHint(self) -> QSize:
        """Preferred size for the event editor.

        Returns:
            QSize: Comfortable working size for editing events.

        """
        return QSize(400, 600)  # Ideal size for editing
