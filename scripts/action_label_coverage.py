"""Explicit source-to-fixture ownership for the UI-GATE-01 inventory.

Ownership is coverage registration, not a claim that every contextual state has
human approval. New actionable source files must acquire an explicit fixture.
"""

from typing import Any

COMPOSITE_OWNERS = {
    "src/gui/widgets/writing_toolbar.py": "WikiTextEdit",
    "src/gui/widgets/menu_caret.py": "UnifiedListWidget",
    "src/gui/delegates/attribute_delegate.py": "EntityEditorWidget",
    "src/gui/widgets/analysis/analysis_panel.py": "MainAnalysisPanel",
    "src/gui/widgets/analysis/intelligence_panel.py": "MainAnalysisPanel",
    "src/gui/widgets/analysis/temporal_panel.py": "MainAnalysisPanel",
    "src/gui/widgets/attribute_editor.py": "EntityEditorWidget",
    "src/gui/widgets/tag_editor.py": "EntityEditorWidget",
    "src/gui/widgets/relation_item_widget.py": "RelationItemWidget",
    "src/gui/widgets/relation_type_picker.py": "RelationTypePicker",
    "src/gui/widgets/editor_inspector_composition.py": "EntityEditorWidget",
    "src/gui/widgets/editor_presentation.py": "EntityEditorWidget",
    "src/gui/widgets/focus_writing.py": "WorkspaceShell",
    "src/gui/widgets/gallery_widget.py": "EntityEditorWidget",
    "src/gui/widgets/inspector_section.py": "EntityEditorWidget",
    "src/gui/widgets/map/feature_actions.py": "MapWidget",
    "src/gui/widgets/map/interaction_handler.py": "MapWidget",
    "src/gui/widgets/relation_authoring.py": "EntityEditorWidget",
    "src/gui/widgets/timeline/group_band_manager.py": "TimelineWidget",
    "src/gui/widgets/wiki_link_authoring.py": "EntryLinkPicker",
    "src/gui/workspace/pane_container.py": "WorkspaceShell",
    "src/app/ui_manager.py": "WorkspaceShell",
    "src/app/main_window.py": "WorkspaceShell",
    "src/app/coordinators/wiki_link_navigation.py": "EntryLinkPicker",
}


def coverage_records(inventory: list[dict[str, Any]], surfaces: Any) -> list[dict]:
    """Fail closed for sources without a registered production owner."""
    direct = {
        surface.module.replace(".", "/") + ".py": surface.name for surface in surfaces
    }
    direct["src/gui/widgets/timeline/__init__.py"] = "TimelineWidget"
    registered = {surface.name for surface in surfaces}
    records = []
    for source in inventory:
        owner = direct.get(source["source"], COMPOSITE_OWNERS.get(source["source"]))
        records.append(
            {
                **source,
                "fixture": owner,
                "status": "registered" if owner in registered else "missing_fixture",
            }
        )
    return records
