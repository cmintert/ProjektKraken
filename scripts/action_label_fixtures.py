"""Explicit, isolated production-widget factories for the action label gate.

No generic runtime repair or arbitrary constructor invocation is performed.
Fixtures use snapshots and do not execute commands or click authoring actions.
"""

from __future__ import annotations

import importlib
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractButton, QStackedWidget, QTabWidget, QWidget


@dataclass(frozen=True)
class Surface:
    """A production root and its nominal audit allocations."""

    module: str
    name: str
    widths: tuple[int, ...] = (360, 800)

    @property
    def key(self) -> str:
        """Return a stable inventory identifier."""
        return f"{self.module}.{self.name}"


_DIALOGS = {
    "about_dialog": "AboutDialog",
    "ai_settings_dialog": "AISettingsDialog",
    "analysis_run_dialog": "AnalysisRunDialog",
    "backup_settings_dialog": "BackupSettingsDialog",
    "calendar_config_dialog": "CalendarConfigDialog",
    "context_tag_dialogs": "ContextTagReviewDialog",
    "create_template_dialog": "CreateTemplateDialog",
    "database_manager_dialog": "DatabaseManagerDialog",
    "entity_creation_dialog": "EntityCreationDialog",
    "event_chronology_dialog": "EventChronologyDialog",
    "fast_inject_dialog": "FastInjectDialog",
    "feature_geometry_states_dialog": "FeatureGeometryStatesDialog",
    "filter_dialog": "FilterDialog",
    "generation_review_dialog": "GenerationReviewDialog",
    "go_to_date_dialog": "GoToDateDialog",
    "graph_filter_dialog": "GraphFilterDialog",
    "grouping_config_dialog": "GroupingConfigDialog",
    "icon_picker_dialog": "IconPickerDialog",
    "icon_metadata_dialog": "IconMetadataDialog",
    "image_viewer_dialog": "ImageViewerDialog",
    "import_preview_dialog": "ImportPreviewDialog",
    "keyboard_shortcuts_dialog": "KeyboardShortcutsDialog",
    "layer_properties_dialog": "LayerPropertiesDialog",
    "lexicon_editor_dialog": "LexiconEditorDialog",
    "map_edit_transition_dialog": "MapEditTransitionDialog",
    "map_object_picker_dialog": "MapObjectPickerDialog",
    "paste_json_import_dialog": "PasteJsonImportDialog",
    "raster_notes_dialog": "RasterNotesDialog",
    "raster_orphan_warning_dialog": "RasterOrphanWarningDialog",
    "raster_query_dialog": "RasterQueryDialog",
    "register_detail_map_dialog": "RegisterDetailMapDialog",
    "relation_dialog": "RelationEditDialog",
    "temporal_evidence_dialog": "TemporalEvidenceDialog",
    "temporal_validity_dialog": "TemporalValidityDialog",
    "transfer_dialog": "TransferDialog",
    "transfer_csv_dialog": "TransferCsvDialog",
    "progress_dialog": "ProgressDialog",
}
_WIDGETS = {
    "ai_search_panel": "AISearchPanelWidget",
    "analysis.main_analysis_panel": "MainAnalysisPanel",
    "authoring_context_widget": "AuthoringContextWidget",
    "compact_date_widget": "CompactDateWidget",
    "context_tag_bar": "ContextTagBar",
    "empty_state_widget": "EmptyStateWidget",
    "entity_list": "EntityListWidget",
    "event_list": "EventListWidget",
    "filter_widget": "FilterWidget",
    "graph_view.graph_filter_bar": "GraphFilterBar",
    "graph_view.graph_widget": "GraphWidget",
    "history_panel": "HistoryPanelWidget",
    "llm_generation_widget": "LLMGenerationWidget",
    "longform.editor": "LongformEditorWidget",
    "longform.membership": "LongformMembershipWidget",
    "longform.outline": "LongformOutlineWidget",
    "lore_date_widget": "LoreDateWidget",
    "map.calibration_distance_dialog": "CalibrationDistanceDialog",
    "map.map_layer_panel": "MapLayerPanel",
    "map.map_scale_dialog": "MapScaleDialog",
    "map.marker_size_dialog": "MarkerSizeDialog",
    "map.raster_stats_panel": "RasterStatsPanel",
    "map.raster_layer_dialog": "RasterLayerDialog",
    "map.raster_palette_editor": "RasterPaletteEditor",
    "map_widget": "MapWidget",
    "prompt_editor": "PromptEditorWidget",
    "relation_form": "RelationForm",
    "relation_item_widget": "RelationItemWidget",
    "relation_type_picker": "RelationTypePicker",
    "sheet_builder": "SheetBuilderWidget",
    "splitter_tab_inspector": "SplitterTabInspector",
    "summary_widget": "SummaryWidget",
    "temporal_range_widget": "TemporalRangeWidget",
    "timeline": "TimelineWidget",
    "unified_list": "UnifiedListWidget",
    "wiki_peek_panel": "WikiPeekPanel",
    "wiki_text_edit": "WikiTextEdit",
    "color_pickers.inline_color_picker": "InlineColorPickerPopover",
}
SURFACES = tuple(
    [
        Surface(f"src.gui.dialogs.{module}", name, (640, 1000))
        for module, name in _DIALOGS.items()
    ]
    + [Surface(f"src.gui.widgets.{module}", name) for module, name in _WIDGETS.items()]
    + [
        Surface("src.gui.widgets.entity_editor", "EntityEditorWidget", (240, 360, 800)),
        Surface("src.gui.widgets.event_editor", "EventEditorWidget", (240, 360, 800)),
        Surface(
            "src.gui.dialogs.context_tag_dialogs", "ContextTagEditorDialog", (640, 1000)
        ),
        Surface("src.gui.widgets.compact_date_widget", "CalendarPopup", (360, 800)),
        Surface("src.gui.widgets.overflow_toolbar", "OverflowToolBar", (240, 360, 800)),
        Surface("src.gui.workspace.workspace_shell", "WorkspaceShell", (1280, 1600)),
        Surface("src.gui.widgets.wiki_link_authoring", "EntryLinkPicker"),
    ]
)
FAST_KEYS = {
    "OverflowToolBar",
    "EntityEditorWidget",
    "EventEditorWidget",
    "TimelineWidget",
    "GraphFilterBar",
    "UnifiedListWidget",
    "HistoryPanelWidget",
    "MainAnalysisPanel",
    "MapEditTransitionDialog",
    "EntityCreationDialog",
}


def _snapshot_arguments(name: str) -> dict:
    from src.core.calendar import CalendarConfig, CalendarConverter
    from src.core.date_parser import DateParser
    from src.core.events import Event
    from src.core.map import Map, MapLayerNode
    from src.core.marker_icon import MarkerIconDefinition, MarkerIconSource
    from src.core.marker_sizing import MarkerSizingSettings
    from src.gui.widgets.map.map_data_buffer import ColorMap, CoverageStats

    converter = CalendarConverter(CalendarConfig.create_default())
    node = MapLayerNode(id="audit-layer", name="Audit layer", layer_type="group")
    world_map = Map(id="audit-map", name="Audit map", image_path="")
    arguments = {
        "ContextTagEditorDialog": {
            "tags": ["audit"],
            "suggestions": ["audit"],
            "active": True,
        },
        "RelationItemWidget": {
            "label": "Connected to Audit entity",
            "target_id": "audit",
            "target_name": "Audit entity",
        },
        "CalendarPopup": {
            "parent": None,
            "converter": converter,
            "year": 1,
            "month": 1,
            "day": 1,
        },
        "IconMetadataDialog": {
            "definition": MarkerIconDefinition(
                "audit", "Audit icon", "audit.svg", MarkerIconSource.DEFAULT
            ),
            "path": "src/resources/icons/map.svg",
        },
        "TransferCsvDialog": {
            "path": "audit.csv",
            "headers": ["name", "description"],
            "rows": [{"name": "Audit entity"}],
            "fields": {
                "entities": ["name", "description"],
                "events": ["name", "lore_date"],
                "relations": ["source_id", "target_id", "rel_type"],
            },
            "parent": None,
        },
        "ProgressDialog": {"label_text": "Audit operation", "cancelable": True},
        "MarkerSizeDialog": {
            "settings": MarkerSizingSettings(),
            "map_width_meters": 1000.0,
            "image_width": 1000.0,
            "view_scale": 1.0,
        },
        "RasterStatsPanel": {"stats": CoverageStats(mode="discrete", total_pixels=100)},
        "ContextTagReviewDialog": {"records": []},
        "CreateTemplateDialog": {"source_tags": [], "source_attributes": {}},
        "EventChronologyDialog": {
            "event_id": "audit-event",
            "events": [Event(id="audit-event", name="Audit event", lore_date=0)],
            "converter": converter,
        },
        "FastInjectDialog": {"templates": []},
        "FeatureGeometryStatesDialog": {"feature_label": "Audit feature", "states": []},
        "GenerationReviewDialog": {"generated_text": "Audit generated text"},
        "GoToDateDialog": {"converter": converter, "playhead_time": 0.0},
        "GroupingConfigDialog": {
            "tags_data": [],
            "current_config": {},
            "command_coordinator": None,
        },
        "LayerPropertiesDialog": {"node": node},
        "MapEditTransitionDialog": {
            "reason": "change maps",
            "status": {"label": "Audit journey", "can_apply": True, "explanation": ""},
        },
        "MapObjectPickerDialog": {"entities": [], "events": []},
        "RasterNotesDialog": {"layer_name": "Audit layer"},
        "RasterOrphanWarningDialog": {
            "entity_name": "Audit entity",
            "refs": [],
            "map_names": {},
        },
        "RasterQueryDialog": {"layers": []},
        "RegisterDetailMapDialog": {"detail_map": world_map, "candidate_parents": []},
        "TemporalEvidenceDialog": {
            "event_id": "audit-event",
            "metadata": {},
            "parser": DateParser(CalendarConfig.create_default()),
            "events": [],
        },
        "TemporalValidityDialog": {"node": node, "calendar_converter": converter},
        "MapScaleDialog": {"current_width": 1000.0},
        "RasterPaletteEditor": {"color_map": ColorMap()},
    }
    return arguments.get(name, {})


def make_surface(surface: Surface, temporary_root: Path) -> QWidget:
    """Construct one known surface without personal world/storage access."""
    if surface.name == "WorkspaceShell":
        return _workspace_surface()
    if surface.name == "EntryLinkPicker":
        from src.gui.widgets.wiki_link_authoring import EntryLinkPicker
        from src.gui.widgets.wiki_text_edit import WikiTextEditView

        host = WikiTextEditView()
        picker = EntryLinkPicker(host, [("audit", "Audit entity", "entity")], "Audit")
        picker._action_audit_host = host
        return picker
    if surface.name in ("EntityEditorWidget", "EventEditorWidget"):
        from scripts.capture_inspector_evidence import _EvidenceHost, _make_editor

        host = _EvidenceHost()
        editor = _make_editor(
            "entity" if surface.name == "EntityEditorWidget" else "event", host
        )
        editor.setWindowFlag(Qt.WindowType.Window, True)
        # Keep the snapshot provider alive for gallery refreshes.
        editor._action_audit_host = host
        return editor
    module = importlib.import_module(surface.module)
    factory = getattr(module, surface.name)
    if surface.name == "DatabaseManagerDialog":
        with patch.object(
            module, "ensure_worlds_directory", return_value=temporary_root
        ):
            return factory()
    if surface.name == "IconPickerDialog":
        return factory(world_root=str(temporary_root))
    if surface.name == "OverflowToolBar":
        from src.gui.widgets.wrapping_buttons import (
            WrappingPrimaryButton,
            WrappingPushButton,
        )

        toolbar = factory()
        for index, text in enumerate(
            ("Apply changes", "Create entity", "Create event", "Manage options")
        ):
            button = (
                WrappingPrimaryButton(text) if index == 0 else WrappingPushButton(text)
            )
            toolbar.add_button(button, pinned=index == 0)
        return toolbar
    return factory(**_snapshot_arguments(surface.name))


def _workspace_surface() -> QWidget:
    """Build the production shell and menus around inert snapshot presenters."""
    from unittest.mock import Mock

    from PySide6.QtWidgets import QLabel, QMainWindow

    from scripts.capture_inspector_evidence import _EvidenceHost, _make_editor
    from src.app.ui_manager import UIManager
    from src.gui.workspace.workspace_shell import WorkspaceShell

    root = QMainWindow()
    host = _EvidenceHost()
    root._action_audit_host = host
    root.workspace = WorkspaceShell(root)
    root.setCentralWidget(root.workspace)
    root.entity_editor = _make_editor("entity", host)
    root.event_editor = _make_editor("event", host)
    root.workspace.register_panel(
        "entity", "Entity", root.entity_editor, "right", "entity"
    )
    root.workspace.register_panel("event", "Event", root.event_editor, "right", "event")
    for identifier, title, zone in (
        ("explorer", "Explorer", "left"),
        ("timeline", "Timeline", "center"),
        ("analysis", "Analysis", "bottom"),
    ):
        root.workspace.register_panel(
            identifier, title, QLabel("Audit snapshot"), zone, identifier
        )
    for name in (
        "app_coordinator",
        "import_coordinator",
        "backup_coordinator",
        "grouping_manager",
        "ai_search_manager",
    ):
        setattr(root, name, Mock())
    root.toggle_auto_relation_setting = lambda: None
    root.toggle_longform_auto_refresh = lambda: None
    manager = UIManager(root)
    root._action_audit_manager = manager
    for name in ("file", "edit", "view", "timeline", "settings", "help"):
        getattr(manager, f"create_{name}_menu")(root.menuBar())
    return root


def surface_states(widget: QWidget) -> Iterator[str]:
    """Visit default and all production tab destinations without authoring clicks."""
    yield "default"
    yield from _navigation_states(widget)
    for number, button in enumerate(widget.findChildren(QAbstractButton)):
        if type(button).__name__ == "DisclosureButton" and button.isVisibleTo(widget):
            initial = button.isChecked()
            button.setChecked(True)
            yield f"disclosure-{number}"
            button.setChecked(initial)
    enabled = widget.isEnabled()
    widget.setEnabled(False)
    yield "disabled"
    widget.setEnabled(enabled)


def _navigation_states(widget: QWidget, prefix: str = "") -> Iterator[str]:
    """Visit nested tab/settings destinations while their parents are visible."""
    containers = [
        child
        for child in widget.findChildren(QWidget)
        if isinstance(child, (QTabWidget, QStackedWidget))
        and child.objectName() != "qt_tabwidget_stackedwidget"
    ]
    outer = []
    for child in containers:
        if not any(
            other is not child and other.isAncestorOf(child) for other in containers
        ):
            outer.append(child)
    for number, container in enumerate(outer):
        initial = container.currentIndex()
        for index in range(container.count()):
            if isinstance(container, QTabWidget) and not container.isTabEnabled(index):
                continue
            container.setCurrentIndex(index)
            state = f"{prefix}nav-{number}-{index}"
            yield state
            yield from _navigation_states(container.currentWidget(), state + "-")
        container.setCurrentIndex(initial)
